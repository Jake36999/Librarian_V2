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
    flagged = {v["note"] for v in out["violations"]}
    assert "vendor-notes" not in flagged and "README" not in flagged


def test_a_created_library_is_unchanged(vault):
    """No manifest: shapes still follow the folder, as before."""
    path = vault.root / "Sources" / "plain.md"
    path.write_text("# Plain\n\nNo frontmatter.\n", encoding="utf-8")
    assert shapes(vault)["Sources/plain.md"] == "source"
