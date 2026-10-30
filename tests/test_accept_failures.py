"""ACCEPT-01, no mutation on failure: a failed or refused step leaves the library as
it was. These fill the cells of the acceptance matrix that no existing test
stated outright (research intake, V1 import, service slots)."""
from __future__ import annotations

import hashlib
import json

import pytest

from resource_librarian import v1_export
from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.app import ApiError, App
from resource_librarian.keys import KeyStore
from resource_librarian.providers import Reply, Scripted
from resource_librarian.registry import REGISTRY

from test_intake import ctx, library  # noqa: F401  (the intake fixture and context)
from test_v1_export import v1_tree


def tree(root, *, skip=(".librarian/quarantine",)):
    """Every file under the vault with its content hash, except the named folders."""
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_file() and not any(rel.startswith(s) for s in skip) and \
                "/derived/" not in f"/{rel}":
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def test_a_failed_intake_catalogues_stages_and_records_nothing(library):  # noqa: F811
    before = tree(library.root)
    out = REGISTRY.call("ingest", {"ref": "nobody/nothing"}, ctx(library))
    assert out["status"] == "quarantined"
    after = tree(library.root)
    new = sorted(set(after) - set(before))
    # No note, no evidence, nothing staged for review: only the failed capture is
    # kept, marked failed, for a person to retry or remove (intake.settle).
    assert {k: v for k, v in after.items() if k not in new} == before
    assert len(new) == 1 and new[0].startswith(".librarian/staging/source/queued-")
    record = json.loads((library.root / new[0]).read_text(encoding="utf-8"))
    assert record["status"] == "failed"
    assert len(list((library.work("quarantine") / "intake").glob("*.json"))) == 1


def test_a_refused_v1_import_stages_nothing(vault, tmp_path):
    v1 = v1_tree(tmp_path / "v1")
    before = tree(vault.root)
    with pytest.raises(TypeError, match="not in this import plan"):
        v1_export.stage(v1, vault, paths=["01-Resources/no such note.md"])
    assert tree(vault.root) == before


def test_a_v1_import_from_a_second_root_stages_nothing(vault, tmp_path):
    first = v1_tree(tmp_path / "first")
    v1_export.stage(first, vault, paths=["01-Resources/acme - rowstream.md"])
    before = tree(vault.root)
    with pytest.raises(TypeError, match="already bound"):
        v1_export.stage(v1_tree(tmp_path / "other"), vault)
    assert tree(vault.root) == before


@pytest.fixture
def app(vault):
    app = App(vault, keys=KeyStore(use_keyring=False), coordinate=True,
              provider_for=lambda choice: Scripted(lambda *_: Reply(choice["model"])))
    try:
        yield app
    finally:
        app.close_runtime()


@pytest.mark.parametrize("args,detail", [
    (("ocr", "nowhere", "vision-x"), "nowhere"),                      # unknown host
    (("tts", "openai", "voice-x"), "native speech services"),         # wrong host for speech
    (("search", "deepinfra", "m"), "not built yet"),                  # no such slot
])
def test_a_refused_service_choice_changes_no_slot_and_no_binding(app, args, detail):
    app.set_service("ocr", "deepinfra", "vision-m")
    services = json.dumps(app.services(), sort_keys=True, default=str)
    bindings = app.role_routes.path.read_bytes()
    with pytest.raises(ApiError, match=detail):
        app.set_service(*args)
    assert json.dumps(app.services(), sort_keys=True, default=str) == services
    assert app.role_routes.path.read_bytes() == bindings


def test_mutations_refused_after_shutdown_admission_closes_change_nothing(app):
    """Lifecycle: once the Core stops admitting work, a refused change leaves
    settings, checkpoints and service bindings exactly as they were."""
    app.set_service("ocr", "deepinfra", "vision-m")
    settings = json.dumps(app.settings.data, sort_keys=True, default=str)
    checkpoints = json.dumps(app.checkpoints.all(), sort_keys=True, default=str)
    bindings = app.role_routes.path.read_bytes()
    with app._lock:
        app._admitting = False
    for mutate in (lambda: app.set_context(working_context="too late"),
                   lambda: app.checkpoint_create("review", "late"),
                   lambda: app.set_service("ocr", "deepinfra", "vision-late")):
        with pytest.raises(ApiError) as refused:
            mutate()
        assert refused.value.status == 503
    assert json.dumps(app.settings.data, sort_keys=True, default=str) == settings
    assert json.dumps(app.checkpoints.all(), sort_keys=True, default=str) == checkpoints
    assert app.role_routes.path.read_bytes() == bindings
