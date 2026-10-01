"""Requirements Addendum R8 (2026-09-30): topics are proposed from what the library holds,
and only a person grows the list. A proposed member must be a real source; a decided
topic is never restaged; refiling and the generated views use accepted topics only."""
from resource_librarian import clerk, notes, tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context

from test_sessions import library  # noqa: F401  (fixture: osquery, duckdb, falco, painter)

HOST = {"name": "Host Monitoring", "what_belongs": "watching what a machine does",
        "members": ["osquery", "Falco", "made-up-tool"], "aliases": ["host observability"]}


def ctx(vault, topics, tier="contribute"):
    def answers(payload):
        assert payload["task"] == "topics"
        return {"topics": topics}
    return Context(tier=tier, vault=vault, extras={"clerk": clerk.Scripted(answers)})


def call(c, name, **args):
    return REGISTRY.call(name, args, c)


def test_proposals_are_staged_with_real_members_only(library):
    lone = {"name": "Drawing", "what_belongs": "pictures", "members": ["painter"]}
    out = call(ctx(library, [HOST, lone]), "topic_propose")
    assert [p["name"] for p in out["proposed"]] == ["Host Monitoring"]      # lone: one member
    assert out["dropped_members"] == 1 and out["considered"] == 4
    row = call(ctx(library, []), "staging_list", kind="topic")["items"][0]
    assert row["examples"] == ["osquery", "falco"] and row["coverage"] == {"sources": 2, "of": 4}
    assert row["aliases"] == ["host observability"]
    assert library.topics() == ["Unfiled"]                     # proposing writes nothing


def test_only_a_person_accepts_a_topic(library):
    call(ctx(library, [HOST]), "topic_propose")
    out = call(ctx(library, []), "staging_decide", item_ids=["topic-host-monitoring"],
               decision="accept")
    assert out["results"][0]["refused"] == "PERSON_CONFIRMS"
    assert library.topics() == ["Unfiled"]


def test_accepting_writes_the_row_and_files_its_members(library):
    call(ctx(library, [HOST]), "topic_propose")
    out = call(ctx(library, [], tier="curate"), "staging_decide",
               item_ids=["topic-host-monitoring"], decision="accept",
               fields={"name": "Host Telemetry"})
    assert out["results"][0]["topic"] == "Host Telemetry"
    assert library.topics() == ["Unfiled", "Host Telemetry"]
    assert "(also: host observability)" in (library.root / "About" / "Topics.md").read_text(
        encoding="utf-8")
    for name in ("osquery", "falco"):
        note = notes.load(library.root / "Sources" / "repository" / f"{name}.md")
        assert note.frontmatter["primary_topic"] == "Host Telemetry"
    index = (library.root / "Indexes" / "Topic - Host Telemetry.md").read_text(encoding="utf-8")
    assert "[[osquery]]" in index and "[[falco]]" in index
    assert "Host Telemetry" in (library.root / "Indexes" / "Master Index.md").read_text(
        encoding="utf-8")


def test_a_decided_topic_is_never_restaged_and_its_name_becomes_a_refile(library):
    call(ctx(library, [HOST]), "topic_propose")
    person = ctx(library, [], tier="curate")
    call(person, "staging_decide", item_ids=["topic-host-monitoring"], decision="accept",
         fields={"refile": False})
    again = call(ctx(library, [{**HOST, "name": "host monitoring",
                                "members": ["osquery", "duckdb"]}]),
                 "topic_propose", only_unfiled=False)
    assert again["proposed"] == []
    assert {"source": "duckdb", "topic": "Host Monitoring"} in again["refile"]


def test_a_proposal_close_to_an_accepted_topic_is_marked(library):
    call(ctx(library, [HOST]), "topic_propose")
    call(ctx(library, [], tier="curate"), "staging_decide",
         item_ids=["topic-host-monitoring"], decision="accept")
    near = {"name": "Observability", "what_belongs": "w", "members": ["duckdb", "painter"],
            "aliases": ["Host monitoring"]}
    call(ctx(library, [near]), "topic_propose", only_unfiled=False)
    listed = call(ctx(library, []), "topics_list")
    assert listed["proposed"] == [{"id": "topic-observability", "name": "Observability",
                                   "sources": 2, "duplicate_of": "Host Monitoring"}]
    assert {"topic": "Host Monitoring", "sources": 2} in listed["topics"]


def test_refiling_and_views_use_accepted_topics_only(library):
    c = ctx(library, [])
    out = call(c, "refile_source", sources=["osquery"], topic="Made Up")
    assert out["error"] == "invalid_arguments" and "not an accepted topic" in out["detail"]
    views = call(c, "views_refresh")
    assert "Indexes/Master Index.md" in views["written"] and views["not_accepted"] == []
