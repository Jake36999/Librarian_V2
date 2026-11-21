"""W7's root causes (owner, 2026-11-21): OP1 (read work waiting for acceptance is told to
someone), F2 (attestation names who actually accepted), OP8 (a library's review route applies
inside the Core)."""
import json

import pytest

from resource_librarian import clerk, notes, staging, tools  # noqa: F401
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.tools.staging import clerk_endpoint, decided_by_of
from resource_librarian.vault import render_config

from test_staging import ctx, source_item, staged  # noqa: F401  (fixture)


def set_mode(vault, mode):
    config = vault.config()
    config.setdefault("promotion", {})["mode"] = mode
    vault.config_path.write_text(render_config(config))


# ----------------------------------------------------------------------------- OP1

def test_read_work_waiting_for_acceptance_is_on_the_agenda_and_batch_status(staged):
    store = staging.StagingStore(staged)
    assert store.awaiting_acceptance() == {"count": 0}
    store.add(source_item("s-c", "read - one", status="enriched"))
    store.add(source_item("s-d", "read - two", status="partial"))
    waiting = store.awaiting_acceptance()
    assert (waiting["count"], waiting["enriched"], waiting["partial"]) == (2, 1, 1)
    assert waiting["oldest_days"] == 0 and "staging_decide" in waiting["next"]
    agenda = REGISTRY.call("agenda", {}, ctx(staged))
    assert agenda["awaiting_acceptance"]["count"] == 2
    status = REGISTRY.call("batch_status", {}, ctx(staged))
    assert status["awaiting_acceptance"]["count"] == 2


def test_the_lead_is_told_read_sources_are_not_in_the_library_yet(staged):
    from resource_librarian.loop import Loop

    class NoModel:
        def chat(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError

    loop = Loop(staged, NoModel(), tier="contribute", scribe=None, extras={})
    assert "waiting to be accepted" not in loop.library_context()
    staging.StagingStore(staged).add(source_item("s-c", "read - one", status="enriched"))
    text = loop.library_context()
    assert "1 source(s) in staging have been read and are waiting to be accepted" in text
    assert "cannot be cited until accepted" in text


# ----------------------------------------------------------------------------- F2

def test_an_agent_on_the_persons_surface_is_recorded_as_the_agent(staged):
    agent = Context(tier="curate", vault=staged, extras={
        "clerk": clerk.Scripted(lambda p: {}), "actor": {"kind": "agent", "name": "tier 0"}})
    assert decided_by_of(agent) == "agent"
    assert decided_by_of(ctx(staged)) == "person"
    assert decided_by_of(Context(tier="contribute", vault=staged)) == "agent"


def test_under_agent_mode_its_acceptance_says_agent_and_under_person_mode_it_waits(staged):
    from test_staging import drafts
    agent = Context(tier="curate", vault=staged, extras={
        "clerk": clerk.Scripted(drafts), "actor": {"kind": "agent", "name": "tier 0"}})
    REGISTRY.call("staging_review", {"item_id": "s-a"}, agent)
    set_mode(staged, "person")
    held = REGISTRY.call("staging_decide", {"item_ids": ["s-a"], "decision": "accept",
                                            "reason": "agent run"}, agent)
    first = held["results"][0]
    assert first.get("refused") == "PERSON_CONFIRMS", held   # not the agent's to make
    set_mode(staged, "agent")
    out = REGISTRY.call("staging_decide", {"item_ids": ["s-a"], "decision": "accept",
                                           "reason": "agent run"}, agent)
    result = out["results"][0]
    assert result["status"] == "accepted", result
    note = notes.load(staged.root / result["promotion"]["path"])
    assert note.frontmatter["attested_by"] == "agent"


def test_the_core_api_takes_only_an_agent_declaration():
    from resource_librarian import app as app_module
    source = open(app_module.__file__, encoding="utf-8").read()
    assert "actor is {kind: 'agent', name: '<who>'}" in source


# ----------------------------------------------------------------------------- OP8

def test_a_surfaces_clerk_still_takes_the_librarys_review_route(vault):
    config = vault.config()
    config["clerk"] = {"provider": "", "route_review": "deepinfra:zai-org/GLM-5.3"}
    vault.config_path.write_text(render_config(config))
    assigned = clerk.Scripted(lambda p: {})
    endpoint = clerk_endpoint(Context(tier="contribute", vault=vault, extras={"clerk": assigned}))
    assert isinstance(endpoint, clerk.Router)
    assert endpoint.for_task("review") is not assigned
    assert "GLM-5.3" in str(getattr(endpoint.for_task("review"), "model", "")) or \
        "GLM-5.3" in json.dumps(getattr(endpoint.for_task("review"), "models", {}) or {}) or \
        "GLM-5.3" in endpoint.name
    assert endpoint.for_task("bottom_line") is assigned               # the rest: the assigned Clerk


def test_without_task_routes_the_surfaces_clerk_is_used_as_it_is(vault):
    assigned = clerk.Scripted(lambda p: {})
    assert clerk_endpoint(Context(tier="contribute", vault=vault,
                                  extras={"clerk": assigned})) is assigned
