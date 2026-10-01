"""Session replays: a scripted model walks each purpose through the registry,
exactly as a surface would, and the artefacts are checked."""
import hashlib
import threading
import time
from pathlib import Path

import pytest

from resource_librarian import clerk, notes, tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.session import SessionStore
from resource_librarian.vault import render_config

from conftest import add_source

OSQUERY_LINE = "Exposes the operating system as a relational database you query with SQL."


@pytest.fixture
def library(vault):
    add_source(vault.root, "osquery", OSQUERY_LINE,
               "Query operating system state such as processes and open sockets.")
    add_source(vault.root, "duckdb", "An in-process analytical SQL database for a laptop.",
               "Analytical queries over local files.")
    add_source(vault.root, "falco", "Watches kernel system calls and alerts on suspicious "
               "process behaviour.", "Runtime security for hosts and containers.")
    add_source(vault.root, "painter", "Draws pictures of cats.", "Illustration.")
    return vault


class Model:
    """A scripted model: calls tools through the registry and keeps its context."""

    def __init__(self, vault, tier="contribute"):
        self.ctx = Context(tier=tier, vault=vault)

    def __call__(self, _tool, **arguments):
        return REGISTRY.call(_tool, arguments, self.ctx)

    def ok(self, _tool, **arguments):
        result = self(_tool, **arguments)
        assert "error" not in result, result
        return result

    def person(self, question_id, answer):
        person = Context(tier="curate", vault=self.ctx.vault, session=self.ctx.session)
        result = REGISTRY.call("answer", {"question_id": question_id, "answer": answer}, person)
        assert "error" not in result, result

    def decide_all(self, keep):
        status = self.ok("session_status")
        for c in status["candidates"]:
            if c["disposition"] != "undecided":
                continue
            if c["source"] in keep:
                self.ok("decide", source=c["source"], disposition="keep",
                        role="exposes host state to queries")
            else:
                self.ok("decide", source=c["source"], disposition="reject",
                        reason="does not do the job")

    def run_rounds(self, queries, brief=""):
        """Rounds until the stopping rule fires (the second identical round adds nothing)."""
        for _ in range(4):
            self.ok("research_round", queries=queries, brief=brief)
            if self.ok("checkpoint", learned="the field says 'host instrumentation'",
                       subthreads=["host tables", "event streams"],
                       next_targets=["osquery tables"])["stop"]:
                return
        raise AssertionError("the stopping rule never fired")


def test_add_project_walk(library):
    m = Model(library)
    opened = m.ok("open_session", purpose="add_project")
    assert opened["session"]["phase"] == "frame"

    gated = m("draft_offering", title="x", summary="x", claims=[])
    assert gated["refused"] == "PHASE_GATE" and "synthesise" in gated["detail"]
    assert gated["session"]["phase"] == "frame"                     # envelope on refusals too

    assert m.ok("advance")["moved"] is False
    m.ok("create_project", name="Host Watch", stage="planning", summary="Watch our hosts.",
         constraints={"license_class": "Permissive"}, disqualifiers=["requires a GPU"])
    assert m.ok("advance")["moved"] == "ingest"
    m.ok("update_plan", fields={"ingested": "none"})
    m.ok("advance")
    orient = m.ok("search", query="operating system state", intent="orient")
    assert orient["session"]["phase"] == "map"
    m.ok("update_plan", fields={"map": "host tooling is held under Unfiled"})
    m.ok("advance")

    brief = m.ok("open_brief", need="query operating system state as a database")
    assert brief["brief"] == "B1"                           # the project's disqualifier counts
    moved = m.ok("advance")["moved"]
    if moved == "search":
        m.run_rounds(["operating system state database", "process sockets"], brief="B1")
        assert m.ok("advance")["moved"] == "judge"
    else:
        assert moved == "judge"
        m.ok("add_candidate", source="osquery", brief="B1")
    m.decide_all(keep={"osquery"})
    m.ok("record_assumptions", assumptions=[])
    m.ok("advance")

    m.ok("record_synthesis", outcome="offering", together="osquery alone covers the need",
         unknowns="performance at fleet scale", open_first="osquery")
    bad = m("draft_offering", title="Host Watch Starter", summary="Start with osquery.",
            claims=[{"text": "osquery runs on GPUs", "source": "osquery",
                     "quote": "osquery is accelerated by CUDA kernels on the GPU"}])
    assert bad["refused"] == "EVIDENCE_QUOTE_VERIFIED"
    assert not list((library.librarian / "staging").rglob("*.md"))
    staged = m.ok("draft_offering", title="Host Watch Starter", summary="Start with osquery.",
                  claims=[{"text": "osquery turns host state into SQL tables",
                           "source": "osquery", "quote": OSQUERY_LINE.lower()}])
    asked = m.ok("promote_offering", offering=staged["offering"])
    assert asked["needs_person"] and asked["kind"] == "confirm"
    assert m.ok("advance")["moved"] is False                 # an unanswered question blocks
    m.person(asked["question_id"], "yes")
    promoted = m.ok("promote_offering", offering=staged["offering"])
    note = notes.load(library.root / promoted["promoted"])
    assert promoted["promoted"] == "Offerings/Host Watch/Host Watch Starter.md"
    assert promoted["findable"]                              # R13: indexed, found by title
    assert note.frontmatter["session"] == m.ctx.session and note.frontmatter["status"] == "active"
    assert "> exposes the operating system" in note.body

    m.ok("advance")
    assert m.ok("close_session", summary="s", gaps="g")["closed"] is False
    m.ok("close_brief", brief="B1", coverage="covered", note="answered by osquery")
    assert m.ok("close_session", summary="Framed Host Watch; osquery offered.",
                gaps="nothing on fleet-scale performance")["closed"]
    reopened = m.ok("resume_session", session_id=m.ctx.session)
    assert reopened["status"] == "open" and reopened["history"][-1] == "check_out"


def test_explore_asks_for_disqualifiers_and_widens(library):
    m = Model(library)
    m.ok("open_session", purpose="explore", question="kernel-level monitoring")
    m.ok("advance")
    m.ok("update_plan", fields={"map": "a little host tooling"})
    m.ok("advance")
    asked = m.ok("open_brief", need="watch kernel calls")
    assert asked["needs_person"] and asked["brief_opened"] is False
    assert m.ok("advance")["moved"] is False
    m.person(asked["question_id"], "must not need a kernel module")
    m.ok("open_brief", need="zzqx unmatched wording", disqualifiers=["needs a kernel module"])
    assert m.ok("advance")["moved"] == "search"
    for _ in range(2):
        m.ok("research_round", queries=["zzqx unmatched wording"], brief="B1")
    status = m.ok("session_status")
    assert "widen the vocabulary" in status["next"] and "target='need'" in status["next"]
    assert m.ok("advance", target="need", reason="widen")["back"]


def test_apply_as_a_reader(library):
    m = Model(library, tier="consult")
    assert m("open_session", purpose="explore")["refused"] == "TIER_REFUSED"
    m.ok("open_session", purpose="apply")
    m.ok("update_plan", fields={"question": "need host inventory for our agent"})
    m.ok("advance")
    m.ok("search", query="operating system state")
    assert m("create_project", name="x", stage="x", summary="x")["refused"] == "TIER_REFUSED"
    m.ok("log_use", source="osquery", used_for="inventory tables")
    m.ok("advance")
    recorded = m.ok("record_application", title="Host Inventory", stage="prototype",
                    outcome="worked", sources_used=["osquery"], needed="host inventory",
                    found_and_taken="osquery tables", replaced="a shell script",
                    should_learn="nothing missing")
    assert recorded["recorded"] == "Applications/Application - Host Inventory.md"
    assert m.ok("close_session", summary="used osquery", gaps="none")["closed"]


def test_suggest_reads_the_project_and_never_writes_it(library, tmp_path):
    project = tmp_path / "hostwatch"
    project.mkdir()
    (project / "README.md").write_text("HostWatch collects process lists from every server "
                                       "with a cron job and a shell script.\n")
    before = hashlib.sha256((project / "README.md").read_bytes()).hexdigest()
    config = library.config()
    config["promotion"]["mode"] = "agent"
    library.config_path.write_text(render_config(config))

    m = Model(library)
    m.ok("create_project", name="HostWatch", stage="active", summary="Watches hosts.",
         disqualifiers=["requires a GPU"], repository=str(project))
    m.ok("open_session", purpose="suggest", project="HostWatch")
    m.ok("advance")
    # Research Pipeline §6: off by default - the model is refused, and Map does not ask for it
    assert m("read_project")["refused"] == "PROJECT_ACCESS_OFF"
    assert "read_project" not in " ".join(m.ok("session_status")["open_items"])
    from resource_librarian import projects                   # the person allows the folder
    projects.set_enabled(library, True)
    added = projects.add_root(library, str(project), project="HostWatch")
    assert added["scaffold"]["state"] == "created"
    assert "read_project" in " ".join(m.ok("session_status")["open_items"])
    listing = m.ok("read_project")
    assert listing["files"] == ["README.md"]
    assert m("read_project", path="../../etc/passwd")["error"] == "invalid_arguments"
    m.ok("read_project", path="README.md")
    logged = (project / "librarian-app" / "logs" / "access.jsonl").read_text(encoding="utf-8")
    assert '"path": "README.md"' in logged
    m.ok("update_plan", fields={"map": "the project scripts what osquery does"})
    m.ok("advance")
    m.run_rounds(["collect process lists from servers"])
    m.ok("advance")
    m.decide_all(keep={"osquery"})
    m.ok("record_assumptions", assumptions=[])
    m.ok("advance")
    m.ok("record_synthesis", outcome="offering", together="replace the script with osquery",
         unknowns="agent footprint")
    staged = m.ok("draft_offering", title="Replace The Cron Script", kind="suggestion",
                  summary="osquery could replace the cron job.",
                  claims=[{"text": "the project scrapes process lists by hand",
                           "source": "project:README.md",
                           "quote": "collects process lists from every server with a cron job"},
                          {"text": "osquery exposes that state as tables", "source": "osquery",
                           "quote": "Exposes the operating system as a relational database"}])
    promoted = m.ok("promote_offering", offering=staged["offering"])
    assert promoted["by"] == "agent setting"
    body = (library.root / promoted["promoted"]).read_text()
    assert "`project:README.md`" in body and "[[osquery]]" in body
    assert hashlib.sha256((project / "README.md").read_bytes()).hexdigest() == before
    # the project's own files untouched; only the sidecar the person's "add" created
    assert sorted(p.name for p in project.iterdir()) == ["README.md", "librarian-app"]


def test_budget_is_enforced_and_harness_is_free(library):
    config = library.config()
    config["session"] = {"map": 2}
    library.config_path.write_text(render_config(config))
    m = Model(library)
    m.ok("open_session", purpose="explore", question="q")
    m.ok("advance")
    for _ in range(2):
        m.ok("search", query="database")
    spent = m("search", query="database")
    assert spent["refused"] == "BUDGET_SPENT" and spent["session"]["budget_left"] == 0
    assert "error" not in m("session_status")
    # The budget is the model's: the person's own reads in the thread (the
    # pane's lens list) are neither refused by it nor charged to it.
    person = Context(tier="curate", vault=library, session=m.ctx.session)
    listed = REGISTRY.call("lens_suggest", {"limit": 12}, person)
    assert "refused" not in listed and listed["session"]["budget_left"] == 0
    m.ok("update_plan", fields={"map": "done"})
    assert m.ok("advance")["moved"] == "need"
    assert m.ok("search", query="database")["session"]["budget_left"] > 0


def test_park_resume_and_log_replay(library):
    m = Model(library)
    m.ok("open_session", purpose="explore", question="q")
    session_id = m.ctx.session
    m.ok("park_session", note="lunch")
    assert m("search", query="x")["refused"] == "SESSION_REQUIRED"
    other = Model(library)
    state = other.ok("resume_session", session_id=session_id)
    assert state["status"] == "open" and state["question"] == "q"
    events = (library.work("sessions") / f"{session_id}.jsonl").read_text().splitlines()
    assert len(events) >= 4
    assert SessionStore(library).load(session_id).status == "open"


def test_ask_user_blocks_until_a_person_answers(library):
    """The bug this fixes: answering a question used to be inert - nothing
    fed it back to the call that asked it, or woke it up. With a `Waiters`
    behind it (as the real app always has, via `App._extras()`), `ask_user`
    now blocks the calling thread and returns with the real answer, the same
    handshake `Broker.check()` already uses for a permission gate."""
    from resource_librarian.tools.sessions import Waiters

    waiters = Waiters(timeout=5)
    m = Model(library)
    m.ctx.extras["waiters"] = waiters
    m.ok("open_session", purpose="explore", question="kernel-level monitoring")

    outcome: dict = {}
    asking = threading.Thread(target=lambda: outcome.update(
        m.ok("ask_user", question="Which host is this for?")))
    asking.start()

    # Answering races the asking thread reaching `waiters.wait`: retry, the
    # same as any test of a blocking handshake, rather than assume a delay.
    person = Context(tier="curate", vault=library, session=m.ctx.session,
                     extras={"waiters": waiters})
    woken, question_id, deadline = False, "", time.time() + 2
    while time.time() < deadline and not woken:
        open_questions = SessionStore(library).load(m.ctx.session).open_questions()
        if open_questions:
            question_id = open_questions[0]["id"]
            woken = REGISTRY.call("answer", {"question_id": question_id,
                                             "answer": "Prod-01"}, person)["resumed"]
        if not woken:
            time.sleep(0.02)
    asking.join(timeout=2)
    assert woken, "the question was never actually pending when answered"
    assert not asking.is_alive(), "ask_user never returned once answered"
    assert outcome["question_id"] == question_id
    assert outcome["question"] == "Which host is this for?"
    assert outcome["answer"] == "Prod-01"
    assert "needs_person" not in outcome


def test_ask_user_without_a_waiter_still_returns_immediately(library):
    """No `Waiters` in extras (a scripted test with no App behind it, like
    every other test in this file): the old, non-blocking shape."""
    m = Model(library)
    m.ok("open_session", purpose="explore", question="kernel-level monitoring")
    asked = m.ok("ask_user", question="Which host is this for?")
    assert asked["needs_person"] and asked["question_id"] == "q1"
    assert "answer" not in asked


def test_an_unanswered_question_times_out_and_parks(library):
    from resource_librarian.tools.sessions import Waiters

    waiters = Waiters(timeout=0.05)
    m = Model(library)
    m.ctx.extras["waiters"] = waiters
    m.ok("open_session", purpose="explore", question="kernel-level monitoring")
    asked = m("ask_user", question="Nobody will answer this")
    assert asked["refused"] == "PERMISSION_UNANSWERED"
    assert SessionStore(library).load(m.ctx.session).status == "parked"


def test_every_gated_tool_is_registered():
    from resource_librarian.session import HARNESS, WRITES
    assert set(WRITES) <= set(REGISTRY.names())
    assert set(HARNESS) <= set(REGISTRY.names())


def test_cached_engine_sees_new_notes(vault):
    from resource_librarian.tools.library import engine_for
    ctx = Context(tier="contribute", vault=vault)
    engine_for(ctx, refresh=False)                     # built, not refreshed
    add_source(vault.root, "osquery", OSQUERY_LINE)
    assert engine_for(ctx).index.note_row("osquery") is not None


def _to_need_phase(m, question: str) -> None:
    m.ok("open_session", purpose="explore", question=question)
    m.ok("advance")                                     # frame -> map
    m.ok("update_plan", fields={"map": "done"})
    m.ok("advance")                                     # map -> need


def test_open_brief_asks_the_clerk_to_translate_the_need_into_queries(library):
    def answers(payload):
        return {"queries": ["kernel syscalls", "runtime security"]} \
            if payload["task"] == "queries" else {}
    m = Model(library)
    m.ctx.extras["clerk"] = clerk.Scripted(answers)
    _to_need_phase(m, "watch process behaviour")
    out = m.ok("open_brief", need="watch kernel calls", disqualifiers=["needs a GPU"])
    assert out["suggested_queries"] == ["kernel syscalls", "runtime security"]


def test_open_brief_degrades_to_the_need_itself_with_no_clerk(library):
    m = Model(library)                          # no clerk configured
    _to_need_phase(m, "watch process behaviour")
    out = m.ok("open_brief", need="watch kernel calls", disqualifiers=["needs a GPU"])
    assert out["suggested_queries"] == ["watch kernel calls"]


def test_the_envelope_carries_the_project_once_set(library):
    """The Desk (2B) and the pane's ⋮ menu both read the session's project off
    every tool result's envelope, not just session_status/resume_session's
    full to_dict - a call that only sets it (create_project) must show it too."""
    m = Model(library)
    m.ok("open_session", purpose="add_project", question="q")
    out = m.ok("create_project", name="Host Watch", stage="active", summary="s")
    assert out["session"]["project"] == "Host Watch"
