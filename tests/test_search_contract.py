"""Requirements Addendum R15 (2026-09-30), plan P5.1: the agent search contract.

Each source result says how much of it was read; what the filters removed is a list, not
only a sentence; everything the library holds is findable - including what it made (the
guide that search could not find in P4); `all` answers each intent in its own shape and says
which ran; `max_age_days` filters on the source's own date; feedback is logged, never used
to rank."""
import json

from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context

from conftest import add_source, write_note


def call(vault, tool_name, /, **args):
    return REGISTRY.call(tool_name, args, Context(tier="contribute", vault=vault))


def library(vault):
    add_source(vault.root, "osquery", "Exposes the operating system as SQL tables.",
               extra_fm="coverage: partial 3/9\nnot_examined:\n- 'read: 6 of 9 parts not read'\n"
                        "pushed_at: '2026-09-01T00:00:00Z'")
    add_source(vault.root, "sysql", "Exposes the operating system as SQL tables too.",
               license="Copyleft", extra_fm="pushed_at: '2019-03-01T00:00:00Z'")
    add_source(vault.root, "painter", "Draws pictures of cats.")
    return vault


def test_each_source_says_how_much_of_it_was_read(vault):
    library(vault)
    rows = {r["name"]: r["fields"] for r in
            call(vault, "search", query="operating system SQL tables")["results"]}
    assert rows["osquery"]["read_depth"] == "partial 3/9"
    assert rows["osquery"]["not_examined"] == ["read: 6 of 9 parts not read"]
    assert rows["sysql"]["read_depth"] == "not recorded"          # catalogued before P3


def test_what_the_filters_removed_is_a_list(vault):
    library(vault)
    out = call(vault, "search", query="operating system SQL tables",
               constraints={"license_class": ["Permissive"]})
    assert "sysql" in out["removed_by_filters"]
    assert "sysql" not in [r["name"] for r in out["results"]]


def test_what_the_library_made_is_findable(vault):
    library(vault)
    write_note(vault.root, "Offerings/Uni/Agile Resource Guide.md",
               "type: offering\noffering_kind: insight_report\nstatus: active",
               "# Agile Resource Guide\n\n## Summary\nScrum and Kanban for a first year.\n")
    call(vault, "write_note", folder="Notes", name="Agile Study Plan", body="Day 1: Scrum.")
    made = call(vault, "search", query="agile", intent="made")
    kinds = {r["name"]: r["kind"] for r in made["results"]}
    assert kinds == {"Agile Resource Guide": "offering", "Agile Study Plan": "note"}
    assert "Agile Resource Guide" not in [
        r["name"] for r in call(vault, "search", query="agile", intent="orient")["results"]]


def test_all_answers_each_intent_in_its_own_shape_and_says_which_ran(vault):
    library(vault)
    write_note(vault.root, "Concepts/Host Instrumentation.md",
               "type: concept\nconcept_kind: term\nstatus: active",
               "## Definition\nThe operating system exposed as queryable tables.\n")
    call(vault, "write_note", folder="Notes", name="Operating system notes", body="x")
    out = call(vault, "search", query="operating system tables", intent="all")
    assert out["ran"] == ["orient", "pattern", "made"]
    by = {}
    for r in out["results"]:
        by.setdefault(r["fields"]["intent"], []).append(r["kind"])
    assert "source" in by["orient"] and by["pattern"] == ["concept"] and by["made"] == ["note"]


def test_max_age_days_filters_on_the_sources_own_date(vault):
    library(vault)
    out = call(vault, "search", query="operating system SQL tables", max_age_days=1000)
    names = [r["name"] for r in out["results"]]
    assert "osquery" in names and "sysql" not in names
    assert "sysql" in out["removed_by_filters"]
    assert any("dated within 1000 days" in a for a in out["advisories"])


def test_feedback_is_logged_and_never_ranks(vault):
    library(vault)
    before = call(vault, "search", query="operating system SQL tables")["results"]
    for _ in range(5):
        call(vault, "search_feedback", query="operating system SQL tables", note="sysql",
             verdict="taken", intent="donor", rank=2)
    after = call(vault, "search", query="operating system SQL tables")["results"]
    assert [r["name"] for r in after] == [r["name"] for r in before]
    lines = (vault.librarian / "eval" / "feedback.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5 and json.loads(lines[0])["verdict"] == "taken"
