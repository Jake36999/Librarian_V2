"""Search Methods SM-2, SM-3, SM-4; plan P5.3: the grains beneath a source.

- Where inside a repository a query matched: at most three addresses per surviving source,
  whole-segment, a segment most repositories share skipped, bound to the tree it was read at.
- A dataset's access points, with when each was last checked - apart from rank.
- A pattern's examples and neighbours, as relations to follow."""
from resource_librarian import intake, tools  # noqa: F401  (registers tools)
from resource_librarian.evidence import EvidenceStore
from resource_librarian.registry import REGISTRY, Context

from conftest import add_source, write_note

PLANNER = ["src/planner/join_order.py", "src/planner/cost_model.py", "src/planner/join_graph.py",
           "src/planner/join_hints.py", "src/utils/log.py", "tests/test_join_order.py"]


def call(vault, tool_name, /, **args):
    fetcher = args.pop("fetcher", None)
    return REGISTRY.call(tool_name, args, Context(tier="contribute", vault=vault,
                                                  extras={"fetcher": fetcher} if fetcher else {}))


def repo(vault, name, bottom, paths, license="Permissive", tree="t1"):
    record = EvidenceStore(vault).put("survey", f"https://github.com/example/{name}",
                                      {"paths": paths, "tree_sha": tree})
    add_source(vault.root, name, bottom, license=license,
               extra_fm=f"evidence:\n- {record.id}")


def library(vault):
    repo(vault, "joinplan", "A query planner that picks the join order.", PLANNER, tree="abc123")
    repo(vault, "copyplan", "Another query planner choosing join order.",
         ["src/planner/join_order.rs"], license="Copyleft")
    for i in range(3):
        repo(vault, f"other{i}", f"A tool number {i}.", ["src/main.py", "src/join.py"])


def test_a_repository_result_says_where_inside_it_the_query_matched(vault):
    library(vault)
    out = call(vault, "search", query="join order planner", intent="donor")
    fields = {r["name"]: r["fields"] for r in out["results"]}
    hits = fields["joinplan"]["components"]
    assert len(hits) == 3                                   # capped under its parent
    assert hits[0]["address"] == "src/planner/join_order.py"
    assert hits[0]["matched"] == ["order", "planner"]       # `join`: in all five, says nothing
    assert hits[0]["revision"] == "abc123"


def test_components_only_under_sources_that_survived_the_constraints(vault):
    library(vault)
    out = call(vault, "search", query="join order planner", intent="donor",
               constraints={"license_class": ["Permissive"]})
    assert "copyplan" not in {r["name"] for r in out["results"]}
    assert all("copyplan" not in str(r["fields"].get("components", ""))
               for r in out["results"])


def dataset(vault):
    write_note(vault.root, "Sources/dataset/Rows Benchmark.md",
               "type: source\nkind: dataset\ntitle: Rows Benchmark\ncanonical_url: "
               "https://zenodo.org/records/7\nstatus: active\nprimary_topic: Unfiled\n"
               "captured_at: 2026-09-30\naccess_points:\n- https://zenodo.org/records/7/rows.csv\n"
               "- https://zenodo.org/api/records/7",
               "# Rows Benchmark\n\n## Bottom Line\nRow-change traces from ten databases.\n\n"
               "## What It Solves\nBenchmarking change capture.\n")


def test_a_datasets_access_points_show_when_they_were_checked_apart_from_rank(vault):
    dataset(vault)
    first = call(vault, "search", query="row change traces", intent="data")["results"][0]
    assert first["name"] == "Rows Benchmark"
    assert [p["checked_at"] for p in first["fields"]["access_points"]] == ["never", "never"]
    checked = call(vault, "verify_access", source="Rows Benchmark",
                   fetcher=intake.Replay({"https://zenodo.org/records/7/rows.csv": "a,b\n1,2"}))
    assert [c["reachable"] for c in checked["checked"]] == [True, False]
    again = call(vault, "search", query="row change traces", intent="data")["results"][0]
    points = {p["url"]: p for p in again["fields"]["access_points"]}
    assert points["https://zenodo.org/records/7/rows.csv"]["reachable"] is True
    assert points["https://zenodo.org/api/records/7"]["reachable"] is False
    assert all(p["checked_at"] != "never" for p in points.values())
    assert again["rank"] == first["rank"]                   # checking never moves rank


def test_a_pattern_shows_its_examples_and_neighbours(vault):
    for name in ("Change Data Capture", "Event Sourcing", "Write-Ahead Log"):
        write_note(vault.root, f"Concepts/{name}.md", "type: concept\nconcept_kind: pattern\n"
                   "status: active", f"## Definition\n{name} as a pattern.\n")
    add_source(vault.root, "rowstream", "Streams row changes out of a database.",
               extra_fm="concepts:\n- '[[Change Data Capture]]'\n- '[[Write-Ahead Log]]'")
    add_source(vault.root, "tailer", "Tails a database log.",
               extra_fm="concepts:\n- '[[Change Data Capture]]'\n- '[[Event Sourcing]]'\n"
                        "- '[[Write-Ahead Log]]'")
    out = call(vault, "search", query="change data capture", intent="pattern")
    top = out["results"][0]
    assert top["name"] == "Change Data Capture"
    assert top["fields"]["examples"] == ["rowstream", "tailer"]
    assert top["fields"]["neighbours"] == ["Write-Ahead Log", "Event Sourcing"]
