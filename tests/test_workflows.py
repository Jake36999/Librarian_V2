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
