"""DEPLOY-03: an adopted folder's own Markdown is a workspace document - searchable in
its own scope, never rewritten, and never given a shape by the folder it sits in."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from resource_librarian import content_roots, notes, schema
from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.index import Index
from resource_librarian.init import init
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.search import Engine, search
from resource_librarian.vault import Vault

DOCS = {
    "README.md": "# Team handbook\n\nHow we deploy the ingestion pipeline.\n",
    "guide/deploy.md": "# Deploying\n\nRun the blue-green rollout, then watch the canary.\n",
    "api/README.md": "# API\n\nThe ingestion endpoint accepts batches.\n",
    # A folder named like a Librarian shape: without frontmatter it is still a document.
    "Sources/vendor-notes.md": "# Vendor notes\n\nThe canary vendor bills per seat.\n",
    "node_modules/pkg/README.md": "# dependency readme mentioning canary\n",
}


def hashes(root: Path) -> dict[str, str]:
    out = {}
    for dirpath, _, filenames in os.walk(root):
        if os.path.relpath(dirpath, root).split(os.sep)[0] == ".librarian":
            continue
        for name in filenames:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as handle:
                out[os.path.relpath(path, root)] = hashlib.sha256(handle.read()).hexdigest()
    return out


@pytest.fixture
def adopted(tmp_path):
    root = tmp_path / "Docs"
    for rel, text in DOCS.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    content_roots.apply_adopt(root, content_roots.plan_adopt(root)["survey_fingerprint"])
    return Vault(root)


@pytest.fixture
def with_model(adopted, tmp_path):
    """The adopted library later gains the Librarian's content model and one real note."""
    init(tmp_path / "Starter", name="s")
    model = (tmp_path / "Starter" / schema.MODEL_PATH).read_text(encoding="utf-8")
    target = adopted.root / schema.MODEL_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(model, encoding="utf-8")
    note = adopted.root / "Sources" / "osquery.md"
    note.write_text("---\ntype: source\nkind: repository\ntitle: osquery\n---\n# osquery\n\n"
                    "## Bottom Line\nThe operating system as a SQL database.\n",
                    encoding="utf-8")
    return adopted


def shapes(vault: Vault) -> dict[str, str]:
    with Index(vault) as index:
        index.refresh()
        return {r["path"]: r["shape"] for r in index.conn.execute("SELECT path, shape FROM note")}


def test_unfrontmattered_documents_are_workspace_documents(adopted):
    assert shapes(adopted) == {"README.md": "workspace_document",
                               "guide/deploy.md": "workspace_document",
                               "api/README.md": "workspace_document",
                               "Sources/vendor-notes.md": "workspace_document"}


def test_the_folder_never_assigns_a_shape_to_a_document(with_model):
    found = shapes(with_model)
    assert found["Sources/vendor-notes.md"] == "workspace_document"     # not "source"
    assert found["Sources/osquery.md"] == "source"                      # a real note still is


def test_indexing_and_searching_rewrite_nothing(adopted):
    before = hashes(adopted.root)
    with Index(adopted) as index:
        index.refresh()
        search(Engine(index, adopted.config()["heuristics"]), "canary rollout", "workspace")
    assert hashes(adopted.root) == before


def test_excluded_folders_are_not_documents(adopted):
    assert "node_modules/pkg/README.md" not in shapes(adopted)
    assert all(not p.relative_to(adopted.root).parts[0] == "node_modules"
               for p in notes.iter_paths(adopted.root))


def test_the_workspace_scope_finds_the_documentation(adopted):
    with Index(adopted) as index:
        index.refresh()
        engine = Engine(index, adopted.config()["heuristics"])
        found = search(engine, "blue-green rollout canary", "workspace")
        assert found.results and found.results[0].name == "deploy"
        assert {r.kind for r in found.results} == {"workspace_document"}
        assert not search(engine, "blue-green rollout canary", "donor").results
        everything = search(engine, "blue-green rollout canary", "all")
        assert "workspace" in everything.ran
        assert any(r.fields.get("intent") == "workspace" for r in everything.results)


def test_eligible_agents_search_it_through_the_tool(adopted):
    reader = Context(tier="consult", vault=adopted)
    out = REGISTRY.call("search", {"query": "ingestion endpoint batches",
                                   "intent": "workspace"}, reader)
    assert "error" not in out and "refused" not in out, out
    assert out["results"][0]["name"] == "README"


def test_validation_does_not_judge_documents_by_the_content_model(with_model):
    out = REGISTRY.call("check_notes", {}, Context(tier="consult", vault=with_model))
    assert "violations" in out, out
    # No content-model judgement of documentation. A frontmatter-less file in a
    # note folder carries only REMED-01's informational flag.
    judged = {v["note"] for v in out["violations"] if v["check"] != "undeclared_in_note_folder"}
    assert "vendor-notes" not in judged and "README" not in judged


def test_a_created_library_is_unchanged(vault):
    """No manifest: shapes still follow the folder, as before."""
    path = vault.root / "Sources" / "plain.md"
    path.write_text("# Plain\n\nNo frontmatter.\n", encoding="utf-8")
    assert shapes(vault)["Sources/plain.md"] == "source"


# --- REMED-01: one classification by declared type (Codex consolidated review V1) --

@pytest.fixture
def mixed(with_model):
    root = with_model.root
    for rel, text in {"site/README.md": "---\ntitle: Site\n---\n# Site\n",
                      "api/README.md": "---\ntitle: API\n---\n# API\n",
                      "guide/link.md": "# Guide\n\nSee [[Managed]].\n",
                      "Concepts/Managed.md": "---\ntype: concept\ntitle: Managed\n---\n# Managed\n",
                      "Sources/PreviouslyManaged.md": "# Lost its frontmatter\n"}.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return with_model


def checked(vault):
    out = REGISTRY.call("check_notes", {}, Context(tier="consult", vault=vault))
    assert "violations" in out, out
    return out["violations"]


def test_frontmattered_docs_tree_readmes_are_not_duplicate_notes(mixed):
    assert not [v for v in checked(mixed)
                if v["check"] == "unique_note_names" and v["note"] == "README"]


def test_a_workspace_documents_link_keeps_a_managed_note_from_being_an_orphan(mixed):
    assert not [v for v in checked(mixed)
                if v["check"] == "orphan_notes" and v["note"] == "Managed"]


def test_an_undeclared_file_in_a_note_folder_is_flagged_not_classified_by_folder(mixed):
    flagged = [v for v in checked(mixed) if v["note"] == "PreviouslyManaged"]
    assert [v["check"] for v in flagged] == ["undeclared_in_note_folder"]
    assert flagged[0]["severity"] == "info"


def test_the_index_classifies_by_declared_type_not_by_frontmatter_or_folder(mixed):
    found = shapes(mixed)
    assert found["site/README.md"] == "workspace_document"     # frontmatter, no managed type
    assert found["Sources/PreviouslyManaged.md"] == "workspace_document"
    assert found["Concepts/Managed.md"] == "concept"
    assert found["Sources/osquery.md"] == "source"


# --- REMED-02: the `all` search reports each group honestly (Codex review S1) ------

def everything(vault, **kwargs):
    from resource_librarian.search import search as run
    with Index(vault) as index:
        index.refresh()
        return run(Engine(index, vault.config()["heuristics"]), "blue-green rollout canary",
                   "all", **kwargs)


def test_all_reports_each_groups_own_counts_and_verdict(adopted):
    out = everything(adopted)
    assert "workspace" in out.ran and out.groups["workspace"]["matched"] >= 1
    assert out.verdict != "uncovered"                    # a group found it
    assert out.considered == sum(g["considered"] for g in out.groups.values())
    assert out.coverage["from_group"] in out.groups
    assert "workspace" in out.next_step


def test_filters_say_which_group_they_narrowed(adopted):
    out = everything(adopted, max_age_days=1)
    assert out.groups["orient"]["filters"] == "applied"
    assert out.groups["workspace"]["filters"] == "not applicable"
    assert out.advisories[0].startswith("constraints and max_age_days narrowed the sources")


def test_a_source_argument_that_would_be_ignored_is_refused(adopted):
    from resource_librarian.search import ConstraintError
    with pytest.raises(ConstraintError, match="source narrows only in_text, technique"):
        everything(adopted, source="does-not-exist")
    out = REGISTRY.call("search", {"query": "canary", "intent": "donor", "source": "x"},
                        Context(tier="consult", vault=adopted))
    assert "error" in out and "source narrows only" in str(out)
