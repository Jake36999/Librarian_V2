"""Requirements Addendum R13 (2026-09-30), plan P4: a research task is complete when every
asked topic has a brief and every brief a coverage verdict - covered, partial or gap - with
what was kept for it, context finds labelled as such, and the gaps said out loud.

From the Librarian-Uni session: six topics asked in one request, one brief opened; the
session ended in Judge with the guide never made; a Cyprus campus listing kept as though it
answered the need (SP-6, SP-7, SP-9)."""
from resource_librarian import tools  # noqa: F401  (registers tools)

from test_sessions import Model, library  # noqa: F401  (fixture)

TOPICS = ["host inventory", "kernel events"]


def to_need(m, topics=TOPICS):
    m.ok("open_session", purpose="explore", question="host monitoring")
    m.ok("update_plan", fields={"topics": topics})
    m.ok("advance")
    m.ok("update_plan", fields={"map": "host tooling"})
    m.ok("advance")
    assert m.ok("session_status")["phase"] == "need"


def test_need_asks_for_a_brief_per_asked_topic(library):
    m = Model(library)
    to_need(m)
    assert m.ok("advance")["moved"] is False
    assert "host inventory, kernel events" in m.ok("session_status")["open_items"][0]
    unsure = m("open_brief", need="query operating system state", disqualifiers=["GPU"])
    assert unsure["error"] == "invalid_arguments" and "host inventory" in unsure["detail"]
    assert m.ok("open_brief", need="query operating system state", disqualifiers=["GPU"],
                topic="host inv")["topic"] == "host inventory"            # a unique prefix
    last = m.ok("open_brief", need="watch kernel system calls", disqualifiers=["GPU"])
    assert last["topic"] == "kernel events"                  # the only one left
    ledger = m.ok("session_status")["coverage"]
    assert [(r["topic"], r["brief"], r["verdict"]) for r in ledger] == [
        ("host inventory", "B1", "open"), ("kernel events", "B2", "open")]
    assert m.ok("advance")["moved"] == "search"


def test_a_topic_not_asked_is_refused(library):
    m = Model(library)
    to_need(m)
    out = m("open_brief", need="x", disqualifiers=["y"], topic="cooking")
    assert out["error"] == "invalid_arguments" and "update_plan" in out["detail"]


def to_judge(m):
    to_need(m)
    m.ok("open_brief", need="query operating system state", disqualifiers=["needs a GPU"],
         topic="host inventory")
    m.ok("open_brief", need="watch kernel system calls", disqualifiers=["needs a GPU"],
         topic="kernel events")
    m.ok("advance")
    m.run_rounds(["operating system state database"], brief="B1")
    m.ok("advance")
    names = {c["source"] for c in m.ok("session_status")["candidates"]}
    for name in ("osquery", "duckdb"):
        if name not in names:
            m.ok("add_candidate", source=name, brief="B1")
    m.ok("add_candidate", source="painter", brief="B2")     # B2's only find: not an answer
    assert m.ok("session_status")["phase"] == "judge"


def test_coverage_verdicts_are_earned_and_context_is_not_an_answer(library):
    m = Model(library)
    to_judge(m)
    m.ok("decide", source="osquery", disposition="keep", role="host state as SQL tables")
    m.ok("decide", source="duckdb", disposition="context",
         reason="background on analytical SQL, not a host tool")
    m.ok("decide", source="painter", disposition="context", reason="named in a talk")
    for c in m.ok("session_status")["candidates"]:
        if c["disposition"] == "undecided":
            m.ok("decide", source=c["source"], disposition="reject", reason="off topic")
    covered = m("close_brief", brief="B2", coverage="covered", note="falco")
    assert covered["error"] == "invalid_arguments" and "only context" in covered["detail"]
    assert m("close_brief", brief="B2", coverage="gap", note="")["error"]   # say what's missing
    m.ok("close_brief", brief="B2", coverage="gap",
         note="no kernel-event tool held; painter is only named")
    m.ok("close_brief", brief="B1", coverage="covered", note="osquery")
    ledger = {r["brief"]: r for r in m.ok("session_status")["completion"]["ledger"]}
    assert ledger["B1"]["kept"] == ["osquery"] and ledger["B1"]["context"] == ["duckdb"]
    assert ledger["B2"]["verdict"] == "gap" and ledger["B2"]["context"] == ["painter"]
    done = m.ok("session_status")["completion"]
    assert done["complete"] and done["gaps"] == ["kernel events (gap)"]


def test_a_session_cannot_close_claiming_no_gaps_over_a_gap(library):
    m = Model(library)
    to_judge(m)
    m.decide_all(keep={"osquery"})
    m.ok("close_brief", brief="B1", coverage="covered", note="osquery")
    m.ok("close_brief", brief="B2", coverage="gap", note="nothing on kernel events")
    m.ok("record_assumptions", assumptions=[])
    m.ok("advance")                                                  # synthesise
    m.ok("record_synthesis", outcome="nothing", together="osquery covers host inventory",
         unknowns="kernel events", reason="no guide was asked for")
    assert m.ok("advance")["moved"] == "check_out"
    refused = m("close_session", summary="found osquery", gaps="none")
    assert refused["error"] == "invalid_arguments" and "kernel events (gap)" in refused["detail"]
    closed = m.ok("close_session", summary="found osquery", gaps="kernel events")
    assert closed["completion"]["complete"]


def test_outside_finds_are_screened_against_the_brief_and_queued_with_it(library):
    from resource_librarian import clerk, intake
    from resource_librarian.registry import REGISTRY
    from test_scout import SEARCH, _atom

    def answers(payload):
        if payload["task"] == "screen":
            gpu = "gpu" in payload["user"].lower().split("---")[1]
            return {"verdict": "reject" if gpu else "keep",
                    "reason": "states it needs a GPU" if gpu else "does not contradict",
                    "contradicts": ["Needs a GPU"] if gpu else []}
        return {}
    m = Model(library)
    m.ctx.extras.update(clerk=clerk.Scripted(answers), fetcher=intake.Replay({
        f"{SEARCH}*": {"items": [
            {"full_name": "acme/hostwatch", "description": "Host inventory as SQL tables"},
            {"full_name": "acme/gpuwatch", "description": "Needs a GPU to watch hosts"}]},
        "https://export.arxiv.org/api/query?search_query=*": _atom([])}))
    to_need(m, topics=["host inventory"])
    m.ok("open_brief", need="query operating system state", disqualifiers=["needs a GPU"])
    m.ok("advance")
    assert m("research_round", queries=["host"], outside=True, screen=2)["error"]  # no brief
    out = m.ok("research_round", queries=["host inventory"], brief="B1", outside=True,
               screen=2)
    verdicts = {f["ref"]: f["verdict"] for f in out["screened"]}
    assert verdicts == {"acme/hostwatch": "keep", "acme/gpuwatch": "reject"}
    assert out["queued"] == 1 and "intake_run" in out["next"]
    queued = REGISTRY.call("queue_list", {}, m.ctx)["queued"]
    assert [(q["ref"], q["found_for"]) for q in queued] == [
        ("acme/hostwatch", {"session": m.ctx.session, "brief": "B1"})]


def test_a_spent_budget_is_not_a_dead_end(library):
    from resource_librarian.registry import REGISTRY, Context
    m = Model(library)
    m.ok("open_session", purpose="explore")                 # no question yet: frame unfinished
    for _ in range(40):
        out = m("vault_status")
        if out.get("refused") == "BUDGET_SPENT":
            break
    assert out["refused"] == "BUDGET_SPENT" and "Extend budget" in out["detail"]
    status = m.ok("session_status")
    assert status["budget_spent"] and status["budget_left"] == 0
    assert m("extend_budget", add=5)["refused"] == "TIER_REFUSED"      # never the model's own
    person = Context(tier="curate", vault=library, session=m.ctx.session)
    added = REGISTRY.call("extend_budget", {"add": 5, "reason": "let it finish framing"}, person)
    assert added["budget_left"] == 5
    assert "error" not in m("vault_status")
