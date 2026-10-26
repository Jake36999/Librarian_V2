"""Capability extraction never substitutes mutable metadata for a repository tree."""
from __future__ import annotations

import base64

import pytest

from resource_librarian import extract, intake, tools  # noqa: F401 - register tools
from resource_librarian.evidence import EvidenceStore
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.rules import Refusal

from conftest import add_source


def repository(vault, *, tree: str = "tree-123", second_tree: str = "",
               include_structure: bool = True) -> None:
    store = EvidenceStore(vault)
    survey = store.put(
        "survey", "https://github.com/example/planner",
        {"paths": ["src/surveyed.py"], **({"tree_sha": tree} if tree else {})},
        fetched_at="2026-10-01T10:00:00Z")
    evidence = [survey.id]
    if second_tree:
        later = store.put(
            "survey", "https://github.com/example/planner",
            {"paths": ["src/later.py"], "tree_sha": second_tree},
            fetched_at="2026-10-03T10:00:00Z")
        evidence.append(later.id)
    if include_structure:
        structure = store.put(
            "code_structure", "https://github.com/example/planner (shallow clone)",
            {"modules": ["src/from-structure.py"]},
            fetched_at="2026-10-02T11:22:33Z")
        evidence.append(structure.id)
    add_source(vault.root, "planner", "A bounded planner.",
               extra_fm="evidence:\n" + "".join(f"- {item}\n" for item in evidence))


def test_plan_pins_every_component_to_survey_tree_not_component_timestamp(vault):
    repository(vault)

    planned = extract.plan(vault, "planner", offline=True)

    assert planned["revision"] == "tree-123"
    assert {item["path"] for item in planned["files"]} == {
        "src/surveyed.py", "src/from-structure.py"}
    assert {item["revision"] for item in planned["files"]} == {"tree-123"}
    assert "2026-10-02" not in str(planned)
    assert planned["plan_token"].startswith("extract-plan-v1:")
    assert extract.plan(vault, "planner", offline=True)["plan_token"] == \
        planned["plan_token"]
    assert extract.plan(vault, "planner", seed="surveyed", offline=True)["plan_token"] != \
        planned["plan_token"]


def test_plan_refuses_when_components_have_only_timestamp_like_revisions(vault):
    repository(vault, tree="")

    with pytest.raises(Refusal) as refused:
        extract.plan(vault, "planner", offline=True)

    assert refused.value.code == "PINNED_REVISION_REQUIRED"


def test_read_source_file_never_falls_back_to_default_branch(vault):
    repository(vault, tree="", include_structure=False)

    class NoFetch:
        def get(self, url):
            raise AssertionError(f"unpinned retrieval attempted: {url}")

    result = REGISTRY.call(
        "read_source_file", {"source": "planner", "path": "src/surveyed.py"},
        Context(tier="consult", vault=vault, extras={"fetcher": NoFetch()}))

    assert result["refused"] == "PINNED_REVISION_REQUIRED"


def test_distinct_survey_tree_shas_are_ambiguous_not_first_one_wins(vault):
    repository(vault, tree="tree-123", second_tree="tree-456", include_structure=False)

    with pytest.raises(Refusal) as refused:
        extract.plan(vault, "planner", offline=True)
    assert refused.value.code == "PINNED_REVISION_REQUIRED"

    class NoFetch:
        def get(self, url):
            raise AssertionError(f"ambiguous retrieval attempted: {url}")

    result = REGISTRY.call(
        "read_source_file", {"source": "planner", "path": "src/surveyed.py"},
        Context(tier="consult", vault=vault, extras={"fetcher": NoFetch()}))
    assert result["refused"] == "PINNED_REVISION_REQUIRED"


def test_materialize_requires_the_reviewed_plan_revision(vault):
    repository(vault, include_structure=False)
    planned = extract.plan(vault, "planner", offline=True)
    api = "https://api.github.com/repos/example/planner"
    replay = intake.Replay({
        f"{api}/git/trees/tree-123?recursive=1": {
            "tree": [{"path": "src/surveyed.py", "type": "blob", "sha": "blob-1"}]},
        f"{api}/git/blobs/blob-1": {
            "content": base64.b64encode(b"def surveyed():\n    return True\n").decode()},
    })

    ctx = Context(tier="curate", vault=vault, extras={"fetcher": replay})
    missing = REGISTRY.call("extract_materialize", {"source": "planner"}, ctx)
    assert missing["refused"] == "PINNED_REVISION_REQUIRED"

    missing_token = REGISTRY.call("extract_materialize", {
        "source": "planner", "revision": planned["revision"]}, ctx)
    assert missing_token["refused"] == "PINNED_REVISION_REQUIRED"

    stale = REGISTRY.call("extract_materialize", {
        "source": "planner", "revision": "older-tree",
        "plan_token": planned["plan_token"]}, ctx)
    assert stale["refused"] == "PINNED_REVISION_REQUIRED"

    changed_options = REGISTRY.call("extract_materialize", {
        "source": "planner", "seed": "surveyed", "revision": planned["revision"],
        "plan_token": planned["plan_token"]}, ctx)
    assert changed_options["refused"] == "PINNED_REVISION_REQUIRED"

    result = REGISTRY.call("extract_materialize", {
        "source": "planner", "revision": planned["revision"],
        "plan_token": planned["plan_token"]}, ctx)
    assert result["revision"] == "tree-123"
    assert result["excerpts"][0]["revision"] == "tree tree-123 (as surveyed)"
    assert result["excerpts"][0]["text"].startswith("def surveyed")
