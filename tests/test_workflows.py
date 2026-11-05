import json
import subprocess

import pytest

from resource_librarian import clerk, intake, tools, workflows  # noqa: F401
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.staging import StagingStore
from resource_librarian.vault import render_config

from conftest import add_source
from test_intake import RESPONSES, clerk_answers


def person(vault, **extras):
    return Context(tier="curate", vault=vault, extras=extras)


def agent(vault, **extras):
    return Context(tier="contribute", vault=vault, extras=extras)


GOOD = """
workflow: find-and-review
purpose: search for something and review the first staged item
inputs:
  query: {type: string}
steps:
  - id: found
    action: search
    args: {query: {from: inputs.query}, limit: 3}
  - id: waiting
    action: staging_list
    args: {kind: source}
outputs:
  verdict: {from: steps.found.verdict}
"""


def test_standard_set_is_valid(vault):
    out = REGISTRY.call("list_workflows", {}, person(vault))
    names = {d["name"]: d for d in out["definitions"]}
    assert {"sync-vault", "ingest-cited", "review-staged", "deep-read-staged",
            "clear-enrichment-backlog"} <= set(names)
    assert all(d["valid"] and d["accepted"] for d in names.values())


@pytest.mark.parametrize("bad, expected", [
    ("workflow: x1\npurpose: p\nsteps:\n  - id: a\n    action: rm_rf\n", "not a registered action"),
    ("workflow: x1\npurpose: p\nsteps:\n  - id: a\n    action: search\n    args: {qury: x}\n",
     "takes no argument 'qury'"),
    ("workflow: x1\npurpose: p\nsteps:\n  - id: a\n    action: search\n", "needs 'query'"),
    ("workflow: x1\npurpose: p\nsteps:\n  - id: a\n    action: search\n"
     "    args: {query: {from: steps.later.x}}\n", "names no earlier step"),
    ("workflow: x1\npurpose: p\nsteps:\n  - id: a\n    action: search\n    args: {query: q}\n"
     "  - id: b\n    action: get_note\n    args: {name: {from: steps.a.nonsense}}\n",
     "returns"),
    ("workflow: x1\npurpose: p\nsteps:\n  - id: a\n    action: search\n"
     "    args: {query: {from: inputs.missing}}\n", "no declared input"),
    ("workflow: x1\npurpose: p\nsteps:\n  - id: a\n    action: search\n"
     "    args: {query: q, intent: poetry}\n", "is not one of"),
    ("workflow: x1\npurpose: p\nsteps:\n  - id: a\n    action: search\n    args: {query: q}\n"
     "    python: print(1)\n", "unknown key 'python'"),
    ("pipeline: x1\npurpose: p\nsteps:\n  - id: a\n    action: search\n    args: {query: q}\n",
     "a pipeline's steps are workflows or routes"),
    ("pipeline: x1\npurpose: p\nsteps:\n  - id: r\n    route:\n      decide: reason\n"
     "      question: q\n      options:\n        a: {workflow: run-queue}\n        b: {end: true}\n",
     "when_to_choose"),
    ("workflow: Bad Name\npurpose: p\nsteps: []\n", "lower-case"),
])
def test_invalid_definitions_are_refused_at_save(vault, bad, expected):
    out = REGISTRY.call("save_workflow", {"yaml_text": bad}, person(vault))
    assert out["error"] == "invalid_arguments" and expected in out["detail"], out
    assert not (vault.librarian / "workflows").exists() or \
        not list((vault.librarian / "workflows").glob("x1.yaml"))


def test_standard_names_cannot_be_shadowed(vault):
    text = "workflow: sync-vault\npurpose: p\nsteps:\n  - id: a\n    action: rules\n"
    out = REGISTRY.call("save_workflow", {"yaml_text": text}, person(vault))
    assert "standard" in out["detail"]


def test_agent_saved_definitions_wait_for_a_person(vault):
    a = agent(vault)
    assert REGISTRY.call("save_workflow", {"yaml_text": GOOD}, a)["accepted"] is False
    refused = REGISTRY.call("run_workflow", {"name": "find-and-review",
                                             "inputs": {"query": "x"}}, a)
    assert refused["refused"] == "PERSON_CONFIRMS"
    assert REGISTRY.call("accept_workflow", {"name": "find-and-review"}, a)["refused"] == \
        "TIER_REFUSED"
    REGISTRY.call("accept_workflow", {"name": "find-and-review"}, person(vault))
    ran = REGISTRY.call("run_workflow", {"name": "find-and-review", "inputs": {"query": "x"}}, a)
    assert ran["status"] == "finished" and ran["outputs"]["verdict"]
    edited = (vault.librarian / "workflows" / "find-and-review.yaml")
    edited.write_text(edited.read_text().replace("limit: 3", "limit: 4"))
    assert REGISTRY.call("run_workflow", {"name": "find-and-review", "inputs": {"query": "x"}},
                         a)["refused"] == "PERSON_CONFIRMS"            # an edit revokes it


def test_inputs_are_checked(vault):
    REGISTRY.call("save_workflow", {"yaml_text": GOOD}, person(vault))
    out = REGISTRY.call("run_workflow", {"name": "find-and-review", "inputs": {}}, person(vault))
    assert "needs input 'query'" in out["detail"]
    out = REGISTRY.call("run_workflow", {"name": "find-and-review",
                                         "inputs": {"query": "x", "extra": 1}}, person(vault))
    assert "no input" in out["detail"]


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo_vault(vault, tmp_path):
    remote = tmp_path / "remote.git"
    _git("init", "--bare", str(remote), cwd=tmp_path)
    for args in (("init", "-b", "main"), ("config", "user.email", "t@example.org"),
                 ("config", "user.name", "Test"), ("remote", "add", "origin", str(remote))):
        _git(*args, cwd=vault.root)
    return vault, remote


def test_sync_vault_commits_and_pushes_as_a_person(repo_vault):
    vault, remote = repo_vault
    (vault.derived / "junk.bin").write_text("derived")
    out = REGISTRY.call("run_workflow", {"name": "sync-vault"}, person(vault))
    assert out["status"] == "finished" and out["outputs"]["committed"] is True, out
    tracked = subprocess.run(["git", "ls-files"], cwd=vault.root, capture_output=True,
                             text=True).stdout
    assert "About/Rules.md" in tracked and "junk.bin" not in tracked
    log = subprocess.run(["git", "log", "--oneline", "main"], cwd=remote, capture_output=True,
                         text=True).stdout
    assert "sync the vault" in log
    # The run's own log (tracked, like sessions) gained its closing events after
    # the commit, so the next commit carries them; after that, nothing is left.
    assert REGISTRY.call("vault_commit", {"message": "tail"}, person(vault))["committed"]
    assert REGISTRY.call("vault_commit", {"message": "none"}, person(vault))["committed"] is False


def test_agent_push_needs_the_vault_setting(repo_vault):
    vault, _ = repo_vault
    out = REGISTRY.call("run_workflow", {"name": "sync-vault"}, agent(vault))
    assert out["status"] == "failed" and out["at"] == "push"
    assert out["result"]["refused"] == "PERSON_CONFIRMS"
    config = vault.config()
    config["vault"]["agent_push"] = True
    vault.config_path.write_text(render_config(config))
    (vault.root / "Inbox" / "note.md").write_text("new")
    assert REGISTRY.call("run_workflow", {"name": "sync-vault"}, agent(vault))["status"] == \
        "finished"


def test_commit_refuses_secrets(repo_vault):
    vault, _ = repo_vault
    (vault.root / "Inbox" / "server.key").write_text("-----BEGIN KEY-----")
    out = REGISTRY.call("vault_commit", {"message": "x"}, person(vault))
    assert out["error"] == "refused" and "server.key" in out["detail"]


def backlog(vault):
    for ref in ("acme/rowstream", "arXiv:2405.01234", "nobody/nothing"):
        intake.enqueue(vault, ref)
    for i in range(3):
        add_source(vault.root, f"filler {i}", f"Draws pictures number {i}.")


def routing_ctx(vault, router, tier="curate"):
    return Context(tier=tier, vault=vault, extras={
        "clerk": clerk.Scripted(clerk_answers), "fetcher": intake.Replay(RESPONSES),
        "router": router})


def test_pipeline_routes_by_reasoning_with_minimal_framing(vault):
    backlog(vault)

    def choose(payload):
        item = json.loads(payload["user"].split("---\n", 1)[1].rsplit("\n---", 1)[0])
        if item.get("status") != "staged":
            return {"option": "done", "reason": "not staged"}
        if "Lovelace" in item.get("name", ""):
            return {"option": "flag", "reason": "test"}
        return {"option": "review", "reason": "ordinary"}
    router = workflows.Router(clerk.Scripted(choose))
    out = REGISTRY.call("run_pipeline", {"name": "clear-enrichment-backlog"},
                        routing_ctx(vault, router))
    assert out["status"] == "finished", out
    assert out["steps"]["next"]["chosen"] == ["review", "flag", "done"]
    store = StagingStore(vault)
    flagged = [i for i in store.items("source") if i["sensitivity"] == "review"]
    assert [i["name"] for i in flagged] == [n for n in [flagged[0]["name"]]
                                            if n.startswith("Lovelace")]
    for payload in router.endpoint.payloads:
        text = payload["user"] + payload["system"]
        assert "found_for" not in text and "session" not in text.lower()
        assert set(payload["schema"]["properties"]["option"]["enum"]) == {"review", "flag",
                                                                           "done"}
    events = workflows.RunStore(vault).events(out["run"])
    assert [e["option"] for e in events if e["type"] == "routed"] == ["review", "flag", "done"]


def test_pipeline_pauses_without_a_model_and_a_person_can_route(vault):
    backlog(vault)
    ctx = routing_ctx(vault, workflows.Router(None))
    paused = REGISTRY.call("run_pipeline", {"name": "clear-enrichment-backlog"}, ctx)
    assert paused["status"] == "paused" and paused["at"] == "next[0]"
    assert "no routing model" in paused["reason"]
    assert "found_for" not in json.dumps(paused["item"])
    fetched = len(ctx.extras["fetcher"].calls)
    refused = REGISTRY.call("run_resume", {"run_id": paused["run"],
                                           "choices": {"next[0]": "done"}},
                            routing_ctx(vault, workflows.Router(None), tier="contribute"))
    assert refused["refused"] == "PERSON_CONFIRMS"
    choices = {"next[0]": "review", "next[1]": "review", "next[2]": "done"}
    done = REGISTRY.call("run_resume", {"run_id": paused["run"], "choices": choices}, ctx)
    assert done["status"] == "finished", done
    assert len(ctx.extras["fetcher"].calls) == fetched          # finished steps not redone
    status = REGISTRY.call("run_status", {"run_id": paused["run"]}, ctx)
    assert status["status"] == "finished"
    assert [r["by"] for r in status["routes"]] == ["person"] * 3


DECLARED = """
pipeline: sort-queue
purpose: run the queue and review what was staged, by declaration alone
steps:
  - id: intake
    workflow: run-queue
  - id: next
    route:
      each: {from: steps.intake.outputs.results}
      decide: declared
      options:
        review:
          workflow: review-item
          args: {item_id: {from: item.item}}
          when: {from: item.status, is: staged}
        done: {end: true}
      otherwise: done
"""


def test_declared_routing_needs_no_model(vault):
    backlog(vault)
    ctx = routing_ctx(vault, workflows.Router(None))
    REGISTRY.call("save_workflow", {"yaml_text": DECLARED}, ctx)
    out = REGISTRY.call("run_pipeline", {"name": "sort-queue"}, ctx)
    assert out["status"] == "finished" and out["steps"]["next"]["chosen"] == [
        "review", "review", "done"]


def test_ingest_cited_is_v1s_script_declared(vault):
    from test_scout import SYNTHETIC_TRACE
    from conftest import write_note
    write_note(vault.root, "Inbox/Trace.md", "type: report", SYNTHETIC_TRACE)
    atom = RESPONSES["https://export.arxiv.org/api/query?id_list=2405.01234"]
    ctx = routing_ctx(vault, None)
    ctx.extras["fetcher"] = intake.Replay({
        "https://export.arxiv.org/api/query?id_list=2401.00001": atom,
        "https://export.arxiv.org/api/query?id_list=2402.00002": atom.replace(
            "Log-Based Change Capture at Scale", "A Gym For Hierarchical Problems")})
    import resource_librarian.intake as intake_mod
    saved, intake_mod.ARXIV_INTERVAL = intake_mod.ARXIV_INTERVAL, 0.0
    try:
        out = REGISTRY.call("run_workflow", {"name": "ingest-cited",
                                             "inputs": {"path": "Inbox/Trace.md"}}, ctx)
    finally:
        intake_mod.ARXIV_INTERVAL = saved
    assert out["status"] == "finished", out
    assert out["outputs"] == {"cited": 3, "ingested": 2}          # the Wikipedia link skipped
    assert out["steps"]["papers"]["considered"] == 3


BRIEF = """
workflow: open-a-brief
purpose: open a brief with a standing disqualifier
inputs:
  need: {type: string}
steps:
  - id: brief
    action: open_brief
    args: {need: {from: inputs.need}, disqualifiers: ["needs a GPU"]}
"""


def test_steps_obey_the_session_phase_gate(vault):
    ctx = agent(vault)
    REGISTRY.call("save_workflow", {"yaml_text": BRIEF}, person(vault))
    REGISTRY.call("open_session", {"purpose": "explore", "question": "q"}, ctx)
    early = REGISTRY.call("run_workflow", {"name": "open-a-brief", "inputs": {"need": "x"}}, ctx)
    assert early["status"] == "failed" and early["result"]["refused"] == "PHASE_GATE"
    assert early["session"]["phase"] == "frame"            # the run itself is in the session
    REGISTRY.call("advance", {}, ctx)
    REGISTRY.call("update_plan", {"fields": {"map": "m"}}, ctx)
    REGISTRY.call("advance", {}, ctx)
    ok = REGISTRY.call("run_workflow", {"name": "open-a-brief", "inputs": {"need": "x"}}, ctx)
    assert ok["status"] == "finished", ok
    assert REGISTRY.call("session_status", {}, ctx)["briefs"]["B1"]["disqualifiers"] == \
        ["needs a GPU"]


# -- MF-017: a run is pinned to the definitions it started with -------------------

CHILD_A = """
workflow: child-a
purpose: list the staged sources
steps:
  - id: listed
    action: staging_list
    args: {kind: source}
"""
CHILD_B = """
workflow: child-b
purpose: the version the run started with
steps:
  - id: original
    action: staging_list
    args: {kind: source}
"""
CHILD_B_EDITED = CHILD_B.replace("id: original", "id: edited")
PAUSING = """
pipeline: pinned-run
purpose: run one child, then ask whether to run another
steps:
  - id: first
    workflow: child-a
  - id: next
    route:
      decide: reason
      question: carry on?
      options:
        go: {workflow: child-b, when_to_choose: always}
        stop: {end: true, when_to_choose: never}
"""
STRAIGHT = """
pipeline: pinned-now
purpose: run one child, then the other, by declaration
steps:
  - id: first
    workflow: child-a
  - id: next
    route:
      decide: declared
      options:
        go: {workflow: child-b}
        stop: {end: true, when: {from: steps.first.status, is: never}}
      otherwise: go
"""


def child_b(vault):
    return vault.librarian / "workflows" / "child-b.yaml"


def saved(vault, *texts, by=None):
    for text in texts:
        out = REGISTRY.call("save_workflow", {"yaml_text": text}, by or person(vault))
        assert "error" not in out, out


def ran_keys(vault, run_id):
    return [e["key"] for e in workflows.RunStore(vault).events(run_id) if e["type"] == "done"]


def test_a_child_edited_during_the_run_still_runs_as_it_started(vault):
    saved(vault, CHILD_A, CHILD_B, STRAIGHT)

    def edit_child_b(event):
        if event["step"] == "first/listed":
            child_b(vault).write_text(CHILD_B_EDITED, encoding="utf-8")

    out = REGISTRY.call("run_pipeline", {"name": "pinned-now"},
                        person(vault, router=workflows.Router(None), progress=edit_child_b))

    assert out["status"] == "finished", out
    assert "next->go/original" in ran_keys(vault, out["run"])
    assert not any(k.endswith("/edited") for k in ran_keys(vault, out["run"]))
    started = workflows.RunStore(vault).events(out["run"])[0]
    assert set(started["closure"]) == {"pinned-now", "child-a", "child-b"}


def test_a_resume_runs_the_pinned_children_or_refuses_drift(vault):
    saved(vault, CHILD_A, CHILD_B, PAUSING)
    ctx = person(vault, router=workflows.Router(None))
    paused = REGISTRY.call("run_pipeline", {"name": "pinned-run"}, ctx)
    assert paused["status"] == "paused" and paused["at"] == "next", paused

    child_b(vault).write_text(CHILD_B_EDITED, encoding="utf-8")
    refused = REGISTRY.call("run_resume", {"run_id": paused["run"], "choices": {"next": "go"}},
                            ctx)
    assert "'child-b' changed or went after this run started" in refused["detail"]

    child_b(vault).write_text(CHILD_B, encoding="utf-8")         # back as it was
    done = REGISTRY.call("run_resume", {"run_id": paused["run"], "choices": {"next": "go"}},
                         ctx)
    assert done["status"] == "finished", done
    assert "next->go/original" in ran_keys(vault, paused["run"])


def test_a_child_no_person_accepted_stops_the_run_before_it_starts(vault):
    saved(vault, CHILD_A)
    saved(vault, CHILD_B, by=agent(vault))                       # saved, not accepted
    saved(vault, PAUSING)
    # An agent's run (a person's own run is its own acceptance).
    out = REGISTRY.call("run_pipeline", {"name": "pinned-run"},
                        agent(vault, router=workflows.Router(None)))
    assert out["refused"] == "PERSON_CONFIRMS" and "'child-b'" in out["detail"]
    assert not list((vault.librarian / "runs").glob("*.jsonl"))


def test_an_unpinned_or_tampered_run_log_is_not_resumed(vault):
    saved(vault, CHILD_A, CHILD_B, PAUSING)
    store = workflows.RunStore(vault)
    library = workflows.Library(vault)
    store.append("legacy-run", {"type": "started", "name": "pinned-run", "kind": "pipeline",
                                "digest": library.get("pinned-run").digest, "inputs": {}})
    store.append("legacy-run", {"type": "paused", "step": "next"})
    ctx = person(vault, router=workflows.Router(None))
    legacy = REGISTRY.call("run_resume", {"run_id": "legacy-run"}, ctx)
    assert "started before the workflows it runs were pinned" in legacy["detail"]

    paused = REGISTRY.call("run_pipeline", {"name": "pinned-run"}, ctx)
    log = store.path(paused["run"])
    lines = log.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("id: original", "id: swapped")   # the text, not its digest
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tampered = REGISTRY.call("run_resume", {"run_id": paused["run"], "choices": {"next": "go"}},
                             ctx)
    assert "does not match its digest" in tampered["detail"]


def test_a_resume_refuses_an_action_that_is_no_longer_registered(vault, monkeypatch):
    saved(vault, CHILD_A, CHILD_B, PAUSING)
    ctx = person(vault, router=workflows.Router(None))
    paused = REGISTRY.call("run_pipeline", {"name": "pinned-run"}, ctx)
    monkeypatch.delitem(REGISTRY._tools, "staging_list")         # noqa: SLF001
    out = REGISTRY.call("run_resume", {"run_id": paused["run"], "choices": {"next": "go"}}, ctx)
    assert "no longer valid" in out["detail"] and "staging_list" in out["detail"]


def test_a_closure_refuses_a_cycle_and_an_unknown_name(vault):
    def wf(name, child):
        return workflows.parse(f"workflow: {name}\npurpose: p\nsteps:\n"
                               f"  - id: s\n    workflow: {child}\n")

    class Fixed(workflows.Library):
        def __init__(self, *defs):
            super().__init__(None)
            self.defs = {d.name: d for d in defs}

        def all(self):
            return dict(self.defs)

    loop = Fixed(wf("aa", "bb"), wf("bb", "aa"))
    with pytest.raises(workflows.DefinitionError, match="aa -> bb -> aa"):
        workflows.closure(loop.get("aa"), loop)
    gap = Fixed(wf("aa", "zz"))
    with pytest.raises(workflows.DefinitionError, match="no workflow or pipeline named 'zz'"):
        workflows.closure(gap.get("aa"), gap)


# -- MF-018: a step that stopped part way is never repeated blindly ---------------

WRITES = """
workflow: write-then-list
purpose: write one note, then list staging
steps:
  - id: note
    action: write_note
    args: {folder: Notes, name: Run note, body: written once}
  - id: after
    action: staging_list
    args: {kind: source}
"""


class Crash(Exception):
    """The app stopping after an action took effect, before its result was logged."""


def crash_after(monkeypatch, tool):
    """Run `tool` for real once, then stop the run; count every call to it."""
    calls = []
    original = REGISTRY.call

    def call(name, arguments, ctx):
        result = original(name, arguments, ctx)
        if name == tool:
            calls.append(dict(arguments or {}))
            if len(calls) == 1:
                raise Crash("stopped part way")
        return result

    monkeypatch.setattr(REGISTRY, "call", call)
    return calls


def a_run(vault, name, ctx, **arguments):
    out = REGISTRY.call("run_workflow", {"name": name, **arguments}, ctx)
    assert out["error"] == "failed" and "stopped part way" in out["detail"], out
    return [p.stem for p in (vault.librarian / "runs").glob("*.jsonl")][0]


def test_a_write_that_stopped_part_way_waits_for_a_person(vault, monkeypatch):
    saved(vault, WRITES)
    calls = crash_after(monkeypatch, "write_note")
    run_id = a_run(vault, "write-then-list", agent(vault))
    assert (vault.root / "Notes" / "Run note.md").is_file()      # it took effect
    assert [e["type"] for e in workflows.RunStore(vault).events(run_id)][-1] == "dispatch"

    held = REGISTRY.call("run_resume", {"run_id": run_id}, agent(vault))
    assert held["status"] == "paused" and held["reason"] == "outcome_unknown", held
    assert held["at"] == "note" and held["options"] == ["retry", "applied"]
    assert len(calls) == 1                                       # not sent again

    done = REGISTRY.call("run_resume", {"run_id": run_id, "choices": {"note": "applied"}},
                         person(vault))
    assert done["status"] == "finished", done
    assert len(calls) == 1 and done["steps"]["note"]["recorded_as"] == "applied"


def test_a_person_may_send_an_interrupted_write_again(vault, monkeypatch):
    saved(vault, WRITES)
    calls = crash_after(monkeypatch, "write_note")
    run_id = a_run(vault, "write-then-list", agent(vault))
    (vault.root / "Notes" / "Run note.md").unlink()               # the person checked: no note
    bad = REGISTRY.call("run_resume", {"run_id": run_id, "choices": {"note": "maybe"}},
                        person(vault))
    assert "choose one of ['retry', 'applied']" in bad["detail"]

    done = REGISTRY.call("run_resume", {"run_id": run_id, "choices": {"note": "retry"}},
                         person(vault))
    assert done["status"] == "finished", done
    assert len(calls) == 2 and (vault.root / "Notes" / "Run note.md").is_file()


def test_an_interrupted_read_is_simply_run_again(vault, monkeypatch):
    saved(vault, GOOD)
    calls = crash_after(monkeypatch, "search")
    run_id = a_run(vault, "find-and-review", agent(vault), inputs={"query": "x"})

    done = REGISTRY.call("run_resume", {"run_id": run_id}, agent(vault))

    assert done["status"] == "finished", done
    assert len(calls) == 2                                       # a read: safe to repeat
