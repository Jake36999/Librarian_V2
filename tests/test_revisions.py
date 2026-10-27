"""CORE-05: replace-existing writes bring the revision their caller read.

The writer's compare-and-swap existed but no caller passed a precondition,
so an agent's read-modify-write silently overwrote an edit made since -
after a document lease's quiet window, or with no plugin at all.  Now a read
hands out an opaque revision token, a replace-existing write must bring it
back, and a note that changed since becomes a write-conflict checkpoint.
"""
import json

import pytest

from conftest import add_source
from resource_librarian import revisions
from resource_librarian.app import App
from resource_librarian.registry import REGISTRY, Context


def call(vault, tool_name, /, session=None, caller_kind=None, **args):
    extras = {"caller_kind": caller_kind} if caller_kind else {}
    return REGISTRY.call(tool_name, args, Context(tier="contribute", vault=vault,
                                                  session=session, extras=extras))


@pytest.fixture
def core(vault):
    app = App(vault, coordinate=True)
    app.broker.set_mode("auto")
    yield app
    app.close_runtime()


def core_call(core, tool_name, /, **args):
    ctx = Context(tier="contribute", vault=core.vault, extras=core._extras())
    return REGISTRY.call(tool_name, args, ctx)


def _ops(vault):
    path = vault.librarian / "runtime" / "operations.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_a_read_hands_out_a_revision_and_each_write_the_next(vault):
    written = call(vault, "write_note", folder="Notes", name="Plan", body="# Plan\n\n## Monday\nRead.\n")
    read = call(vault, "get_note", name="Plan")
    assert read["revision"].startswith("rev1.") and written["revision"].startswith("rev1.")
    first = call(vault, "edit_note", note="Plan", section="Monday", text="Practise.",
                 revision=read["revision"])
    second = call(vault, "edit_note", note="Plan", section="Tuesday", text="Rest.",
                  revision=first["revision"])            # chained, no re-read needed
    assert "error" not in second, second
    assert first["revision"] != second["revision"]


def test_a_replace_needs_a_revision_and_a_new_note_needs_none(vault):
    assert "error" not in call(vault, "write_note", folder="Notes", name="Plan", body="b")
    refused = call(vault, "edit_note", note="Plan", section="Monday", text="x")
    assert refused["refused"] == "REVISION_REQUIRED" and "get_note" in refused["detail"]
    assert call(vault, "write_note", folder="Notes", name="Plan", body="c",
                mode="replace")["refused"] == "REVISION_REQUIRED"
    # A new note is token-free, and a stray revision does not make it need one.
    stray = call(vault, "get_note", name="Plan")["revision"]
    assert "error" not in call(vault, "write_note", folder="Notes", name="Other", body="d",
                               revision=stray)


def test_a_persons_own_edit_needs_no_revision(vault):
    call(vault, "write_note", folder="Notes", name="Plan", body="b")
    out = call(vault, "edit_note", caller_kind="person", note="Plan", section="Mine", text="x")
    assert "error" not in out, out


def test_an_external_edit_between_read_and_write_becomes_a_conflict_checkpoint(core, vault):
    # This is the revision/CAS fixture. The independent watcher fixtures cover
    # its editor quiet window; leaving that poller active makes the second
    # fresh-revision write race whether it observed the external edit yet.
    # Stop it here to exercise the documented no-plugin revision path only.
    assert core.watcher is not None
    core.watcher.close()
    core_call(core, "write_note", folder="Notes", name="Plan", body="# Plan\n\nFirst.\n")
    read = core_call(core, "get_note", name="Plan")
    path = vault.root / "Notes" / "Plan.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nA person's addition.\n",
                    encoding="utf-8")                   # outside the Core, after the read
    refused = core_call(core, "edit_note", note="Plan", section="More", text="agent's",
                        revision=read["revision"])
    assert refused["refused"] == "DOCUMENT_ACTIVE" and "changed after it was read" in refused["detail"]
    assert refused["checkpoint"]["type"] == "write_conflict"
    assert "A person's addition." in path.read_text(encoding="utf-8")
    assert "agent's" not in path.read_text(encoding="utf-8")
    failed = [op for op in _ops(vault) if op["status"] == "failed"][-1]
    assert failed["targets"] == ["Notes/Plan.md"]
    assert failed["precondition_fingerprints"]["Notes/Plan.md"] != \
        failed["observed_fingerprints"]["Notes/Plan.md"]
    # Read again, and the same change goes through.
    again = core_call(core, "get_note", name="Plan")
    assert "error" not in core_call(core, "edit_note", note="Plan", section="More",
                                    text="agent's", revision=again["revision"])


def test_offline_the_same_check_runs_without_a_writer(vault):
    call(vault, "write_note", folder="Notes", name="Plan", body="b")
    read = call(vault, "get_note", name="Plan")
    path = vault.root / "Notes" / "Plan.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nEdited.\n", encoding="utf-8")
    refused = call(vault, "edit_note", note="Plan", section="S", text="x", revision=read["revision"])
    assert refused["refused"] == "DOCUMENT_ACTIVE"
    assert "Edited." in path.read_text(encoding="utf-8")


def test_a_revision_read_from_a_source_authorises_no_other_note(vault):
    add_source(vault.root, "osquery", "Exposes the OS as SQL tables.")
    call(vault, "write_note", folder="Notes", name="Plan", body="b")
    source_revision = call(vault, "get_note", name="osquery")["revision"]
    refused = call(vault, "edit_note", note="Plan", section="S", text="x", revision=source_revision)
    assert refused["refused"] == "REVISION_REFUSED" and "Sources/" in refused["detail"]


def test_a_revision_is_bound_to_its_session_caller_and_core(core):
    # MCP is never a standalone registry surface. Test token caller binding
    # against the same coordinated Core, not an offline MCP-shaped Context.
    def bound_call(tool_name, *, session=None, caller_kind="agent", **args):
        ctx = Context(tier="contribute", vault=core.vault, session=session,
                      extras={**core._extras(), "caller_kind": caller_kind})
        return REGISTRY.call(tool_name, args, ctx)

    bound_call("write_note", folder="Notes", name="Plan", body="b")
    other = bound_call("open_session", purpose="explore", question="q")["opened"]
    theirs = bound_call("get_note", session=other, name="Plan")["revision"]
    assert bound_call("edit_note", note="Plan", section="S", text="x",
                revision=theirs)["refused"] == "REVISION_REFUSED"
    mcp = bound_call("get_note", caller_kind="mcp", name="Plan")["revision"]
    assert bound_call("edit_note", note="Plan", section="S", text="x",
                revision=mcp)["refused"] == "REVISION_REFUSED"
    mine = bound_call("get_note", name="Plan")["revision"]
    body, signature = mine.rsplit(".", 1)
    forged = body[:-2] + ("A" if body[-2] != "A" else "B") + body[-1] + "." + signature
    assert bound_call("edit_note", note="Plan", section="S", text="x",
                revision=forged)["refused"] == "REVISION_REFUSED"
    assert bound_call("edit_note", note="Plan", section="S", text="x",
                revision="0123456789abcdef0123")["refused"] == "REVISION_REFUSED"  # a raw fingerprint
    revisions._KEYS.clear()                              # as after a Core restart
    assert bound_call("edit_note", note="Plan", section="S", text="x",
                revision=mine)["refused"] == "REVISION_REFUSED"


def test_an_unresolvable_note_is_refused_before_anything_is_written(vault):
    call(vault, "write_note", folder="Notes", name="Plan", body="b")
    out = call(vault, "edit_note", note="No Such Note", section="S", text="x")
    assert out["error"] == "invalid_arguments" and "no single note" in out["detail"]


def test_moves_and_promotions_declare_their_targets(core, vault):
    core_call(core, "write_note", folder="Notes", name="Old Plan", body="b")
    assert "error" not in core_call(core, "archive_note", note="Old Plan", reason="superseded")
    archived = [op for op in _ops(vault) if op["status"] == "done"][-1]
    assert archived["targets"] == ["Notes/Old Plan.md", "Archive/Notes/Old Plan.md"]


def test_a_promotion_declares_where_it_writes(tmp_path):
    from walks import add_project_walk, library
    lib = library(tmp_path / "lib")
    app = App(lib, coordinate=True)
    app.broker.set_mode("auto")
    try:
        extras = {k: v for k, v in app._extras().items() if k != "waiters"}
        ctx = Context(tier="contribute", vault=lib, extras=extras)
        add_project_walk(lib, lambda _tool, **a: REGISTRY.call(_tool, a, ctx))
    finally:
        app.close_runtime()
    promoted = [op for op in _ops(lib)
                if op["status"] == "done" and any(t.startswith("Offerings/") for t in op["targets"])]
    # The first call asks the person to confirm, the second promotes: both declared.
    assert promoted, "no promotion declared its destination"
    target = promoted[-1]["targets"][0]
    assert target.startswith("Offerings/Host Watch/") and (lib.root / target).is_file()


def test_a_note_made_by_another_write_after_resolution_is_not_replaced_unread(vault):
    """Delegate review (DeepSeek-V4-Pro): replace on a missing note needed no
    revision, so a note another write made in between was replaced unread."""
    from resource_librarian.tools import authoring
    ctx = Context(tier="contribute", vault=vault)
    intent = revisions.canonical_intent(vault, authoring._write_note_intent(
        ctx, {"folder": "Notes", "name": "Race", "mode": "replace"}))
    assert intent.absent == ("Notes/Race.md",) and not intent.replaces
    expected = revisions.preconditions(ctx, intent, "")
    (vault.root / "Notes").mkdir(exist_ok=True)
    (vault.root / "Notes" / "Race.md").write_text("made in between\n", encoding="utf-8")
    from resource_librarian.coordination import PreconditionChangedError
    with pytest.raises(PreconditionChangedError):
        revisions.check_now(ctx, expected)
