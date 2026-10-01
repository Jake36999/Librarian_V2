"""Requirements Addendum R1 (2026-09-30): the librarian writes its own notes - in Notes/ and
Projects/<p>/ only, never over a person's edits, always with the path - and can look at a
page or file before keeping it."""
from resource_librarian import intake, notes, tools  # noqa: F401  (registers tools)
from resource_librarian.broker import Broker
from resource_librarian.registry import REGISTRY, Context

from conftest import add_source, write_note


def call(vault, tool_name, /, tier="contribute", **args):
    return REGISTRY.call(tool_name, args, Context(tier=tier, vault=vault))


def a_project(vault, name="Uni"):
    return call(vault, "create_project", name=name, stage="planning", summary="A course.",
                pursuit_kind="course")


def test_a_note_is_written_indexed_and_findable_and_its_path_returned(vault):
    out = call(vault, "write_note", folder="Notes", name="Agile Study Plan",
               body="Day 1: read the Scrum Guide.")
    assert out["written"] == "Notes/Agile Study Plan.md" and out["created"] and out["findable"]
    note = notes.load(vault.root / out["written"])
    assert note.frontmatter["type"] == "note" and note.frontmatter["written_by"] == "librarian"
    found = call(vault, "search", query="Agile Study Plan", intent="orient")
    assert "error" not in found


def test_only_notes_and_project_folders_are_writable(vault):
    for folder in ("Sources", "Concepts/x", "Offerings", "About", ".librarian", "../outside",
                   "Projects/No Such Project"):
        out = call(vault, "write_note", folder=folder, name="x", body="y")
        assert out["error"] == "invalid_arguments", folder
    a_project(vault)
    assert call(vault, "write_note", folder="Projects/Uni", name="Week 1", body="b")["written"] \
        == "Projects/Uni/Week 1.md"


def test_an_existing_note_is_not_overwritten_without_replace(vault):
    call(vault, "write_note", folder="Notes", name="Plan", body="first")
    again = call(vault, "write_note", folder="Notes", name="Plan", body="second")
    assert again["error"] == "invalid_arguments" and "mode='replace'" in again["detail"]
    replaced = call(vault, "write_note", folder="Notes", name="Plan", body="second",
                    mode="replace")
    assert not replaced["created"] and "+second" in replaced["diff"].replace(" ", "")


def test_a_note_a_person_edited_is_never_replaced(vault):
    out = call(vault, "write_note", folder="Notes", name="Plan", body="first")
    path = vault.root / out["written"]
    path.write_text(path.read_text(encoding="utf-8") + "\nMy own addition.\n", encoding="utf-8")
    refused = call(vault, "write_note", folder="Notes", name="Plan", body="new", mode="replace")
    assert refused["refused"] == "PERSON_CONFIRMS"
    assert "My own addition." in path.read_text(encoding="utf-8")


def test_a_name_used_elsewhere_in_the_vault_is_refused(vault):
    add_source(vault.root, "osquery", "Exposes the OS as SQL tables.")
    out = call(vault, "write_note", folder="Notes", name="osquery", body="x")
    assert out["error"] == "invalid_arguments" and "Sources/" in out["detail"]


def test_reserved_and_empty_names_are_refused(vault):
    for name in ("CON", "nul.md", "///"):
        assert call(vault, "write_note", folder="Notes", name=name, body="x")["error"] \
            == "invalid_arguments", name


def test_writes_wait_for_the_broker_in_the_core(vault):
    broker = Broker(mode="plan")                          # plan mode never writes
    out = REGISTRY.call("write_note", {"folder": "Notes", "name": "P", "body": "b"},
                        Context(tier="contribute", vault=vault, extras={"broker": broker}))
    assert out["refused"] == "PERMISSION_DENIED"
    assert not (vault.root / "Notes" / "P.md").exists()


def test_edit_appends_or_replaces_a_section_and_sets_fields(vault):
    call(vault, "write_note", folder="Notes", name="Plan", body="# Plan\n\n## Monday\nRead.\n")
    out = call(vault, "edit_note", note="[[Plan]]", section="Monday", text="Then practise.")
    assert "+Then practise." in out["diff"]
    call(vault, "edit_note", note="Plan", section="Tuesday", text="Stand-up.", mode="replace",
         fields={"aliases": ["Study plan"]})
    note = notes.load(vault.root / "Notes" / "Plan.md")
    assert "Stand-up." in note.body and note.frontmatter["aliases"] == ["Study plan"]
    # still the librarian's own, unedited by a person: replace is still allowed
    assert "written" in call(vault, "write_note", folder="Notes", name="Plan", body="x",
                             mode="replace")


def test_edit_refuses_typed_library_notes_and_protected_fields(vault):
    add_source(vault.root, "osquery", "Exposes the OS as SQL tables.")
    assert call(vault, "edit_note", note="osquery", section="Bottom Line",
                text="x")["error"] == "invalid_arguments"
    call(vault, "write_note", folder="Notes", name="Plan", body="b")
    assert call(vault, "edit_note", note="Plan", fields={"written_by": "person"})["error"] \
        == "invalid_arguments"


def test_update_project_changes_stage_goal_and_disqualifiers(vault):
    a_project(vault)
    out = call(vault, "update_project", name="Uni", stage="Active", goal="Pass year one.",
               disqualifiers=["paywalled"])
    note = notes.load(vault.root / "Projects" / "Uni.md")
    assert note.frontmatter["stage"] == "active" and note.frontmatter["disqualifiers"] == \
        ["paywalled"]
    assert "Pass year one." in note.sections()["Goal"] and out["diff"]
    assert call(vault, "update_project", name="Nope", stage="active")["error"] == \
        "invalid_arguments"


def test_archive_moves_a_note_and_keeps_it(vault):
    call(vault, "write_note", folder="Notes", name="Old Plan", body="b")
    out = call(vault, "archive_note", note="Old Plan", reason="superseded")
    assert out["archived"] == "Archive/Notes/Old Plan.md"
    assert not (vault.root / "Notes" / "Old Plan.md").exists()
    assert notes.load(vault.root / out["archived"]).frontmatter["archived_reason"] == "superseded"
    add_source(vault.root, "osquery", "Exposes the OS as SQL tables.")
    assert call(vault, "archive_note", note="osquery", reason="r")["error"] == \
        "invalid_arguments"                               # the person archives sources
    assert "archived" in call(vault, "archive_note", tier="curate", note="osquery", reason="r")


def test_read_url_reads_without_keeping(vault):
    page = ("<html><head><title>Scrum Guide</title></head><body><p>Scrum is a lightweight "
            "framework.</p></body></html>")
    out = REGISTRY.call("read_url", {"url": "https://scrumguides.org/"},
                        Context(tier="consult", vault=vault, extras={
                            "fetcher": intake.Replay({"https://scrumguides.org/": page})}))
    assert out["title"] == "Scrum Guide" and "lightweight framework" in out["text"]
    assert not (vault.librarian / "evidence").exists() or not list(
        (vault.librarian / "evidence").rglob("*.json"))
    assert call(vault, "read_url", url="Inbox/x.docx")["error"] == "invalid_arguments"


def test_read_file_and_list_files_stay_inside_the_vault(vault):
    (vault.root / "Inbox").mkdir(exist_ok=True)
    (vault.root / "Inbox" / "lab.txt").write_text("Lab 1: install Thunkable.", encoding="utf-8")
    listed = call(vault, "list_files", folder="Inbox")
    assert {"name": "lab.txt", "kind": "file", "bytes": 25} in listed["entries"]
    got = call(vault, "read_file", path="Inbox/lab.txt")
    assert got["text"] == "Lab 1: install Thunkable." and got["pages"] == 1
    for bad in ("../secret.txt", ".librarian/config.toml"):
        assert call(vault, "read_file", path=bad)["error"] == "invalid_arguments", bad


def test_check_notes_reports_broken_links_and_orphaned_sources(vault):
    add_source(vault.root, "osquery", "Exposes the OS as SQL tables.")
    write_note(vault.root, "Notes/Plan.md", "type: note", "See [[No Such Note]] and [[osquery]].\n")
    out = call(vault, "check_notes", tier="consult", limit=200)
    checks = {(v["check"], v["note"]) for v in out["violations"]}
    assert ("wikilinks_resolve", "Plan") in checks
    assert ("orphan_notes", "osquery") not in checks     # Plan links to it


def test_run_list_is_empty_before_any_run(vault):
    assert call(vault, "run_list", tier="consult") == {"runs": []}


def test_a_write_inside_a_session_is_listed_with_its_path_in_any_phase(vault):
    ctx = Context(tier="contribute", vault=vault)
    REGISTRY.call("open_session", {"purpose": "explore", "question": "agile"}, ctx)
    out = REGISTRY.call("write_note", {"folder": "Notes", "name": "Agile Plan", "body": "b"}, ctx)
    assert out["path"] == "Notes/Agile Plan.md", out                # the chat links `path`
    status = REGISTRY.call("session_status", {}, ctx)
    assert status["phase"] == "frame"
    assert {"tool": "write_note", "path": "Notes/Agile Plan.md"}.items() <= \
        [w for w in status["writes"] if w["tool"] == "write_note"][0].items()
