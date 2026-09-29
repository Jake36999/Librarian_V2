"""Session tools: open a thread, walk its phases, and write what it produced.

Every tool here runs inside a session (`ctx.session`) except `open_session`,
`resume_session` and `list_sessions`. The registry's session hooks gate the
writes by phase and attach the envelope, so these functions only do the work.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from .. import agenda as _agenda, clerk, notes, registry, scribe
from ..evidence import EvidenceStore
from ..registry import Card, Context, tool
from ..rules import Refusal
from ..search import Constraints, search, terms_from
from ..session import PURPOSES, SessionStore, after_call, before_call
from ..vault import now_iso
from .library import DUE_DATE, engine_for
from .staging import clerk_endpoint, scribe_endpoint

registry.REGISTRY.session_hooks = (before_call, after_call)

Purpose = Literal["add_project", "explore", "suggest", "apply", "start_pursuit", "learn",
                  "add_capability"]
PLAN_KEYS = ("project", "question", "map", "ingested", "nothing_found", "no_application", "notes",
            # W1 start_pursuit
            "inventory", "no_dates",
            # W2 learn
            "goal", "deadline", "baseline", "focus", "practice_stopped", "consolidated",
            "scheduled",
            # F2 add_capability
            "candidate", "assessment")
UNDERSTANDING_CONFIDENCE = ("shaky", "ok", "solid")
MIN_QUOTE_WORDS = 5
MAX_PROJECT_FILE = 20_000
MAX_PROJECT_LIST = 200


def _store(ctx: Context) -> SessionStore:
    return SessionStore(ctx.vault)


def _session(ctx: Context):
    if not ctx.session:
        raise Refusal("SESSION_REQUIRED", "no session is open in this context: open_session, "
                                          "or resume_session(id)")
    return _store(ctx).load(ctx.session)


def _event(ctx: Context, event: dict[str, Any]) -> None:
    _store(ctx).append(ctx.session, event)


class Waiters:
    """Lets `ask_user` block the turn's own thread until a person answers, the
    same handshake `Broker.check()` already uses for a permission gate
    (broker.py) - a threading.Event per pending question instead of per tool
    call, and an event emitted the moment one starts waiting so the interface
    can show it immediately rather than only once the (now-delayed) tool
    result finally arrives."""

    def __init__(self, timeout: float = 600.0):
        self.timeout = timeout
        self._lock = threading.Lock()
        self._pending: dict[str, threading.Event] = {}
        self._answers: dict[str, str] = {}
        self._listeners: list[Callable[[dict[str, Any]], None]] = []

    def subscribe(self, listener: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def _emit(self, event: dict[str, Any]) -> None:
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:                               # noqa: BLE001
                pass                                        # a broken listener never blocks

    def wait(self, key: str, **event: Any) -> str | None:
        """Blocks until `answer()` is called with this key, or the timeout
        passes. Returns the answer text, or None if nobody answered in time."""
        done = threading.Event()
        with self._lock:
            self._pending[key] = done
        self._emit({"type": "question_asked", **event})
        done.wait(self.timeout)
        with self._lock:
            self._pending.pop(key, None)
            answer = self._answers.pop(key, None)
        self._emit({"type": "question_answered", "answered": answer is not None, **event})
        return answer

    def answer(self, key: str, text: str) -> bool:
        """True when a call was actually waiting on this key; False when it
        already gave up (timed out) or nothing was ever waiting on it."""
        with self._lock:
            done = self._pending.get(key)
            if done is None:
                return False
            self._answers[key] = text
            done.set()
            return True


def _waiter_key(ctx: Context, question_id: str) -> str:
    return f"{ctx.vault.root}::{ctx.session}::{question_id}"


def _ask(ctx: Context, question: str, kind: str = "clarify", ref: str = "",
         options: list[str] | None = None) -> dict[str, Any]:
    session = _session(ctx)
    qid = f"q{len(session.questions) + 1}"
    _event(ctx, {"type": "question", "id": qid, "question": question, "kind": kind,
                 "ref": ref, "options": options})
    waiters: Waiters | None = ctx.extras.get("waiters")
    if waiters is None:
        # No one able to signal back (e.g. a scripted test with no App
        # behind it): the old, non-blocking shape, unanswered until a
        # caller comes back with `answer` on its own.
        return {"needs_person": True, "question_id": qid, "question": question,
                "options": options, "kind": kind}
    answer_text = waiters.wait(_waiter_key(ctx, qid), session=ctx.session, question_id=qid,
                               question=question, kind=kind, options=options)
    if answer_text is None:
        _event(ctx, {"type": "status", "status": "parked",
                     "note": f"question {qid} went unanswered"})
        raise Refusal("PERMISSION_UNANSWERED", f"{qid} waited {waiters.timeout:.0f}s for a "
                                               f"person; the session is parked")
    return {"question_id": qid, "question": question, "answer": answer_text}


# ------------------------------------------------------------------ the thread

@tool("open_session", tier="consult", effect="write",
      card=Card("Start a research thread: add a project, explore, suggest for a project, or "
                "apply (a Reader working elsewhere)",
                "you are about to do more than one search toward a purpose",
                "Every later result carries the session envelope: phase, open items, "
                "budget left and the next step"))
def open_session(ctx: Context, purpose: Purpose, project: str = "", question: str = "") -> dict:
    if purpose != "apply" and ctx.tier == "consult":
        raise Refusal("TIER_REFUSED", f"a {purpose} session is Librarian work, granted at "
                                      f"'contribute'; a Reader opens an 'apply' session")
    if project:
        ctx.vault.project_note(project)       # a plain name, or refused: it becomes a path
    session = _store(ctx).new(purpose, project, question)
    ctx.session = session.id
    return {"opened": session.id, "phases": list(PURPOSES[purpose]),
            **{"session": session.envelope(ctx.vault)}}


@tool("list_sessions", tier="consult", effect="read",
      card=Card("Open, parked and closed research threads", "picking a thread back up"))
def list_sessions(ctx: Context, status: str = "") -> dict:
    rows = _store(ctx).list()
    return {"sessions": [r for r in rows if not status or r["status"] == status][:50]}


@tool("resume_session", tier="consult", effect="write",
      card=Card("Reopen a parked or closed thread with its plan, briefs and decisions",
                "coming back to earlier work, or discussing what a thread produced"))
def resume_session(ctx: Context, session_id: str) -> dict:
    session = _store(ctx).load(session_id)
    ctx.session = session.id
    if session.status == "parked":
        _event(ctx, {"type": "status", "status": "open"})
    elif session.status == "closed":
        _event(ctx, {"type": "reopened"})
    return _store(ctx).load(session.id).to_dict(ctx.vault)


@tool("session_status", tier="consult", effect="read",
      card=Card("Where this thread is: phase, plan, briefs, candidates, questions",
                "you have lost track of the walk"))
def session_status(ctx: Context) -> dict:
    return _session(ctx).to_dict(ctx.vault)


@tool("park_session", tier="consult", effect="write",
      card=Card("Pause this thread so it can be resumed later", "stopping for now"))
def park_session(ctx: Context, note: str = "") -> dict:
    _event(ctx, {"type": "status", "status": "parked", "note": note})
    return {"parked": ctx.session}


@tool("rewind_session", tier="curate", effect="write",
      card=Card("Discard a message and everything after it, in this thread",
                "a message (or its reply) turned out wrong and the thread should continue from "
                "before it - never the model's own call, only the person's"))
def rewind_session(ctx: Context, to_index: int) -> dict:
    store = _store(ctx)
    session = store.load(ctx.session)
    if not 0 <= to_index < len(session.messages):
        raise TypeError(f"no message at index {to_index}; this thread has "
                        f"{len(session.messages)}")
    if to_index < session.min_rewind_index:
        raise Refusal("REWIND_BLOCKED",
                      f"a vault write happened after message {session.min_rewind_index - 1}; "
                      f"rewinding to {to_index} would silently discard it")
    store.truncate_to(ctx.session, to_index)
    fresh = store.load(ctx.session).to_dict(ctx.vault)
    return {"rewound_to": to_index, "messages": fresh["messages"],
            "min_rewind_index": fresh["min_rewind_index"]}


@tool("branch_session", tier="curate", effect="write",
      card=Card("Fork a new thread from a message here, leaving this one as it is",
                "exploring a different reply to the same point without losing this thread - "
                "never the model's own call, only the person's"))
def branch_session(ctx: Context, to_index: int) -> dict:
    store = _store(ctx)
    session = store.load(ctx.session)
    if not 0 <= to_index < len(session.messages):
        raise TypeError(f"no message at index {to_index}; this thread has "
                        f"{len(session.messages)}")
    new_id = store.copy_through(ctx.session, to_index)
    return {"branched": new_id}


@tool("update_plan", tier="consult", effect="write",
      card=Card("Record the thread's framing and progress: project, question, map, "
                "ingested, nothing_found, no_application, notes",
                "a phase asks you to record something"))
def update_plan(ctx: Context, fields: dict) -> dict:
    unknown = sorted(set(fields) - set(PLAN_KEYS))
    if unknown:
        raise TypeError(f"unknown plan field(s) {unknown}; plan fields are {list(PLAN_KEYS)}")
    if "focus" in fields:
        focus = fields["focus"]
        focus = [f for f in (focus.split(",") if isinstance(focus, str) else focus or [])]
        fields = {**fields, "focus": [str(f).strip() for f in focus if str(f).strip()]}
        if not fields["focus"]:
            raise TypeError("focus is a list of one or more concept names")
    if fields.get("project") and not ctx.vault.project_note(fields["project"]).exists():
        raise TypeError(f"no Project note named {fields['project']!r}: create_project first")
    _event(ctx, {"type": "plan", "fields": fields})
    return {"recorded": sorted(fields)}


@tool("record_assumptions", tier="consult", effect="write",
      card=Card("Say what you are assuming before you commit, and how each assumption was "
                "settled",
                "the envelope asks for it: before an answer, a proposal or a plan",
                "Checked, not believed: `settled_by` must be a tool this session called "
                "successfully (with `how` - what its result showed), the id of a question the "
                "person answered, or 'unverifiable'. An empty list says you assume nothing"))
def record_assumptions(ctx: Context, assumptions: list[dict]) -> dict:
    """Roadmap §4 G2. An assumption the model cannot settle is still worth
    recording as `unverifiable`: it is then visible in the session, and belongs
    in the answer's own caveats, instead of being silently relied on."""
    from ..session import HARNESS
    session = _session(ctx)
    items: list[dict[str, str]] = []
    if assumptions:
        problems = []
        answered = {q["id"] for q in session.questions if q.get("answer") is not None}
        for i, raw in enumerate(assumptions or [], 1):
            raw = raw if isinstance(raw, dict) else {"assumption": str(raw)}
            text = str(raw.get("assumption") or "").strip()
            by = str(raw.get("settled_by") or "").strip()
            how = str(raw.get("how") or "").strip()
            by = by.split(":", 1)[1] if by.startswith("ask_user:") else by
            if not text:
                problems.append(f"#{i}: no assumption stated")
            elif by == "unverifiable" or by in answered:
                pass
            elif by in HARNESS or not session.called.get(by):
                problems.append(f"#{i} ({text[:40]}): {by or 'nothing'!r} is not a tool this "
                                f"session called successfully, an answered question, or "
                                f"'unverifiable'")
            elif not how:
                problems.append(f"#{i} ({text[:40]}): say what {by}'s result showed (`how`)")
            items.append({"assumption": text, "settled_by": by, "how": how})
        if problems:
            raise TypeError("not recorded: " + "; ".join(problems))
    _event(ctx, {"type": "assumptions", "phase": session.phase,
                 "visit": session.visits.get(session.phase, 1), "items": items})
    return {"recorded": len(items),
            "unverifiable": [a["assumption"] for a in items if a["settled_by"] == "unverifiable"]}


@tool("ask_user", tier="consult", effect="write",
      card=Card("Ask the person something only they can answer",
                "a phase needs a decision, a fixed constraint, or a disqualifier you do not "
                "know", "The question blocks advancing until it is answered"))
def ask_user(ctx: Context, question: str, options: list[str] | None = None) -> dict:
    return _ask(ctx, question, "clarify", "", options)


@tool("answer", tier="curate", effect="write",
      card=Card("Record the person's answer to a question the session asked",
                "the person has answered",
                "A person's answer: surfaces route this to the person, never to the model. "
                "Wakes the call still waiting on it, if one still is"))
def answer(ctx: Context, question_id: str, answer: str) -> dict:
    session = _session(ctx)
    if not any(q["id"] == question_id for q in session.questions):
        raise TypeError(f"no question {question_id!r} in this session")
    _event(ctx, {"type": "answer", "id": question_id, "answer": answer, "by": ctx.tier})
    waiters: Waiters | None = ctx.extras.get("waiters")
    resumed = bool(waiters and waiters.answer(_waiter_key(ctx, question_id), answer))
    return {"answered": question_id, "resumed": resumed}


@tool("advance", tier="consult", effect="write",
      card=Card("Move the thread to its next phase, or back to an earlier one",
                "the envelope says the phase is complete, or a phase needs redoing",
                "Refused with what is missing when the exit condition is not met"))
def advance(ctx: Context, target: str = "", reason: str = "") -> dict:
    session = _session(ctx)
    phases = session.phases
    here = phases.index(session.phase)
    if target:
        if target not in phases:
            raise TypeError(f"{target!r} is not a phase of {session.purpose}: {list(phases)}")
        if target == session.phase:
            return {"moved": False, "phase": target, "missing": session.missing(ctx.vault)}
        if phases.index(target) < here:
            _event(ctx, {"type": "phase", "to": target, "back": True, "reason": reason})
            return {"moved": target, "back": True}
    missing = session.missing(ctx.vault)
    if missing:
        return {"moved": False, "missing": missing}
    if here + 1 >= len(phases):
        return {"moved": False, "missing": ["this is the last phase: close_session"]}
    to = phases[here + 1]
    skipped = ""
    if to == "search" and session.briefs and all(b.verdict == "covered"
                                                 for b in session.briefs.values()):
        to, skipped = "judge", "search: every brief's coverage verdict is already 'covered'"
    if target and target != to and phases.index(target) > phases.index(to):
        raise TypeError(f"phases are walked in order; the next phase is {to!r}")
    _event(ctx, {"type": "phase", "to": to, "skipped": skipped})
    return {"moved": to, **({"skipped": skipped} if skipped else {})}


@tool("close_session", tier="consult", effect="write",
      card=Card("Close the thread with its summary and what the library failed to answer",
                "check out: briefs closed, work recorded",
                "A session with a project also writes the summary to that project's own "
                "Current Focus, so the pursuit's note reflects where it stands without a "
                "separate write"))
def close_session(ctx: Context, summary: str, gaps: str) -> dict:
    session = _session(ctx)
    missing = session.missing(ctx.vault)
    if missing:
        return {"closed": False, "missing": missing}
    if not summary.strip() or not gaps.strip():
        raise TypeError("a session closes with a summary and the gaps (write 'none' if the "
                        "library answered everything)")
    _event(ctx, {"type": "closed", "summary": summary, "gaps": gaps})
    if session.project:
        path = ctx.vault.project_note(session.project)
        if path.is_file():
            loaded = notes.load(path)
            body = notes.with_section(loaded.body, "Current Focus", summary.strip())
            path.write_text(notes.render(loaded.frontmatter, body), encoding="utf-8")
            engine_for(ctx).index.upsert(path)
    return {"closed": session.id}


# ------------------------------------------------------------------- framing

def _axis_value(model, shape: str, field_name: str, value: str) -> None:
    permitted = model.axes_for(shape).get(field_name)
    if permitted and value not in permitted:
        raise TypeError(f"{field_name}={value!r} is not one of {permitted}")


@tool("create_project", tier="contribute", effect="vault_write",
      card=Card("Create the Project note a thread works toward - a pursuit (course, job, "
                "project, research or learning) with its own goal, milestones and focus",
                "framing a new project",
                "Fixed constraints are axis values; standing disqualifiers apply to every brief"))
def create_project(ctx: Context, name: str, stage: str, summary: str,
                   constraints: dict | None = None, disqualifiers: list[str] | None = None,
                   aliases: list[str] | None = None, repository: str = "",
                   pursuit_kind: str = "project", started: str = "", horizon: str = "",
                   goal: str = "") -> dict:
    safe = notes.safe_name(name)
    if not safe:
        raise TypeError("a project needs a name")
    engine = engine_for(ctx, refresh=False)
    model = engine.index.model
    _axis_value(model, "project", "pursuit_kind", pursuit_kind)
    _axis_value(model, "project", "stage", stage)
    bounds = Constraints.of(constraints, engine.permitted_axes("source"))
    path = ctx.vault.root / "Projects" / f"{safe}.md"
    if path.exists():
        _event(ctx, {"type": "plan", "fields": {"project": safe}})
        return {"exists": True, "project": safe, "path": f"Projects/{safe}.md"}
    fm: dict[str, Any] = {"type": "project", "status": "active", "stage": stage,
                          "pursuit_kind": pursuit_kind, "session": ctx.session or ""}
    if aliases:
        fm["aliases"] = aliases
    if bounds.values:
        fm["constraints"] = {a: list(v) for a, v in bounds.values.items()}
    if disqualifiers:
        fm["disqualifiers"] = disqualifiers
    if repository:
        fm["repository"] = repository
    if started:
        fm["started"] = started
    if horizon:
        fm["horizon"] = horizon
    body = notes.compose(safe, [
        ("Summary", summary),
        ("Goal", goal.strip() or "Not yet stated."),
        ("Milestones", "None yet."),
        ("Current Focus", "Not yet started."),
        ("Fixed Constraints", "\n".join(f"- {a}: {', '.join(v)}" for a, v in
                                        bounds.values.items()) or "None stated."),
        ("Standing Disqualifiers", "\n".join(f"- {d}" for d in disqualifiers or []) or
         "None stated."),
        ("Open Needs", "Recorded as briefs in the sessions that work on this project."),
        ("Decisions", "None recorded."),
        ("Reflections", "None yet.")])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(notes.render(fm, body), encoding="utf-8")
    engine.index.upsert(path)
    if ctx.session:
        _event(ctx, {"type": "plan", "fields": {"project": safe}})
        _event(ctx, {"type": "write", "tool": "create_project", "path": f"Projects/{safe}.md"})
    return {"created": f"Projects/{safe}.md", "project": safe}


@tool("read_project", tier="consult", effect="read",
      card=Card("Read the project's own files, read-only",
                "mapping a project for a suggestion (1A)",
                "Lists the project's repository, or returns one file's text. Never writes to "
                "a project (OBSERVER_WITHOUT_ACTUATION)"))
def read_project(ctx: Context, path: str = "") -> dict:
    session = _session(ctx)
    root = _project_root(ctx, session.project)
    if not path:
        files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*")
                       if p.is_file() and not any(part.startswith(".") for part in
                                                  p.relative_to(root).parts))
        _event(ctx, {"type": "plan", "fields": {"project_read": f"listed {len(files)} files"}})
        return {"root": str(root), "files": files[:MAX_PROJECT_LIST], "total": len(files)}
    target = (root / path).resolve()
    if root not in target.parents or not target.is_file():
        raise TypeError(f"{path!r} is not a file inside the project")
    text = target.read_text(encoding="utf-8", errors="replace")
    _event(ctx, {"type": "plan", "fields": {"project_read": path}})
    return {"path": path, "text": text[:MAX_PROJECT_FILE],
            "truncated": len(text) > MAX_PROJECT_FILE,
            "cite_as": f"project:{path}"}


# --------------------------------------------------------------- W2 · learn

@tool("understanding_record", tier="contribute", effect="vault_write",
      returns=("concept", "recorded"),
      card=Card("Record what the person understands about a concept, in their own words",
                "a learn session's practice or consolidate phase",
                "own_words is the person's own explanation, never the model's paraphrase of "
                "it - appended, dated, to the concept's own Understanding section"))
def understanding_record(ctx: Context, concept: str, own_words: str,
                         confidence: Literal["shaky", "ok", "solid"]) -> dict:
    if not own_words.strip():
        raise TypeError("own_words needs the person's own explanation, not a summary of it")
    engine = engine_for(ctx)
    row = engine.index.note_row(concept)
    if row is None or row["shape"] != "concept":
        raise TypeError(f"no concept named {concept!r}; names are exact")
    path = ctx.vault.root / row["path"]
    loaded = notes.load(path)
    # The person's local date - the same calendar `agenda` buckets review tasks by.
    entry = (f"- {date.today().isoformat()} (confidence: {confidence}): "
             f"{notes.one_line(own_words, 'own_words')}")
    body = notes.append_to_section(loaded.body, "Understanding", entry)
    path.write_text(notes.render(loaded.frontmatter, body), encoding="utf-8")
    engine.index.upsert(path)
    if ctx.session:
        _event(ctx, {"type": "write", "tool": "understanding_record", "concept": row["name"],
                     "path": row["path"]})
    return {"concept": row["name"], "recorded": entry}


UNDERSTANDING_REVIEW = re.compile(r"^Review: (.+)$")


@tool("understanding_due", tier="consult", effect="read",
      returns=("due",),
      card=Card("Concepts with a review task that is due today or overdue",
                "starting a learn session's spaced review, if the Spaced Repetition plugin "
                "is not installed",
                "Reads the review tasks `task_add(heading='Understanding')` writes on a "
                "concept's own note - the same checkboxes agenda() already scans"))
def understanding_due(ctx: Context) -> dict:
    return {"due": _due_reviews(ctx)}


def _due_reviews(ctx: Context) -> list[dict[str, str]]:
    buckets = _agenda.scan(ctx.vault)
    due = []
    for bucket in ("overdue", "today"):
        for entry in buckets[bucket]:
            match = UNDERSTANDING_REVIEW.match(entry["text"])
            if match:
                due.append({"concept": match.group(1).strip(), "note": entry["note"],
                           "due": entry["due"]})
    return due


@tool("review_due_open", tier="contribute", effect="write",
      returns=("opened", "already_waiting"),
      card=Card("Open a parked learn session for each concept whose review is due",
                "review tasks have piled up and the Spaced Repetition plugin is not installed",
                "Each opens framed for a review (goal, baseline and focus filled), parked for "
                "the person to resume from Sessions; a concept with a review already open or "
                "parked is skipped, so running it twice opens nothing new"))
def review_due_open(ctx: Context, limit: int = 5) -> dict:
    """Roadmap §2 W4's auto-open half (§4 D4). A learn session walks goal ->
    baseline -> focus before practice (phases are never skipped), so a review
    is opened with those three already recorded: resuming it, each advances
    at once, and the person's time goes to the practice itself."""
    store = _store(ctx)
    waiting = {row["question"] for row in store.list()
               if row["purpose"] == "learn" and row["status"] in ("open", "parked")}
    opened, skipped, seen = [], [], set()
    for entry in _due_reviews(ctx):
        concept = entry["concept"]
        question = f"Review: {concept}"
        if concept.casefold() in seen:
            continue
        seen.add(concept.casefold())
        if question in waiting:
            skipped.append(concept)
            continue
        if len(opened) >= max(1, limit):
            break
        session = store.new("learn", "", question)
        store.append(session.id, {"type": "plan", "fields": {
            "goal": f"Recall and use {concept} again: its review fell due on {entry['due']}",
            "baseline": "Learned before (see its Understanding section); this is a spaced review",
            "focus": [concept]}})
        store.append(session.id, {"type": "status", "status": "parked",
                                  "note": "opened by review_due_open: resume it to review"})
        opened.append({"session": session.id, "concept": concept, "due": entry["due"],
                       "note": entry["note"]})
    return {"opened": opened, "already_waiting": skipped}


def _project_root(ctx: Context, project: str) -> Path:
    if not project:
        raise Refusal("SESSION_REQUIRED", "this session has no project")
    note = notes.load(ctx.vault.project_note(project))
    repository = str(note.frontmatter.get("repository") or "")
    root = Path(repository).expanduser()
    if not repository or not root.is_absolute() or not root.is_dir():
        raise TypeError(f"Project {project!r} names no local repository folder "
                        f"(`repository:` must be an absolute path to a folder)")
    return root.resolve()


# -------------------------------------------------------------------- needs

@tool("open_brief", tier="contribute", effect="write",
      card=Card("State a need, what a candidate must not assume, and any fixed constraints",
                "the Need phase", "A brief without a disqualifier becomes a question for "
                                  "the person, not a refusal"))
def open_brief(ctx: Context, need: str, disqualifiers: list[str] | None = None,
               constraints: dict | None = None) -> dict:
    session = _session(ctx)
    engine = engine_for(ctx)
    project_fm: dict[str, Any] = {}
    if session.project:
        project_fm = notes.load(ctx.vault.project_note(session.project)).frontmatter
    merged = {**(project_fm.get("constraints") or {}), **(constraints or {})}
    bounds = Constraints.of(merged, engine.permitted_axes("source"))
    standing = [d for d in project_fm.get("disqualifiers") or [] if d]
    stated = [d.strip() for d in disqualifiers or [] if d.strip()]
    if not stated and not standing:
        return {**_ask(ctx, f"For the need {need!r}: what must a candidate not assume, "
                            f"require or depend on? (BRIEF_REQUIRED)", "disqualifier"),
                "brief_opened": False}
    verdict = search(engine, need, "donor", merged, limit=5)
    # A person's own wording rarely matches the field's vocabulary; let the
    # clerk translate it once, up front, so the first research_round has
    # better queries to start from than the need's own phrasing (V1's
    # search_queries - degrades to the need itself if nothing usable comes
    # back, never blocking the brief on it).
    drafted = clerk.run([clerk.queries(need)], clerk_endpoint(ctx),
                        ctx.vault.work("queue") / "clerk")[0]
    suggested = [str(q).strip() for q in drafted.value.get("queries", [])
                if drafted.ok and str(q).strip()] or [need]
    brief_id = f"B{len(session.briefs) + 1}"
    _event(ctx, {"type": "brief", "id": brief_id, "need": need,
                 "disqualifiers": stated + [d for d in standing if d not in stated],
                 "constraints": {a: list(v) for a, v in bounds.values.items()},
                 "verdict": verdict.verdict, "suggested_queries": suggested})
    return {"brief": brief_id, "verdict": verdict.verdict,
            "already_held": [r.name for r in verdict.results[:5]],
            "coverage": verdict.coverage.get("sentence", ""),
            "suggested_queries": suggested}


@tool("close_brief", tier="contribute", effect="write",
      card=Card("Close a brief with what was decided about it", "a need is settled"))
def close_brief(ctx: Context, brief: str, note: str) -> dict:
    session = _session(ctx)
    if brief not in session.briefs:
        raise TypeError(f"no brief {brief!r}; briefs: {sorted(session.briefs)}")
    _event(ctx, {"type": "brief_closed", "id": brief, "note": note})
    return {"closed": brief}


# ------------------------------------------------------------------- search

@tool("research_round", tier="contribute", effect="write",
      card=Card("Run one research round: the queries, against the catalogue first",
                "the Search phase; the queries come from the last checkpoint, not the "
                "original wording",
                "New results become candidates. Outside search arrives with intake (M4)"))
def research_round(ctx: Context, queries: list[str], brief: str = "", limit: int = 8,
                   outside: bool = False) -> dict:
    session = _session(ctx)
    if not queries:
        raise TypeError("a round needs at least one query")
    if brief and brief not in session.briefs:
        raise TypeError(f"no brief {brief!r}; briefs: {sorted(session.briefs)}")
    engine = engine_for(ctx)
    constraints = session.briefs[brief].constraints if brief else {}
    seen_vocab = {w for r in session.rounds for w in r.get("vocabulary", [])}
    seen_vocab |= {t.lower() for q in queries for t in terms_from(q)}
    for r in session.rounds:
        seen_vocab |= {t.lower() for q in r.get("queries", []) for t in terms_from(q)}
    new, vocabulary, per_query = [], [], []
    for query in queries[:6]:
        response = search(engine, query, "donor", constraints, limit=limit)
        names = []
        for result in response.results:
            names.append({"name": result.name, "why": result.why})
            if result.name not in session.candidates and \
                    result.name not in {c["source"] for c in new}:
                new.append({"source": result.name, "brief": brief, "query": query})
            for word in terms_from(f"{result.fields.get('title', '')} "
                                   f"{result.fields.get('topic', '')}"):
                low = word.lower()
                if low not in seen_vocab and low not in vocabulary and not low.isdigit():
                    vocabulary.append(low)
        entry = {"query": query, "verdict": response.verdict, "results": names}
        if outside:
            entry["outside"] = _outside(ctx, query, limit, seen_vocab, vocabulary, new, brief)
        per_query.append(entry)
    n = len(session.rounds) + 1
    _event(ctx, {"type": "round", "n": n, "queries": queries[:6],
                 "new": [c for c in new if not c.get("outside")],
                 "vocabulary": vocabulary[:40],
                 "outside_found": [c for c in new if c.get("outside")],
                 "outside": "searched" if outside else "not searched (outside=false)"})
    return {"round": n, "new_candidates": [c["source"] for c in new if not c.get("outside")],
            "outside_found": [{k: c[k] for k in ("ref", "title", "description")}
                              for c in new if c.get("outside")],
            "new_vocabulary": vocabulary[:40], "queries": per_query,
            "next": "ingest(ref, brief) the outside finds worth screening; they become "
                    "candidates when staged" if outside else ""}


def _outside(ctx: Context, query: str, limit: int, seen_vocab: set[str], vocabulary: list[str],
             new: list[dict], brief: str) -> list[dict]:
    """GitHub and arXiv for one query. Finds are listed, not ingested: the
    model chooses what to screen, and screening is `ingest` with the brief."""
    from .. import scout
    from .intake import _fetcher
    fetcher = _fetcher(ctx)
    session = _session(ctx)
    found: list[dict] = []
    try:
        for item in scout.search_github(query, fetcher, per_page=limit):
            found.append({"ref": item.get("full_name", ""),
                          "title": item.get("full_name", "").replace("/", " - "),
                          "description": item.get("description") or ""})
    except Exception as exc:                                # noqa: BLE001
        found.append({"ref": "", "title": "", "description": f"GitHub search failed: {exc}"})
    try:
        for item in scout.search_arxiv(query, fetcher, limit):
            found.append(item)
    except Exception as exc:                                # noqa: BLE001
        found.append({"ref": "", "title": "", "description": f"arXiv search failed: {exc}"})
    # The open web too, once a real web backend is set up (websearch.py);
    # the keyless Wikipedia fallback is left to web_search, asked for by name.
    from .. import websearch
    if websearch.backend(ctx.vault) != "wikipedia":
        try:
            for item in websearch.search(query, "web", limit, vault=ctx.vault,
                                         fetcher=fetcher)["results"]:
                found.append({"ref": item["url"], "title": item["title"] or item["url"],
                              "description": item["snippet"]})
        except Exception as exc:                            # noqa: BLE001
            found.append({"ref": "", "title": "", "description": f"web search failed: {exc}"})
    known = {c["ref"] for r in session.rounds for c in r.get("outside_found", [])}
    out = []
    for item in found:
        if not item["ref"] or item["ref"] in known or item["ref"] in {c.get("ref") for c in new}:
            continue
        out.append(item)
        new.append({**item, "source": item["title"], "brief": brief, "query": query,
                    "outside": True})
        for word in terms_from(item["title"]):
            low = word.lower()
            if low not in seen_vocab and low not in vocabulary and not low.isdigit():
                vocabulary.append(low)
    return out


@tool("checkpoint", tier="contribute", effect="write",
      card=Card("Close a round: what was learned, the field's own vocabulary, 2-4 open "
                "sub-threads and the next named targets",
                "after every research_round",
                "The stopping rule is computed here: a round with no new candidates and no "
                "new vocabulary ends the Search phase"))
def checkpoint(ctx: Context, learned: str, subthreads: list[str] | None = None,
               next_targets: list[str] | None = None, vocabulary: list[str] | None = None) -> dict:
    session = _session(ctx)
    if not session.rounds:
        raise TypeError("run a research_round before its checkpoint")
    last = session.rounds[-1]
    if len(session.checkpoints) >= len(session.rounds):
        raise TypeError(f"round {last['n']} already has its checkpoint; run the next round")
    stop = not last.get("new") and not last.get("outside_found") and not last.get("vocabulary")
    subthreads = [s for s in subthreads or [] if s.strip()]
    targets = [t for t in next_targets or [] if t.strip()]
    if not stop:
        if not 2 <= len(subthreads) <= 4:
            raise TypeError("name 2-4 open sub-threads (the stopping rule has not fired)")
        if not targets:
            raise TypeError("name the next specific target: the next round starts from it")
    _event(ctx, {"type": "checkpoint", "round": last["n"], "learned": learned,
                 "vocabulary": vocabulary or [], "subthreads": subthreads,
                 "next_targets": targets, "stop": stop,
                 "stop_reason": "the last round added no new candidates and no new "
                                "vocabulary" if stop else ""})
    return {"round": last["n"], "stop": stop}


@tool("add_candidate", tier="contribute", effect="write",
      card=Card("Put a catalogued source forward as a candidate by hand",
                "you know of a source a round did not surface"))
def add_candidate(ctx: Context, source: str, brief: str = "") -> dict:
    engine = engine_for(ctx)
    if engine.index.note_row(source) is None:
        raise TypeError(f"no note named {source!r}")
    _event(ctx, {"type": "candidate", "source": source, "brief": brief})
    return {"candidate": source}



@tool("log_use", tier="consult", effect="write",
      card=Card("Record that a source was used, and for what",
                "you opened or relied on a source"))
def log_use(ctx: Context, source: str, used_for: str) -> dict:
    engine = engine_for(ctx)
    if engine.index.note_row(source) is None:
        raise TypeError(f"no note named {source!r}")
    _event(ctx, {"type": "use", "source": source, "used_for": used_for})
    return {"logged": source}


# -------------------------------------------------------------------- judge

@tool("decide", tier="contribute", effect="write",
      card=Card("Decide a candidate: keep (with the role it would play), reject or defer "
                "(with the reason)", "the Judge phase"))
def decide(ctx: Context, source: str, disposition: Literal["keep", "reject", "defer"],
           reason: str = "", role: str = "") -> dict:
    session = _session(ctx)
    if source not in session.candidates:
        raise TypeError(f"{source!r} is not a candidate in this session")
    if disposition == "keep" and not role.strip():
        raise TypeError("a kept candidate needs its role: what would it do in this project?")
    if disposition in ("reject", "defer") and not reason.strip():
        raise TypeError(f"a {disposition}ed candidate needs its reason")
    _event(ctx, {"type": "decision", "source": source, "disposition": disposition,
                 "reason": reason, "role": role})
    left = sum(1 for c in _session(ctx).candidates.values() if c.disposition == "undecided")
    return {"decided": source, "undecided_left": left}


# --------------------------------------------------------------- synthesise

@tool("record_synthesis", tier="contribute", effect="write",
      card=Card("Record the cross-source synthesis over what survived Judge",
                "the Synthesise phase, before any offering",
                "outcome 'nothing' with a reason is a complete answer"))
def record_synthesis(ctx: Context, outcome: Literal["offering", "nothing"], together: str,
                     unknowns: str, open_first: str = "", cost: str = "",
                     reason: str = "") -> dict:
    session = _session(ctx)
    kept = [c.source for c in session.candidates.values() if c.disposition == "keep"]
    if outcome == "offering" and not kept:
        raise TypeError("nothing was kept; record outcome 'nothing' with the reason")
    if outcome == "nothing" and not reason.strip():
        raise TypeError("'nothing worth offering' needs its reason")
    _event(ctx, {"type": "synthesis", "outcome": outcome, "together": together,
                 "unknowns": unknowns, "open_first": open_first, "cost": cost,
                 "reason": reason, "kept": kept})
    return {"recorded": outcome, "kept": kept}


def _normal(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"') \
        .replace("”", '"').replace("—", "-").replace("–", "-")
    text = re.sub(r"[*_`>#]", "", text)
    return " ".join(text.lower().split())


def _quote_found(ctx: Context, engine, source: str, quote: str) -> str:
    """Where the quote was found, or empty. Looks in the Source note, its
    evidence records, or (for `project:<path>`) the project's own file."""
    return _quote_source(ctx, engine, source, quote)[0]


def _quote_source(ctx: Context, engine, source: str, quote: str) -> tuple[str, str]:
    """Where the quote was found and the text it was found in, or ("", "")."""
    needle = _normal(quote)
    if source.startswith("project:"):
        session = _session(ctx)
        root = _project_root(ctx, session.project)
        target = (root / source[len("project:"):]).resolve()
        if root in target.parents and target.is_file():
            text = target.read_text(encoding="utf-8", errors="replace")
            if needle in _normal(text):
                return source, text
        return "", ""
    row = engine.index.note_row(source)
    if row is None:
        return "", ""
    text = (ctx.vault.root / row["path"]).read_text(encoding="utf-8", errors="replace")
    if needle in _normal(text):
        return f"note:{row['name']}", text
    fm = json.loads(row["frontmatter"])
    ids = [str(i) for i in fm.get("evidence") or [] if i] if isinstance(
        fm.get("evidence"), list) else []
    store = EvidenceStore(ctx.vault)
    url = str(fm.get("canonical_url") or "")
    for record in store.iter():
        if record.id in ids or (url and record.source == url):
            if needle in _normal(json.dumps(record.payload, ensure_ascii=False)):
                return f"evidence:{record.id}", "\n\n".join(
                    str(v) for v in record.payload.values() if isinstance(v, str))
    for doc in engine.conn.execute("SELECT text FROM chunk WHERE note = ? AND role = "
                                   "'document'", (row["name"],)):
        if needle in _normal(doc["text"]):
            return f"document:{row['name']}", doc["text"]
    return "", ""


@tool("draft_offering", tier="contribute", effect="write",
      card=Card("Draft the offering: a summary and claims, each with the exact quote it "
                "rests on", "the Synthesise phase, after record_synthesis",
                "Every quote is verified before anything is written; the draft is staged, "
                "not written into the vault"))
def draft_offering(ctx: Context, title: str, summary: str, claims: list[dict],
                   kind: Literal["branch_offering", "insight_report", "suggestion"] =
                   "branch_offering") -> dict:
    session = _session(ctx)
    if session.synthesis is None:
        raise TypeError("record_synthesis first: the offering is written from it")
    if not claims:
        raise TypeError("an offering makes at least one claim")
    engine = engine_for(ctx)
    failures, checked = [], []
    for i, claim in enumerate(claims, 1):
        text = str(claim.get("text") or "").strip()
        source = str(claim.get("source") or "").strip()
        quote = str(claim.get("quote") or claim.get("evidence_quote") or "").strip()
        if not text or not source or not quote:
            failures.append(f"claim {i}: needs text, source and quote")
            continue
        if len(quote.split()) < MIN_QUOTE_WORDS:
            failures.append(f"claim {i}: a quote of fewer than {MIN_QUOTE_WORDS} words "
                            f"proves nothing")
            continue
        where = _quote_found(ctx, engine, source, quote)
        if not where:
            failures.append(f"claim {i}: the quote was not found in {source!r}")
            continue
        checked.append({"text": text, "source": source, "quote": quote, "found_in": where})
    if failures:
        raise Refusal("EVIDENCE_QUOTE_VERIFIED", "; ".join(failures))
    review = _review_claims(ctx, engine, checked) if _reviewing(ctx) else []
    challenges = []
    for i, (claim, c, verdict) in enumerate(zip(claims, checked, review), 1):
        if verdict["verdict"] != "fails":
            continue
        rebuttal = str(claim.get("rebuttal") or "").strip()
        if rebuttal:
            c["challenge"] = {**verdict, "rebuttal": rebuttal}
        else:
            challenges.append(f"claim {i}: {verdict['reason']} The passage says: "
                              f"\"{verdict['counter_quote']}\"")
    if review:
        _event(ctx, {"type": "review", "of": "draft_offering", "verdicts": [
            {"claim": c["text"][:200], **v} for c, v in zip(checked, review)]})
    if challenges:
        raise Refusal("REVIEW_CHALLENGED", "; ".join(challenges) + ". Revise the claim, or "
                      "keep it with claims[i].rebuttal - then the person decides")
    slug = notes.safe_name(title)
    offering_id = f"{session.id}-{re.sub(r'[^a-z0-9]+', '-', slug.lower()).strip('-')[:40]}"
    sources = sorted({c["source"] for c in checked if not c["source"].startswith("project:")})
    fm = {"type": "offering", "offering_kind": kind, "status": "draft",
          "created": session.opened_at[:10], "sources": [f"[[{s}]]" for s in sources],
          "project": session.project, "attested_by": "agent", "session": session.id}
    # The prose is the scribe's to write, from these parts alone; the quotes
    # are set by code, verbatim, under their claims.
    written = scribe.compose(scribe.offering(slug, summary, checked, session.synthesis),
                             scribe_endpoint(ctx))
    prose = written["sections"]
    claims_md = "\n\n".join(
        f"{i}. {text}\n   > {c['quote']}\n   - {_cite(c['source'])} ({c['found_in']})"
        + (f"\n   - ⚑ Challenged by review: {c['challenge']['reason']} The passage says: "
           f"\"{c['challenge']['counter_quote']}\" Kept because: {c['challenge']['rebuttal']}"
           if c.get("challenge") else "")
        for i, (c, text) in enumerate(zip(checked, written["claims"]), 1))
    kept = sum(1 for c in checked if c.get("challenge"))
    if review:
        fm["review"] = {"by": next((v["model"] for v in review if v["model"]), ""),
                        **{k: sum(v["verdict"] == k for v in review)
                           for k in ("holds", "unchecked", "queued")},
                        "challenged_kept": kept}
    body = notes.compose(slug, [
        ("Summary", prose.get("summary", summary)), ("Claims", claims_md),
        ("Together", prose.get("together", "")),
        ("Unknowns", prose.get("unknowns", "")),
        ("Open First", prose.get("open_first", "") or "Not stated."),
        ("Sources", "\n".join(f"- [[{s}]]" for s in sources))])
    staging = ctx.vault.work("staging") / "offerings"
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / f"{offering_id}.md"
    path.write_text(notes.render(fm, body), encoding="utf-8")
    rel = path.relative_to(ctx.vault.root).as_posix()
    _event(ctx, {"type": "offering", "id": offering_id, "title": slug, "status": "staged",
                 "path": rel, "claims": len(checked), **({"challenged": kept} if kept else {})})
    return {"staged": rel, "offering": offering_id, "claims_verified": len(checked),
            "composed_by": written["composed_by"],
            **({"kept_as_given": written["kept_as_given"]} if written["kept_as_given"]
               else {}),
            **({"scribe_error": written["scribe_error"]} if "scribe_error" in written
               else {})}


REVIEW_WINDOW = 2000         # characters of the source either side of a claim's quote


def _reviewing(ctx: Context) -> bool:
    """§4 G3 is opt-in per library: `review_offerings = true` under [clerk],
    routed like any clerk task (`route_review = "<provider>:<model>"`)."""
    return bool((ctx.vault.config().get("clerk") or {}).get("review_offerings"))


def _review_claims(ctx: Context, engine, checked: list[dict]) -> list[dict[str, str]]:
    """One `review` task per claim: the claim, its quote and the passage the
    quote sits in - never the draft, its summary or the synthesis, so the
    draft's framing cannot lean on the verdict (Chain-of-Verification)."""
    tasks = []
    for c in checked:
        text = _quote_source(ctx, engine, c["source"], c["quote"])[1]
        at = clerk.locate(c["quote"], text)
        start = max(0, at - REVIEW_WINDOW) if at >= 0 else 0
        tasks.append(clerk.review(c["text"], c["quote"],
                                  text[start:(at if at >= 0 else 0) + len(c["quote"])
                                       + REVIEW_WINDOW]))
    out = []
    for r in clerk.run(tasks, clerk_endpoint(ctx), ctx.vault.work("queue") / "clerk"):
        verdict = r.value.get("verdict", "unchecked") if r.ok else (
            "queued" if r.status == "queued" else "unchecked")
        if verdict == "unsupported":        # the quote was found; a silent passage proves nothing
            verdict = "unchecked"
        out.append({"verdict": verdict, "counter_quote": str(r.value.get("counter_quote", "")),
                    "reason": str(r.value.get("reason", "")), "model": r.model or ""})
    return out


def _cite(source: str) -> str:
    return f"`{source}`" if source.startswith("project:") else f"[[{source}]]"


@tool("promote_offering", tier="contribute", effect="vault_write",
      card=Card("Move a staged offering into the vault, as the vault's promotion setting "
                "allows", "the offering is drafted",
                "Under promotion.mode = 'person' this asks the person first"))
def promote_offering(ctx: Context, offering: str) -> dict:
    session = _session(ctx)
    record = next((o for o in session.offerings if o["id"] == offering), None)
    if record is None or record.get("status") != "staged":
        raise TypeError(f"no staged offering {offering!r} in this session")
    mode = str(ctx.vault.setting("promotion", "mode") or "person")
    # A claim the review challenged and the lead model kept is for a person to
    # weigh, whatever the promotion setting (§4 G3).
    if record.get("challenged"):
        mode = "person"
    if mode != "agent":
        confirmed = session.answered("confirm", offering)
        if confirmed is None:
            if any(q["kind"] == "confirm" and q.get("ref") == offering
                   for q in session.open_questions()):
                return {"promoted": False, "waiting_for": "the person's answer"}
            return {**_ask(ctx, f"Promote the offering {record['title']!r} "
                                f"({record['path']}) into the vault?", "confirm", offering,
                           ["yes", "no"]), "promoted": False}
        if str(confirmed["answer"]).strip().lower() not in ("yes", "y", "promote"):
            _event(ctx, {"type": "offering", "id": offering, "status": "declined"})
            return {"promoted": False, "declined_by_person": True}
    source = ctx.vault.root / record["path"]
    folder = session.project or "Insights"
    destination = ctx.vault.root / "Offerings" / notes.safe_name(folder) / f"{record['title']}.md"
    if destination.exists():
        raise TypeError(f"{destination.relative_to(ctx.vault.root)} already exists")
    note = notes.load(source)
    note.frontmatter["status"] = "active"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(notes.render(note.frontmatter, note.body), encoding="utf-8")
    source.unlink()
    rel = destination.relative_to(ctx.vault.root).as_posix()
    engine_for(ctx, refresh=False).index.upsert(destination)
    _event(ctx, {"type": "offering", "id": offering, "status": "promoted", "path": rel})
    _event(ctx, {"type": "write", "tool": "promote_offering", "path": rel})
    return {"promoted": rel, "by": "agent setting" if mode == "agent" else "person"}


# ----------------------------------------------------------------- check out

@tool("record_application", tier="consult", effect="vault_write",
      card=Card("Record what was applied, where, what it replaced, and what the library "
                "should learn", "checking out of an apply session"))
def record_application(ctx: Context, title: str, stage: str, outcome: str,
                       sources_used: list[str], needed: str, found_and_taken: str,
                       replaced: str, should_learn: str) -> dict:
    session = _session(ctx)
    engine = engine_for(ctx)
    unknown = [s for s in sources_used if engine.index.note_row(s) is None]
    if not sources_used or unknown:
        raise TypeError("an application must reach at least one catalogued source"
                        + (f"; not notes: {unknown}" if unknown else ""))
    name = notes.safe_name(title if title.startswith("Application - ")
                           else f"Application - {title}")
    path = ctx.vault.root / "Applications" / f"{name}.md"
    if path.exists():
        raise TypeError(f"Applications/{name}.md already exists")
    fm = {"type": "application", "project": session.project or session.question,
          "stage": stage, "outcome": outcome, "sources_used": [f"[[{s}]]" for s in sources_used],
          "attested_by": "agent", "session": session.id}
    body = notes.compose(name, [("What Was Needed", needed),
                                ("What Was Found And Taken", found_and_taken),
                                ("What It Replaced", replaced),
                                ("What The Catalogue Should Learn", should_learn)])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(notes.render(fm, body), encoding="utf-8")
    engine.index.upsert(path)
    rel = path.relative_to(ctx.vault.root).as_posix()
    _event(ctx, {"type": "write", "tool": "record_application", "path": rel})
    return {"recorded": rel}


# --------------------------------------------------------------- W3 · weekly-review

_RELATIVE_SINCE = re.compile(r"^-(\d+)([dw])$")


def _since_cutoff(since: str) -> str:
    """A UTC ISO timestamp, comparable with every event's own `t`. Anything
    that is not an offset or a real date/time is refused: comparing a stray
    string against timestamps silently matched everything before."""
    since = since.strip()
    match = _RELATIVE_SINCE.match(since)
    if match:
        days = int(match.group(1)) * (7 if match.group(2) == "w" else 1)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return cutoff.isoformat(timespec="seconds")
    try:
        if len(since) == 10:                     # a date: the start of that day, locally
            moment = datetime.combine(date.fromisoformat(since), datetime.min.time()).astimezone()
        else:
            moment = datetime.fromisoformat(since)
            if moment.tzinfo is None:
                moment = moment.astimezone()
    except ValueError:
        raise TypeError(f"since is an offset ('-7d', '-2w') or an ISO date/time, not "
                        f"{since!r}") from None
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


@tool("activity", tier="consult", effect="read",
      returns=("since", "uses", "writes"),
      card=Card("What was read and written across every session, since a cutoff",
                "a weekly review, or catching up on cross-session work",
                "`since` accepts a relative offset ('-7d') or an ISO date/time. Unlike a "
                "single session's own uses/writes, this crosses every session in the vault"))
def activity(ctx: Context, since: str = "-7d", project: str = "") -> dict:
    cutoff = _since_cutoff(since)
    store = _store(ctx)
    uses: list[dict] = []
    writes: list[dict] = []
    for row in store.list():
        if project and row["project"] != project:
            continue                      # a pursuit's review reads only its own threads
        session = store.load(row["id"])
        for u in session.uses:
            if u.get("t", "") >= cutoff:
                uses.append({"session": session.id, "project": session.project, **u})
        for w in session.writes:
            if w.get("t", "") >= cutoff:
                writes.append({"session": session.id, "project": session.project, **w})
    uses.sort(key=lambda e: e.get("t", ""))
    writes.sort(key=lambda e: e.get("t", ""))
    return {"since": cutoff, "uses": uses, "writes": writes}


@tool("reflection_draft", tier="contribute", effect="write",
      returns=("project", "gathered", "draft", "ok"),
      card=Card("Draft a short reflection from a week's own gathered tasks, activity and desk",
                "a weekly review, once agenda/activity/desk_show have been gathered",
                "Grounded only in what is passed in - gathered facts, never source evidence - "
                "and never written to the vault by this tool: reflection_accept does that, "
                "after a person has read it"))
def reflection_draft(ctx: Context, project: str, agenda_buckets: dict, activity_summary: dict,
                     desk: dict | None = None) -> dict:
    lines = ["Tasks:"]
    for bucket in ("overdue", "today", "this_week"):
        for item in (agenda_buckets or {}).get(bucket, [])[:10]:
            lines.append(f"- [{bucket}] {item.get('text', '')} ({item.get('note', '')})")
    lines.append("Activity:")
    for u in (activity_summary or {}).get("uses", [])[:15]:
        lines.append(f"- used {u.get('source', '')} for {u.get('used_for', '')}")
    for w in (activity_summary or {}).get("writes", [])[:15]:
        lines.append(f"- wrote via {w.get('tool', '')} "
                     f"({w.get('path') or w.get('concept') or ''})")
    titles = [row.get("note", "") for row in (desk or {}).get("working_set", [])]
    if titles:
        lines.append("On the desk: " + ", ".join(titles))
    gathered = "\n".join(lines)
    drafted = clerk.run([clerk.reflection(gathered)], clerk_endpoint(ctx),
                        ctx.vault.work("queue") / "clerk")[0]
    text = str(drafted.value.get("reflection", "")).strip() if drafted.ok else ""
    return {"project": project, "gathered": gathered, "draft": text, "ok": drafted.ok,
            "drafted_by": drafted.model if drafted.ok else ""}


@tool("reflection_accept", tier="curate", effect="vault_write",
      returns=("project", "recorded"),
      card=Card("Append a reflection to a pursuit's own Reflections section",
                "a person has read a drafted (or their own) reflection and wants it kept",
                "Person-only: a reflection is never written to the vault except by a "
                "person's own decision, whatever it was drafted from"))
def reflection_accept(ctx: Context, project: str, text: str) -> dict:
    if not text.strip():
        raise TypeError("a reflection needs text")
    engine = engine_for(ctx)
    row = engine.index.note_row(project)
    if row is None or row["shape"] != "project":
        raise TypeError(f"no pursuit named {project!r}; create_project first")
    path = ctx.vault.root / row["path"]
    loaded = notes.load(path)
    entry = f"- {date.today().isoformat()}: {notes.one_line(text, 'a reflection')}"
    body = notes.append_to_section(loaded.body, "Reflections", entry)
    path.write_text(notes.render(loaded.frontmatter, body), encoding="utf-8")
    engine.index.upsert(path)
    return {"project": row["name"], "recorded": entry}


@tool("task_route", tier="curate", effect="vault_write",
      returns=("note", "task", "action"),
      card=Card("Triage one overdue task: reschedule it, drop it, or keep it as is",
                "a weekly review's overdue list - decided by the person, never the model",
                "Person-only, matching the roadmap's own rule that overdue triage is a "
                "person's call at review time"))
def task_route(ctx: Context, note: str, text: str,
              action: Literal["reschedule", "drop", "keep"], new_due: str = "") -> dict:
    engine = engine_for(ctx)
    row = engine.index.note_row(note)
    if row is None:
        raise TypeError(f"no note named {note!r}; names are exact, including owner prefixes")
    if action == "keep":
        return {"note": row["name"], "task": text, "action": "keep"}
    path = ctx.vault.root / row["path"]
    loaded = notes.load(path)
    task = _agenda.find_open(loaded.body, text)
    if task is None:
        raise TypeError(f"no open task {text!r} on {note!r}")
    if action == "drop":
        # The whole line goes, with its own line ending (LF or CRLF alike).
        newline = loaded.body.find("\n", task.end)
        body = (loaded.body[:task.start] + loaded.body[newline + 1:] if newline != -1
                else loaded.body[:task.start].rstrip("\r\n") + "\n")
    else:
        if not new_due or not DUE_DATE.match(new_due):
            raise TypeError("reschedule needs new_due (YYYY-MM-DD)")
        # Only the date changes: indentation, status and any other Tasks
        # signifiers (priority, recurrence) stay exactly as the person wrote them.
        line = (_agenda.DUE.sub(f"📅 {new_due}", task.line, count=1)
                if _agenda.DUE.search(task.line) else f"{task.line} 📅 {new_due}")
        body = loaded.body[:task.start] + line + loaded.body[task.end:]
    path.write_text(notes.render(loaded.frontmatter, body), encoding="utf-8")
    engine.index.upsert(path)
    return {"note": row["name"], "task": text, "action": action}
