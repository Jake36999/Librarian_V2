from resource_librarian import notes, schema
from resource_librarian.schema import ContentModel

from conftest import write_note

GOOD_REPO = """
type: source
kind: repository
title: Example
canonical_url: https://example.org
status: active
primary_topic: Unfiled
captured_at: 2026-09-25
repo_key: example/example
license_class: Permissive
ecosystem: Python
maturity_stage: Active
deployment_target: Local_Only
interface_protocol: Python_SDK
data_locality: Local_First
hardware_footprint: CPU_Only
security_compliance: Uncertified
agent_surface: Callable
"""
GOOD_BODY = notes.compose("Example", [("Bottom Line", "b"), ("What It Solves", "w"),
                                      ("Evidence", "- e")])


def test_starter_model_parses(vault):
    model = schema.load(vault.root)
    assert model.found and not model.error
    assert set(model.shapes) == {"source", "concept", "project", "offering", "application",
                                 "note"}                          # P5: findable by `made`
    assert "repository" in model.kinds and "model" in model.kinds


def test_kind_adds_fields_and_replaces_sections(vault):
    model = schema.load(vault.root)
    fields = model.fields_for("source", "repository")
    assert fields["title"] == "required" and fields["repo_key"] == "required"
    paper_sections = [s for s, _ in model.sections_for("source", "paper")]
    assert "Claim" in paper_sections and "What It Solves" not in paper_sections


def test_note_checks(vault):
    model = schema.load(vault.root)
    ok = write_note(vault.root, "Sources/repository/Example.md", GOOD_REPO, GOOD_BODY)
    assert model.check(notes.load(ok), vault.root) == []

    bad = write_note(vault.root, "Sources/repository/Bad.md",
                     GOOD_REPO.replace("title: Example\n", ""),
                     notes.compose("Bad", [("Bottom Line", "b")]))
    checks = {v.check for v in model.check(notes.load(bad), vault.root)}
    assert {"required_fields", "required_sections"} <= checks


def test_unknown_kind_and_parse_error(vault):
    model = schema.load(vault.root)
    odd = write_note(vault.root, "Sources/Odd.md", "type: source\nkind: podcast", "x")
    assert "kind_known" in {v.check for v in model.check(notes.load(odd), vault.root)}
    broken = vault.root / "Sources" / "Broken.md"
    broken.write_text("---\na: [\n---\n")
    assert model.check(notes.load(broken), vault.root)[0].check == "frontmatter_parses"


def test_shape_from_folder_when_type_missing(vault):
    model = schema.load(vault.root)
    note = notes.load(write_note(vault.root, "Concepts/Term.md", "status: active", "x"))
    assert model.shape_of(note, vault.root) == "concept"


def test_missing_model_means_no_checks(tmp_path):
    model = schema.load(tmp_path)
    assert not model.found
    note = notes.load(write_note(tmp_path, "Sources/A.md", "type: source", ""))
    assert model.check(note) == []


def test_model_without_shapes_is_an_error():
    model = schema.parse("# Empty\n\n## Other\n\n| a | b |\n| - | - |\n| 1 | 2 |\n")
    assert model.error and isinstance(model, ContentModel)
    assert model.check(notes.Note("x", None)) == []


def test_axis_values_enforced(vault):
    model = schema.load(vault.root)
    path = write_note(vault.root, "Sources/repository/Axis.md",
                      GOOD_REPO.replace("ecosystem: Python", "ecosystem: [Python, Cobol]"),
                      GOOD_BODY)
    violations = model.check(notes.load(path), vault.root)
    assert [v.check for v in violations] == ["axis_values"] and "Cobol" in violations[0].detail


def test_open_axis_refuses_values_until_one_is_accepted(vault):
    model = schema.load(vault.root)
    assert model.axes_for("source", "repository")["domain_primary"] == []
    path = write_note(vault.root, "Sources/repository/Open.md",
                      GOOD_REPO + "domain_primary: Robotics", GOOD_BODY)
    violations = model.check(notes.load(path), vault.root)
    assert [v.check for v in violations] == ["axis_values"]
    assert "no accepted values yet" in violations[0].detail
    no_value = write_note(vault.root, "Sources/repository/Empty.md", GOOD_REPO, GOOD_BODY)
    assert model.check(notes.load(no_value), vault.root) == []        # optional


def test_starter_ecosystem_is_languages_only(vault):
    values = schema.load(vault.root).axes_for("source", "repository")["ecosystem"]
    assert "Python" in values and "Ruby" in values
    assert not {"Security_Analytics", "Geo_Data", "Observability", "Web_CSS"} & set(values)
