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
        "macro_run", "model_catalog_adopt", "process_approved"]
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
