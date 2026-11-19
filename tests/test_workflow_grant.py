"""A workflow a person approved or started is authorised for its own steps, once."""
import threading

from resource_librarian import batch, tools, workflows  # noqa: F401
from resource_librarian.app import App
from resource_librarian.keys import KeyStore
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.tools.workflows import _library


def test_the_batch_grant_is_exactly_the_tools_its_stages_call():
    import inspect
    source = inspect.getsource(batch)
    called = {name for name in REGISTRY.names() if f'REGISTRY.call("{name}"' in source}
    assert called == set(batch.STAGE_TOOLS)


def test_an_approved_batch_runs_with_a_grant_on_its_own_context(vault, monkeypatch):
    seen = {}
    monkeypatch.setattr(batch, "_commit", lambda ctx, fn, **kw: ("run-1", [], threading.Event()))
    monkeypatch.setattr(batch, "_run", lambda ctx, run_id, items, cancel: seen.update(ctx.extras))
    monkeypatch.setattr(batch, "status", lambda vault, run="": {})
    ctx = Context(tier="contribute", vault=vault, extras={"broker": object()})
    batch.start(ctx, "contribute")
    grant = seen["workflow_grant"]
    assert grant["tools"] == batch.STAGE_TOOLS and "run-1" in grant["label"]
    assert "workflow_grant" not in ctx.extras           # the caller's own context is untouched


def test_a_workflow_started_by_a_person_carries_a_grant_for_its_actions(vault, monkeypatch):
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    captured = {}

    class Recorder:
        def __init__(self, library, ctx, router):
            captured.update(ctx.extras)
        def start(self, name, inputs):
            return {"status": "finished", "run": "r"}
    monkeypatch.setattr(workflows, "Runner", Recorder)
    try:
        name = "clear-enrichment-backlog"
        app.start_action(name)
        for _ in range(100):
            if captured:
                break
            threading.Event().wait(0.02)
        grant = captured["workflow_grant"]
        definition = _library(Context(tier="contribute", vault=vault, extras={})).get(name)
        assert grant["tools"] == workflows.granted_actions(definition, _library(
            Context(tier="contribute", vault=vault, extras={})))
        assert grant["tools"] and grant["tools"] <= set(REGISTRY.names())
        assert "project_edit" not in grant["tools"] and "sandbox_output" not in grant["tools"]
    finally:
        app.close_runtime()


def test_a_workflow_the_vault_defines_is_not_given_a_grant(vault):
    """Stress F-03: a person accepts a vault definition once, as text. Starting it is not the
    permission for its writes (the shipped set is reviewed; this is not), however it is reached."""
    ctx = Context(tier="contribute", vault=vault, extras={})
    library = _library(ctx)
    library.save("workflow: vault-writer\npurpose: writes a note\ninputs: {}\nsteps:\n"
                 "  - id: s1\n    action: write_note\n    args: {folder: Notes, name: X, body: x}\n",
                 accepted_by_person=True)
    library.save("pipeline: vault-parent\npurpose: runs it\ninputs: {}\nsteps:\n"
                 "  - id: s1\n    workflow: vault-writer\n    args: {}\n", accepted_by_person=True)
    assert workflows.granted_actions(library.get("vault-writer"), library) == frozenset()
    assert workflows.granted_actions(library.get("vault-parent"), library) == frozenset()
    shipped = library.get("clear-enrichment-backlog")
    assert workflows.granted_actions(shipped, library)             # the shipped set still has it
