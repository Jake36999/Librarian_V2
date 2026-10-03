"""Requirements Addendum R7 and R14 (2026-09-30): one lifecycle store for a source, from a
queued reference to a library note, and a batch only a person begins.

- A queued reference keeps who asked, why, and the session and brief it was found for;
  capture restores that framing while the brief is open (Deeper Audit, DA-2).
- Approving a source for ingestion starts nothing. The batch takes exactly the approved
  set when a person begins it; a second start is a no-op; approvals during a run wait for
  the next; a crash or cancel resumes without repeating a finished stage; one item's
  failure never undoes another's work (Research Pipeline §4.1-4.3)."""
import json
import threading

import pytest

from resource_librarian import batch, clerk, intake, notes, tools  # noqa: F401
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.session import SessionStore
from resource_librarian.staging import StagingStore

from conftest import add_source
from test_intake import RESPONSES, clerk_answers


@pytest.fixture
def library(vault):
    for i in range(4):
        add_source(vault.root, f"filler {i}", f"Draws pictures number {i}.")
    return vault


def ctx(vault, tier="curate", session=None, seen=None):
    def answers(payload):
        if seen is not None:
            seen.append(payload)
        return clerk_answers(payload)
    return Context(tier=tier, vault=vault, session=session, extras={
        "clerk": clerk.Scripted(answers), "fetcher": intake.Replay(RESPONSES)})


def call(c, name, **args):
    return REGISTRY.call(name, args, c)


def a_session_with_a_brief(vault):
    c = ctx(vault, tier="contribute")
    assert "error" not in call(c, "open_session", purpose="explore", question="stream tables")
    sid = c.session                                       # open_session sets it
    call(c, "advance")
    assert "error" not in call(c, "open_brief", need="query a write-ahead log as rows",
                               disqualifiers=["needs a GPU"])
    return sid


def staged(vault, *names):
    store = StagingStore(vault)
    for name in names:
        store.add({"id": name, "kind": "source", "source_kind": "document", "name": name,
                   "evidence": [{"sha256": "x"}], "status": "staged"})
    return store


# ------------------------------------------------------------------ the queue (R7)

def test_a_queued_reference_keeps_who_asked_why_and_for_which_brief(library):
    sid = a_session_with_a_brief(library)
    c = ctx(library, tier="contribute", session=sid)
    call(c, "queue_source", ref="acme/rowstream", note="named in the talk", brief="b1")
    listed = call(c, "queue_list")["queued"]
    assert listed == [{"id": intake.queue_id("acme/rowstream"), "ref": "acme/rowstream",
                       "note": "named in the talk", "requested_by": sid,
                       "found_for": {"session": sid, "brief": "B1"},
                       "queued_at": listed[0]["queued_at"]}]


def test_capture_restores_the_brief_and_joins_the_session_undecided(library):
    sid = a_session_with_a_brief(library)
    c = ctx(library, tier="contribute", session=sid)
    call(c, "queue_source", ref="acme/rowstream", note="named in the talk", brief="B1")
    seen: list = []
    out = call(ctx(library, tier="contribute", seen=seen), "intake_run")   # no session here
    result = out["results"][0]
    assert result["status"] == "staged" and result["framing"] == f"framed by {sid}/B1"
    assert any(p["task"] == "screen" and "write-ahead log as rows" in p["user"] for p in seen)
    item = StagingStore(library).load(result["item"])
    assert item["found_for"] == {"session": sid, "brief": "B1"}
    assert item["queued"]["note"] == "named in the talk"
    status = call(c, "session_status")
    assert [x["disposition"] for x in status["candidates"] if x["source"] == item["name"]] \
        == ["undecided"]


def test_a_closed_brief_is_captured_unframed_and_says_so(library):
    sid = a_session_with_a_brief(library)
    c = ctx(library, tier="contribute", session=sid)
    call(c, "queue_source", ref="acme/rowstream", brief="B1")
    # the event close_brief writes (it unlocks later than this map phase)
    SessionStore(library).append(sid, {"type": "brief_closed", "id": "B1", "note": "gap"})
    assert SessionStore(library).load(sid).briefs["B1"].status == "closed"
    out = call(ctx(library, tier="contribute"), "intake_run")["results"][0]
    assert out["framing"].endswith("brief B1 is closed, so not screened")


def test_a_failed_capture_stays_visible_and_can_be_retried_or_removed(library):
    c = ctx(library)
    call(c, "queue_source", ref="nobody/nothing", note="a guess")
    out = call(c, "intake_run")["results"][0]
    assert out["queue"]["state"] == "failed"
    failed = call(c, "queue_list")["failed"]
    assert failed[0]["ref"] == "nobody/nothing" and failed[0]["failure"]["stage"] == "capture"
    assert call(c, "queue_retry", item_ids=[failed[0]["id"]])["requeued"] == 1
    assert call(c, "queue_list")["queued"][0]["ref"] == "nobody/nothing"
    assert call(c, "queue_remove", item_ids=[failed[0]["id"]], reason="dead link")["removed"] == 1
    assert call(c, "queue_list") == {"queued": [], "failed": []}
    kept = json.loads((library.work("quarantine") / "staging" / f"{failed[0]['id']}.json")
                      .read_text(encoding="utf-8"))
    assert kept["reason"] == "dead link"


def test_the_old_queue_log_is_carried_over_once(library):
    path = intake.queue_path(library)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ref": "a/one", "note": "n", "logged_by": "x", "at": "t"})
                    + "\n" + json.dumps({"ref": "a/two"}) + "\n"
                    + json.dumps({"ref": "a/two", "done": True}) + "\n", encoding="utf-8")
    assert [e["ref"] for e in intake.pending(library)] == ["a/one"]
    assert not path.exists() and path.with_suffix(".jsonl.migrated").exists()


# ------------------------------------------------------------------ the batch (R14)

def test_approving_starts_nothing_and_only_a_person_begins_the_batch(library):
    store = staged(library, "doc-a")
    out = call(ctx(library), "staging_decide", item_ids=["doc-a"], decision="approve")
    assert out["results"][0]["status"] == "approved"
    assert store.load("doc-a")["status"] == "approved"
    assert call(ctx(library), "batch_status") == {"waiting": 1, "running": "",
                                                  "waiting_on_model": 0}
    refused = call(ctx(library, tier="contribute"), "process_approved")
    assert refused["refused"] == "TIER_REFUSED"


def test_restarting_the_app_never_starts_an_approved_batch(library, tmp_path, monkeypatch):
    """Research Pipeline §10: "reloading or restarting does not start it" - only a person's
    Begin does. The app is built twice over a library with an approved item."""
    import time
    from resource_librarian.app import App
    from resource_librarian.keys import KeyStore
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    store = staged(library, "doc-a")
    call(ctx(library), "staging_decide", item_ids=["doc-a"], decision="approve")
    for _ in range(2):                                    # a start, and a restart
        app = App(library, token="t", keys=KeyStore(use_keyring=False),
                  provider_for=lambda choice: None)
        time.sleep(0.3)                                   # anything started would show by now
        assert store.load("doc-a")["status"] == "approved"
        assert call(ctx(library), "batch_status") == {"waiting": 1, "running": "",
                                                  "waiting_on_model": 0}
        if app.mcp is not None:
            app.mcp.stop()


def test_a_model_cannot_approve_under_person_promotion(library):
    staged(library, "doc-a")
    out = call(ctx(library, tier="contribute"), "staging_decide", item_ids=["doc-a"],
               decision="approve")
    assert out["results"][0]["refused"] == "PERSON_CONFIRMS"


def test_the_batch_reads_and_reviews_then_waits_for_acceptance(library):
    c = ctx(library)
    item = call(c, "ingest", ref="acme/rowstream")["item"]
    call(c, "staging_decide", item_ids=[item], decision="approve")
    out = call(c, "process_approved")
    assert out["started"] and out["status"] == "finished", out
    assert out["items"][0]["status"] == "enriched"
    assert out["items"][0]["stages"] == {
        "validate": "complete", "parse": "complete", "read": "complete", "lenses": "complete",
        "data": "complete", "relate": "complete", "metadata": "complete", "review": "complete"}
    enriched = StagingStore(library).load(item)
    assert enriched["processing"]["coverage"] == "full"
    accepted = call(c, "staging_decide", item_ids=[item], decision="accept")
    assert accepted["results"][0]["status"] == "accepted"


def test_unfinished_work_is_partial_never_enriched(library):
    c = Context(tier="curate", vault=library, extras={"fetcher": intake.Replay(RESPONSES)})
    item = call(c, "ingest", ref="acme/rowstream")["item"]     # no clerk: reading waits
    call(c, "staging_decide", item_ids=[item], decision="approve")
    call(c, "process_approved")
    done = StagingStore(library).load(item)
    assert done["status"] == "partial" and done["processing"]["coverage"].startswith("partial")
    assert any(n.startswith("read:") for n in done["processing"]["not_examined"])
    out = call(c, "staging_decide", item_ids=[item], decision="accept",
               bottom_line="Rows from a log.", what_it_solves="Querying a log.")
    fm = notes.load(library.root / out["results"][0]["promotion"]["path"]).frontmatter
    assert fm["coverage"].startswith("partial") and fm["not_examined"]   # the note says so


def test_approving_a_partial_item_again_runs_only_what_is_unfinished(library, monkeypatch):
    stages = Stages(monkeypatch)
    staged(library, "doc-a")
    c = ctx(library)
    call(c, "staging_decide", item_ids=["doc-a"], decision="approve")
    stages.queue_on = ("doc-a", "b")                      # the clerk does not answer, once
    first = call(c, "process_approved")
    assert first["items"][0]["status"] == "partial"
    assert StagingStore(library).load("doc-a")["processing"]["stages"] == {
        "a": "complete", "b": "queued", "c": "complete"}
    call(c, "staging_decide", item_ids=["doc-a"], decision="approve")
    second = call(c, "process_approved")
    assert second["items"][0]["status"] == "enriched"
    assert stages.calls.count(("doc-a", "a")) == 1 and stages.calls.count(("doc-a", "c")) == 1


def test_accepting_as_captured_says_so_on_the_note(library):
    c = ctx(library)
    item = call(c, "ingest", ref="acme/rowstream")["item"]
    out = call(c, "staging_decide", item_ids=[item], decision="accept")
    assert out["results"][0]["coverage"] == "captured"
    fm = notes.load(library.root / out["results"][0]["promotion"]["path"]).frontmatter
    assert fm["coverage"] == "captured" and "accepted as captured" in fm["not_examined"][0]


class Stages:
    """Stand-in stages that count their calls, and can block, fail or crash on cue."""

    def __init__(self, monkeypatch):
        self.calls: list[tuple[str, str]] = []
        self.gate = threading.Event()
        self.gate.set()
        self.entered = threading.Event()
        self.crash_on: tuple[str, str] | None = None
        self.fail_on: tuple[str, str] | None = None
        self.queue_on: tuple[str, str] | None = None
        self.on_call = None
        monkeypatch.setattr(batch, "STAGES", [(s, self.stage(s)) for s in ("a", "b", "c")])

    def stage(self, name):
        def run(ctx, item):
            key = (item["id"], name)
            self.calls.append(key)
            self.entered.set()
            self.gate.wait(10)
            if self.on_call:
                self.on_call(key)
            if key == self.crash_on:
                self.crash_on = None
                raise KeyboardInterrupt                    # the process dies mid-stage
            if key == self.fail_on:
                return {"status": "failed", "reason": "broken"}
            if key == self.queue_on:
                self.queue_on = None
                return {"status": "queued", "reason": "waiting for the clerk model"}
            return {"status": "complete"}
        return run


def test_a_second_start_while_running_is_a_no_op_and_new_approvals_wait(library, monkeypatch):
    stages = Stages(monkeypatch)
    staged(library, "doc-a", "doc-b")
    c = ctx(library)
    call(c, "staging_decide", item_ids=["doc-a"], decision="approve")
    stages.gate.clear()
    first = call(c, "process_approved", background=True)
    assert first["started"] and first["items"] == ["doc-a"]
    stages.entered.wait(5)
    again = call(c, "process_approved", background=True)
    assert again["started"] is False and again["already_running"] == first["run"]
    call(c, "staging_decide", item_ids=["doc-b"], decision="approve")   # approved mid-run
    running = call(c, "batch_status")
    assert running["waiting"] == 1 and running["status"] == "running" and \
        running["current"]["item"] == "doc-a"
    stages.gate.set()
    for _ in range(100):
        if not batch.live(library):
            break
        threading.Event().wait(0.05)
    assert call(c, "batch_status", run=first["run"])["status"] == "finished"
    assert StagingStore(library).load("doc-b")["status"] == "approved"   # the next run's


def test_a_crash_resumes_without_repeating_a_finished_stage(library, monkeypatch):
    stages = Stages(monkeypatch)
    staged(library, "doc-a", "doc-b")
    c = ctx(library)
    call(c, "staging_decide", item_ids=["doc-a", "doc-b"], decision="approve")
    stages.crash_on = ("doc-b", "b")
    with pytest.raises(KeyboardInterrupt):
        REGISTRY.get("process_approved").fn(c)             # a crash is not a tool result
    run = batch.latest(library)
    assert call(c, "batch_status")["status"] == "interrupted"
    assert call(c, "process_approved")["started"] is False         # nothing new approved
    out = call(c, "process_approved", resume=run)
    assert out["status"] == "finished" and {i["status"] for i in out["items"]} == {"enriched"}
    assert stages.calls.count(("doc-a", "a")) == 1 and stages.calls.count(("doc-b", "a")) == 1
    assert stages.calls.count(("doc-b", "b")) == 2                    # the one that died


def test_cancel_stops_after_the_current_stage_and_rolls_back_nothing(library, monkeypatch):
    stages = Stages(monkeypatch)
    staged(library, "doc-a", "doc-b")
    c = ctx(library)
    call(c, "staging_decide", item_ids=["doc-a", "doc-b"], decision="approve")
    stages.on_call = lambda key: key == ("doc-a", "b") and batch.cancel(library)
    out = call(c, "process_approved")
    assert out["status"] == "cancelled" and out["detail"] == "cancelled after doc-a: b"
    store = StagingStore(library)
    assert store.load("doc-a")["status"] == "processing"            # nothing undone
    resumed = call(c, "process_approved", resume=out["run"])
    assert resumed["status"] == "finished" and stages.calls.count(("doc-a", "b")) == 1


def test_one_item_failing_keeps_the_others_work(library, monkeypatch):
    stages = Stages(monkeypatch)
    staged(library, "doc-a", "doc-b")
    c = ctx(library)
    call(c, "staging_decide", item_ids=["doc-a", "doc-b"], decision="approve")
    stages.fail_on = ("doc-a", "b")
    out = call(c, "process_approved")
    assert {i["id"]: i["status"] for i in out["items"]} == {"doc-a": "failed",
                                                            "doc-b": "enriched"}
    failed = StagingStore(library).load("doc-a")
    assert failed["failure"] == {"stage": "b", "reason": "broken", "at": failed["failure"]["at"]}
    assert ("doc-a", "c") not in stages.calls
    again = call(c, "staging_decide", item_ids=["doc-a"], decision="approve")
    assert again["results"][0]["status"] == "approved"               # can be tried again


def test_steps_that_waited_for_a_model_are_run_once_one_is_chosen(library):
    """2026-10-03: a new library's 284 sources were read before it had any model."""
    bare = Context(tier="curate", vault=library, extras={"fetcher": intake.Replay(RESPONSES)})
    item = call(bare, "ingest", ref="acme/rowstream")["item"]
    call(bare, "staging_decide", item_ids=[item], decision="approve")
    call(bare, "process_approved")
    assert StagingStore(library).load(item)["status"] == "partial"
    assert call(bare, "batch_status")["waiting_on_model"] == 1
    out = call(ctx(library), "process_approved", retry_waiting=True)      # a model now
    assert out["started"]
    done = StagingStore(library).load(item)
    assert done["processing"]["stages"]["read"] == "complete"
    assert any(h.get("decision") == "retry_waiting" for h in done["history"])
    assert call(ctx(library), "batch_status")["waiting_on_model"] == 0
