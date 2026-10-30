"""ACCEPT-01, manual ranking: a person's offline ranking experiment end to end.

Success, refusal, recovery and no mutation on failure, through the registry
the way the browser and the CLI reach it.
"""
from __future__ import annotations

import json

import pytest

from resource_librarian import ranking
from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.tools.library import with_engine

from conftest import add_source


def person(vault):
    return Context(tier="curate", vault=vault, extras={"caller_kind": "person"})


def agent(vault):
    return Context(tier="curate", vault=vault)


def feedback(vault, events=ranking.EXPLORATORY_EVENTS, queries=ranking.EXPLORATORY_QUERIES):
    path = vault.work("eval") / "feedback.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"query": f"query {i % queries}", "note": "osquery",
             "verdict": "opened" if i % 3 else "dismissed"} for i in range(events)]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


@pytest.fixture
def library(vault):
    add_source(vault.root, "osquery", "Exposes the operating system as a SQL database.",
               "Query processes.")
    add_source(vault.root, "duckdb", "An in-process analytical SQL database.", "Analytics.")
    return vault


def state(vault):
    path = ranking._path(vault)
    return path.read_bytes() if path.exists() else None


def generated(vault):
    feedback(vault)
    out = REGISTRY.call("ranking_candidate_generate", {}, agent(vault))
    assert out.get("generated") is True, out
    return out["candidate"]["id"]


def benchmarked(vault):
    candidate = generated(vault)
    report = REGISTRY.call("ranking_benchmark", {"candidate_id": candidate}, agent(vault))
    assert "error" not in report and "refused" not in report, report
    return candidate


def test_success_a_person_selects_a_candidate_and_search_uses_its_weights(library):
    candidate = benchmarked(library)
    selected = REGISTRY.call("ranking_select", {"candidate_id": candidate}, person(library))
    assert selected == {"active": candidate, "previous": "current", "mode": "Candidate"}
    weights = ranking._candidate(library, candidate)["heuristics"]
    used = with_engine(agent(library), lambda engine: dict(engine.h))
    assert {k: used[k] for k in weights} == weights
    assert REGISTRY.call("ranking_status", {}, agent(library))["mode"] == "Candidate"


def test_refusal_an_agent_cannot_select_or_restore_a_policy(library):
    candidate = generated(library)
    before = state(library)
    for tool, args in (("ranking_select", {"candidate_id": candidate}), ("ranking_restore", {})):
        out = REGISTRY.call(tool, args, agent(library))
        assert out["refused"] == "PERSON_CONFIRMS", out
    assert state(library) == before
    assert ranking.status(library)["mode"] == "Current"


def test_refusal_and_no_mutation_an_unbenchmarked_candidate_cannot_be_selected(library):
    candidate = generated(library)
    before = state(library)
    out = REGISTRY.call("ranking_select", {"candidate_id": candidate}, person(library))
    assert out["refused"] == "RANKING_UNBENCHMARKED", out
    assert state(library) == before and ranking.status(library)["mode"] == "Current"


def test_refusal_too_little_feedback_proposes_nothing(library):
    feedback(library, events=5, queries=2)
    out = REGISTRY.call("ranking_candidate_generate", {}, agent(library))
    assert out["generated"] is False and out["evidence"]["state"] == "insufficient"
    assert state(library) is None


def test_recovery_restore_returns_to_the_previous_policy(library):
    candidate = benchmarked(library)
    REGISTRY.call("ranking_select", {"candidate_id": candidate}, person(library))
    restored = REGISTRY.call("ranking_restore", {}, person(library))
    assert restored["active"] == "current" and restored["restored"] is True
    assert ranking.active_overrides(library) == {}
    used = with_engine(agent(library), lambda engine: dict(engine.h))
    assert used.get("coverage_weight") == library.config()["heuristics"].get("coverage_weight")


def test_recovery_a_damaged_experiment_file_never_breaks_search(library):
    ranking._path(library).write_text("{not json", encoding="utf-8")
    assert ranking.status(library)["mode"] == "Current"
    out = REGISTRY.call("search", {"query": "SQL database"}, agent(library))
    assert out["results"], out


def test_no_mutation_selecting_an_unknown_candidate_changes_nothing(library):
    generated(library)
    before = state(library)
    out = REGISTRY.call("ranking_select", {"candidate_id": "ranking-missing"}, person(library))
    assert "error" in out or "refused" in out, out
    assert state(library) == before
