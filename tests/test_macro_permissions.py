"""Macro control flow never owns the writer while waiting for approval."""
from dataclasses import replace
import queue
import threading

import pytest

from resource_librarian import agent_runtime, tools  # noqa: F401
from resource_librarian.agent_runtime import Macro, MacroStep
from resource_librarian.app import App
from resource_librarian.coordination import on_writer_thread
from resource_librarian.keys import KeyStore
from resource_librarian.registry import Card, Context, REGISTRY, Registry, ToolSpec


@pytest.fixture
def core(vault, monkeypatch):
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    monkeypatch.setitem(agent_runtime.MACROS, "two_notes", Macro(
        "two_notes", 1, "Two separately authorized notes", (
            MacroStep("write_note", {"folder": "Notes", "name": "$first", "body": "First"}),
            MacroStep("write_note", {"folder": "Notes", "name": "$second", "body": "Second"}),
        ), True))
    try:
        yield app
    finally:
        app.close_runtime()


def test_macro_permissions_wait_outside_writer_and_keep_completed_work(core):
    sid = core.person_call("open_session", {"purpose": "explore", "question": "Two notes"})["opened"]
    requests = queue.Queue()
    def listen(event):
        if event.get("type") == "permission_request":
            requests.put((event, on_writer_thread()))
    core.broker.subscribe(listen)
    def start(inputs):
        results = []
        thread = threading.Thread(target=lambda: results.append(core.mcp_call(
            "macro_run", {"macro": "two_notes", "inputs": inputs}, sid, "contribute")))
        thread.start()
        return thread, results
    def answer(tool, decision="allow_once"):
        event, inside_writer = requests.get(timeout=3)
        assert event["tool"] == tool and not inside_writer
        # A separate write must be able to finish before the person answers.
        core.writer.submit(lambda: None, caller="unrelated", timeout=1)
        core.broker.answer(event["id"], decision)
    inputs = {"first": "First note", "second": "Second note"}
    thread, results = start(inputs)
    answer("macro_run")
    thread.join(3)
    assert not thread.is_alive()
    checkpoint = results[0]["result"]["checkpoint"]
    assert results[0]["result"]["status"] == "awaiting_checkpoint"
    assert not (core.vault.root / "Notes" / "First note.md").exists()
    core._serialized("approve-macro", lambda: core.checkpoints.resolve(checkpoint["id"], "approve"))
    thread, results = start({**inputs, "checkpoint_id": checkpoint["id"]})
    answer("macro_run")
    answer("write_note")
    answer("write_note", "deny")
    thread.join(3)
    assert not thread.is_alive()
    result = results[0]["result"]
    assert result["status"] == "paused" and len(result["steps"]) == 2
    assert result["steps"][1]["result"]["refused"] == "PERMISSION_DENIED"
    assert result["next_action"]["arguments"]["name"] == "Second note"
    assert result["next_action"]["completed_steps"] == 1
    assert (core.vault.root / "Notes" / "First note.md").is_file()
    assert not (core.vault.root / "Notes" / "Second note.md").exists()


def test_macro_checkpoint_is_invalid_after_plan_changes_without_version_bump(core, monkeypatch):
    core.set_mode("auto")
    inputs = {"first": "First note", "second": "Second note"}
    initial = core.person_call("macro_run", {"macro": "two_notes", "inputs": inputs})
    checkpoint = initial["checkpoint"]
    core._serialized("approve-macro", lambda: core.checkpoints.resolve(checkpoint["id"], "approve"))
    macro = agent_runtime.MACROS["two_notes"]
    monkeypatch.setitem(agent_runtime.MACROS, "two_notes", replace(macro, steps=macro.steps[:1]))
    result = core.person_call("macro_run", {"macro": "two_notes", "inputs": {
        **inputs, "checkpoint_id": checkpoint["id"]}})
    assert result["status"] == "awaiting_checkpoint"
    assert result["checkpoint"]["scope"] != checkpoint["scope"]
    assert not (core.vault.root / "Notes" / "First note.md").exists()


def test_macro_approval_never_overrides_a_denied_step_or_plan_mode(core):
    core.set_mode("auto")
    inputs = {"first": "First note", "second": "Second note"}
    initial = core.person_call("macro_run", {"macro": "two_notes", "inputs": inputs})
    checkpoint = initial["checkpoint"]
    core._serialized("approve-macro", lambda: core.checkpoints.resolve(checkpoint["id"], "approve"))
    core.broker.set_tool("write_note", "deny")
    result = core.mcp_call("macro_run", {"macro": "two_notes", "inputs": {
        **inputs, "checkpoint_id": checkpoint["id"]}}, tier="contribute")["result"]
    assert result["status"] == "paused" and result["steps"][0]["result"]["refused"] == "PERMISSION_DENIED"
    assert not (core.vault.root / "Notes" / "First note.md").exists()
    core.set_mode("plan")
    result = core.mcp_call("macro_run", {"macro": "two_notes", "inputs": {
        **inputs, "checkpoint_id": checkpoint["id"]}}, tier="contribute")["result"]
    assert result["refused"] == "PERMISSION_DENIED"


def test_only_reviewed_first_party_workflows_can_orchestrate_writer_operations():
    assert [name for name in REGISTRY.names() if REGISTRY.get(name).orchestrates] == [
        "macro_resolve", "macro_run", "model_catalog_adopt", "process_approved"]
    # macro_resolve only re-enters run_macro with the inputs a run's log recorded.
    assert REGISTRY.get("macro_resolve").tier == "curate"
    assert REGISTRY.get("process_approved").tier == "curate"
    assert REGISTRY.get("model_catalog_adopt").tier == "curate"
    external = ToolSpec("external", lambda ctx: {}, "consult", "write", Card("External"),
                        external=True, orchestrates=True)
    with pytest.raises(ValueError, match="external tools cannot orchestrate"):
        Registry().register(external)


def test_macro_nested_in_writer_refuses_before_asking_permission(core):
    ctx = Context(tier="contribute", vault=core.vault, extras=core._extras())
    result = core.writer.submit(lambda: REGISTRY.call("macro_run", {
        "macro": "two_notes", "inputs": {"first": "One", "second": "Two"}}, ctx),
        caller="invalid-nesting", timeout=2)
    assert result["refused"] == "ORCHESTRATION_CONTEXT"
    assert not core.broker.pending()


# -- MF-018: an approved macro run is resumed, never blindly repeated -------------

class Crash(Exception):
    """The app stopping after a step took effect, before its result was logged."""


def approved_two_notes(core):
    core.set_mode("auto")
    inputs = {"first": "First note", "second": "Second note"}
    checkpoint = core.person_call("macro_run", {"macro": "two_notes", "inputs": inputs})["checkpoint"]
    core._serialized("approve-macro", lambda: core.checkpoints.resolve(checkpoint["id"], "approve"))
    return {**inputs, "checkpoint_id": checkpoint["id"]}


def watch_writes(monkeypatch, *, refuse_second_once=False, crash_first_once=False):
    writes = []
    original = REGISTRY.call

    def call(name, arguments, ctx):
        if name != "write_note":
            return original(name, arguments, ctx)
        writes.append(arguments["name"])
        if refuse_second_once and arguments["name"] == "Second note" and \
                writes.count("Second note") == 1:
            return {"error": "refused", "refused": "PERMISSION_DENIED", "detail": "not now"}
        result = original(name, arguments, ctx)
        if crash_first_once and writes == ["First note"]:
            raise Crash("stopped part way")
        return result

    monkeypatch.setattr(REGISTRY, "call", call)
    return writes


def test_running_an_approved_macro_again_reuses_its_completed_steps(core, monkeypatch):
    inputs = approved_two_notes(core)
    writes = watch_writes(monkeypatch, refuse_second_once=True)
    paused = core.person_call("macro_run", {"macro": "two_notes", "inputs": inputs})
    assert paused["status"] == "paused" and "reused, not repeated" in \
        paused["next_action"]["detail"]

    resumed = core.person_call("macro_run", {"macro": "two_notes", "inputs": inputs})
    assert resumed["status"] == "completed", resumed
    assert resumed["steps"][0]["reused"] is True
    assert writes == ["First note", "Second note", "Second note"]   # the first, once

    again = core.person_call("macro_run", {"macro": "two_notes", "inputs": inputs})
    assert again["status"] == "completed" and again["reused"] is True
    assert len(writes) == 3                                         # nothing repeated


def test_an_interrupted_macro_write_waits_for_a_person(core, monkeypatch):
    inputs = approved_two_notes(core)
    writes = watch_writes(monkeypatch, crash_first_once=True)
    stopped = core.person_call("macro_run", {"macro": "two_notes", "inputs": inputs})
    assert stopped["error"] == "failed" and "stopped part way" in stopped["detail"]
    assert (core.vault.root / "Notes" / "First note.md").is_file()

    held = core.person_call("macro_run", {"macro": "two_notes", "inputs": inputs})
    assert held["status"] == "outcome_unknown" and held["next_action"]["options"] == [
        "retry", "applied"]
    assert writes == ["First note"]                                 # not sent again
    ctx = Context(tier="contribute", vault=core.vault, extras=core._extras())
    agent = REGISTRY.call("macro_run", {"macro": "two_notes",
                                        "inputs": {**inputs, "unknown_step": "applied"}}, ctx)
    assert agent["refused"] == "PERSON_CONFIRMS"

    done = core.person_call("macro_run", {"macro": "two_notes",
                                          "inputs": {**inputs, "unknown_step": "applied"}})
    assert done["status"] == "completed", done
    assert writes == ["First note", "Second note"]
    assert done["steps"][0]["result"]["recorded_as"] == "applied"


# -- Codex UI ask 2: a recovery handle that holds after a reconnect ------------------

def held_on_unknown(core, monkeypatch):
    inputs = approved_two_notes(core)
    writes = watch_writes(monkeypatch, crash_first_once=True)
    core.person_call("macro_run", {"macro": "two_notes", "inputs": inputs})
    held = core.person_call("macro_run", {"macro": "two_notes", "inputs": inputs})
    return inputs, writes, held


def test_an_unknown_outcome_carries_a_recovery_handle(core, monkeypatch):
    inputs, _, held = held_on_unknown(core, monkeypatch)
    assert held["recovery"] == {"checkpoint_id": inputs["checkpoint_id"], "step": 0,
                                "tool": "write_note", "macro": "two_notes",
                                "options": ["retry", "applied"]}
    status = core.person_call("macro_status", {"checkpoint_id": inputs["checkpoint_id"]})
    assert status["status"] == "outcome_unknown" and status["step"] == 0
    assert status["inputs_recorded"] is True and status["options"] == ["retry", "applied"]


def test_a_person_resolves_it_by_handle_with_the_inputs_the_log_recorded(core, monkeypatch):
    inputs, writes, held = held_on_unknown(core, monkeypatch)
    handle = held["recovery"]
    done = core.person_call("macro_resolve", {"checkpoint_id": handle["checkpoint_id"],
                                              "step": handle["step"], "choice": "applied"})
    assert done["status"] == "completed", done
    assert writes == ["First note", "Second note"]                  # the first, never again
    assert core.person_call("macro_status", {
        "checkpoint_id": handle["checkpoint_id"]})["status"] == "completed"


def test_a_stale_handle_changes_nothing(core, monkeypatch):
    inputs, writes, held = held_on_unknown(core, monkeypatch)
    handle = held["recovery"]
    wrong = core.person_call("macro_resolve", {"checkpoint_id": handle["checkpoint_id"],
                                               "step": 1, "choice": "retry"})
    assert wrong["status"] == "changed" and writes == ["First note"]
    first = core.person_call("macro_resolve", {"checkpoint_id": handle["checkpoint_id"],
                                               "step": 0, "choice": "applied"})
    assert first["status"] == "completed"
    again = core.person_call("macro_resolve", {"checkpoint_id": handle["checkpoint_id"],
                                               "step": 0, "choice": "retry"})
    assert again["status"] == "changed" and writes == ["First note", "Second note"]


def test_only_a_person_resolves_by_handle(core, monkeypatch):
    _, writes, held = held_on_unknown(core, monkeypatch)
    ctx = Context(tier="contribute", vault=core.vault, extras=core._extras())
    agent = REGISTRY.call("macro_resolve", {"checkpoint_id": held["recovery"]["checkpoint_id"],
                                            "step": 0, "choice": "applied"}, ctx)
    assert agent.get("refused") in ("TIER_REFUSED", "PERSON_CONFIRMS") and writes == ["First note"]


def test_a_step_still_being_sent_is_never_offered_for_an_answer(core, monkeypatch):
    inputs, _, _ = held_on_unknown(core, monkeypatch)
    from resource_librarian.agent_runtime import MacroJournal
    MacroJournal(core.vault, inputs["checkpoint_id"]).append(
        {"type": "dispatch", "index": 1, "tool": "write_note", "arguments": {}})
    status = core.person_call("macro_status", {"checkpoint_id": inputs["checkpoint_id"]})
    assert status["status"] == "running_or_interrupted"
    out = core.person_call("macro_resolve", {"checkpoint_id": inputs["checkpoint_id"],
                                             "step": 1, "choice": "applied"})
    assert out["status"] == "changed"
