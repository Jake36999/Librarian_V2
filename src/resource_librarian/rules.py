"""Every rule the system enforces, stated once.

V1 stated some of its rules in four places: a docstring, the Design
Specification, an agent prompt and a test. This module is the one place. Code
refuses by raising `Refusal` with a code from `RULES`, and the documentation
page is generated from the same table, so the statement a reader sees and the
statement the code enforces cannot drift apart.

A refusal names the rule that refused and says what to do instead. A generic
error tells the caller nothing about what to change; a named one produces a
decision.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    code: str
    group: str
    statement: str


_RULES = [
    # --- truth and evidence ------------------------------------------------
    Rule("MARKDOWN_IS_TRUTH", "truth",
         "Notes are authoritative. Everything under .librarian/ is derived and "
         "can be deleted and rebuilt; a conflict resolves to the note."),
    Rule("EVIDENCE_REQUIRED", "truth",
         "No factual field is written without a fetched source. 'Unknown' is a "
         "valid value; a plausible guess is not."),
    Rule("EVIDENCE_IS_NEVER_EDITED", "truth",
         "Evidence is kept exactly as it was fetched. A new fetch is a new "
         "record; an old one is never rewritten."),
    Rule("EVIDENCE_QUOTE_VERIFIED", "truth",
         "Every claim in an offering carries a quote: the exact text it rests "
         "on, found in the cited Source, its evidence, or the project file. A quote that "
         "cannot be found refuses the whole draft."),
    Rule("REVIEW_CHALLENGED", "truth",
         "Where a library turns review on, a claim a reviewer found unsupported - with the "
         "passage's own words to show it - goes back to the lead model: revise it, or keep "
         "it with a rebuttal. A kept, challenged claim is shown with the challenge, and only "
         "a person promotes the offering that holds it."),
    Rule("RUN_BEFORE_CLAIM", "truth",
         "A capability is not reported as available until it has produced a "
         "result, an answer or a recorded refusal on this install."),
    # --- framing -----------------------------------------------------------
    Rule("DATA_IS_UNFRAMED", "framing",
         "What a source contains and says is recorded with no knowledge of any "
         "project, need or session. Framing enters only at the knowledge layer."),
    Rule("OPEN_ANALYSIS_STRICT_RETURN", "framing",
         "A model describing a source gets one chunk and one question, and its "
         "answer must match a closed shape or it is refused."),
    Rule("INTERPRETATION_IS_NOT_MACHINE_WORK", "framing",
         "The sentence a reader acts on (Bottom Line, What It Solves) is written "
         "by a person unless the vault's promotion setting says otherwise, and "
         "is never drafted by a model that can see the project."),
    Rule("LOCATE_DO_NOT_ADJUDICATE", "framing",
         "The catalogue identifies and describes; the user decides. A signal "
         "may lower a rank when it predicts irrelevance, never hide a source "
         "because of a use nobody stated."),
    Rule("POSTURE_DECIDES_CONSEQUENCE", "framing",
         "A licence is recorded as read. What it costs is read from the vault's "
         "distribution posture, not from the classifier."),
    # --- search ------------------------------------------------------------
    Rule("CONSTRAINTS_ELIMINATE", "search",
         "A stated constraint removes candidates; it never merely re-ranks them."),
    Rule("READS_NEVER_CALL_A_GENERATIVE_MODEL", "search",
         "Search can only return things that exist. No generative model stands "
         "between a query and the index."),
    Rule("EVERY_RESULT_SAYS_WHY", "search",
         "Every result carries a reason assembled from what matched, never "
         "generated."),
    # --- vocabulary --------------------------------------------------------
    Rule("NO_SCHEMA_DRIFT", "vocabulary",
         "Note shapes, axes and axis values change only by editing the vault's "
         "About notes. Growth goes through proposals a person accepts."),
    Rule("BRIEF_REQUIRED", "vocabulary",
         "A research request must state at least one disqualifier: what a "
         "candidate must not assume, require or depend on."),
    Rule("UNIQUE_NOTE_NAMES", "vocabulary",
         "A note name is unique across the whole vault, whatever its folder."),
    # --- failure -----------------------------------------------------------
    Rule("FAILURE_MUST_BE_LOUD", "failure",
         "An operation that can fail must be unable to fail silently."),
    Rule("THRESHOLD_CARRIES_ITS_DISTRIBUTION", "failure",
         "A corpus-relative constant ships with the function that re-derives it."),
    # --- sessions ----------------------------------------------------------
    Rule("PHASE_GATE", "sessions",
         "Inside a session, a write is refused outside the phase that unlocks it. "
         "Reads are never gated."),
    Rule("BUDGET_SPENT", "sessions",
         "A phase's call budget is spent: advance, park the session, or ask the person."),
    Rule("SESSION_REQUIRED", "sessions",
         "The operation needs an open session. open_session starts one; resume_session "
         "reopens a parked or closed one."),
    Rule("PROJECT_ACCESS_OFF", "sessions",
         "A project's own files are read only where a person allowed it: project access on "
         "for this library, and the folder added in Settings -> Projects. The model never "
         "names a project path; nothing was read."),
    Rule("PROJECT_WRITES_OFF", "sessions",
         "Reading a project is not editing it: edits are allowed per folder by a person, "
         "separately from project access, and every applied edit is asked for. Nothing was "
         "changed."),
    Rule("PERMISSION_DENIED", "sessions",
         "The permission mode or the tool's own setting denied this action; nothing was "
         "done. Plan mode proposes and never writes."),
    Rule("PERMISSION_UNANSWERED", "sessions",
         "A permission request waited for a person and nobody answered. The session is "
         "parked; silence is never approval."),
    Rule("PERSON_CONFIRMS", "sessions",
         "Writes the vault reserves for a person (promotion under `promotion.mode = "
         "\"person\"`, closing a session's offering) wait for a person's answer to a "
         "recorded question; the surface routes it to the person, never to the model."),
    Rule("LENS_LIMIT", "sessions",
         "A thread holds at most three adopted lenses: each is an instruction in every "
         "later prompt. Drop one before adopting another."),
    Rule("REWIND_BLOCKED", "sessions",
         "A message is rewound to only when nothing after it has written to the vault; "
         "rewinding past a write would silently discard it. Branch instead, or accept the "
         "write."),
    Rule("MESSAGE_NOT_FOUND", "sessions",
         "rewind_session and branch_session act on a message index this thread actually "
         "has, counted from the messages a resumed thread would show."),
    # --- boundaries --------------------------------------------------------
    Rule("CLOSED_ACTION_REGISTRY", "boundaries",
         "Only registered tools run. An unregistered name is an error; a blocked "
         "agent reports the gap rather than writing a script."),
    Rule("TIER_REFUSED", "boundaries",
         "A tool outside the caller's tier is refused by name, with the tier "
         "that grants it."),
    Rule("EXECUTION_SANDBOX_ONLY", "boundaries",
         "Code runs only in a fresh Docker container of its own: no network, no credentials, "
         "a read-only root, removed afterwards - never on this machine itself. The agent runs "
         "code it wrote (asked like any write); a person runs a script file or a claim's "
         "failing input. A run writes outside its container only to its own landing pad, and "
         "nothing that lands is ever run, imported or moved by the app. Without a running "
         "Docker there is no run."),
    Rule("NO_ARBITRARY_SHELL", "boundaries",  # code a model writes runs only in the sandbox
         "No command line is built from model output. Models emit parameters; "
         "code builds commands."),
    Rule("STAGING_BEFORE_VAULT", "boundaries",
         "Machine-produced notes are staged first and promoted by the vault's "
         "promotion rule."),
    Rule("SENSITIVITY_REVIEW", "boundaries",
         "Dual-use material goes to a person for review and is never promoted "
         "automatically, whatever the promotion setting."),
    Rule("OBSERVER_WITHOUT_ACTUATION", "boundaries",
         "The librarian reads projects and never writes into a project's repository, except "
         "through project_edit: in a folder where a person allowed edits, one asked-for, "
         "diffed, logged and backed-up change at a time. It never runs a project's code."),
    Rule("SWEEP_GATED", "boundaries",
         "An unattended sweep waits until the vault's retrieval has passed its own eval "
         "and a person has read the previous cohort: volume into unproven search hides "
         "the problem instead of exposing it."),
    Rule("VAULT_EXISTS", "boundaries",
         "A folder that is already a vault is never initialised again."),
    Rule("VAULT_REQUIRED", "boundaries",
         "The operation needs a vault. Run `init` to create one, or point at an "
         "existing vault."),
]

RULES: dict[str, Rule] = {rule.code: rule for rule in _RULES}


class Refusal(Exception):
    """A decision, not a crash: which rule refused, and what to do instead."""

    def __init__(self, code: str, detail: str, extra: dict | None = None):
        if code not in RULES:
            raise KeyError(f"unknown rule code {code!r}")
        self.code = code
        self.detail = detail
        self.extra = dict(extra or {})
        super().__init__(f"{code}: {detail}")

    def to_dict(self) -> dict:
        return {"refused": self.code, "rule": RULES[self.code].statement,
                "detail": self.detail, **self.extra}


def render_markdown() -> str:
    """The rules page, generated from the table above so it cannot drift."""
    lines = ["# Rules", "", "Generated from `rules.py`. Edit the code, not this page.", ""]
    for group in dict.fromkeys(rule.group for rule in _RULES):
        lines += [f"## {group.capitalize()}", "", "| Code | Rule |", "| --- | --- |"]
        lines += [f"| `{r.code}` | {r.statement} |" for r in _RULES if r.group == group]
        lines.append("")
    return "\n".join(lines)
