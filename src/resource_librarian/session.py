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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Iterator

from . import agenda, notes
from .rules import Refusal
from .vault import Vault, jsonl_lines, now_iso

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
}
MODE = {"add_project": "librarian", "explore": "librarian", "suggest": "librarian",
        "apply": "reader", "start_pursuit": "librarian", "learn": "librarian",
        "add_capability": "librarian"}

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
                     "set_effort",
                     # a person choosing how the thread reasons is not the model's work
                     "lens_adopt", "lens_drop",
                     # a check on the model's own reasoning; charging it would make it a cost
                     "record_assumptions",
                     # tier "curate" already keeps these the person's alone; harness too,
                     # since editing the thread itself is bookkeeping, not the model's work
                     "rewind_session", "branch_session"})

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
                   "next": 14}

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
        return [q for q in self.questions if q.get("answer") is None]

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
        elif kind == "call":
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
        elif kind == "closed":
            self.status = "closed"
            self.summary, self.gaps = event.get("summary", ""), event.get("gaps", "")
        elif kind == "reopened":
            self.status = "open"

    # -- exit conditions ------------------------------------------------------
    def missing(self, vault: Vault) -> list[str]:
        """What stands between this phase and the next. Empty means it may advance."""
        out = [f"unanswered question {q['id']}: {q['question']}" for q in self.open_questions()]
        p = self.phase
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
                    f"{missing[0]}. Advance if you can, park_session, or ask_user - the person "
                    f"can extend the budget (Extend budget, in the Plan pane)")
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
        be judged, and what the session made is listed with its path - gaps stated."""
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
                "lenses": self.lenses, "capabilities": list(self.capabilities.values()),
                "assumptions": self.assumptions,
                "completion": self.completion(),
                "messages": [{"index": i, **m} for i, m in enumerate(self.messages)],
                # Rewinding to a message discards it and everything after it in
                # the log, including any vault write in between - so it is only
                # offered from `min_rewind_index` on: the fewest messages that
                # had happened, log-order, as of the most recent write. A write
                # before any message at all (min_rewind_index 0) blocks nothing.
                "min_rewind_index": self.min_rewind_index}


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

    def truncate_to(self, session_id: str, message_index: int) -> None:
        """Rewind: discard this message's log line and everything after it -
        in place, so `session_id` still means the same thread."""
        path = self.path(session_id)
        with _append_lock(path):
            kept = self._lines_through(session_id, message_index)
            path.write_text("\n".join(kept) + "\n", encoding="utf-8")

    def copy_through(self, session_id: str, message_index: int) -> str:
        """Branch: a new session whose log is `session_id`'s up to and
        including this message - same phase, plan and budget state (folded
        from the same events), continuing independently from here."""
        path = self.path(session_id)
        with _append_lock(path):
            kept = self._lines_through(session_id, message_index)
        new_id = self._new_id()
        new_path = self.path(new_id)
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        return new_id

    def append(self, session_id: str, event: dict[str, Any]) -> None:
        """Each event carries `h`, a hash of itself chained to the event
        before it (roadmap §4 B4): editing or removing an event in the middle
        of a log breaks every hash after it, and `verify` says where."""
        event = {"t": now_iso(), **{k: v for k, v in event.items() if k != "h"}}
        path = self.path(session_id)
        with _append_lock(path):
            event["h"] = chain_hash(_last_hash(path), event)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

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

def before_call(tool_name: str, effect: str, ctx: Any) -> None:
    """Refuse a gated write outside its phase, or any charged call once the
    phase budget is spent. Runs inside `Registry.call` for every in-session call."""
    if tool_name in HARNESS:
        return
    store = SessionStore(ctx.vault)
    session = store.load(ctx.session)
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


def after_call(tool_name: str, arguments: dict[str, Any], result: dict[str, Any],
               ctx: Any, effect: str = "", permission: str = "",
               normalised: dict[str, Any] | None = None) -> dict[str, Any]:
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
