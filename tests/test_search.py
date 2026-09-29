import pytest

from resource_librarian.index import Index
from resource_librarian.search import (ConstraintError, Engine, _name_qualifies, search,
                                       terms_from)

from conftest import add_source, write_note


@pytest.fixture
def engine(vault):
    add_source(vault.root, "osquery", "Exposes the operating system as a relational database "
               "you query with SQL.", "Query operating system state such as processes.")
    add_source(vault.root, "duckdb", "An in-process analytical SQL database.",
               "Analytical queries on a laptop.", license="Permissive")
    add_source(vault.root, "gudu", "A commercial SQL lineage service.",
               reading="Often described as a database for operating system state; it is not.",
               license="Source_Available")
    add_source(vault.root, "airflow", "Schedules dependent jobs nightly and recovers from "
               "partial failure.", topic="Orchestration")
    for i in range(6):
        add_source(vault.root, f"filler {i}", f"Unrelated tool number {i} for pictures.")
    write_note(vault.root, "Concepts/Change Data Capture.md",
               "type: concept\nconcept_kind: pattern\nstatus: active",
               "# Change Data Capture\n\n## Definition\nStreaming row changes out of a database.\n")
    write_note(vault.root, "Applications/Application - Nightly.md",
               "type: application\nproject: P\nstage: done\noutcome: worked\nsources_used: []",
               "## What Was Needed\nnightly dependent jobs\n")
    index = Index(vault)
    index.refresh()
    yield Engine(index, {**vault.config()["heuristics"], "data_shaped": ["kind=dataset"]})
    index.close()


def test_terms():
    assert terms_from('what "change data capture" does the SQL need') == \
        ["change data capture", "SQL"]


def test_finds_and_explains(engine):
    r = search(engine, "query operating system state as a database")
    assert r.results[0].name == "osquery"
    assert "matched" in r.results[0].why and "`" in r.results[0].why
    assert r.results[0].rank == 1.0 and r.verdict in ("covered", "thin")


def test_caveat_earns_no_coverage(engine):
    r = search(engine, "database for operating system state")
    names = [x.name for x in r.results]
    assert names.index("osquery") < names.index("gudu")
    gudu = next(x for x in r.results if x.name == "gudu")
    assert gudu.fields["matched_role"] == "caveat" and "caveat" in gudu.why


def test_constraints_eliminate_and_say_so(engine):
    r = search(engine, "SQL lineage", constraints={"license_class": "Permissive"})
    assert "gudu" not in [x.name for x in r.results] and r.filtered_out >= 1
    assert any("removed by your constraints" in a for a in r.advisories)
    assert all("passes license_class=Permissive" in x.why for x in r.results)


def test_bad_constraints_are_refused(engine):
    with pytest.raises(ConstraintError, match="Permitted"):
        search(engine, "x", constraints={"license_class": "permissive"})
    with pytest.raises(ConstraintError, match="not a filterable axis"):
        search(engine, "x", constraints={"colour": "red"})


def test_filters_only_listing(engine):
    r = search(engine, "zzzz", constraints={"topic": "Orchestration"})
    assert [x.name for x in r.results] == ["airflow"] and r.tier_reached == 2


def test_uncovered_is_said(engine):
    r = search(engine, "soufflé rising evenly in an oven")
    assert r.verdict == "uncovered"
    assert r.advisories[-1].startswith("nothing here covers this")


def test_intents(engine):
    assert search(engine, "streaming row changes", "pattern").results[0].name == \
        "Change Data Capture"
    assert search(engine, "nightly dependent jobs", "precedent").results[0].name == \
        "Application - Nightly"
    tech = search(engine, "processes", "technique", source="osquery")
    assert tech.results and all(x.fields["note"] == "osquery" for x in tech.results)
    data = search(engine, "anything", "data")
    assert data.results == [] and any("data_shaped" in a for a in data.advisories)
    orient = search(engine, "nightly jobs", "orient")
    assert any(x.kind == "topic" and x.name == "Orchestration" for x in orient.results)
    assert search(engine, "x", "in_text").advisories == \
        ["no document text is indexed in this vault yet"]


def test_facets_only_vary(engine):
    r = search(engine, "SQL database")
    assert "license_class" in r.facets and "ecosystem" not in r.facets


def test_name_qualification():
    assert not _name_qualifies(("run",), ["run", "twelve", "dependent", "jobs"],
                               "run-llama - llama_index")
    assert _name_qualifies(("plumbing",), ["plumbing", "scheduler", "queue"], "Plumbing")
    assert _name_qualifies(("airflow",), ["airflow"], "apache - airflow")


def test_coverage_orders_measured_alternatives(engine):
    engine.h["coverage_order"] = "bm25"
    assert search(engine, "query operating system state").results[0].name == "osquery"
