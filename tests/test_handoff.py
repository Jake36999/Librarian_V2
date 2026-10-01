"""P3 of the 2026-09-30 plan: the two hand-offs the Deeper Audit found left to the model.

- DA-3: a source a person accepts joins the session it was found for as an undecided
  candidate under its catalogued name, with the exact next step - never kept for it.
- DA-5 / Research Pipeline §10: an Application records the leads the library does not
  hold without claiming them as sources, and sends the fetchable ones to intake."""
from resource_librarian import intake, notes, tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.staging import StagingStore

from test_intake import RESPONSES
from test_sessions import Model, library  # noqa: F401  (fixture)


def test_an_accepted_source_joins_its_session_undecided(library):
    m = Model(library)
    m.ok("open_session", purpose="explore", question="stream tables")
    person = Context(tier="curate", vault=library,
                     extras={"fetcher": intake.Replay(RESPONSES)})
    item = REGISTRY.call("ingest", {"ref": "acme/rowstream"}, person)["item"]  # outside it
    store = StagingStore(library)
    staged = store.load(item)
    staged["found_for"] = {"session": m.ctx.session}
    store.save(staged)
    out = REGISTRY.call("staging_decide", {"item_ids": [item], "decision": "accept",
                                           "bottom_line": "Rows from a log.",
                                           "what_it_solves": "Querying a log."}, person)
    handoff = out["results"][0]["handoff"]
    assert handoff["candidate"] == "undecided" and handoff["path"].endswith(
        f"{handoff['note']}.md")
    assert f"decide(source={handoff['note']!r}" in handoff["next"]
    candidates = {c["source"]: c["disposition"] for c in m.ok("session_status")["candidates"]}
    assert candidates == {handoff["note"]: "undecided"}


def to_check_out(m):
    m.ok("open_session", purpose="apply")
    m.ok("update_plan", fields={"question": "need host inventory for our agent"})
    m.ok("advance")
    m.ok("log_use", source="osquery", used_for="inventory tables")
    m.ok("advance")


def test_an_application_records_leads_apart_and_queues_the_fetchable(library):
    m = Model(library, tier="consult")
    to_check_out(m)
    out = m.ok("record_application", title="Host Inventory", stage="prototype",
               outcome="worked", sources_used=["osquery"], needed="host inventory",
               found_and_taken="osquery tables", replaced="a shell script",
               should_learn="a log reader was missing",
               unresolved_sources=["https://github.com/acme/rowstream", "Thunkable"])
    assert [u["status"] for u in out["unresolved"]] == ["queued for intake",
                                                        "recorded: no fetchable reference"]
    note = notes.load(library.root / out["recorded"])
    assert note.frontmatter["sources_used"] == ["[[osquery]]"]           # never the leads
    assert note.frontmatter["unresolved_sources"] == ["https://github.com/acme/rowstream",
                                                      "Thunkable"]
    assert "Thunkable (recorded" in note.sections()["Not Yet In The Library"]
    queued = REGISTRY.call("queue_list", {}, m.ctx)["queued"]
    assert queued[0]["ref"] == "https://github.com/acme/rowstream"
    assert queued[0]["note"] == "named in Application - Host Inventory"
    assert queued[0]["found_for"] == {"session": m.ctx.session}


def test_a_lead_named_as_a_used_source_is_refused_with_the_remedy(library):
    m = Model(library, tier="consult")
    to_check_out(m)
    out = m("record_application", title="Host Inventory", stage="prototype", outcome="worked",
            sources_used=["osquery", "Thunkable"], needed="n", found_and_taken="f",
            replaced="r", should_learn="s")
    assert out["error"] == "invalid_arguments" and "unresolved_sources" in out["detail"]
