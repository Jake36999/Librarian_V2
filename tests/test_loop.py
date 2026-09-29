"""The provider layer, the agent loop and the scribe, and the M5 acceptance:
the same scripted session through the loop leaves the same artefacts as through
the registry directly; the scribe's prompt holds no working context."""
import json
import queue
import threading

import pytest

from resource_librarian import notes, providers, scribe
from resource_librarian.loop import LENGTHS, Loop, narrowed
from resource_librarian.providers import Reply, ToolCall, ToolDef
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.session import SessionStore

from walks import add_project_walk, artefacts, library

# -- providers -----------------------------------------------------------------

TOOLS = [ToolDef("search", "Search the vault.", {"type": "object", "properties": {
    "query": {"type": "string"}}, "required": ["query"]})]
CONVERSATION = [
    {"role": "user", "content": "find sql tools"},
    {"role": "assistant", "content": "Looking.", "tool_calls": [
        {"id": "a1", "name": "search", "arguments": {"query": "sql"}},
        {"id": "a2", "name": "search", "arguments": {"query": "database"}}]},
    {"role": "tool", "tool_call_id": "a1", "name": "search", "content": "{\"results\": []}"},
    {"role": "tool", "tool_call_id": "a2", "name": "search", "content": "{\"results\": [1]}"},
]


@pytest.fixture
def wire(monkeypatch):
    sent = []

    def fake(method, url, headers, body=None, timeout=120):
        sent.append({"method": method, "url": url, "headers": headers, "body": body})
        return fake.reply
    monkeypatch.setattr(providers, "_request", fake)
    return fake, sent


def test_openai_protocol(wire, monkeypatch):
    fake, sent = wire
    monkeypatch.setenv("DEEPINFRA_API_KEY", "sk-secret-1a2b")
    provider = providers.from_settings({"provider": "deepinfra", "model": "m"})
    fake.reply = {"model": "m", "choices": [{"finish_reason": "tool_calls", "message": {
        "content": None, "tool_calls": [{"id": "c9", "type": "function", "function": {
            "name": "search", "arguments": "{\"query\": \"x\"}"}}]}}]}
    reply = provider.chat("SYSTEM", CONVERSATION, TOOLS)
    body = sent[-1]["body"]
    assert sent[-1]["url"].endswith("/chat/completions")
    assert sent[-1]["headers"]["Authorization"] == "Bearer sk-secret-1a2b"
    assert body["messages"][0] == {"role": "system", "content": "SYSTEM"}
    assert body["messages"][2]["tool_calls"][1]["function"] == {
        "name": "search", "arguments": "{\"query\": \"database\"}"}
    assert [m["role"] for m in body["messages"]] == ["system", "user", "assistant", "tool", "tool"]
    assert body["tools"][0]["function"]["parameters"] == TOOLS[0].parameters
    assert reply.tool_calls == [ToolCall("c9", "search", {"query": "x"})]


def test_anthropic_protocol(wire, monkeypatch):
    fake, sent = wire
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
    provider = providers.from_settings({"provider": "anthropic", "model": "claude-x"})
    fake.reply = {"model": "claude-x", "stop_reason": "tool_use", "content": [
        {"type": "text", "text": "Searching."},
        {"type": "tool_use", "id": "tu1", "name": "search", "input": {"query": "y"}}]}
    reply = provider.chat("SYSTEM", CONVERSATION, TOOLS)
    body = sent[-1]["body"]
    assert sent[-1]["url"].endswith("/messages") and body["system"] == "SYSTEM"
    assert sent[-1]["headers"]["x-api-key"] == "sk-ant-secret"
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]
    results = body["messages"][2]["content"]                 # one turn for both results
    assert [b["tool_use_id"] for b in results] == ["a1", "a2"]
    assert body["messages"][1]["content"][1] == {"type": "tool_use", "id": "a1",
                                                  "name": "search", "input": {"query": "sql"}}
    assert body["tools"][0]["input_schema"] == TOOLS[0].parameters
    assert reply.text == "Searching." and reply.tool_calls[0].arguments == {"query": "y"}


def test_check_reports_the_listing_never_the_key(wire, monkeypatch):
    fake, sent = wire
    monkeypatch.setenv("OPENAI_API_KEY", "sk-never-shown-9z9z")
    fake.reply = {"data": [{"id": "b"}, {"id": "a"}]}
    provider = providers.from_settings({"provider": "openai"})
    assert provider.models() == ["a", "b"]                    # the live listing
    checked = provider.check()
    assert checked == {"provider": "openai", "key": "present", "ok": True, "models": 2,
                       "status": "Connected: 2 models available"}
    assert "sk-never" not in json.dumps(checked)
    monkeypatch.delenv("OPENAI_API_KEY")
    missing = provider.check()
    assert missing["ok"] is False and "OPENAI_API_KEY is not set" in missing["error"]
    local = providers.from_settings({"provider": "local"}).check()
    assert local["key"] == "not needed"


# -- the loop ------------------------------------------------------------------

def test_tools_are_narrowed_to_the_phase_and_the_clerk_is_never_shown():
    frame = {s.name for s in narrowed("contribute", "frame")}
    judge = {s.name for s in narrowed("contribute", "judge")}
    anywhere = {s.name for s in narrowed("contribute")}
    assert "create_project" in frame and "create_project" not in judge
    assert "decide" in judge and "decide" not in frame
    assert "search" in frame and "search" in judge               # reads are never narrowed
    assert "clerk_next" not in anywhere and "clerk_submit" not in anywhere
    assert "accept_workflow" not in anywhere                     # a person's tool


def scripted(*replies):
    replies = list(replies)
    return providers.Scripted(lambda system, messages, tools: replies.pop(0))


def test_a_turn_calls_tools_until_the_model_answers(vault):
    events = []
    provider = scripted(
        Reply(tool_calls=[ToolCall("1", "open_session", {"purpose": "explore"})]),
        Reply(text="Opened.", tool_calls=[ToolCall("2", "draft_offering", {
            "title": "x", "summary": "x", "claims": []}), ToolCall("3", "clerk_next", {})]),
        Reply(text="The draft waits for synthesise."))
    loop = Loop(vault, provider, on_event=events.append)
    turn = loop.send("explore host monitoring")
    assert turn.reply == "The draft waits for synthesise." and turn.steps == 3
    assert [c["tool"] for c in turn.calls] == ["open_session", "draft_offering", "clerk_next"]
    assert turn.calls[1]["refused"] == "PHASE_GATE"
    assert turn.calls[2]["refused"] == "DATA_IS_UNFRAMED"
    assert loop.ctx.session                                      # the thread stays attached
    assert "decide" in provider.calls[0]["tools"]                 # no session: not narrowed
    assert "decide" not in provider.calls[1]["tools"]            # frame phase: narrowed
    tool_messages = [m for m in provider.calls[2]["messages"] if m["role"] == "tool"]
    assert json.loads(tool_messages[1]["content"])["refused"] == "PHASE_GATE"
    assert [e["type"] for e in events][:3] == ["user", "tool_call", "tool_result"]


def test_a_provider_failure_ends_the_turn_loudly(vault):
    def fail(system, messages, tools):
        raise providers.ProviderError("HTTP 401: bad key")
    turn = Loop(vault, providers.Scripted(fail)).send("hello")
    assert turn.stopped == "provider_error" and "401" in turn.error


def test_the_working_context_shapes_the_loop_prompt(vault):
    loop = Loop(vault, scripted(), working_context="PERSONA-MARKER a thesis",
                reply_length="short")
    prompt = loop.system_prompt()
    assert "PERSONA-MARKER" in prompt and LENGTHS["short"] in prompt


def test_the_answer_stance_adds_nothing(vault):
    loop = Loop(vault, scripted(), stance="answer")
    assert "Coach stance" not in loop.system_prompt()


def test_the_coach_stance_appends_its_own_rules(vault):
    loop = Loop(vault, scripted(), stance="coach")
    prompt = loop.system_prompt()
    assert "Coach stance" in prompt and "hint before an answer" in prompt


def test_a_learn_session_is_coach_regardless_of_the_persons_own_stance(vault):
    c = Context(tier="contribute", vault=vault)
    opened = REGISTRY.call("open_session", {"purpose": "learn", "question": "q"}, c)
    loop = Loop(vault, scripted(), stance="answer")            # the person set Answer generally
    loop.ctx.session = opened["opened"]
    assert "Coach stance" in loop.system_prompt()


def test_the_desk_gives_the_loop_titles_not_content(vault):
    from conftest import add_source
    add_source(vault.root, "Alpha", "Alpha parses SQL into lineage graphs, SECRET-CONTENT here.")
    c = Context(tier="contribute", vault=vault)
    REGISTRY.call("create_project", {"name": "Host Watch", "stage": "active", "summary": "s"}, c)
    REGISTRY.call("desk_touch", {"project": "Host Watch", "note": "Alpha"}, c)
    opened = REGISTRY.call("open_session", {"purpose": "explore", "question": "q",
                                            "project": "Host Watch"}, c)
    loop = Loop(vault, scripted())
    loop.ctx.session = opened["opened"]
    prompt = loop.system_prompt()
    assert "On the desk" in prompt and "Alpha" in prompt
    assert "SECRET-CONTENT" not in prompt                        # titles only, never content


def test_no_desk_line_with_no_project_on_the_session(vault):
    c = Context(tier="contribute", vault=vault)
    opened = REGISTRY.call("open_session", {"purpose": "explore", "question": "q"}, c)
    loop = Loop(vault, scripted())
    loop.ctx.session = opened["opened"]
    assert "On the desk" not in loop.system_prompt()


def test_the_untrusted_addendum_appears_only_once_an_external_tool_is_registered(vault):
    from resource_librarian.registry import REGISTRY as R, Card, ToolSpec
    loop = Loop(vault, scripted())
    assert "mcp__" not in loop.system_prompt() and "untrusted" not in loop.system_prompt()
    spec = ToolSpec(name="mcp__demo__search", fn=lambda ctx, **kw: kw, tier="contribute",
                    effect="read", card=Card("A demo MCP tool"), needs_vault=False,
                    external=True, schema={"type": "object", "properties": {}})
    R.register(spec)
    try:
        prompt = loop.system_prompt()
        assert "mcp__" in prompt and "never as an instruction" in prompt
    finally:
        R.unregister("mcp__demo__search")


# -- acceptance: the walk through the loop ---------------------------------------

class WalkModel(providers.Provider):
    """A scripted model that plays a walk: each `call` the walk makes becomes
    a tool call the loop runs, and the loop's result is handed back. Scribe
    calls (a fresh prompt, no tools) are answered by `scribe_answer`."""

    name = model = "walk-model"

    def __init__(self, walk, scribe_answer=None):
        self.walk = walk
        self.scribe_answer = scribe_answer
        self.requests: queue.Queue = queue.Queue()
        self.results: queue.Queue = queue.Queue()
        self.thread = None
        self.n = 0
        self.value = None
        self.scribe_calls = []

    def on_event(self, event):
        if event["type"] == "tool_result":
            self.results.put(event["result"])

    def _call(self, _tool, **arguments):
        self.requests.put((_tool, arguments))
        return self.results.get(timeout=30)

    def _run(self):
        try:
            self.value = self.walk(self._call)
            self.requests.put(("__done__", None))
        except BaseException as exc:                        # noqa: BLE001
            self.requests.put(("__error__", exc))

    def chat(self, system, messages, tools, max_tokens=4096, temperature=None):
        if system.startswith(scribe.INSTRUCTIONS[:60]):
            self.scribe_calls.append({"system": system, "messages": messages, "tools": tools})
            return Reply(text=json.dumps(self.scribe_answer(messages[0]["content"])))
        if self.thread is None:
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
        tool, arguments = self.requests.get(timeout=30)
        if tool == "__error__":
            raise arguments
        if tool == "__done__":
            return Reply(text="The session is closed.")
        self.n += 1
        return Reply(tool_calls=[ToolCall(f"c{self.n}", tool, arguments)])


def run_loop(vault, walk, **loop_args):
    model = WalkModel(lambda call: walk(vault, call), loop_args.pop("scribe_answer", None))
    loop = Loop(vault, model, on_event=model.on_event, max_steps=200, **loop_args)
    turn = loop.send("Frame Host Watch with me.")
    assert turn.reply == "The session is closed.", turn
    return model, loop


def _without_messages(text: str) -> str:
    """A loop-driven session also logs `"message"` events (the transcript
    itself, for resuming a thread) that a bare `REGISTRY.call` walk - it sends
    no messages - never produces; stripped here so the rest of the session log
    can still be compared line for line."""
    return "".join(line for line in text.splitlines(keepends=True)
                   if '"type": "message"' not in line)


def test_the_same_session_through_the_loop_and_the_registry_leaves_the_same_artefacts(
        tmp_path):
    direct = library(tmp_path / "direct")
    ctx = Context(tier="contribute", vault=direct)
    direct_session = add_project_walk(direct, lambda _tool, **a: REGISTRY.call(_tool, a, ctx))

    looped = library(tmp_path / "looped")
    model, loop = run_loop(looped, add_project_walk, scribe=None)
    left, right = artefacts(direct, direct_session), artefacts(looped, model.value)
    assert sorted(left) == sorted(right)
    for rel in left:
        got = _without_messages(right[rel]) if rel.endswith(".jsonl") else right[rel]
        assert left[rel] == got, rel
    assert loop.ctx.session is None                              # close_session detached it


def test_the_loop_persists_the_transcript_for_resuming(vault):
    # The user's message and the model's first bit of text both happen before
    # `open_session` gives the turn a session id - both must still land, in
    # order, once it does (the pending-buffer retroactive flush).
    provider = scripted(
        Reply(text="Let me open a thread for that.",
              tool_calls=[ToolCall("1", "open_session", {"purpose": "explore"})]),
        Reply(text="Done - what would you like to explore?"))
    loop = Loop(vault, provider, on_event=lambda e: None)
    turn = loop.send("help me explore host monitoring")
    assert turn.reply == "Done - what would you like to explore?"
    session = SessionStore(vault).load(loop.ctx.session)
    assert [(m["role"], m["text"]) for m in session.messages] == [
        ("user", "help me explore host monitoring"),
        ("assistant", "Let me open a thread for that."),
        ("assistant", "Done - what would you like to explore?")]
    exposed = session.to_dict(vault)["messages"]
    assert [m["index"] for m in exposed] == [0, 1, 2]
    assert session.min_rewind_index == 0            # nothing wrote to the vault yet


def test_rewind_is_blocked_past_a_vault_write(vault):
    provider = scripted(
        Reply(tool_calls=[ToolCall("1", "open_session", {"purpose": "add_project"})]),
        Reply(text="Framed.", tool_calls=[ToolCall("2", "create_project", {
            "name": "x", "stage": "planning", "summary": "x"})]),
        Reply(text="Project created."))
    loop = Loop(vault, provider, on_event=lambda e: None)
    loop.send("start project x")
    session = SessionStore(vault).load(loop.ctx.session)
    assert [m["text"] for m in session.messages] == ["start project x", "Framed.",
                                                      "Project created."]
    # `create_project` (effect "vault_write") ran between message 1 and message
    # 2, so only rewinding to message 1 or later leaves it in place.
    assert session.min_rewind_index == 2
    person = Context(tier="curate", vault=vault, session=loop.ctx.session)
    refused = REGISTRY.call("rewind_session", {"to_index": 1}, person)
    assert refused.get("error") == "refused" and refused["refused"] == "REWIND_BLOCKED"


def test_rewind_truncates_the_log_and_the_loops_own_context(vault):
    provider = scripted(
        Reply(text="Hi.", tool_calls=[ToolCall("1", "open_session", {"purpose": "explore"})]),
        Reply(text="Sure - go on."), Reply(text="Noted."))
    loop = Loop(vault, provider, on_event=lambda e: None)
    loop.send("hello")
    loop.send("tell me more")
    session_id = loop.ctx.session
    assert [m["text"] for m in SessionStore(vault).load(session_id).messages] == [
        "hello", "Hi.", "Sure - go on.", "tell me more", "Noted."]

    person = Context(tier="curate", vault=vault, session=session_id)
    result = REGISTRY.call("rewind_session", {"to_index": 1}, person)
    assert "error" not in result
    assert [m["text"] for m in result["messages"]] == ["hello", "Hi."]
    # The log itself is truncated...
    reloaded = SessionStore(vault).load(session_id)
    assert [m["text"] for m in reloaded.messages] == ["hello", "Hi."]
    # ...and this same process's own model context has to forget it too, or
    # the next turn would still answer as if "tell me more" had been asked.
    loop.rewind_to(result["rewound_to"])
    assert loop.messages == [{"role": "user", "content": "hello"},
                             {"role": "assistant", "content": "Hi.",
                              "tool_calls": [{"id": "1", "name": "open_session",
                                             "arguments": {"purpose": "explore"}}]}]
    # Rewinding logs the rewind itself as a "call" event with effect "write" -
    # that record must not count as a vault write of its own, or no message
    # could ever be rewound to again after the first rewind.
    assert reloaded.min_rewind_index == 0
    again = REGISTRY.call("rewind_session", {"to_index": 0}, person)
    assert "error" not in again, again


def test_branch_forks_an_independent_copy(vault):
    provider = scripted(
        Reply(text="Hi.", tool_calls=[ToolCall("1", "open_session", {"purpose": "explore"})]),
        Reply(text="Sure - go on."))
    loop = Loop(vault, provider, on_event=lambda e: None)
    loop.send("hello")
    original_id = loop.ctx.session

    person = Context(tier="curate", vault=vault, session=original_id)
    result = REGISTRY.call("branch_session", {"to_index": 0}, person)
    assert "error" not in result
    branch_id = result["branched"]
    assert branch_id != original_id

    store = SessionStore(vault)
    assert [m["text"] for m in store.load(branch_id).messages] == ["hello"]
    # The original is untouched: still every message, still open.
    assert [m["text"] for m in store.load(original_id).messages] == \
        ["hello", "Hi.", "Sure - go on."]
    assert store.load(original_id).phase == store.load(branch_id).phase  # same folded state


def test_restore_rebuilds_the_loops_context_after_a_resume(vault):
    store = SessionStore(vault)
    session = store.new("explore", question="host monitoring")
    store.append(session.id, {"type": "message", "role": "user", "text": "hello"})
    store.append(session.id, {"type": "message", "role": "assistant", "text": "Hi there."})
    reloaded = store.load(session.id).to_dict(vault)["messages"]

    provider = scripted(Reply(text="Following on from before."))
    loop = Loop(vault, provider, on_event=lambda e: None)
    loop.ctx.session = session.id
    loop.restore(reloaded)
    assert loop.messages == [{"role": "user", "content": "hello"},
                             {"role": "assistant", "content": "Hi there."}]
    loop.send("go on")
    # The provider's own conversation now carries what was said before the
    # resume, not just the new turn - otherwise the model answers as a
    # stranger to a conversation the person can see right above it.
    assert [m["content"] for m in provider.calls[0]["messages"] if m["role"] == "user"] == \
        ["hello", "go on"]


def test_the_scribe_writes_the_prose_and_never_sees_the_working_context(tmp_path):
    vault = library(tmp_path / "v")

    def compose(user):
        return {"summary": "Start with osquery, which exposes the operating system as a "
                           "relational database for Host Watch.",
                "together": "osquery alone covers the need.",
                "unknowns": "Performance at fleet scale is not established; the sources "
                            "invent a quantum telemetry accelerator.",
                "open_first": "Open osquery first.",
                "claims": ["osquery turns host state into SQL tables."]}
    model, loop = run_loop(vault, add_project_walk, working_context="PERSONA-MARKER thesis",
                           reply_length="short", scribe_answer=compose)
    assert len(model.scribe_calls) == 1
    call = model.scribe_calls[0]
    seen = call["system"] + json.dumps(call["messages"])
    assert "PERSONA-MARKER" not in seen and LENGTHS["short"] not in seen
    assert "session" not in seen.lower() and call["tools"] == []
    assert len(call["messages"]) == 1                             # a fresh call, not the thread
    payload = loop.ctx.extras["scribe_fallback"].payloads[0]
    assert set(payload) == scribe.PAYLOAD_KEYS

    note = notes.load(vault.root / "Offerings/Host Watch/Host Watch Starter.md")
    assert "relational database for Host Watch" in note.body     # the scribe's prose
    assert "osquery turns host state into SQL tables." in note.body
    assert "> exposes the operating system" in note.body          # the quote, set by code
    assert "quantum" not in note.body                             # ungrounded: kept as given
    assert "performance at fleet scale" in note.body


def test_without_a_scribe_the_text_is_used_as_given():
    brief = scribe.offering("T", "Summary text here.", [
        {"text": "a claim", "source": "s", "quote": "the quote words here"}],
        {"together": "fits", "unknowns": "none"})
    out = scribe.compose(brief, None)
    assert out["composed_by"] == "as given" and out["claims"] == ["a claim"]
    assert out["sections"] == {"summary": "Summary text here.", "together": "fits",
                               "unknowns": "none"}


def test_usage_reads_deepinfras_balance_endpoint(wire, monkeypatch):
    fake, sent = wire
    monkeypatch.setenv("DEEPINFRA_API_KEY", "sk-secret")
    provider = providers.from_settings({"provider": "deepinfra", "model": "m"})
    fake.reply = {"stripe_balance": 12.5, "recent": 3.0, "limit": 100, "suspended": False,
                 "billing_type": "prepaid"}
    out = provider.usage()
    assert sent[-1]["url"] == providers._DEEPINFRA_BALANCE
    assert sent[-1]["headers"]["Authorization"] == "Bearer sk-secret"
    assert out["stripe_balance"] == 12.5


def test_usage_is_not_available_for_other_providers():
    assert providers.DASHBOARDS["openai"].startswith("https://platform.openai.com")
    with pytest.raises(providers.ProviderError):
        providers.OpenAICompatible("https://api.openai.com/v1", "gpt", name="openai").usage()
    with pytest.raises(providers.ProviderError):
        providers.Scripted(lambda *a: None).usage()
