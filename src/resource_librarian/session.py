"""The session harness: a research thread as an append-only event log.

A session is `.librarian/sessions/<id>.jsonl`. Every change is an event
appended to it, and the session's state is a fold over its events, so resuming
a thread is replaying its file, and nothing about a thread lives only in a
process's memory.

What the harness does, so the model does not have to hold the walk in its head:

- **Phases, per purpose.** `add_project`, `explore`, `suggest` (1A) and
  `apply` each walk their own path. A phase has an exit condition; `advance`
  refuses to leave until it is met and says what is missing.
- **Phases gate writes, never reads** (`PHASE_GATE`). A write outside the phase
  that unlocks it is refused by name, with the phase that would allow it.
- **Budgets.** Each phase has a call budget; when it is spent, the next tool
  call is refused (`BUDGET_SPENT`) and the model is told to advance, park, or
  ask the person. Harness calls (status, plan, questions) cost nothing.
- **The envelope.** Every tool result inside a session carries
  `{phase, open_items, budget_left, next}`.
- **Questions for the person** are events too. An unanswered question blocks
  `advance`; a write that needs a person's confirmation raises one rather than
  failing.

Framing: the session is the knowledge layer, so it may hold the project, the
need and the checkpoints. None of it is passed to description tasks (M4's
clerk channel), and evidence refuses it structurally (`DATA_IS_UNFRAMED`).
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Callable, Iterator, TypeVar

from . import agenda, audit_events, notes
from .audit_events import AUDIT_EVENTS, AuditState
from .coordination import atomic_write_text
from .rules import Refusal
from .vault import Vault, jsonl_lines, now_iso

T = TypeVar("T")


# ---------------------------------------------------------------- model evidence

# Invocation plans and results deliberately have no session identifier in their
# public diagnostic representation: that keeps a general-purpose runtime trace
# from becoming a cross-session activity feed.  The Loop binds a trace emission
# to the session it is currently walking instead.  Context-local state is
# important here: one Core can run a browser turn and a background task on
# different threads, and a model result must never land in another walk's log.
_MODEL_EVENT_TARGET: ContextVar[tuple[Any, str, list[dict[str, Any]] | None] | None] = \
    ContextVar("librarian_model_event_target", default=None)


def _model_text(value: Any, limit: int = 300) -> str:
    """Bound one piece of route/configuration metadata for session evidence.

    This is intentionally *not* a generic serializer.  Model evidence below
    selects a fixed set of known-safe scalar fields from an invocation trace;
    prompt text, provider payloads, credentials, response text, arguments,
    request ids, and reasoning continuations have no route into this helper.
    """
    return str(value or "").replace("\x00", "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def _model_hash(value: Any) -> str:
    """Keep only the content-addressed hashes the invocation layer produces."""
    text = _model_text(value, 128).casefold()
    return text if re.fullmatch(r"[0-9a-f]{8,128}", text) else ""


def _model_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if 0 <= number <= 2 ** 63 - 1 else None


def _model_usage(value: Any) -> dict[str, int] | str:
    """The small, normalized usage subset; never an arbitrary provider object."""
    if not isinstance(value, Mapping):
        return "unavailable"
    out: dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        number = _model_int(value.get(key))
        if number is not None:
            out[key] = number
    return out or "unavailable"


def _model_adapter(value: Any) -> dict[str, Any]:
    row = value if isinstance(value, Mapping) else {}
    out = {
        "id": _model_text(row.get("id"), 120),
        "version": _model_text(row.get("version"), 80),
        "protocol": _model_text(row.get("protocol"), 120),
    }
    abi = _model_int(row.get("abi"))
    if abi is not None:
        out["abi"] = abi
    return {key: value for key, value in out.items() if value != ""}


def _model_request_event(plan: Any) -> dict[str, Any] | None:
    """Project a plan trace into the durable, redacted request event."""
    if not isinstance(plan, Mapping):
        return None
    plan_id, config_hash = _model_text(plan.get("plan_id"), 80), _model_hash(plan.get("config_hash"))
    if not plan_id or not config_hash:
        return None
    route = plan.get("route") if isinstance(plan.get("route"), Mapping) else {}
    scope = plan.get("scope") if isinstance(plan.get("scope"), Mapping) else {}
    expectation = plan.get("expectation") if isinstance(plan.get("expectation"), Mapping) else {}
    maximum = _model_int(plan.get("max_output_tokens"))
    event: dict[str, Any] = {
        "type": "model_request", "plan_id": plan_id, "config_hash": config_hash,
        "route": {
            "host_id": _model_text(route.get("host_id"), 160),
            "endpoint_fingerprint": _model_hash(route.get("endpoint_fingerprint")),
            "requested_model": _model_text(route.get("requested_model"), 300),
        },
        "adapter": _model_adapter(plan.get("adapter")),
        "scope": {
            "role": _model_text(scope.get("role"), 120),
            "task_id": _model_text(scope.get("task_id"), 120),
            "task_kind": _model_text(scope.get("task_kind"), 120),
            "interaction": _model_text(scope.get("interaction"), 120),
            "phase": _model_text(scope.get("phase"), 80),
            "output_contract": _model_text(scope.get("output_contract"), 120),
        },
        "tool_schema_fingerprint": _model_hash(plan.get("tool_schema_fingerprint")),
        "behavior_mode": _model_text(plan.get("behavior_mode"), 120),
        "reasoning_intent": _model_text(plan.get("reasoning_intent"), 120),
        "expectation": {
            "id": _model_text(expectation.get("id"), 120),
            "fingerprint": _model_hash(expectation.get("fingerprint")),
        },
    }
    if maximum is not None:
        event["max_output_tokens"] = maximum
    # Empty values are less useful than their absence and can imply a field was
    # observed when this version of the runtime did not expose it.
    for key in ("route", "scope", "expectation"):
        event[key] = {name: item for name, item in event[key].items() if item != ""}
    return event


def _model_response_event(result: Any, plan: Any = None) -> dict[str, Any] | None:
    """Project a result trace into the durable, redacted response event."""
    if not isinstance(result, Mapping):
        return None
    plan_row = plan if isinstance(plan, Mapping) else {}
    plan_id = _model_text(result.get("plan_id") or plan_row.get("plan_id"), 80)
    config_hash = _model_hash(result.get("config_hash") or plan_row.get("config_hash"))
    if not plan_id or not config_hash:
        return None
    telemetry = result.get("telemetry") if isinstance(result.get("telemetry"), Mapping) else {}
    failure = result.get("failure") if isinstance(result.get("failure"), Mapping) else {}
    # A fold passes the stored event itself: its failure, retry and usage are
    # already in the durable shape, not the runtime's (delegate review, GLM-5.3).
    retry = result.get("retry") if isinstance(result.get("retry"), Mapping) else {}
    attempts = _model_int(telemetry.get("inner_attempts", retry.get("attempts")))
    outcome = _model_text(result.get("outcome"), 40)
    identity = _model_text(result.get("model_identity"), 40)
    event: dict[str, Any] = {
        "type": "model_response", "plan_id": plan_id, "config_hash": config_hash,
        # The plan carries ABI/protocol; response traces from the initial
        # adapter slice intentionally do not duplicate them.
        "adapter": _model_adapter(plan_row.get("adapter") or result.get("adapter")),
        "route": {
            "requested_model": _model_text(result.get("requested_model"), 300),
            "observed_model": _model_text(result.get("observed_model"), 300),
        },
        "outcome": outcome if outcome in {"completed", "tool_calls", "failed", "cancelled"}
        else "failed",
        "stop_reason": _model_text(result.get("stop_reason"), 160),
        "elapsed_ms": _model_int(result.get("elapsed_ms")) or 0,
        "model_identity": identity if identity in {
            "matched", "absent", "mismatched", "not_applicable"} else "not_applicable",
        "retry": {"attempts": attempts if attempts is not None else "unavailable"},
        "usage": _model_usage(telemetry.get("usage", result.get("usage"))),
    }
    if failure:
        event["failure"] = {
            "class": _model_text(failure.get("category") or failure.get("class"), 80) or "unknown",
            "retryable": bool(failure.get("retryable")),
        }
    else:
        event["failure"] = {"class": "none", "retryable": False}
    event["adapter"] = event["adapter"] or {"id": "unknown"}
    event["route"] = {name: item for name, item in event["route"].items() if item != ""}
    if not event["stop_reason"]:
        event.pop("stop_reason")
    return event


def model_session_events(trace: Any) -> tuple[dict[str, Any], ...]:
    """Return the only invocation fields permitted in a session log.

    The runtime's own trace is already redacted, but retaining a second,
    structural allow-list here makes the persistence boundary durable: a
    future diagnostic field cannot silently turn session JSONL into a prompt
    or provider-payload store.
    """
    if not isinstance(trace, Mapping):
        return ()
    request = _model_request_event(trace.get("plan"))
    response = _model_response_event(trace.get("result"), trace.get("plan"))
    if request is None or response is None:
        return ()
    # A malformed external sink must not manufacture a request/response pair
    # that links two different calls.
    if request["plan_id"] != response["plan_id"] or request["config_hash"] != response["config_hash"]:
        return ()
    return request, response


MAX_PENDING_MODEL_EVENTS = 64


@contextmanager
def bind_model_session_events(vault: "Vault", session_id: str,
                              pending: list[dict[str, Any]] | None = None) -> Iterator[None]:
    """Bind one synchronous invocation trace to a loop's current session.

    Calls made before an ``open_session`` tool proposal are retained only as
    already-redacted events in ``pending``.  Once the tool opens a session the
    Loop flushes them through the normal CORE-03 append path; calls made with
    no session and no pending buffer leave no vault artefact.
    """
    target = (vault, _model_text(session_id, 160), pending)
    token = _MODEL_EVENT_TARGET.set(target)
    try:
        yield
    finally:
        _MODEL_EVENT_TARGET.reset(token)


def model_session_trace_sink(trace: dict[str, Any]) -> None:
    """Persist a bound invocation trace through :class:`SessionStore`.

    ``InvocationRuntime`` deliberately treats trace sinks as diagnostic: this
    function may raise for a failed log append, and the runtime will preserve
    the model call while its caller remains able to surface the storage fault.
    """
    target = _MODEL_EVENT_TARGET.get()
    if target is None:
        return
    events = model_session_events(trace)
    if not events:
        return
    vault, session_id, pending = target
    if vault is None:
        return
    if session_id:
        store = SessionStore(vault)
        for event in events:
            store.append(session_id, event)
    elif pending is not None:
        # Bounded: evidence for calls made before any session opens.
        pending.extend(events)
        del pending[:-MAX_PENDING_MODEL_EVENTS]

PURPOSES: dict[str, tuple[str, ...]] = {
    "add_project": ("frame", "ingest", "map", "need", "search", "judge", "synthesise",
                    "check_out"),
    "explore": ("frame", "map", "need", "search", "judge", "synthesise", "check_out"),
    "suggest": ("frame", "map", "search", "judge", "synthesise", "check_out"),
    "apply": ("check_in", "find", "check_out"),
    # Co-work Roadmap §2, W1: starting a course, job, project, research line or
    # learning goal. Reuses "frame" (create_project's own gate) and "check_out"
    # (close_session's) rather than inventing new phase names for either, since
    # both tools already mean the same thing here as everywhere else.
    "start_pursuit": ("frame", "inventory", "plan", "seed", "check_out"),
    # W2: stewarding, not answering. Every phase name here is new - "map" was
    # deliberately not reused, since its exit condition (concepts read, a
    # focus chosen) is not "the library's own map" the other purposes mean.
    "learn": ("goal", "baseline", "focus", "practice", "consolidate", "next"),
    # Roadmap §4 F2: adding a capability (an outside MCP server) the way the
    # librarian adds anything - assessed as a source first. "candidate", not
    # apply's "find": that name already means "sources used" there.
    "add_capability": ("candidate", "assess", "propose", "install", "check_out"),
    # HARNESS-03: an audited session works in rounds. Each round the Lead
    # proposes (manage), the Core admits a contract (preflight), the contract
    # runs (execute), Tier A checks it (audit) and the Core reduces the results
    # to requirement statuses (reduce); then the next round starts at manage.
    "audited": ("manage", "preflight", "execute", "audit", "reduce"),
}
MODE = {"add_project": "librarian", "explore": "librarian", "suggest": "librarian",
        "apply": "reader", "start_pursuit": "librarian", "learn": "librarian",
        "add_capability": "librarian", "audited": "librarian"}
# A round is not a redo: each one gets its phases' full budgets, up to this cap
# (the vault's [session] audited_max_rounds overrides it).
AUDITED_MAX_ROUNDS = 50

class _PhaseGates(Mapping[str, frozenset]):
    """The writes each phase unlocks: a tool named here is refused in any other phase.
    Reads are never gated. Read off each tool's own declaration (`@tool(phases=...)`,
    2026-09-30) rather than kept as a second list here, which let 19 writes go
    unclassified without anyone deciding they should be."""

    def __getitem__(self, name: str) -> frozenset:
        from .registry import REGISTRY
        spec = REGISTRY.get(name) if name in REGISTRY else None
        if spec is None or spec.scope != "phase":
            raise KeyError(name)
        return spec.phases

    def __iter__(self) -> Iterator[str]:
        from .registry import REGISTRY
        return iter([n for n in REGISTRY.names() if REGISTRY.get(n).scope == "phase"])

    def __len__(self) -> int:
        return sum(1 for _ in self)


WRITES: Mapping[str, frozenset] = _PhaseGates()
# The harness itself: never gated, never charged to a budget.
HARNESS = frozenset({"open_session", "session_status", "update_plan", "ask_user", "answer",
                     "advance", "park_session", "resume_session", "list_sessions",
                     "set_effort", "request_budget",
                     # a person choosing how the thread reasons is not the model's work
                     "lens_adopt", "lens_drop",
                     # a check on the model's own reasoning; charging it would make it a cost
                     "record_assumptions",
                     # tier "curate" already keeps these the person's alone; harness too,
                     # since editing the thread itself is bookkeeping, not the model's work
                     "rewind_session", "branch_session",
                     # the person's own requirement decision (HARNESS-03)
                     "set_requirement",
                     # the person's checkpoint controls in a research round (HARNESS-06)
                     "accept_artifact", "reject_artifact", "request_evidence"})

# Roadmap §4 G2: the phases just before a commitment - an answer (judge, before
# synthesise), a server definition (assess, before propose), a plan (inventory,
# before plan) - do not close until the model has said what it is assuming and
# how each assumption was settled, checked against what this session actually did.
ASSUMPTION_PHASES = frozenset({"judge", "assess", "inventory"})

# Raised 2026-09-28 from the shipped defaults (frame 8, ingest/map 12, need 10,
# check_out 8, check_in 6, inventory/seed 12, plan 10, goal 6, baseline 8,
# focus 12, consolidate 10, next 8): a real first framing session (orient with
# 5-6 read-only calls, create_project, a handful of task_add) spent all of
# frame's 8 on orientation and setup alone, then had every task_add after it
# refused (BUDGET_SPENT) - each one a wasted step, not just a blocked write.
# search/judge/synthesise/find/practice were not reported as tight and are
# left as they were. A vault can still override any of these under [session]
# in its own .librarian/config.toml.
DEFAULT_BUDGETS = {"frame": 24, "ingest": 20, "map": 20, "need": 18, "search": 40,
                   "judge": 40, "synthesise": 16, "check_out": 14, "check_in": 12, "find": 30,
                   "inventory": 18, "plan": 16, "seed": 20,
                   "goal": 12, "baseline": 14, "focus": 18, "practice": 30, "consolidate": 16,
                   "next": 14,
                   "manage": 12, "preflight": 8, "execute": 30, "audit": 16, "reduce": 8}

# Search is sized for one brief. Each further brief - a topic the request asked about -
# adds to it, up to a ceiling: a six-topic request parked in Search, its briefs open, in
# every M0 pass (2026-10-01). The effort setting's scale applies on top.
SEARCH_PER_BRIEF = 12
SEARCH_EXTRA_MAX = 60

ASKS = {
    "frame": "Which project is this for, what stage is it at, and what is fixed?",
    "ingest": "What does the person already have (repositories, papers, notes) that belongs "
              "in the library?",
    "map": "What does the library already hold on this, and under which topics?",
    "need": "What is needed, and what must a candidate not assume, require or depend on?",
    "search": "What did the last round teach? Which 2-4 sub-threads are open, and what is "
              "the next named target?",
    "judge": "What role would each candidate play? A rejection needs its reason.",
    "synthesise": "Which sources together; at what cost; what is unknown; what to open "
                  "first? Every claim carries its source and a verbatim quote.",
    "check_out": "What did the library fail to answer?",
    "check_in": "What are you working on, and what do you need from the library?",
    "find": "Find, qualify, open, extract: which sources did you use, and for what?",
    "inventory": "Kind-specific questions: what does this pursuit actually involve - modules "
                 "and assessments, a role and its first-90-days, deliverables and "
                 "stakeholders, or a research question and what's already known?",
    "plan": "What are the milestones, and which of them have dates?",
    "seed": "What reading, handbooks or onboarding material belongs in the library for this "
            "pursuit, and which of it matters enough to pin to the desk?",
    "goal": "What do they want to be able to do, and by when?",
    "candidate": "Which server? One from capability_candidates (the curated list), or a "
                 "repository URL the person gives - never one found by browsing on your own.",
    "assess": "ingest its repository, read it as a source, and record the assessment: "
              "licence, maintenance, what it claims, caveats, what it can reach - its card is "
              "its own claim, and the narrowest tool that does the job is the one to want.",
    "propose": "Propose one exact, pinned definition: which launcher, which version, which "
               "secrets (as ${ENV} names only), and why this library needs it.",
    "install": "The person decides: capability_install asks them, and installs only on yes.",
    "baseline": "Before teaching anything: 2-3 questions on what they already know.",
    "focus": "What does the library hold on this, and which concepts should this session "
             "focus on?",
    "practice": "Ask one question anchored in a source passage; the person answers; feedback "
                "cites the passage; record what they understand.",
    "consolidate": "Let the person explain it in their own words first; critique it against "
                   "the sources, grounded like the scribe.",
    "next": "When should this be reviewed again, and is there a next session to propose?",
    "manage": "Which open requirement comes next, and what one bounded step serves it? "
              "Record it with update_plan(proposal={'requirements': [...], 'step': ...}); "
              "ask the person instead if the requirement is unclear.",
    "preflight": "The Core admits the proposal as a contract against the current state, "
                 "or refuses it with the reason.",
    "execute": "Do only what the admitted contract allows, through its tools.",
    "audit": "Tier A checks every predicate of the contract's requirements on the actual "
             "artifacts; a missing or failed check is recorded, not skipped.",
    "reduce": "The Core turns the round's results into requirement statuses. Then start "
              "the next round, or close the session if every requirement is accounted for.",
}


def _filled(value: Any) -> bool:
    """A plan field that actually says something - not "", [], {} or None."""
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value) or value is False or value == 0


def _is_none(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() == "none"


def _review_scheduled(vault: Vault, focus: Any) -> bool:
    """`next`'s exit, checked rather than trusted: an open `Review:` task on a
    focus concept's note, or the Spaced Repetition plugin owning review."""
    plugins = vault.root / ".obsidian" / "community-plugins.json"
    if plugins.is_file() and "obsidian-spaced-repetition" in plugins.read_text(
            encoding="utf-8", errors="replace"):
        return True
    wanted = {str(f).casefold() for f in ([focus] if isinstance(focus, str) else focus)}
    for path in notes.iter_paths(vault.root):
        if path.stem.casefold() in wanted and any(
                t.open and t.text.startswith("Review:")
                for t in agenda.tasks(path.read_text(encoding="utf-8", errors="replace"))):
            return True
    return False


def _has_dated_task(vault: Vault, project: str) -> bool:
    """Real, not self-reported (W1's `plan` phase): does the project note
    actually carry a checkbox with a `📅` date, the same regex `agenda.py`
    already reads every note's tasks with."""
    if not project:
        return False
    path = vault.project_note(project)
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return any(task.due for task in agenda.tasks(text))


@dataclass
class Candidate:
    source: str
    brief: str
    found_in: int                  # round number, 0 when added by hand
    query: str = ""
    # keep: it answers the need, in `role`; context: kept as background only, never
    # counted as answering it (SP-7, the Cyprus listing); reject; defer
    disposition: str = "undecided"   # undecided | keep | context | reject | defer
    reason: str = ""
    role: str = ""


@dataclass
class Brief:
    id: str
    need: str
    disqualifiers: list[str]
    constraints: dict[str, Any] = field(default_factory=dict)
    verdict: str = ""
    status: str = "open"            # open | closed
    closing_note: str = ""
    topic: str = ""                 # the asked topic it answers (R13: one brief per topic)
    coverage: str = ""              # at close: covered | partial | gap


@dataclass
class Session:
    id: str
    purpose: str
    project: str = ""
    question: str = ""
    status: str = "open"            # open | parked | closed
    phase: str = ""
    phase_calls: int = 0
    opened_at: str = ""
    plan: dict[str, Any] = field(default_factory=dict)
    briefs: dict[str, Brief] = field(default_factory=dict)
    candidates: dict[str, Candidate] = field(default_factory=dict)
    library_items: dict[str, dict[str, Any]] = field(default_factory=dict)
    rounds: list[dict[str, Any]] = field(default_factory=list)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    questions: list[dict[str, Any]] = field(default_factory=list)
    uses: list[dict[str, Any]] = field(default_factory=list)
    writes: list[dict[str, Any]] = field(default_factory=list)
    offerings: list[dict[str, Any]] = field(default_factory=list)
    synthesis: dict[str, Any] | None = None
    summary: str = ""
    gaps: str = ""
    history: list[str] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)  # the chat transcript itself
    # ADAPT-03: durable, redacted route/adapter evidence.  This remains
    # separate from person-visible messages: it is operational provenance,
    # not conversation text or a provider payload archive.
    model_events: list[dict[str, Any]] = field(default_factory=list)
    min_rewind_index: int = 0      # see `to_dict`'s `min_rewind_index`
    budgets: dict[str, int] = field(default_factory=dict)
    budget_scale: float = 1.0       # the effort setting's share (effort.py)
    visits: dict[str, int] = field(default_factory=dict)
    lenses: list[str] = field(default_factory=list)      # adopted by a person, in order
    called: dict[str, int] = field(default_factory=dict)  # successful calls, by tool
    capabilities: dict[str, dict[str, Any]] = field(default_factory=dict)  # F2 proposals
    assumptions: list[dict[str, Any]] = field(default_factory=list)       # §4 G2
    recent: list[tuple[str, bool]] = field(default_factory=list)          # last calls, R3
    extended: dict[str, int] = field(default_factory=dict)  # calls a person added, R11
    # HARNESS-02: requirements, contracts, evidence and verifier results, folded
    # from typed events in this same log (audit_events.py is their rule book).
    audit: AuditState = field(default_factory=AuditState)
    audit_round: int = 1            # HARNESS-03: the audited purpose's round number
    manager_views: list = field(default_factory=list)   # HARNESS-06 telemetry, latest 20
    # HARNESS-05: each contract's successful calls (class, untrusted, idempotency
    # key), folded from `call` events so composition survives a resume.
    contract_calls: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    # -- identity -------------------------------------------------------------
    @property
    def mode(self) -> str:
        return MODE[self.purpose]

    @property
    def phases(self) -> tuple[str, ...]:
        return PURPOSES[self.purpose]

    def budget_left(self) -> int:
        """Each visit to a phase halves what it gets: going back to redo a
        phase is allowed, but it can never be used to reset a spent budget
        indefinitely (20, 10, 5, 2, 1, then nothing)."""
        budget = self.budgets.get(self.phase, 20)
        if self.phase == "search":
            budget += min(SEARCH_EXTRA_MAX, SEARCH_PER_BRIEF * max(0, len(self.briefs) - 1))
        full = int(round(budget * self.budget_scale))
        base = full >> max(0, self.visits.get(self.phase, 1) - 1)
        return max(0, base + self.extended.get(self.phase, 0) - self.phase_calls)

    def retries(self, tool: str) -> int:
        """How many times `tool` failed since it last succeeded, within the recent calls:
        the call being recorded now is retry number n."""
        n = 0
        for name, ok in reversed(self.recent):
            if name != tool:
                continue
            if ok:
                break
            n += 1
        return n

    def open_questions(self) -> list[dict[str, Any]]:
        """Asked and still waiting. A question that timed out is not: it blocked a thread
        for good once (2026-10-03, q1 asked again as q2-q6, each answered, q1 never), so
        it expires, and whatever needed it asks again."""
        return [q for q in self.questions if q.get("answer") is None and not q.get("expired")]

    def answered(self, kind: str, ref: str) -> dict[str, Any] | None:
        return next((q for q in reversed(self.questions) if q["kind"] == kind
                     and q.get("ref") == ref and q.get("answer") is not None), None)

    # -- the fold -------------------------------------------------------------
    def apply(self, event: dict[str, Any]) -> None:
        kind = event["type"]
        if kind == "opened":
            self.purpose = event["purpose"]
            self.project = event.get("project", "")
            self.question = event.get("question", "")
            self.opened_at = event["t"]
            self.phase = self.phases[0]
            self.budgets = {**DEFAULT_BUDGETS, **event.get("budgets", {})}
            self.visits = {self.phase: 1}
            self.history.append(self.phase)
        elif kind == "effort":                       # the person's effort setting (effort.py)
            self.budget_scale = float(event.get("budget_scale") or 1.0)
        elif kind == "model_request":
            safe = _model_request_event(event)
            if safe is not None:
                timestamp = _model_text(event.get("t"), 80)
                if timestamp:
                    safe["t"] = timestamp
                self.model_events.append(safe)
        elif kind == "model_response":
            # The durable response event contains the adapter ABI copied from
            # its request.  Passing the same event in both positions preserves
            # that ABI on fold without accepting arbitrary raw-log fields.
            safe = _model_response_event(event, event)
            if safe is not None:
                timestamp = _model_text(event.get("t"), 80)
                if timestamp:
                    safe["t"] = timestamp
                self.model_events.append(safe)
        elif kind == "call":
            described = event.get("contract_call")
            if isinstance(described, dict) and event.get("ok", True) and \
                    not event.get("refused"):
                self.contract_calls.setdefault(str(described.get("contract")), []).append(
                    {"class": described.get("class"), "untrusted": bool(described.get("untrusted")),
                     "key": described.get("key"), "tool": event.get("tool"),
                     "targets": list(described.get("targets") or [])})
            self.recent = (self.recent + [(event["tool"], bool(event.get("ok", True)))])[-20:]
            if event.get("charged"):
                self.phase_calls += 1
            if event.get("ok", True):
                self.called[event["tool"]] = self.called.get(event["tool"], 0) + 1
                # Not `rewind_session`/`branch_session` themselves: discarding
                # a rewind's own record on a later rewind loses nothing - it
                # is bookkeeping about the log, not vault content - and
                # counting it would lock further rewinding out after the
                # first one, past nothing anyone would call a write.
                if event.get("effect") in ("write", "vault_write") and \
                        event.get("tool") not in ("rewind_session", "branch_session"):
                    self.min_rewind_index = len(self.messages)
        elif kind == "budget":
            self.extended[event["phase"]] = self.extended.get(event["phase"], 0) + \
                int(event.get("add", 0))
        elif kind == "phase":
            if event.get("round"):
                # A new audited round: every phase starts again with its full
                # budget, unlike going back to redo a phase within a round.
                self.audit_round += 1
                for name in self.phases:
                    self.visits.pop(name, None)
            self.phase = event["to"]
            self.phase_calls = 0
            self.visits[self.phase] = self.visits.get(self.phase, 0) + 1
            self.history.append(self.phase)
        elif kind == "plan":
            for key, value in event["fields"].items():
                if key == "project":
                    self.project = value
                elif key == "question":
                    self.question = value
                else:
                    self.plan[key] = value
        elif kind == "question":
            self.questions.append({"id": event["id"], "question": event["question"],
                                   "kind": event.get("kind", "clarify"),
                                   "ref": event.get("ref", ""), "options": event.get("options"),
                                   "answer": None})
        elif kind == "answer":
            for q in self.questions:
                if q["id"] == event["id"]:
                    q["answer"] = event["answer"]
                    q["answered_by"] = event.get("by", "")
        elif kind == "question_expired":
            for q in self.questions:
                if q["id"] == event["id"]:
                    q["expired"] = True
        elif kind == "brief":
            self.briefs[event["id"]] = Brief(event["id"], event["need"],
                                             list(event["disqualifiers"]),
                                             event.get("constraints") or {},
                                             event.get("verdict", ""),
                                             topic=event.get("topic", ""))
        elif kind == "brief_closed":
            brief = self.briefs[event["id"]]
            brief.status, brief.closing_note = "closed", event.get("note", "")
            brief.coverage = event.get("coverage", "")
        elif kind == "round":
            self.rounds.append({k: event[k] for k in ("n", "queries", "new", "vocabulary",
                                                      "outside", "outside_found")
                                if k in event})
            for c in event.get("new", []):
                self.candidates.setdefault(c["source"], Candidate(
                    c["source"], c.get("brief", ""), event["n"], c.get("query", "")))
        elif kind == "candidate":
            self.candidates.setdefault(event["source"], Candidate(
                event["source"], event.get("brief", ""), 0, ""))
        elif kind == "library_item":
            self.library_items[event["id"]] = {
                k: event[k] for k in ("id", "source", "status", "path", "brief") if k in event
            }
        elif kind == "checkpoint":
            self.checkpoints.append({k: v for k, v in event.items() if k not in ("type", "t")})
        elif kind == "decision":
            c = self.candidates[event["source"]]
            c.disposition, c.reason, c.role = event["disposition"], event.get("reason", ""), \
                event.get("role", "")
        elif kind == "use":
            self.uses.append({k: v for k, v in event.items() if k != "type"})
        elif kind == "synthesis":
            self.synthesis = {k: v for k, v in event.items() if k != "type"}
        elif kind == "offering":
            existing = next((o for o in self.offerings if o["id"] == event["id"]), None)
            if existing:
                existing.update({k: v for k, v in event.items() if k != "type"})
            else:
                self.offerings.append({k: v for k, v in event.items() if k != "type"})
        elif kind == "write":
            self.writes.append({**{k: v for k, v in event.items() if k != "type"},
                                "phase": self.phase})
        elif kind == "capability":
            entry = self.capabilities.setdefault(event["name"], {"name": event["name"]})
            entry.update({k: v for k, v in event.items() if k not in ("type", "t")})
        elif kind == "assumptions":
            # One record per visit to a phase; a new one replaces it.
            self.assumptions = [a for a in self.assumptions
                                if (a["phase"], a["visit"]) != (event["phase"], event["visit"])]
            self.assumptions += [{**item, "phase": event["phase"], "visit": event["visit"]}
                                 for item in event["items"]] or \
                [{"assumption": "none", "settled_by": "none", "phase": event["phase"],
                  "visit": event["visit"]}]
        elif kind == "lens":
            if event.get("on") and event["id"] not in self.lenses:
                self.lenses.append(event["id"])
            elif not event.get("on") and event["id"] in self.lenses:
                self.lenses.remove(event["id"])
        elif kind == "message":
            self.messages.append({"role": event["role"], "text": event["text"], "t": event["t"]})
        elif kind == "status":
            self.status = event["status"]
            note = str(event.get("note", ""))
            if note.endswith(" went unanswered"):
                # before question_expired existed, a timeout was recorded only as this park
                # note ("question q1 went unanswered"): that question expired all the same
                for q in self.questions:
                    if note == f"question {q['id']} went unanswered" and q.get("answer") is None:
                        q["expired"] = True
        elif kind == "closed":
            self.status = "closed"
            self.summary, self.gaps = event.get("summary", ""), event.get("gaps", "")
        elif kind == "reopened":
            self.status = "open"
        elif kind == "manager_view":
            # HARNESS-06: what the Manager was shown, by digest, and how many
            # bundles survived the filter when it was invoked.
            self.manager_views = (self.manager_views + [
                {k: event.get(k) for k in ("digest", "round", "bundles", "fits")}])[-20:]
        elif kind in AUDIT_EVENTS:
            # Checked against the state before it, exactly as at append: a
            # history that breaks the rules is marked invalid, never trusted.
            audit_events.replay(self.audit, event)

    # -- exit conditions ------------------------------------------------------
    def missing(self, vault: Vault) -> list[str]:
        """What stands between this phase and the next. Empty means it may advance."""
        out = [f"unanswered question {q['id']}: {q['question']}" for q in self.open_questions()]
        p = self.phase
        if self.purpose == "audited":
            return out + self._audited_missing()
        if p == "frame":
            if self.purpose in ("add_project", "suggest", "start_pursuit"):
                if not self.project:
                    out.append("no project set: update_plan(project=...) or create_project")
                elif not vault.project_note(self.project).exists():
                    out.append(f"no Project note for {self.project!r}: create_project")
            else:
                if not (self.question or self.project):
                    out.append("no question set: update_plan(question=...)")
                if self.project and not vault.project_note(self.project).exists():
                    # 2026-10-02: an explore thread named a project that had no note, left
                    # Frame, and spent a dozen calls in Need where create_project is not
                    # offered. It is settled here, where it is.
                    out.append(f"no Project note for {self.project!r} yet: "
                               f"create_project(name={self.project!r}, ...) now, or "
                               f"update_plan(fields={{'project': ''}}) to work without one")
        elif p == "ingest" and not _filled(self.plan.get("ingested")):
            out.append("record what the person already has: update_plan(ingested=...) "
                       "(a list, or 'none')")
        elif p == "map":
            if "map" not in self.plan:
                out.append("record the orientation: search with intent 'orient', then "
                           "update_plan(map=...)")
            if self.purpose == "suggest" and "project_read" not in self.plan:
                from .projects import root_for
                try:
                    root_for(vault, self.project, "")
                    out.append("read the project's own files: read_project")
                except Refusal:
                    pass            # access is off: the suggestion rests on the Project note
        elif p == "need":
            # R13: one brief per asked topic, so every topic ends with a coverage verdict
            unbriefed = [r["topic"] for r in self.coverage() if not r["brief"]]
            if unbriefed:
                out.append(f"open a brief for each asked topic still without one: "
                           f"{', '.join(unbriefed[:8])} - open_brief(need, disqualifiers, "
                           f"topic=...)")
            elif not self.briefs:
                out.append("open at least one brief: open_brief(need, disqualifiers)")
        elif p == "search":
            if not self._search_done():
                out.append("run rounds until the stopping rule fires: research_round, then "
                           "checkpoint")
        elif p == "judge":
            undecided = [c.source for c in self.candidates.values()
                         if c.disposition == "undecided"]
            if undecided:
                out.append(f"{len(undecided)} undecided candidate(s): "
                           f"{', '.join(undecided[:8])}")
        elif p == "synthesise":
            if self.synthesis is None:
                out.append("record the cross-source synthesis: record_synthesis")
            elif self.synthesis.get("outcome") == "offering" and not any(
                    o.get("status") in ("staged", "promoted") for o in self.offerings):
                out.append("draft the offering: draft_offering")
            else:
                # Staged is not delivered (M0 pass 2: a guide was drafted, then left in
                # staging): promote it - the person is asked under promotion.mode "person" -
                # or the person declines it.
                staged = [o["id"] for o in self.offerings if o.get("status") == "staged"]
                if staged and not any(o.get("status") == "promoted" for o in self.offerings):
                    out.append(f"promote the staged offering: promote_offering(offering="
                               f"'{staged[-1]}') - it is not in the vault until promoted")
        elif p == "check_in" and not (self.question or self.project):
            out.append("say what you are working on: update_plan(question=..., project=...)")
        elif p == "find" and not self.uses and "nothing_found" not in self.plan:
            out.append("log the sources you used (log_use), or update_plan(nothing_found=...)")
        elif p == "check_out":
            if self.purpose == "apply":
                if not any(w["tool"] == "record_application" for w in self.writes) and \
                        "no_application" not in self.plan:
                    out.append("record_application, or update_plan(no_application=reason)")
            elif self.purpose != "start_pursuit":
                open_briefs = [b.id for b in self.briefs.values() if b.status == "open"]
                if open_briefs:
                    out.append(f"close brief(s) {', '.join(open_briefs)}: close_brief")
        # -- start_pursuit (W1) ------------------------------------------------
        elif p == "inventory" and not _filled(self.plan.get("inventory")):
            out.append("record the kind-specific inventory: update_plan(inventory=...)")
        elif p == "plan":
            if "no_dates" not in self.plan and not _has_dated_task(vault, self.project):
                out.append("add at least one dated milestone (task_add), or "
                           "update_plan(no_dates=reason)")
        elif p == "seed":
            seeded = self.plan.get("ingested")
            if not _filled(seeded):
                out.append("record what was seeded: update_plan(ingested=...) (a list, or "
                           "'none')")
            elif not _is_none(seeded) and not (self.called.get("ingest") or
                                               self.called.get("queue_source")):
                # Self-reported until 2026-09-28: seeded sources are believed
                # only once something was actually ingested or queued here.
                out.append("the seeded sources were listed but none was ingested or queued in "
                           "this session: ingest / queue_source them, or ingested='none'")
        # -- learn (W2) ---------------------------------------------------------
        elif p == "goal" and not _filled(self.plan.get("goal")):
            out.append("what do they want to be able to do, and by when: "
                       "update_plan(goal=..., deadline=...)")
        elif p == "baseline" and not _filled(self.plan.get("baseline")):
            out.append("2-3 diagnostic questions before teaching: ask_user, then "
                       "update_plan(baseline=...)")
        elif p == "focus" and "focus" not in self.plan:
            out.append("read what the library holds, then choose the focus concepts: "
                       "update_plan(focus=[...])")
        elif p == "practice" and "practice_stopped" not in self.plan:
            # A spent budget does not count as practice: the phase stays open,
            # and the envelope says so, until every focus concept has its own
            # understanding_record or someone says, visibly, why it stopped.
            focus = self.plan.get("focus") or []
            focus = [focus] if isinstance(focus, str) else list(focus)
            practised = {str(w.get("concept", "")).casefold() for w in self.writes
                        if w.get("tool") == "understanding_record"}
            remaining = [c for c in focus if str(c).casefold() not in practised]
            if remaining:
                out.append(f"practise the remaining focus concept(s): {', '.join(remaining)} "
                           f"(or update_plan(practice_stopped=reason))")
        elif p == "consolidate" and ("consolidated" not in self.plan or not any(
                w.get("tool") == "understanding_record" and w.get("phase") == "consolidate"
                for w in self.writes)):
            # The person's own explanation is the point of this phase: a flag
            # without an understanding_record made here is not consolidation.
            out.append("let them explain it in their own words, critique it against the "
                       "sources, then understanding_record and update_plan(consolidated=...)")
        # -- add_capability (§4 F2) ----------------------------------------------
        elif p == "candidate" and not _filled(self.plan.get("candidate")):
            out.append("name the candidate: update_plan(candidate=...) - a curated server "
                       "(capability_candidates) or a repository URL the person gave")
        elif p == "assess":
            if not self.called.get("ingest"):
                out.append("ingest the candidate's repository, so it is read as a source")
            elif not _filled(self.plan.get("assessment")):
                out.append("record the assessment: update_plan(assessment=...) - licence, "
                           "maintenance, claims, caveats, what it can reach")
        elif p == "propose" and not self.capabilities:
            out.append("propose its exact definition: capability_propose(...)")
        elif p == "install" and not any(c.get("status") in ("installed", "declined")
                                         for c in self.capabilities.values()):
            out.append("capability_install(name) - it asks the person; a decline is a "
                       "finished outcome too")
        elif p == "next" and ("scheduled" not in self.plan or
                              not _review_scheduled(vault, self.plan.get("focus") or [])):
            out.append("review dates as tasks - task_add(text='Review: <concept>', due=..., "
                       "heading='Understanding') - or enable the Spaced Repetition plugin, "
                       "then update_plan(scheduled=...)")
        if p in ASSUMPTION_PHASES and not self.assumptions_recorded():
            out.append("before committing: record what you are assuming and how each was "
                       "settled - record_assumptions([{assumption, settled_by, how}]), where "
                       "settled_by is a tool you called here, an answered question's id, or "
                       "'unverifiable' (an empty list if you assume nothing)")
        return out

    def _audited_missing(self) -> list[str]:
        """HARNESS-03 exit conditions; unanswered questions block every phase first."""
        audit, p = self.audit, self.phase
        if audit.invalid:
            return [f"the audit history is invalid ({audit.invalid}); a person must review it"]
        contract = audit.current_contract
        if p == "manage":
            if not audit.requirements:
                return ["no requirements yet: the person sets them with set_requirement"]
            proposal = self.plan.get("proposal")
            named = proposal.get("requirements") if isinstance(proposal, dict) else None
            if not named or not isinstance(named, list):
                return ["propose one bounded step: update_plan(proposal={'requirements': "
                        "[...], 'step': '...'})"]
            unknown = [r for r in named if r not in audit.requirements]
            if unknown:
                return [f"the proposal names unknown requirement(s): {', '.join(map(str, unknown))}"]
            return []
        if not contract:
            return ["no contract has been admitted: preflight admits one"]
        if p == "preflight":
            if audit.contracts[contract]["admitted_epoch"] != audit.epoch:
                return [f"contract {contract} was admitted before the latest change (epoch "
                        f"{audit.contracts[contract]['admitted_epoch']}, now {audit.epoch}): "
                        "admit it again"]
            revision = audit.contracts[contract]["revision"]
            if audit_events.mutating(audit, contract) and not any(
                    s["contract"] == contract and s["revision"] == revision
                    for s in audit.snapshots.values()):
                return [f"contract {contract} changes the vault and has no pre-mutation "
                        "snapshot of its protected targets"]
            return []
        if p == "audit":
            unchecked = audit_events.unchecked_predicates(audit, contract)
            out = [f"no result yet at this epoch for {item}" for item in unchecked]
            if audit_events.contract_integrity(audit, contract) == "not_audited":
                out.append(f"contract {contract}'s protected targets are not audited yet "
                           "(audit_targets)")
            return out
        if p == "reduce":
            return [f"requirement {r} has no reduction at this epoch"
                    for r in audit_events.unreduced_requirements(audit, contract)]
        return []                                       # execute: the audit judges it

    def audited_round_limit(self, vault: Vault) -> int:
        configured = (vault.config().get("session") or {}).get("audited_max_rounds")
        try:
            return max(1, int(configured)) if configured is not None else AUDITED_MAX_ROUNDS
        except (TypeError, ValueError):
            return AUDITED_MAX_ROUNDS

    def state_hash(self) -> str:
        """A digest of everything the session's next step depends on.

        Resuming a paused session must reproduce it exactly (HARNESS-03). The
        open/parked status is left out, since pausing and resuming is what is
        being compared; timestamps are left out because replay never changes them.
        """
        state = {
            "purpose": self.purpose, "phase": self.phase, "phase_calls": self.phase_calls,
            "round": self.audit_round, "visits": self.visits, "budgets": self.budgets,
            "budget_scale": self.budget_scale, "extended": self.extended, "plan": self.plan,
            "questions": self.questions, "history": self.history,
            "audit": audit_events.summary(self.audit),
            "contracts": self.audit.contracts, "results": self.audit.results,
            "reductions": self.audit.reductions, "artifacts": self.audit.artifacts,
        }
        body = json.dumps(state, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()[:24]

    def assumptions_recorded(self) -> bool:
        visit = self.visits.get(self.phase, 1)
        return any(a["phase"] == self.phase and a["visit"] == visit for a in self.assumptions)

    def _search_done(self) -> bool:
        if self.briefs and all(b.verdict == "covered" for b in self.briefs.values()):
            return True
        if self.checkpoints and self.checkpoints[-1].get("stop"):
            return True
        return self.budget_left() == 0 and bool(self.rounds)

    # -- what to say next -----------------------------------------------------
    def next_step(self, vault: Vault) -> str:
        if self.status == "closed":
            return "this session is closed; resume_session reopens it to discuss what it made"
        if self.status == "parked":
            return "this session is parked; resume_session to continue"
        missing = self.missing(vault)
        barren = [not r.get("new") and not r.get("outside_found") for r in self.rounds[-2:]]
        if self.phase == "search" and len(barren) == 2 and all(barren) and \
                not self._search_done():
            target = "need" if "need" in self.phases else "map"
            return (f"two rounds found nothing new: widen the vocabulary. "
                    f"advance(target='{target}') and restate the need in the field's own words")
        if self.budget_left() == 0 and missing:
            return (f"the {self.phase} budget is spent with this still needed: "
                    f"{missing[0]}. Advance if you can, park_session, or "
                    f"request_budget(reason=...) to ask the person for more calls - they can "
                    f"also Extend budget in the Plan pane")
        if missing:
            return f"{ASKS.get(self.phase, '')} Still needed: {missing[0]}"
        position = self.phases.index(self.phase)
        if position + 1 < len(self.phases):
            # The same sentence a refused non-harness call sees back
            # (BUDGET_SPENT re-raises this): without it, a phase that is both
            # complete and spent looked identical to one that was merely
            # complete, and a refused write (e.g. task_add) read as "try
            # again" rather than "nothing but advance/park/ask works now".
            spent = (" - its budget is spent, so only advance, park_session, ask_user and "
                     "update_plan still work here" if self.budget_left() == 0 else "")
            return f"{self.phase} is complete: advance to {self.phases[position + 1]}{spent}"
        if self.purpose == "audited":
            done = self.completion()
            if done["complete"]:
                return "every requirement is accounted for: close_session(summary, gaps)"
            return (f"round {self.audit_round} is reduced: advance starts the next round at "
                    f"manage, or close_session naming what is unresolved: "
                    f"{'; '.join(done['gaps'][:6])}")
        return "everything is done: close_session(summary, gaps)"

    def topics(self) -> list[str]:
        raw = self.plan.get("topics") or []
        raw = [raw] if isinstance(raw, str) else raw
        return [str(t).strip() for t in raw if str(t).strip()]

    def coverage(self) -> list[dict[str, Any]]:
        """The coverage ledger (R13): each asked topic, the brief that answers it, and its
        verdict - `covered`, `partial` or `gap` once closed - with what was kept for it."""
        rows: list[dict[str, Any]] = []
        only = len(self.briefs) == 1
        for b in self.briefs.values():
            mine = [c for c in self.candidates.values() if c.brief == b.id or
                    (not c.brief and only)]
            rows.append({"topic": b.topic or b.need, "brief": b.id,
                         "verdict": b.coverage or ("open" if b.status == "open"
                                                   else "closed without a verdict"),
                         "kept": [c.source for c in mine if c.disposition == "keep"],
                         "context": [c.source for c in mine if c.disposition == "context"],
                         "undecided": sum(1 for c in mine if c.disposition == "undecided"),
                         **({"note": b.closing_note} if b.closing_note else {})})
        seen = {r["topic"].casefold() for r in rows}
        rows += [{"topic": t, "brief": "", "verdict": "no brief", "kept": [], "context": [],
                  "undecided": 0} for t in self.topics() if t.casefold() not in seen]
        return rows

    def completion(self) -> dict[str, Any]:
        """Is the research done (R13)? Every brief has a coverage verdict, nothing waits to
        be judged, and what the session made is listed with its path - gaps stated.

        An audited session is complete only when every requirement is verified or
        human-accepted at the current epoch; anything else is a gap to name."""
        if self.purpose == "audited":
            statuses = {r: self.audit.requirement_status(r) for r in self.audit.requirements}
            closed = ("verified", "human_accepted")
            return {"complete": bool(statuses) and not self.audit.invalid and
                    all(s in closed for s in statuses.values()),
                    "outcome": audit_events.session_outcome(self.audit),
                    "requirements": statuses,
                    "gaps": [f"{r} ({s})" for r, s in statuses.items() if s not in closed] +
                            ([f"audit history invalid: {self.audit.invalid}"]
                             if self.audit.invalid else []),
                    "made": [{"artifact": a["path"], "fingerprint": a["fingerprint"]}
                             for a in self.audit.artifacts.values()]}
        ledger = self.coverage()
        verdicts = ("covered", "partial", "gap")
        return {"complete": bool(ledger) and all(r["verdict"] in verdicts for r in ledger)
                and not any(r["undecided"] for r in ledger),
                "ledger": ledger,
                "gaps": [f"{r['topic']} ({r['verdict']})" for r in ledger
                         if r["verdict"] not in ("covered",)],
                "made": [{"offering": o.get("title", o["id"]), "status": o.get("status"),
                          "path": o.get("path", "")} for o in self.offerings] +
                        [{"note": w["path"], "tool": w["tool"]} for w in self.writes
                         if w.get("tool") in ("write_note", "record_application")]}

    def envelope(self, vault: Vault) -> dict[str, Any]:
        library_items = list(self.library_items.values())
        library_item_counts: dict[str, int] = {}
        for item in library_items:
            status = str(item.get("status", "unknown"))
            library_item_counts[status] = library_item_counts.get(status, 0) + 1
        return {"session": self.id, "purpose": self.purpose, "project": self.project,
                "mode": self.mode, "status": self.status, "phase": self.phase,
                "phases": list(self.phases), "open_items": self.missing(vault),
                **({"round": self.audit_round} if self.purpose == "audited" else {}),
                "budget_left": self.budget_left(), "next": self.next_step(vault),
                # R11: spent with the phase unfinished - the person may extend it
                **({"budget_spent": True} if self.budget_left() == 0 and self.missing(vault)
                   else {}),
                **({"coverage": [{k: r[k] for k in ("topic", "brief", "verdict")}
                                 for r in self.coverage()]} if self.coverage() else {}),
                "library_item_count": len(library_items),
                "library_item_counts": library_item_counts,
                "library_items": library_items[-12:]}

    def to_dict(self, vault: Vault) -> dict[str, Any]:
        return {**self.envelope(vault), "project": self.project, "question": self.question,
                "opened_at": self.opened_at, "plan": self.plan,
                "briefs": {k: v.__dict__ for k, v in self.briefs.items()},
                "candidates": [c.__dict__ for c in self.candidates.values()],
                "library_items": list(self.library_items.values()),
                "rounds": self.rounds, "checkpoints": self.checkpoints,
                "questions": self.questions, "uses": self.uses, "writes": self.writes,
                "offerings": self.offerings, "synthesis": self.synthesis,
                "summary": self.summary, "gaps": self.gaps, "history": self.history,
                "model_events": self.model_events,
                "lenses": self.lenses, "capabilities": list(self.capabilities.values()),
                "assumptions": self.assumptions,
                "completion": self.completion(),
                "messages": [{"index": i, **m} for i, m in enumerate(self.messages)],
                # Rewinding to a message discards it and everything after it in
                # the log, including any vault write in between - so it is only
                # offered from `min_rewind_index` on: the fewest messages that
                # had happened, log-order, as of the most recent write. A write
                # before any message at all (min_rewind_index 0) blocks nothing.
                "min_rewind_index": self.min_rewind_index,
                **({"audit": audit_events.summary(self.audit)} if self.audit.used else {})}


# -------------------------------------------------------------------- storage

class SessionStore:
    def __init__(self, vault: Vault):
        self.vault = vault
        self.folder = vault.work("sessions")

    def path(self, session_id: str) -> Path:
        safe = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return self.folder / f"{safe}.jsonl"

    @staticmethod
    def _new_id() -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        return f"{stamp}-{secrets.token_hex(3)}"

    def new(self, purpose: str, project: str = "", question: str = "") -> Session:
        if purpose not in PURPOSES:
            raise ValueError(f"purpose {purpose!r} is not one of {sorted(PURPOSES)}")
        session_id = self._new_id()
        budgets = {k: int(v) for k, v in (self.vault.config().get("session") or {}).items()
                   if k in DEFAULT_BUDGETS}
        self.folder.mkdir(parents=True, exist_ok=True)
        self.append(session_id, {"type": "opened", "purpose": purpose, "project": project,
                                 "question": question, "budgets": budgets})
        return self.load(session_id)

    def _lines_through(self, session_id: str, message_index: int) -> list[str]:
        """Every raw log line up to and including the `message_index`-th
        `"message"` event (0-indexed) - the shared primitive for `rewind` (this
        session, in place) and `branch` (a copy, under a new id): both are
        "the log as it stood right after that message was said"."""
        lines = jsonl_lines(self.path(session_id).read_text(encoding="utf-8"))
        seen = -1
        for n, line in enumerate(lines):
            if not line.strip():
                continue
            if json.loads(line).get("type") == "message":
                seen += 1
                if seen == message_index:
                    return lines[:n + 1]
        raise Refusal("MESSAGE_NOT_FOUND",
                      f"session {session_id} has no message at index {message_index}")

    def _through_core(self, fn: Callable[[], T], caller: str) -> T:
        """Run a log mutation through the active Core's writer when one holds
        this vault (CORE-03), so session events are ordered with the writes
        they describe.

        Without one here a direct write is safe only offline: this process
        holds the vault lease itself (a direct CLI call), or no Core holds it.
        After this process's Core stopped, or while another process's Core
        holds the vault, a write is refused - a straggling thread never writes
        beside whichever Core holds the vault now (review, 2026-10-24).  What
        remains is a process with no Core writing just as one starts
        elsewhere: the append lock is cross-process, so the log's chain stays
        whole, and the order is that of any two offline writers.
        """
        writer, stopped = _core_writer_state(self.vault)
        if writer is not None:
            return writer.submit(fn, caller=caller)
        from .coordination import VaultCoordinator
        if not VaultCoordinator.held_here(self.vault):
            if stopped:
                raise Refusal("CORE_REQUIRED", "this library's Core has stopped, so the thread "
                                               "was not written to; start it and resume the thread")
            if VaultCoordinator.held_elsewhere(self.vault):
                raise Refusal("CORE_REQUIRED", "another process's Core holds this library; "
                                               "make the call through it")
        return fn()

    def truncate_to(self, session_id: str, message_index: int) -> None:
        """Rewind: discard this message's log line and everything after it -
        in place, so `session_id` still means the same thread."""
        path = self.path(session_id)

        def rewrite() -> None:
            with _append_lock(path):
                kept = self._lines_through(session_id, message_index)
                atomic_write_text(path, "\n".join(kept) + "\n")
        self._through_core(rewrite, "session-rewind")

    def copy_through(self, session_id: str, message_index: int) -> str:
        """Branch: a new session whose log is `session_id`'s up to and
        including this message - same phase, plan and budget state (folded
        from the same events), continuing independently from here."""
        path = self.path(session_id)
        with _append_lock(path):
            kept = self._lines_through(session_id, message_index)
        new_id = self._new_id()
        new_path = self.path(new_id)

        def write() -> None:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(new_path, "\n".join(kept) + "\n")
        self._through_core(write, "session-branch")
        return new_id

    def append(self, session_id: str, event: dict[str, Any]) -> None:
        """Each event carries `h`, a hash of itself chained to the event
        before it (roadmap §4 B4): editing or removing an event in the middle
        of a log breaks every hash after it, and `verify` says where."""
        self._through_core(lambda: self._append_now(session_id, event), "session-event")

    def _append_now(self, session_id: str, event: dict[str, Any]) -> None:
        path = self.path(session_id)
        with _append_lock(path):
            _write_event_locked(path, event)

    def append_audit(self, session_id: str, event: dict[str, Any]) -> None:
        """Append one audit event (HARNESS-02) only if the rules accept it here.

        The check and the write share one writer operation and one append lock,
        so no other event can land between them; a refused event is never
        written. The session must exist and must not be closed.
        """
        if event.get("type") not in AUDIT_EVENTS:
            raise Refusal("AUDIT_EVENT_INVALID",
                          f"{event.get('type')!r} is not an audit event")
        path = self.path(session_id)

        def checked_append() -> None:
            with _append_lock(path):
                session = self.load(session_id)
                if session.status == "closed":
                    raise Refusal("SESSION_REQUIRED", f"session {session_id} is closed; "
                                                      "resume it before adding audit events")
                audit_events.check_and_apply(session.audit, dict(event))
                _write_event_locked(path, event)
        self._through_core(checked_append, "session-audit-event")

    def load(self, session_id: str) -> Session:
        path = self.path(session_id)
        if not path.exists():
            raise Refusal("SESSION_REQUIRED", f"no session {session_id!r}; list_sessions shows "
                                              f"what exists")
        session = Session(id=session_id, purpose="explore")
        text = path.read_text(encoding="utf-8")
        lines = jsonl_lines(text)
        for n, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                # Another thread or process mid-append: its last line is not
                # finished yet. Anything else unreadable is a real fault.
                if n == len(lines) - 1 and not text.endswith("\n"):
                    break
                raise
            event.pop("h", None)
            session.apply(event)
        return session

    def events(self, session_id: str) -> list[dict[str, Any]]:
        """The session's events in log order, without their chain hashes.

        A projection reads these for counts and recent activity; an unfinished
        trailing line (another writer mid-append) is skipped, as `load` does.
        """
        path = self.path(session_id)
        if not path.exists():
            raise Refusal("SESSION_REQUIRED", f"no session {session_id!r}")
        text = path.read_text(encoding="utf-8")
        lines = jsonl_lines(text)
        out = []
        for n, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                if n == len(lines) - 1 and not text.endswith("\n"):
                    break
                raise
            event.pop("h", None)
            out.append(event)
        return out

    def verify(self) -> list[str]:
        """Every session log whose chain is broken, with the first line that
        fails. A log from before B4 (no `h`) is chained from its first hashed
        event on; removing events from the *end* of a log is not detectable."""
        broken = []
        for path in sorted(self.folder.glob("*.jsonl")):
            where = verify_chain(jsonl_lines(path.read_text(encoding="utf-8")))
            if where:
                broken.append(f"{path.stem}: {where}")
        return broken

    def list(self) -> list[dict[str, Any]]:
        out = []
        for path in sorted(self.folder.glob("*.jsonl"), reverse=True):
            s = self.load(path.stem)
            out.append({"id": s.id, "purpose": s.purpose, "project": s.project,
                        "question": s.question, "status": s.status, "phase": s.phase,
                        "opened_at": s.opened_at})
        return out


# ------------------------------------------- the Core-owned append path (CORE-03)

# While a Core holds a vault's lease it registers its writer here, and every
# SessionStore for that vault appends through it - whichever module made the
# store.  A vault whose Core stopped in this process stays marked until a new
# Core attaches, so a late write is refused instead of written directly.
_CORE_WRITERS: dict[str, Any] = {}
_STOPPED_CORES: set[str] = set()
_CORE_WRITERS_GUARD = threading.Lock()


def _vault_key(vault: Vault) -> str:
    return str(Path(vault.root).resolve()).casefold()


def attach_core_writer(vault: Vault, writer: Any) -> None:
    with _CORE_WRITERS_GUARD:
        _CORE_WRITERS[_vault_key(vault)] = writer
        _STOPPED_CORES.discard(_vault_key(vault))


def detach_core_writer(vault: Vault, writer: Any) -> None:
    """Detach only the writer that attached: a successor Core's stays."""
    with _CORE_WRITERS_GUARD:
        if _CORE_WRITERS.get(_vault_key(vault)) is writer:
            _CORE_WRITERS.pop(_vault_key(vault), None)
            _STOPPED_CORES.add(_vault_key(vault))


def core_writer(vault: Vault) -> Any:
    with _CORE_WRITERS_GUARD:
        return _CORE_WRITERS.get(_vault_key(vault))


def _core_writer_state(vault: Vault) -> tuple[Any, bool]:
    """This vault's attached writer, and whether a Core here has stopped."""
    with _CORE_WRITERS_GUARD:
        key = _vault_key(vault)
        return _CORE_WRITERS.get(key), key in _STOPPED_CORES


# ------------------------------------------------------ the hash chain (B4)

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


@contextmanager
def _append_lock(path: Path) -> Iterator[None]:
    """One writer at a time per log: a thread lock within this process, and a
    lock on a sidecar file across processes (the CLI and the app appending to
    the same session), so no two appends ever chain from the same event."""
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(str(path), threading.Lock())
    with lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(f"{path}.lock", "a+b") as handle:
            _lock_file(handle)
            try:
                yield
            finally:
                _unlock_file(handle)


if os.name == "nt":                                             # pragma: no cover - Windows
    import msvcrt

    def _lock_file(handle) -> None:
        handle.seek(0)
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                return
            except OSError:                     # LK_LOCK gives up after ~10 s; keep waiting
                continue

    def _unlock_file(handle) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock_file(handle) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

    def _unlock_file(handle) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_event_locked(path: Path, event: dict[str, Any]) -> None:
    """Chain and append one event; the caller holds `_append_lock(path)`."""
    event = {"t": now_iso(), **{k: v for k, v in event.items() if k != "h"}}
    event["h"] = chain_hash(_last_hash(path), event)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass


def chain_hash(previous: str, record: dict[str, Any]) -> str:
    body = json.dumps({k: v for k, v in record.items() if k != "h"}, sort_keys=True,
                      ensure_ascii=False, default=str)
    return hashlib.sha256(f"{previous}\n{body}".encode("utf-8")).hexdigest()[:24]


def _last_hash(path: Path) -> str:
    if not path.exists():
        return ""
    with path.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - 65536))
        tail = handle.read().decode("utf-8", errors="replace")
    for line in reversed(jsonl_lines(tail)):
        if line.strip():
            try:
                return str(json.loads(line).get("h") or "")
            except json.JSONDecodeError:
                return ""
    return ""


def verify_chain(lines: list[str]) -> str:
    """"" when every hashed line follows from the one before, else where it
    first fails. Lines before the first hashed one (an older log) are skipped."""
    previous, started = "", False
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            return f"line {n} is not JSON"
        h = record.get("h")
        if not h:
            if started:
                return f"line {n} has no hash after the chain began"
            continue
        if not started:
            started = True
            if chain_hash(previous, record) != h and chain_hash("", record) != h:
                return f"line {n} does not match its hash"
        elif chain_hash(previous, record) != h:
            return f"line {n} does not follow from line {n - 1}: edited, inserted or removed"
        previous = h
    return ""


# ------------------------------------------------------ the registry's hooks

# --------------------------------------- outside edits to audited targets (HARNESS-02)

# vault -> session id -> ((mtime_ns, size), paths it watches). A log is re-read
# only when it changed, so an outside edit costs a stat per session, not a replay.
_WATCHED: dict[str, dict[str, tuple[tuple[int, int], frozenset[str]]]] = {}
_WATCHED_GUARD = threading.Lock()
_AUDIT_MARKERS = ('"type": "contract"', '"type": "artifact"')


def sessions_watching(vault: Vault, rel: str) -> list[str]:
    """Open audited sessions that read or target `rel`."""
    store = SessionStore(vault)
    found: list[str] = []
    with _WATCHED_GUARD:
        cache = _WATCHED.setdefault(_vault_key(vault), {})
        present = set()
        for path in store.folder.glob("*.jsonl"):
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            stamp, present_id = (stat.st_mtime_ns, stat.st_size), path.stem
            present.add(present_id)
            entry = cache.get(present_id)
            if entry is None or entry[0] != stamp:
                watched: frozenset[str] = frozenset()
                text = path.read_text(encoding="utf-8")
                if any(marker in text for marker in _AUDIT_MARKERS):
                    session = store.load(present_id)
                    if session.status != "closed" and not session.audit.invalid:
                        watched = frozenset(session.audit.watched_paths())
                entry = cache[present_id] = (stamp, watched)
            if rel in entry[1]:
                found.append(present_id)
        for gone in set(cache) - present:
            del cache[gone]
    return sorted(found)


def record_external_edit(vault: Vault, rel: str) -> list[str]:
    """Append `external_edit` to every open audited session watching `rel`.

    Called for changes made outside the Core (DocumentLeases.observe_change):
    the edit advances each session's epoch, so its earlier verifier results and
    closures on that state go stale. Returns the sessions it was recorded in.
    """
    from .coordination import fingerprint
    path = rel.replace("\\", "/")
    watching = sessions_watching(vault, path)
    if not watching:
        return []
    try:
        current = fingerprint(vault.root / path)
    except OSError:
        current = "unreadable"
    store = SessionStore(vault)
    for session_id in watching:
        store.append_audit(session_id, {"type": "external_edit", "path": path,
                                        "fingerprint": current, "source": "watcher"})
    return watching


def before_call(tool_name: str, effect: str, ctx: Any) -> None:
    """Refuse a gated write outside its phase, or any charged call once the
    phase budget is spent. Runs inside `Registry.call` for every in-session call."""
    if tool_name in HARNESS:
        return
    store = SessionStore(ctx.vault)
    session = store.load(ctx.session)
    if session.status != "open" and effect == "read":
        return              # looking is never refused: a parked thread still sees its library
    if session.status != "open":
        raise Refusal("SESSION_REQUIRED", f"session {session.id} is {session.status}; "
                                          f"resume_session first")
    phases = WRITES.get(tool_name)
    if phases is not None and session.phase not in phases:
        allowed = [p for p in session.phases if p in phases]
        raise Refusal("PHASE_GATE",
                      f"{tool_name!r} is a write unlocked in "
                      f"{', '.join(allowed) or 'no phase of this purpose'}; "
                      f"the session is in {session.phase}. {session.next_step(ctx.vault)}")
    # The budget is the model's allowance. A person's own calls in the thread
    # (the pane's lens list, a desk read) are neither refused by it nor
    # charged to it - found by the browser smoke test, 2026-09-28, when a
    # spent frame budget hid the person's own lens list behind BUDGET_SPENT.
    if session.budget_left() == 0 and not _is_person(ctx):
        raise Refusal("BUDGET_SPENT", session.next_step(ctx.vault))


def _is_person(ctx: Any) -> bool:
    return getattr(ctx, "tier", "") == "curate"


def authorize_call(tool_name: str, spec: Any, kwargs: dict[str, Any], intent: Any,
                   ctx: Any, raw: dict[str, Any] | None = None,
                   adjusted: list[str] | None = None) -> dict[str, Any] | None:
    """HARNESS-05: check a call against the executing audited contract.

    Runs after the write intent is resolved and before anyone is asked to
    approve the call, so a call outside the contract is refused before it runs.
    """
    if tool_name in HARNESS:
        return None          # session bookkeeping, not an effect on the vault
    from . import closure
    session = SessionStore(ctx.vault).load(ctx.session)
    return closure.authorize(session, spec, kwargs, intent, ctx.vault, raw=raw,
                             adjusted=adjusted)


def after_call(tool_name: str, arguments: dict[str, Any], result: dict[str, Any],
               ctx: Any, effect: str = "", permission: str = "",
               normalised: dict[str, Any] | None = None,
               authorization: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record the call and hand the walk back with the result. `effect` (the
    tool's own declared "read"/"write"/"vault_write") is recorded too, so a
    fold can tell whether anything after a message actually changed the vault
    - which is what gates whether that message can still be rewound to."""
    store = SessionStore(ctx.vault)
    charged = tool_name not in HARNESS and "error" not in result and not _is_person(ctx)
    before = store.load(ctx.session)
    event = {"type": "call", "tool": tool_name, "charged": charged,
             "ok": "error" not in result, "effect": effect,
             "args": {k: _trace_value(k, v) for k, v in arguments.items()},
             # Requirements Addendum R3: who called, where, and what really happened.
             "model": str((getattr(ctx, "extras", None) or {}).get("model") or ""),
             "tier": getattr(ctx, "tier", ""), "phase": before.phase,
             **({"lead": str(ctx.extras["lead_status"])[:120]}
                if (getattr(ctx, "extras", None) or {}).get("lead_status") else {}),
             "budget_before": before.budget_left(),
             "budget_after": max(0, before.budget_left() - (1 if charged else 0)),
             "permission": "person" if _is_person(ctx) and permission in ("", "no broker")
                           else permission or "no broker",
             # this tool's failed calls since it last succeeded, among the recent ones
             "retry": before.retries(tool_name)}
    if normalised is not None:
        shown = {k: _trace_value(k, v) for k, v in normalised.items()}
        if shown != event["args"]:
            event["normalised"] = shown
    if authorization is not None:
        event["contract_call"] = authorization
    for key in ("refused", "error"):
        if key in result:
            event[key] = str(result[key])[:80]
    if "error" in result and result.get("detail"):
        event["detail"] = str(result["detail"])[:200]
    if result.get("adjusted_arguments"):
        event["adjusted"] = [str(a)[:120] for a in result["adjusted_arguments"]][:6]
    if result.get("outcome"):
        event["outcome"] = result["outcome"]
        event["items"] = [_trace_item(i) for i in result.get("results", [])[:20]
                          if isinstance(i, dict)]
    store.append(ctx.session, event)
    return {**result, "session": store.load(ctx.session).envelope(ctx.vault)}


def _trace_item(item: dict[str, Any]) -> dict[str, Any]:
    """One item of a multi-item result, as the trace keeps it: what happened to it and why,
    not just its id."""
    out = {"id": str(item.get("id", ""))[:80],
           "status": str(item.get("status") or ("refused" if "refused" in item else
                                                "error" if "error" in item else ""))[:40]}
    for key in ("refused", "error", "detail", "reason", "path", "state"):
        if item.get(key):
            out[key] = str(item[key])[:160]
    promotion = item.get("promotion")
    if isinstance(promotion, dict) and promotion.get("path"):
        out["path"] = str(promotion["path"])[:160]
    return out


_SECRET_NAME = re.compile(r"(?:^|_)(?:key|token|secret|password|passwd|auth)(?:$|_)", re.I)


def _trace_value(name: str, value: Any) -> Any:
    """An argument as the trace keeps it: clipped, and masked when its name says secret."""
    if _SECRET_NAME.search(name):
        return "••••"
    return value if len(str(value)) < 200 else str(value)[:200] + "..."
