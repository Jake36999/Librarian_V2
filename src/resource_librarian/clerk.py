"""The clerk channel: description tasks that carry nothing but the task.

A clerk task is one chunk of evidence, one question and a closed shape for the
answer (`OPEN_ANALYSIS_STRICT_RETURN`). It is built here, by the core, and its
payload has exactly those parts: no project, brief, session, catalogue purpose
or earlier answer can reach it, because no constructor accepts one
(`DATA_IS_UNFRAMED`). A model that knows what the catalogue wants drifts toward
it; one that does not can only describe what is in front of it.

Four tasks are allowed minimal framing, because their job is impossible
without it: `screen` and `fit` see the need wording and the disqualifiers, and
are asked what the text *contradicts* or *shows*, never whether the source is
good; `queries` sees a need to translate into search vocabulary; `relevance`
sees a topic to check a paper's abstract against, never the source's other
evidence. None of the four write anything that ends up on a Source note
(`inside`, `mechanics`, `uses`, `terms`, `axis`, `bottom_line`, all unframed).

Answers are checked, not trusted:
- the reply must match the schema (one repair attempt, then refused);
- `confident: false` is dropped;
- every bullet must be grounded in the chunk it came from, and every quote
  must appear in it; what fails is dropped and reported;
- a screen `reject` whose quoted contradiction is not in the text becomes
  `unclear`; a `fit` answer with an unverifiable quote becomes `uncertain`.

Endpoints are configured in `[clerk]` of the vault's config. Concurrency is a
property of the endpoint: a local server keeps one resident model and runs
tasks one after another; a hosted API gets a bounded pool. With no endpoint,
tasks wait in `.librarian/queue/clerk/` and the caller is told; the research
model is never offered them as a fallback, because a framed answer is worse
than a late one.

A waiting task is named by its content, so re-running the review that raised
it raises the same task. A clerk agent (the Cowork plugin's subagent, in its
own context) takes waiting tasks one at a time and submits answers; the next
run of the owning review uses them, checked like any other reply.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

MAX_BULLETS = 6
BULLET_CHARS = 160
REPAIR_ATTEMPTS = 1
GROUNDED_SHARE = 0.5          # share of a bullet's content words found in its chunk
STOP = set("""a an and are as at be but by can do does for from has have how i if in
into is it its of on or so that the their then there these they this to was were what
when where which who will with without would you your via also any each other such""".split())
PAYLOAD_KEYS = frozenset({"task", "system", "user", "schema", "temperature", "max_tokens"})


def _bullets(name: str = "bullets", max_items: int = MAX_BULLETS) -> dict[str, Any]:
    return {"type": "object", "required": [name], "properties": {
        name: {"type": "array", "maxItems": max_items,
               "items": {"type": "string", "maxLength": BULLET_CHARS}}}}


@dataclass(frozen=True)
class Kind:
    """How one kind of task is asked and checked."""
    name: str
    purpose: str
    schema: dict[str, Any]
    temperature: float = 0.0
    max_tokens: int = 500
    chunk_chars: int = 6000
    bullet_fields: tuple[str, ...] = ()        # each string must be grounded in the chunk
    quote_fields: tuple[str, ...] = ()         # each must appear verbatim in the chunk


KINDS: dict[str, Kind] = {k.name: k for k in (
    Kind("screen", "decide whether a text contradicts any of the stated constraints",
         {"type": "object", "required": ["verdict", "reason"], "properties": {
             "verdict": {"type": "string", "enum": ["keep", "reject", "unclear"]},
             "reason": {"type": "string", "maxLength": 300},
             "contradicts": {"type": "array", "maxItems": 5,
                             "items": {"type": "string", "maxLength": 200}}}},
         max_tokens=300, chunk_chars=5000, quote_fields=("contradicts",)),
    Kind("fit", "decide whether the evidence shows a source doing what a need describes",
         {"type": "object", "required": ["recommendation", "reason", "evidence_quote"],
          "properties": {
              "recommendation": {"type": "string", "enum": ["fits", "does_not_fit",
                                                            "uncertain"]},
              "reason": {"type": "string", "maxLength": 300},
              "evidence_quote": {"type": "string", "maxLength": 300}}},
         temperature=0.1, max_tokens=500, quote_fields=("evidence_quote",)),
    Kind("inside", "say what a repository is made of, from its file listing", _bullets(),
         temperature=0.15, max_tokens=600, chunk_chars=7000, bullet_fields=("bullets",)),
    Kind("mechanics", "say how a project works, from its own documentation", _bullets(),
         temperature=0.15, max_tokens=700, chunk_chars=8000, bullet_fields=("bullets",)),
    Kind("uses", "say where a project is meant to be used, from its documentation",
         _bullets(max_items=4), temperature=0.15, max_tokens=600, chunk_chars=8000,
         bullet_fields=("bullets",)),
    Kind("claims", "say what a paper's own abstract claims", _bullets(max_items=5),
         temperature=0.15, max_tokens=500, chunk_chars=3000, bullet_fields=("bullets",)),
    Kind("terms", "list the technical terms a text uses, with the sentence each appears in",
         {"type": "object", "required": ["terms"], "properties": {
             "terms": {"type": "array", "maxItems": 12, "items": {
                 "type": "object", "required": ["term", "sentence"], "properties": {
                     "term": {"type": "string", "maxLength": 60},
                     "sentence": {"type": "string", "maxLength": 300}}}}}},
         max_tokens=900, chunk_chars=6000),
    Kind("queries", "turn a description of a need into search terms",
         {"type": "object", "required": ["queries"], "properties": {
             "queries": {"type": "array", "maxItems": 6,
                         "items": {"type": "string", "maxLength": 80}}}},
         temperature=0.3, max_tokens=400, chunk_chars=2000),
    Kind("relevance", "decide whether a paper's own abstract engages with a topic",
         {"type": "object", "required": ["verdict", "reason"], "properties": {
             "verdict": {"type": "string", "enum": ["keep", "reject", "unclear"]},
             "reason": {"type": "string", "maxLength": 250}}},
         max_tokens=300, chunk_chars=3000),
    Kind("sensitivity", "say whether material is dual-use",
         {"type": "object", "required": ["sensitivity", "reason"], "properties": {
             "sensitivity": {"type": "string", "enum": ["normal", "review_required"]},
             "reason": {"type": "string", "maxLength": 250}}},
         max_tokens=300, chunk_chars=5000),
    Kind("bottom_line", "state plainly what a source is and what it does, from evidence alone",
         {"type": "object", "required": ["bottom_line", "what_it_solves", "confident"],
          "properties": {
              "bottom_line": {"type": "string", "maxLength": 220},
              "what_it_solves": {"type": "string", "maxLength": 600},
              "confident": {"type": "boolean"}}},
         temperature=0.2, max_tokens=600, bullet_fields=("bottom_line", "what_it_solves")),
    Kind("points", "say what a passage of a text itself claims, argues or explains",
         _bullets(max_items=5), temperature=0.15, max_tokens=600, chunk_chars=6000,
         bullet_fields=("bullets",)),
    Kind("limits", "say what a text itself states about its own limits, assumptions and "
                   "conditions", _bullets(max_items=4),
         temperature=0.15, max_tokens=500, chunk_chars=6000, bullet_fields=("bullets",)),
    # The lens chain (V1's progressive perspective prompts, E1-E11 in
    # `internal docs/Literature Alignment - Agentic AI Trust and Architecture
    # 2026-09-26.md`): perspective -> attention -> challenge -> role -> probe
    # -> synthesize. Each step after the first is given the previous steps'
    # own answers, drawn from this chunk and nothing else, so the chain
    # narrows toward a stance the passage itself teaches rather than jumping
    # to one. The challenge (`lens_discriminate`) is the odd one out: it is
    # never told which stance was proposed, and judges it blind among decoys -
    # a guard against the "stochastic mirror" effect where later steps just
    # elaborate on an earlier claim rather than checking it (deep_read.py
    # wires the actual sequence and the windowing each step reads).
    Kind("lens_perspective", "decide what stance or way of framing a problem, if any, a "
                             "passage requires - not summarize the passage's topic",
         {"type": "object",
          "required": ["has_perspective", "name", "explanation", "source_quote"],
          "properties": {
              "has_perspective": {"type": "boolean"},
              "name": {"type": "string", "maxLength": 80},
              "explanation": {"type": "string", "maxLength": 400},
              "source_quote": {"type": "string", "maxLength": 300}}},
         temperature=0.2, max_tokens=500, chunk_chars=6000, quote_fields=("source_quote",)),
    Kind("lens_attention", "say what a named reasoning stance makes someone weigh, and what "
                           "it lets fade into the background",
         {"type": "object", "required": ["attends_to", "deprioritizes"], "properties": {
             "attends_to": {"type": "array", "maxItems": 5, "items": {
                 "type": "object", "required": ["what", "because"], "properties": {
                     "what": {"type": "string", "maxLength": 160},
                     "because": {"type": "string", "maxLength": 300}}}},
             "deprioritizes": {"type": "array", "maxItems": 5,
                               "items": {"type": "string", "maxLength": 160}}}},
         temperature=0.3, max_tokens=600, chunk_chars=3000),
    # E11, rebuilt blind (review 2026-09-27, P1-L2): the live run found the
    # challenge above returned one verdict per model whatever it was shown
    # (qwen3-4b `weak` 9/9, qwen3-8b `fails` 9/9, true stance included) -
    # being told "someone proposed this, try to disprove it" steers the label,
    # the benchmark's own warning. Here the model is never told which stance
    # was proposed: it judges three unlabelled candidates, and Python scores
    # whether it picked the proposed one and rejected the decoys.
    Kind("lens_discriminate", "judge which, if any, of several candidate reasoning stances a "
                              "passage itself teaches",
         {"type": "object", "required": ["judgements"], "properties": {
             "judgements": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
                 "type": "object", "required": ["option", "teaches", "quote"], "properties": {
                     "option": {"type": "string", "enum": ["A", "B", "C", "D"]},
                     "teaches": {"type": "boolean"},
                     "quote": {"type": "string", "maxLength": 300}}}}}},
         temperature=0.0, max_tokens=500, chunk_chars=3200),
    Kind("lens_role", "cast a reasoning stance as a role a reasoning agent could adopt",
         {"type": "object",
          "required": ["role_purpose", "role_capabilities", "role_expectations",
                      "transfers_to"],
          "properties": {
              "role_purpose": {"type": "string", "maxLength": 300},
              "role_capabilities": {"type": "array", "maxItems": 5,
                                    "items": {"type": "string", "maxLength": 160}},
              "role_expectations": {"type": "array", "maxItems": 5,
                                    "items": {"type": "string", "maxLength": 160}},
              "transfers_to": {"type": "array", "minItems": 2, "maxItems": 2,
                               "items": {"type": "string", "maxLength": 120}}}},
         temperature=0.3, max_tokens=600, chunk_chars=3000),
    # E1: what V1's LENS_SCAN called activation_triggers/known_blind_spots,
    # restated as falsifiable probes plus the failure they catch.
    Kind("lens_probe", "say what concrete questions a reasoning stance should make you ask, "
                       "the failure they catch, and when the stance is and isn't worth "
                       "reaching for",
         {"type": "object",
          "required": ["probes", "catches", "applies_when", "not_when"],
          "properties": {
              "probes": {"type": "array", "minItems": 1, "maxItems": 3, "items": {
                  "type": "object", "required": ["question", "because"], "properties": {
                      "question": {"type": "string", "maxLength": 200},
                      "because": {"type": "string", "maxLength": 300}}}},
              "catches": {"type": "string", "maxLength": 250},
              "applies_when": {"type": "string", "maxLength": 200},
              "not_when": {"type": "string", "maxLength": 200}}},
         temperature=0.3, max_tokens=600, chunk_chars=3000),
    Kind("lens_synthesize", "combine a stance, its attention pattern and its role into one "
                            "open-ended instruction that equips a model to reason from it",
         {"type": "object", "required": ["prompt_fragment"], "properties": {
             "prompt_fragment": {"type": "string", "maxLength": 800}}},
         temperature=0.3, max_tokens=500, chunk_chars=3000),
    # W3 weekly-review (Co-work Roadmap §2): composed from a structured dump
    # of what was actually gathered (agenda buckets, cross-session activity,
    # the desk), not source evidence, so this has no quote/bullet grounding
    # check the way a source claim would - the person reviewing the draft
    # before `reflection_accept` ever writes it is the safeguard instead,
    # the same trust boundary `ask_user`-mediated confirmations use elsewhere.
    Kind("reflection", "write a short first-person reflection on a week's own gathered "
                       "activity - only what is actually listed below",
         {"type": "object", "required": ["reflection"], "properties": {
             "reflection": {"type": "string", "maxLength": 1200}}},
         temperature=0.4, max_tokens=500, chunk_chars=4000),
    # Roadmap §4 G3: the review gate. One claim, its quote and the passage the
    # quote sits in - never the draft - and a verdict. A `fails` counts only
    # with a counter-quote found in the passage (else `unchecked`); G1 found
    # judges rarely wave a false claim through but often dismiss a sound one,
    # so a `fails` goes back to the lead model as a challenge, not a veto.
    Kind("review", "check whether a passage supports a claim made from it",
         {"type": "object", "required": ["verdict", "reason"], "properties": {
             "verdict": {"type": "string", "enum": ["holds", "fails", "unsupported"]},
             "counter_quote": {"type": "string", "maxLength": 400},
             "reason": {"type": "string", "maxLength": 300}}},
         max_tokens=1500, chunk_chars=5000, quote_fields=("counter_quote",)),
    # Roadmap §4 C4: the document-level pass over a fully read source. Which
    # claims each stance rests on is checked by code (they must exist and
    # come from two or more parts); its verbatim quotes come from `lens_support`.
    Kind("lens_document", "say which reasoning stances a text teaches across its parts, "
                          "from the claims each part makes",
         {"type": "object", "required": ["stances"], "properties": {
             "stances": {"type": "array", "maxItems": 3, "items": {
                 "type": "object",
                 "required": ["name", "explanation", "claims", "catches", "prompt_fragment"],
                 "properties": {
                     "name": {"type": "string", "maxLength": 80},
                     "explanation": {"type": "string", "maxLength": 400},
                     "claims": {"type": "array", "minItems": 2, "maxItems": 6,
                                "items": {"type": "string", "maxLength": 8}},
                     "catches": {"type": "string", "maxLength": 250},
                     "applies_when": {"type": "string", "maxLength": 200},
                     "not_when": {"type": "string", "maxLength": 200},
                     "prompt_fragment": {"type": "string", "maxLength": 400}}}}}},
         temperature=0.2, max_tokens=1800, chunk_chars=9000),
    Kind("lens_support", "copy the sentence of a passage that shows a stance",
         {"type": "object", "required": ["quote"], "properties": {
             "quote": {"type": "string", "maxLength": 400}}},
         max_tokens=400, chunk_chars=6500, quote_fields=("quote",)),
    Kind("reply_claims", "list the claims a reply makes about the notes it links",
         {"type": "object", "required": ["claims"], "properties": {
             "claims": {"type": "array", "maxItems": 5, "items": {
                 "type": "object", "required": ["claim", "note"], "properties": {
                     "claim": {"type": "string", "maxLength": 300},
                     "note": {"type": "string", "maxLength": 120}}}}}},
         max_tokens=900, chunk_chars=8000),
    Kind("probe_answers", "say which questions a text's own claims answer",
         {"type": "object", "required": ["answered"], "properties": {
             "answered": {"type": "array", "maxItems": 12, "items": {
                 "type": "object", "required": ["probe", "claim"], "properties": {
                     "probe": {"type": "string", "maxLength": 12},
                     "claim": {"type": "string", "maxLength": 8}}}}}},
         max_tokens=800, chunk_chars=9000),
)}

LENS_QUOTE_CHARS = 15         # V1's floor: a shorter "quote" is not a passage


def axis_kind(axis: str, values: Sequence[str]) -> Kind:
    return Kind(f"axis:{axis}", f"choose the single value of '{axis}' the evidence supports",
                {"type": "object", "required": ["value", "confident"], "properties": {
                    "value": {"type": "string", "enum": sorted(values)},
                    "evidence": {"type": "string", "maxLength": 200},
                    "confident": {"type": "boolean"}}},
                max_tokens=200, chunk_chars=5000, quote_fields=("evidence",))


def topic_kind(topics: Sequence[str]) -> Kind:
    """The vault's own closed list of topics is the schema, like an axis's
    values: structure of the catalogue, not a need to write toward."""
    return Kind("topic", "choose which one of a closed list of subject areas a text belongs "
                         "under",
                {"type": "object", "required": ["topic", "evidence", "confident"],
                 "properties": {
                     "topic": {"type": "string", "enum": sorted(topics)},
                     "evidence": {"type": "string", "maxLength": 200},
                     "confident": {"type": "boolean"}}},
                max_tokens=250, chunk_chars=5000, quote_fields=("evidence",))


# ------------------------------------------------------------------ tasks

@dataclass(frozen=True)
class Task:
    """What a clerk sees, entire. Built only by the constructors below."""
    kind: Kind
    chunk: str
    question: str
    id: str = field(default_factory=lambda: secrets.token_hex(6))

    def clipped(self) -> str:
        text = (self.chunk or "").strip()
        limit = self.kind.chunk_chars
        if len(text) <= limit:
            return text
        head = text[:limit]
        cut = head.rfind("\n")
        return (head[:cut] if cut > limit // 2 else head) + "\n[... truncated ...]"

    def payload(self) -> dict[str, Any]:
        """Exactly what leaves the core. A test holds this to `PAYLOAD_KEYS`."""
        return {"task": self.kind.name,
                "system": _system_prompt(self.kind),
                "user": f"{self.question}\n\n---\n{self.clipped()}\n---",
                "schema": self.kind.schema,
                "temperature": self.kind.temperature,
                "max_tokens": self.kind.max_tokens}


def _system_prompt(kind: Kind) -> str:
    """Short, and silent about the wider system: the job, the evidence rule,
    the shape."""
    return (f"You describe material from evidence. Your task: {kind.purpose}.\n\n"
            "Rules:\n"
            "- Use only what is in the text you are given. You have no other knowledge "
            "of it.\n"
            "- If the text does not say, choose the least committed option the schema "
            "allows, or leave the field empty. Do not infer.\n"
            "- Do not judge whether it is good, popular or worth using.\n"
            "- Reply with one JSON object matching this schema, and nothing else:\n"
            f"{json.dumps(kind.schema)}")


def screen(text: str, need: str, disqualifiers: Sequence[str]) -> Task:
    rules = "\n".join(f"- {d}" for d in disqualifiers)
    return Task(KINDS["screen"], text, (
        f"Someone is looking for something that meets this description:\n  {need}\n\n"
        f"It must not do any of the following:\n{rules}\n\n"
        "Read the text below. Does anything in it contradict one of those constraints?\n"
        "- 'reject' only if the text states something that contradicts one; quote it, "
        "exactly, in `contradicts`.\n"
        "- 'unclear' if the text does not say either way. This is a normal answer.\n"
        "- 'keep' if the text positively shows it does not contradict them.\n"
        "Match on function, never on shared vocabulary. Do not judge quality or "
        "popularity."))


def fit(evidence: str, need: str, disqualifiers: Sequence[str]) -> Task:
    rules = "\n".join(f"- {d}" for d in disqualifiers) or "- (none stated)"
    return Task(KINDS["fit"], evidence, (
        f"Below is evidence about a source. It was found against this need:\n  {need}\n\n"
        f"It must not:\n{rules}\n\n"
        "Does the evidence show the source actually DOING what the need describes, not "
        "merely mentioning a word the need also uses? Match on function, never on "
        "shared vocabulary.\n"
        "- 'fits' only if the evidence shows it.\n"
        "- 'does_not_fit' if it shows something else, or contradicts a constraint.\n"
        "- 'uncertain' if you cannot tell.\n"
        "`reason`: what the evidence does or does not show. `evidence_quote`: the exact "
        "words your reason rests on, copied verbatim. The quote is checked."))


def inside(listing: str) -> Task:
    return Task(KINDS["inside"], listing, (
        "Below is a summary of a repository's directories, file extensions and counts, "
        "and sometimes its modules with the names they define. Write up to six short "
        "bullets saying what it is made of.\n"
        "- Every bullet must cite a directory, file, name or count that appears "
        "below.\n- Do not say what it is for; only what is in it."))


def mechanics(documentation: str) -> Task:
    return Task(KINDS["mechanics"], documentation, (
        "Below is a project's own documentation. Write up to six short bullets on how "
        "it works: what it takes in, what it does, what it produces, what it requires.\n"
        "- Only state what the text states.\n- Prefer a specific mechanism over a "
        "general claim.\n- Leave out marketing sentences, badges and comparisons."))


def uses(documentation: str) -> Task:
    return Task(KINDS["uses"], documentation, (
        "Below is a project's own documentation. Write up to four short bullets on the "
        "situations it says it is for.\n- Only situations the text names. If it names "
        "none, return an empty list."))


def claims(abstract: str) -> Task:
    return Task(KINDS["claims"], abstract, (
        "Below is a paper's own abstract. Write up to five short bullets stating what "
        "the paper itself claims to show, argue or contribute.\n- Only what the "
        "abstract states; its own claim, not an assessment of it."))


def terms(text: str) -> Task:
    return Task(KINDS["terms"], text, (
        "List up to twelve technical terms the text below uses, each with the sentence "
        "it appears in, copied exactly. Only terms the text itself uses; do not define "
        "them."))


def queries(need: str) -> Task:
    return Task(KINDS["queries"], need, (
        "Below is a description of something someone needs. Write up to six short "
        "search queries that would find material matching it.\n- Use the words the "
        "field itself uses, not the words in the description.\n- Vary them: a specific "
        "term, a general one, a synonym.\n- Two to five words each."))


def relevance(abstract: str, topic: str) -> Task:
    return Task(KINDS["relevance"], abstract, (
        f"Someone is researching this topic:\n  {topic}\n\n"
        "Below is a paper's own abstract. Does it show the paper engages with that "
        "topic's substance, not merely sharing a word with it?\n- 'keep' only if the "
        "abstract describes work on the topic.\n- 'reject' if it is about something "
        "else.\n- 'unclear' if you cannot tell from the abstract alone."))


def sensitivity(text: str) -> Task:
    return Task(KINDS["sensitivity"], text, (
        "Read the text below. Is this offensive security tooling (exploitation, "
        "credential theft, evasion), surveillance or tracking of people, or otherwise "
        "dual-use in a way that could cause harm?\n- 'review_required' if the text shows "
        "that it is.\n- 'normal' otherwise, including defensive security tools.\n"
        "Say which words in the text you relied on."))


def bottom_line(evidence: str) -> Task:
    """Unframed: the sentence a reader acts on, drafted from evidence alone."""
    return Task(KINDS["bottom_line"], evidence, (
        "Below is evidence about a source. From it alone:\n"
        "- `bottom_line`: one sentence saying what this specifically is and does.\n"
        "- `what_it_solves`: two or three sentences on the problem it addresses, "
        "stated so someone in an unrelated field could follow.\n"
        "Use only what the evidence states. Set `confident` to false if the evidence is "
        "too thin to say."))


def axis(name: str, values: Sequence[str], text: str, ask: str = "") -> Task:
    ask = ask or f"Which value of '{name}' does the evidence support?"
    return Task(axis_kind(name, values), text, (
        f"{ask}\n\nChoose exactly one value from the schema's list. Set `confident` to "
        f"false if the text does not really say, and quote what you used in `evidence`."))


def points(passage: str) -> Task:
    return Task(KINDS["points"], passage, (
        "Below is a passage from a text. Write up to five short bullets stating what the "
        "passage itself claims, argues or explains.\n- Only what the passage states; its "
        "own point, not an assessment of it.\n- Leave out headings, navigation, citations "
        "and boilerplate. If it states nothing of substance, return an empty list."))


def limits(text: str) -> Task:
    return Task(KINDS["limits"], text, (
        "Below is part of a text. Write up to four short bullets on what the text itself "
        "says about its own limits: assumptions it makes, conditions under which it holds, "
        "what it leaves out, open questions it names, or evidence it says is weak.\n"
        "- Only what the text states about itself; not your assessment of it.\n"
        "- If it states none, return an empty list. That is a normal answer."))


def reflection(gathered: str) -> Task:
    """`gathered` is a plain-text rendering of the week's own agenda/activity/
    desk facts (`tools/sessions.py`'s `reflection_draft`); never source
    evidence, so this carries no quote requirement - only "don't invent
    anything not listed below.\""""
    return Task(KINDS["reflection"], gathered, (
        "Below is what was actually gathered this week: tasks, cross-session activity, and "
        "the working desk. Write a short reflection (3-6 sentences) grounded only in what is "
        "listed - what got done, what's overdue, what's still open.\n"
        "- Do not invent activity, sources or tasks that are not listed below.\n"
        "- Plain prose, first person plural ('this week...'), no headings or bullets."))


def topic(text: str, topics: Sequence[str]) -> Task:
    return Task(topic_kind(topics), text, (
        "Below is text from a source. Which one subject area from the schema's list does it "
        "belong under?\n- Choose by what the text is about, not by words it shares with a "
        "topic name.\n- Set `confident` to false if none really fits; quote what you "
        "relied on in `evidence`."))


def lens_perspective(chunk: str) -> Task:
    # Measured 2026-09-28 (`scripts/lens_eval.py`, three gold sources, four
    # model tiers): the earlier wording - a doctor/engineer exemplar and "most
    # passages do not... that is the normal, correct answer" - recovered the
    # gold stance in 0-2 of 3 sources; this one in 3/3 on the API tiers at a
    # similar precision floor. Recall belongs here; precision is the blind
    # challenge's job (`lens_discriminate`) and, last, the person's.
    return Task(KINDS["lens_perspective"], chunk, (
        "Does the passage below teach, name or demonstrate a reusable way of reasoning - a way "
        "of looking at, evaluating or approaching a problem that someone could apply again to "
        "other material (for example an evaluation framework, a principle for structuring work, "
        "or a method for checking results)? A plain fact, a definition, a citation list or a "
        "chapter's own introduction is not one, even when it mentions a named concept.\n\n"
        "If yes, set `has_perspective` true and give:\n"
        "- `name`: short, naming the way of reasoning itself - not the paper, the tool or the "
        "topic it is applied to\n"
        "- `explanation`: what it makes someone do differently\n"
        "- `source_quote`: the exact sentence(s) below it comes from, word for word. This is "
        "checked; an unverifiable quote discards the whole answer.\n\n"
        "If not, set `has_perspective` false and leave the rest empty."))


def lens_attention(chunk: str, name: str, explanation: str) -> Task:
    return Task(KINDS["lens_attention"], chunk, (
        f"Someone has adopted the '{name}' stance on the material below - {explanation}\n\n"
        "Every stance makes some things easy to notice and others easy to miss - that is what "
        "makes it a stance rather than a neutral view. Given this specific one:\n"
        "- `attends_to`: up to five things this stance makes you weigh or prioritize, that a "
        "generic reading would not. Each needs `what` (the thing itself) and `because`: the "
        "exact words below that make it relevant here, copied verbatim. This is checked; an "
        "item without a real quote is dropped.\n"
        "- `deprioritizes`: what it lets fade into the background, risk missing, or treat as "
        "someone else's problem.\n\n"
        "Answer from the stance itself, not from the passage's topic list."))


def _weighs(attends_to: Sequence[dict[str, str] | str]) -> str:
    return "; ".join((w if isinstance(w, str) else str(w.get("what", ""))) for w in attends_to
                     if w) or "(none given)"


OPTIONS = "ABCD"


def lens_document(listing: str) -> Task:
    return Task(KINDS["lens_document"], listing, (
        "Below are the claims a text makes, part by part (each with an id like C4 and the "
        "pages it came from), and any reasoning stances already found inside single parts.\n"
        "Is there a way of reasoning the text teaches across its parts - a stance no single "
        "part states in full, but several parts apply? Give up to three.\n"
        "- A stance is a way of looking at a problem (what to attend to, what failure it "
        "catches), not the text's topic or a summary of it.\n"
        "- `claims`: the ids of the claims it rests on, from at least two different parts. "
        "They are checked.\n"
        "- Do not repeat a stance already found in a single part unless the whole text "
        "widens it.\n"
        "- `prompt_fragment`: one or two sentences telling a model how to reason this way.\n"
        "- If the text teaches no such stance, return an empty list. That is a normal "
        "answer."))


def lens_support(passage: str, name: str, explanation: str) -> Task:
    return Task(KINDS["lens_support"], passage, (
        f"A reader thinks the text below teaches this way of reasoning:\n  {name}: "
        f"{explanation}\n\nCopy, exactly, the one sentence (or two) from the text that "
        "best shows it. The quote is checked against the text; if none shows it, return "
        "an empty quote."))


def probe_answers(listing: str) -> Task:
    return Task(KINDS["probe_answers"], listing, (
        "Below are questions (ids like L1.P2) and the claims a text makes (ids like C4). "
        "For each question that one of the claims directly answers, give the pair. Only a "
        "claim that answers the question itself counts, not one on the same topic. Most "
        "questions may have none; an empty list is a normal answer."))


def reply_claims(reply: str) -> Task:
    return Task(KINDS["reply_claims"], reply, (
        "Below is an assistant's reply. List the factual claims it makes about a note it "
        "links as [[Note Name]] - what the note says, holds or shows - at most five, each "
        "with the linked note's name exactly as written inside the brackets.\n"
        "- Only claims about a linked note's content; not advice, plans or opinions.\n"
        "- If there are none, return an empty list. That is a normal answer."))


def review(claim: str, quote: str, passage: str) -> Task:
    resting = f"resting on these words from it:\n  \"{quote}\"\n" if quote else ""
    return Task(KINDS["review"], passage, (
        f"Someone read the passage below and claims:\n  {claim}\n{resting}\n"
        "Does the passage support the claim as stated?\n"
        "- 'holds': the passage says what the claim says - not more, not broader, not "
        "stronger.\n"
        "- 'fails': the claim goes beyond the passage, contradicts it, or reads the quote "
        "out of its context. Copy into `counter_quote` the exact words from the passage "
        "that show it; the quote is checked, and a 'fails' without one is not counted.\n"
        "- 'unsupported': the passage says nothing either way about what the claim asserts.\n"
        "`reason`: one sentence."))


def lens_discriminate(chunk: str, candidates: Sequence[tuple[str, str]]) -> Task:
    """`candidates` are (name, explanation) pairs, already in the order to show
    them; the caller knows which is the proposed stance, the task never does."""
    listed = "\n".join(f"{OPTIONS[i]}. {name} - {explanation}"
                       for i, (name, explanation) in enumerate(candidates[:len(OPTIONS)]))
    return Task(KINDS["lens_discriminate"], chunk, (
        "Below are some candidate reasoning stances - ways of approaching a problem - and a "
        "passage. Most passages teach at most one stance, and many teach none.\n\n"
        f"{listed}\n\n"
        "For EACH candidate, say whether the passage itself teaches or demonstrates that way of "
        "reasoning - not merely mentions its subject. `teaches` true needs `quote`: the exact "
        "words below that teach it, copied verbatim (this is checked). `teaches` false needs "
        "`quote` empty. Judge each candidate on its own; do not assume any of them is right."))


def lens_role(chunk: str, name: str, explanation: str, attends_to: Sequence[dict[str, str]],
              deprioritizes: Sequence[str]) -> Task:
    return Task(KINDS["lens_role"], chunk, (
        f"The '{name}' stance - {explanation} - weighs {_weighs(attends_to)}, and lets "
        f"{'; '.join(deprioritizes) or '(none given)'} fade into the background.\n\n"
        "If this were a role you briefed a specialist to take before handing them a task - "
        "the way you'd brief a structural engineer differently from a doctor before either "
        "looked at the same machine - what is:\n"
        "- `role_purpose`: what this role exists to do\n"
        "- `role_capabilities`: what it needs to bring or already know\n"
        "- `role_expectations`: what you'd expect from someone actually operating in this "
        "role, given what it weighs and what it misses\n"
        "- `transfers_to`: exactly two OTHER situations, outside this passage's own subject, "
        "where someone would reach for this same stance. If you cannot think of a genuine one "
        "outside this material's own topic, that is a sign this is a topic, not a reusable "
        "stance - name the closest two you can, honestly."))


def lens_probe(chunk: str, name: str, explanation: str, attends_to: Sequence[dict[str, str]],
               deprioritizes: Sequence[str], role_purpose: str) -> Task:
    return Task(KINDS["lens_probe"], chunk, (
        f"The '{name}' stance - {explanation} - weighs {_weighs(attends_to)}, and lets "
        f"{'; '.join(deprioritizes) or '(none given)'} fade into the background. Briefed with "
        f"this role: {role_purpose}\n\n"
        "What makes this stance actually useful, in practice?\n"
        "- `probes`: one to three concrete questions someone briefed with this stance would "
        "ask of a similar artifact - specific to what this stance weighs, not a generic 'is "
        "this good?'. Each needs `because`: the exact words below this question is drawn "
        "from. This is checked; a question without a real quote is dropped, and the whole "
        "stance is dropped if none survive.\n"
        "- `catches`: the one failure a generic reading would miss, that these questions "
        "catch.\n"
        "- `applies_when` / `not_when`: what kind of material this stance is worth reaching "
        "for, and when it would be the wrong lens even though it superficially fits."))


def lens_synthesize(chunk: str, name: str, explanation: str, attends_to: Sequence[dict[str, str]],
                    deprioritizes: Sequence[str], role_purpose: str,
                    role_capabilities: Sequence[str],
                    role_expectations: Sequence[str],
                    probes: Sequence[dict[str, str]] = (), catches: str = "") -> Task:
    questions = "; ".join(p.get("question", "") for p in probes if p) or "(none given)"
    return Task(KINDS["lens_synthesize"], chunk, (
        f"stance: {name} - {explanation}\n"
        f"weighs: {_weighs(attends_to)}\n"
        f"deprioritizes: {'; '.join(deprioritizes) or '(none given)'}\n"
        f"role purpose: {role_purpose}\n"
        f"role capabilities: {'; '.join(role_capabilities) or '(none given)'}\n"
        f"role expectations: {'; '.join(role_expectations) or '(none given)'}\n"
        f"probe questions this stance should prompt: {questions}\n"
        f"failure it catches: {catches or '(none given)'}\n\n"
        "Combine all of this into ONE open-ended instruction that would equip a language "
        "model to adopt this exact reasoning stance before approaching a similar task - it "
        "should lead the model toward asking the probe questions above, not just describe the "
        "stance in the abstract. Write `prompt_fragment` AS the instruction itself, addressed "
        "directly to the model that will use it - not as a description of the instruction, "
        "and not naming this exercise or where it came from."))


def model_specs_kind(modalities: Sequence[str], license_classes: Sequence[str],
                     best_for: Sequence[str], tiers: Sequence[str]) -> Kind:
    return Kind("model_specs", "read a model's specifications off its provider's own "
                              "listing page, and propose a first guess at what it is best "
                              "suited for",
                {"type": "object",
                 "required": ["modality", "license_class", "context_length",
                             "price_input_per_1m", "price_output_per_1m", "tool_calling",
                             "reasoning", "best_for", "suggested_tier", "confident"],
                 "properties": {
                     "modality": {"type": "string", "enum": sorted(modalities)},
                     "license_class": {"type": "string", "enum": sorted(license_classes)},
                     "context_length": {"type": "integer"},
                     "price_input_per_1m": {"type": "number"},
                     "price_output_per_1m": {"type": "number"},
                     "tool_calling": {"type": "boolean"},
                     "reasoning": {"type": "boolean"},
                     "best_for": {"type": "array", "maxItems": len(best_for),
                                 "items": {"type": "string", "enum": sorted(best_for)}},
                     "suggested_tier": {"type": "string", "enum": sorted(tiers)},
                     "evidence": {"type": "string", "maxLength": 250},
                     "confident": {"type": "boolean"}}},
                max_tokens=400, chunk_chars=6000, quote_fields=("evidence",))


def model_specs(text: str, modalities: Sequence[str], license_classes: Sequence[str],
                best_for: Sequence[str], tiers: Sequence[str], model_id: str = "") -> Task:
    """Unframed: a model is a Source like any other, described from its own
    listing page, never from what the librarian already believes about it.

    `best_for` and `suggested_tier` are a first guess only - a listing page
    rarely states them outright, so this is a draft for a person to confirm
    or correct once they have actually used the model, not a measurement."""
    named = f" for '{model_id}'" if model_id else ""
    return Task(model_specs_kind(modalities, license_classes, best_for, tiers), text, (
        f"Below is a provider's own public listing page{named}. Read its specifications from "
        f"the page alone.\n"
        f"- `context_length`: the largest context window stated, in tokens (not characters); "
        f"0 if the page states none.\n"
        f"- `price_input_per_1m` / `price_output_per_1m`: US dollars per 1,000,000 tokens; 0 "
        f"if the page states no per-token price (free, self-hosted, or priced by a different "
        f"unit such as per second or per character).\n"
        f"- `tool_calling`: true only if the page states support for function or tool "
        f"calling.\n"
        f"- `reasoning`: true only if the page describes it as a reasoning model, or as "
        f"returning a separate chain-of-thought.\n"
        f"- `modality`, `license_class`: choose exactly one value from the schema's list "
        f"for each.\n"
        f"- `best_for`: zero or more of the schema's tags, from what the page says about size, "
        f"speed and intended use - a starting guess, not a claim you have tested it.\n"
        f"- `suggested_tier`: your best guess at which of the schema's three roles fits, from "
        f"the same signals; only Tier_1 if the page suggests real scale.\n"
        f"Use only what the page states. Set `confident` to false if the page does not "
        f"really describe this model, and quote what you used for price or context length "
        f"in `evidence`."))


CONSTRUCTORS: dict[str, Callable[..., Task]] = {
    "screen": screen, "fit": fit, "inside": inside, "mechanics": mechanics, "uses": uses,
    "claims": claims, "terms": terms, "queries": queries, "relevance": relevance,
    "bottom_line": bottom_line, "axis": axis, "sensitivity": sensitivity,
    "model_specs": model_specs, "points": points, "limits": limits, "topic": topic,
    "lens_perspective": lens_perspective, "lens_attention": lens_attention,
    "lens_discriminate": lens_discriminate,
    "lens_role": lens_role, "lens_probe": lens_probe,
    "lens_synthesize": lens_synthesize, "reflection": reflection}


# ----------------------------------------------------------------- checking

@dataclass
class Result:
    task: str
    task_id: str
    status: str                       # ok | not_confident | refused | error | queued
    value: dict[str, Any] = field(default_factory=dict)
    dropped: list[str] = field(default_factory=list)
    problems: str = ""
    model: str = ""
    attempts: int = 0

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)


def parse(raw: str, schema: dict[str, Any]) -> tuple[dict[str, Any], str]:
    text = FENCE.sub("", (raw or "").strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return {}, "no JSON object in the reply"
    try:
        value = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON ({exc})"
    if not isinstance(value, dict):
        return {}, "the reply was not a JSON object"
    problems = _check(value, schema)
    return value, "; ".join(problems)


def _check(value: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    problems = [f"missing '{n}'" for n in schema.get("required", []) if n not in value]
    for name, rule in schema.get("properties", {}).items():
        if name in value:
            problems += _check_one(name, value[name], rule)
    return problems


def _check_one(name: str, item: Any, rule: dict[str, Any]) -> list[str]:
    kind = rule.get("type")
    if kind == "string":
        if not isinstance(item, str):
            return [f"'{name}' must be a string"]
        if rule.get("enum") and item not in rule["enum"]:
            return [f"'{name}' must be one of {rule['enum']}, not {item!r}"]
        if rule.get("maxLength") and len(item) > rule["maxLength"]:
            return [f"'{name}' is longer than {rule['maxLength']} characters"]
    elif kind == "array":
        if not isinstance(item, list):
            return [f"'{name}' must be an array"]
        if rule.get("maxItems") and len(item) > rule["maxItems"]:
            return [f"'{name}' has more than {rule['maxItems']} items"]
        if rule.get("minItems") and len(item) < rule["minItems"]:
            return [f"'{name}' has fewer than {rule['minItems']} items"]
        return [p for element in item for p in _check_one(f"{name}[]", element,
                                                          rule.get("items", {}))]
    elif kind == "object":
        if not isinstance(item, dict):
            return [f"'{name}' must be an object"]
        return _check(item, rule)
    elif kind == "boolean" and not isinstance(item, bool):
        return [f"'{name}' must be true or false"]
    return []


_SAME = str.maketrans({"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
                       "\u2014": "-", "\u2013": "-", "\u2010": "-", "\u2011": "-",
                       "\u00a0": " ", "\u202f": " "})


def _normal_map(text: str) -> tuple[str, list[int]]:
    """`normal(text)` plus, for each character of it, the index in `text` it
    came from - so a quote matched in normalised form can be found again in
    the original (deep_read's E3 window). One pass, so the two can't drift:
    typographic quotes and dashes unified, Markdown emphasis dropped,
    whitespace collapsed, lower-cased, and a line-break hyphen between two
    letters joined ("intro- duces" -> "introduces"). PDF text is full of the
    last, and a model quoting it writes the word whole: measured 2026-09-27,
    that alone discarded the gold "four evaluative lenses" passage."""
    out: list[str] = []
    idx: list[int] = []
    for i, ch in enumerate(str(text).translate(_SAME)):
        if ch in "*_`>#\u00ad":                  # emphasis marks; a soft hyphen
            continue
        if ch.isspace():
            if not out or out[-1] == " ":
                continue
            ch = " "
        for low in ch.lower():
            if low.isalpha() and len(out) >= 3 and out[-1] == " " and out[-2] == "-" and \
                    out[-3].isalpha():
                del out[-2:], idx[-2:]
            out.append(low)
            idx.append(i)
    while out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def normal(text: str) -> str:
    return _normal_map(text)[0]


def locate(quote: str, chunk: str) -> int:
    """Where `quote` starts in `chunk`, matched the way `quoted` matches it
    (normalised), or -1."""
    q = normal(quote).strip(" .\"'")
    if not q:
        return -1
    text, idx = _normal_map(chunk)
    at = text.find(q)
    return idx[at] if at != -1 else -1


def quoted(quote: str, chunk: str) -> bool:
    q = normal(quote).strip(" .\"'")
    return len(q) >= 8 and q in normal(chunk)


def grounded(bullet: str, chunk: str) -> bool:
    words = {w for w in re.findall(r"[a-z0-9][a-z0-9_.\-/]+", normal(bullet))
             if len(w) >= 4 and w not in STOP}
    if not words:
        return True
    source = normal(chunk)
    return sum(1 for w in words if w in source) / len(words) >= GROUNDED_SHARE


def verify(task: Task, value: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    """Status, cleaned value and what was dropped, checked against the chunk."""
    chunk = task.clipped()
    dropped: list[str] = []
    value = dict(value)
    if value.get("confident") is False:
        return "not_confident", value, dropped
    for name in task.kind.bullet_fields:
        item = value.get(name)
        if isinstance(item, list):
            kept = [b for b in item if grounded(b, chunk)]
            dropped += [f"{name}: {b}" for b in item if b not in kept]
            value[name] = kept
        elif isinstance(item, str) and item and not grounded(item, chunk):
            dropped.append(f"{name}: {item}")
            value[name] = ""
    for name in task.kind.quote_fields:
        item = value.get(name)
        if isinstance(item, list):
            kept = [q for q in item if quoted(q, chunk)]
            dropped += [f"{name}: {q}" for q in item if q not in kept]
            value[name] = kept
        elif isinstance(item, str) and item and not quoted(item, chunk):
            dropped.append(f"{name}: {item}")
            value[name] = ""
    if task.kind.name == "screen" and value.get("verdict") == "reject" and \
            not value.get("contradicts"):
        value["verdict"] = "unclear"
        value["reason"] = f"[no verifiable contradiction; was 'reject'] {value.get('reason', '')}"
    if task.kind.name == "fit" and value.get("recommendation") != "uncertain" and \
            not value.get("evidence_quote"):
        value["reason"] = (f"[unverifiable quote; was '{value.get('recommendation')}'] "
                           f"{value.get('reason', '')}")
        value["recommendation"] = "uncertain"
    if task.kind.name == "review" and value.get("verdict") == "fails" and \
            not value.get("counter_quote"):
        value["verdict"] = "unchecked"
        value["reason"] = f"[no verifiable counter-quote; was 'fails'] {value.get('reason', '')}"
    if task.kind.name == "bottom_line" and not value.get("bottom_line"):
        return "not_confident", value, dropped
    if task.kind.name == "terms":
        kept_terms = [t for t in value.get("terms", []) if isinstance(t, dict)
                      and quoted(t.get("sentence", ""), chunk)
                      and normal(t.get("term", "")) in normal(t.get("sentence", ""))]
        dropped += [f"terms: {t}" for t in value.get("terms", []) if t not in kept_terms]
        value["terms"] = kept_terms
    if task.kind.name == "lens_perspective" and value.get("has_perspective"):
        name = str(value.get("name") or "").strip()
        explanation = str(value.get("explanation") or "").strip()
        quote = str(value.get("source_quote") or "").strip()
        if not name or not explanation or len(normal(quote)) < LENS_QUOTE_CHARS:
            # An ungrounded stance is discarded whole, never kept without its passage.
            dropped.append(f"lens_perspective: '{name or '(unnamed)'}' has no verifiable "
                           f"source_quote")
            value = {"has_perspective": False, "name": "", "explanation": "",
                     "source_quote": ""}
    if task.kind.name == "lens_attention":
        # E2: each weighed item stands or falls on its own quote; a stance
        # dropping some of them is still a stance, so nothing here fails whole.
        kept = []
        for w in value.get("attends_to", []):
            what = str(w.get("what") or "").strip() if isinstance(w, dict) else ""
            because = str(w.get("because") or "").strip() if isinstance(w, dict) else ""
            if what and quoted(because, chunk):
                kept.append({"what": what, "because": because})
            else:
                dropped.append(f"attends_to: {w}")
        value["attends_to"] = kept
    if task.kind.name == "lens_discriminate":
        # A "teaches" with no real quote is not a judgement anyone can check:
        # it counts as not teaching, whichever candidate it was.
        kept = []
        for j in value.get("judgements", []):
            if not isinstance(j, dict):
                continue
            teaches = bool(j.get("teaches")) and quoted(str(j.get("quote") or ""), chunk)
            if j.get("teaches") and not teaches:
                dropped.append(f"judgements: {j.get('option')} 'teaches' has no verifiable quote")
            kept.append({"option": j.get("option"), "teaches": teaches,
                         "quote": str(j.get("quote") or "") if teaches else ""})
        value["judgements"] = kept
    if task.kind.name == "lens_role":
        # E4: a "transfer" that just restates the passage's own words is a
        # sign of a topic, not a stance. It is a *warning* for the reviewer,
        # not a discard: the schema makes a model name two transfers whether
        # or not any are genuine, so this lexical test catches restatement
        # only, and dropping a lens on it would lose real stances whose
        # transfers happen to share the passage's words (review 2026-09-27).
        transfers = [str(t).strip() for t in value.get("transfers_to", []) if str(t).strip()]
        genuine = [t for t in transfers if not grounded(t, chunk)]
        dropped += [f"transfers_to: {t}" for t in transfers if t not in genuine]
        value["transfers_to"] = genuine
        value["topic_warning"] = not genuine
    if task.kind.name == "lens_probe":
        # E1/E2: probe questions are the point of this step; one without a
        # real quote is dropped, and a lens with none left is not staged.
        kept_probes = []
        for p in value.get("probes", []):
            question = str(p.get("question") or "").strip() if isinstance(p, dict) else ""
            because = str(p.get("because") or "").strip() if isinstance(p, dict) else ""
            if question and quoted(because, chunk):
                kept_probes.append({"question": question, "because": because})
            else:
                dropped.append(f"probes: {p}")
        value["probes"] = kept_probes
        if not kept_probes:
            return "not_confident", value, dropped
    for name in ("deprioritizes", "role_capabilities", "role_expectations"):
        if isinstance(value.get(name), list):
            value[name] = [str(v).strip() for v in value[name] if str(v).strip()]
    return "ok", value, dropped


# ------------------------------------------------------------- lens assembly

INJECTION_MARKERS = re.compile(
    r"https?://|www\.|ignore (all |any )?(previous|prior|earlier) instructions?|"
    r"system prompt|disregard (the |your )?(above|previous|instructions)|"
    r"new instructions|you are now|act as (a |an )?system", re.I)


def discrimination(value: dict[str, Any], proposed: int, n: int) -> tuple[str, str]:
    """Score a `lens_discriminate` answer in Python: (verdict, reason).
    `holds` - the proposed stance is taught and no decoy is; `fails` - it is
    not taught; `undiscriminating` - it and a decoy both are, so the answer
    says nothing about this stance in particular (a yes-to-everything model,
    the mirror failure in its other form)."""
    said = {j.get("option"): j for j in value.get("judgements", []) if isinstance(j, dict)}
    mine = said.get(OPTIONS[proposed], {})
    decoys_taught = [OPTIONS[i] for i in range(n) if i != proposed
                     and said.get(OPTIONS[i], {}).get("teaches")]
    if not mine.get("teaches"):
        return "fails", "a blind judgement did not find the passage teaching this stance"
    if decoys_taught:
        return "undiscriminating", (f"the passage was also judged to teach decoy(s) "
                                    f"{', '.join(decoys_taught)}, so the judgement does not "
                                    f"single this stance out")
    return "holds", f"chosen blind over {n - 1} decoy(s): \"{mine.get('quote', '')[:120]}\""


def verbatim_run(text: str, chunk: str, min_words: int = 8) -> bool:
    """True if `text` copies `min_words` or more consecutive words straight
    out of `chunk` - E5: an instruction should reframe the stance, not quote
    the passage back."""
    words = normal(text).split()
    source = normal(chunk)
    return any(" ".join(words[i:i + min_words]) in source
              for i in range(len(words) - min_words + 1))


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9_.\-/]+", normal(text))
           if len(w) >= 4 and w not in STOP}


def screen_instruction(phi: str, chunk: str, referenced: Sequence[str]) -> str:
    """Empty if `phi` passes E5's checks on a lens instruction, else the
    reason it was discarded. `referenced` is every probe question and
    weighed item the instruction should draw on."""
    phi = (phi or "").strip()
    if not phi:
        return "empty instruction"
    if INJECTION_MARKERS.search(phi):
        return "reads as an embedded instruction or link, not a reasoning stance"
    if verbatim_run(phi, chunk):
        return "copies a long run of the passage verbatim instead of framing a stance"
    pool = set().union(*(_content_words(r) for r in referenced)) if referenced else set()
    if pool and not (_content_words(phi) & pool):
        return "doesn't reference anything the chain actually extracted"
    return ""


# ---------------------------------------------------------------- endpoints

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def is_local(endpoint: Any) -> bool:
    """Whether `endpoint` runs on this machine (LM Studio, Ollama...): directly,
    or through a chat provider standing in as the clerk. A local model is
    slow (about 50 s per task measured for a 4B on a 6,000-character
    chunk, 2026-09-28), so callers keep each call it serves short."""
    from urllib.parse import urlparse
    target = getattr(endpoint, "base_url", "") or \
        getattr(getattr(endpoint, "provider", None), "base_url", "")
    host = urlparse(str(target)).hostname or ""
    return host in LOCAL_HOSTS or host.endswith(".local")


class ClerkUnavailable(RuntimeError):
    pass


PRESETS = {
    "deepinfra": {"base_url": "https://api.deepinfra.com/v1/openai",
                  "key_env": "DEEPINFRA_API_KEY", "concurrency": 4,
                  "model": "openai/gpt-oss-20b", "min_tokens": 1800},
    "openai": {"base_url": "https://api.openai.com/v1", "key_env": "OPENAI_API_KEY",
               "concurrency": 4, "model": "gpt-4.1-mini", "min_tokens": 0},
    "lmstudio": {"base_url": "http://127.0.0.1:1234/v1", "key_env": "", "concurrency": 1,
                 "model": "", "min_tokens": 0},
}


class Endpoint:
    name = "endpoint"
    concurrency = 1

    def complete(self, payload: dict[str, Any], repair: str = "") -> tuple[str, str]:
        """(raw reply, model used)."""
        raise NotImplementedError


class Scripted(Endpoint):
    """A function standing in for a model: tests and replays."""

    def __init__(self, answer: Callable[[dict[str, Any]], Any], concurrency: int = 1):
        self.answer = answer
        self.concurrency = concurrency
        self.name = "scripted"
        self.payloads: list[dict[str, Any]] = []

    def complete(self, payload: dict[str, Any], repair: str = "") -> tuple[str, str]:
        self.payloads.append(payload)
        reply = self.answer(payload)
        return (reply if isinstance(reply, str) else json.dumps(reply)), "scripted"


class OpenAICompatible(Endpoint):
    """Any `/chat/completions` endpoint: DeepInfra, OpenAI, LM Studio. Standard
    library only. The key is read from the environment, never from config."""

    def __init__(self, base_url: str, model: str, key_env: str = "", concurrency: int = 1,
                 min_tokens: int = 0, timeout: int = 120, models: dict[str, str] | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.key_env = key_env
        self.concurrency = max(1, int(concurrency))
        self.min_tokens = int(min_tokens)
        self.timeout = timeout
        self.models = models or {}
        self.name = self.base_url

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.key_env:
            key = os.environ.get(self.key_env, "")
            if not key:
                raise ClerkUnavailable(f"{self.key_env} is not set")
            headers["Authorization"] = f"Bearer {key}"
        request = urllib.request.Request(f"{self.base_url}/chat/completions",
                                         data=json.dumps(body).encode("utf-8"),
                                         headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise ClerkUnavailable(f"{self.base_url} is not reachable: {exc}") from exc

    def complete(self, payload: dict[str, Any], repair: str = "") -> tuple[str, str]:
        model = self.models.get(payload["task"].split(":")[0], self.model)
        messages = [{"role": "system", "content": payload["system"]},
                    {"role": "user", "content": payload["user"]}]
        if repair:
            messages.append({"role": "user", "content":
                             f"That did not match the required shape: {repair}\n"
                             f"Return only the JSON object, corrected."})
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", payload["task"]) or "task"
        body: dict[str, Any] = {
            "model": model, "messages": messages, "temperature": payload["temperature"],
            "max_tokens": max(payload["max_tokens"], self.min_tokens),
            "response_format": {"type": "json_schema", "json_schema": {
                "name": safe, "strict": True, "schema": _strict(payload["schema"])}}}
        try:
            reply = self._post(body)
        except RuntimeError as exc:
            if "response_format" not in str(exc) and "json_schema" not in str(exc):
                raise
            body.pop("response_format")         # the model refuses constrained output
            reply = self._post(body)
        message = (reply.get("choices") or [{}])[0].get("message") or {}
        content = message.get("content") or ""
        if not content and message.get("reasoning_content"):
            raise RuntimeError("the model spent its whole token budget reasoning; raise "
                               "`min_tokens` for this endpoint")
        return content, reply.get("model", model)


def _strict(schema: dict[str, Any]) -> dict[str, Any]:
    """OpenAI-style strict mode: every property required, nothing extra."""
    schema = dict(schema)
    properties = schema.get("properties")
    if isinstance(properties, dict):
        out = {}
        for name, rule in properties.items():
            rule = dict(rule)
            if rule.get("type") == "object":
                rule = _strict(rule)
            if rule.get("type") == "array" and isinstance(rule.get("items"), dict) and \
                    rule["items"].get("type") == "object":
                rule["items"] = _strict(rule["items"])
            out[name] = rule
        schema["properties"] = out
        schema["required"] = list(out)
        schema["additionalProperties"] = False
    return schema


def _endpoint(provider: str, settings: dict[str, Any]) -> OpenAICompatible:
    base = dict(PRESETS.get(provider, {}))
    base.update({k: v for k, v in settings.items() if k in
                 ("base_url", "key_env", "model", "concurrency", "min_tokens", "timeout")})
    if not base.get("base_url"):
        raise ClerkUnavailable(f"clerk provider {provider!r} needs a base_url")
    models = {k[len("model_"):]: str(v) for k, v in settings.items()
              if k.startswith("model_") and v}
    return OpenAICompatible(models=models, **base)


def from_config(settings: dict[str, Any]) -> Endpoint | None:
    """The configured endpoint, or None. `[clerk] provider = "deepinfra"` is
    enough; any preset value can be overridden, and `model_<task>` routes one
    task to another model *of the same provider*.

    `route_<task> = "<provider>[:<model>]"` sends one task to a different
    provider altogether - the split the lens evaluation recommends
    (`internal docs/Lens Chain Evaluation 2026-09-28.md`): a local 4B for the
    bulk and for checking, an API model only for finding stances -

        [clerk]
        provider = "lmstudio"
        model = "qwen/qwen3-4b-2507"
        route_lens_perspective = "deepinfra:deepseek-ai/DeepSeek-V4-Pro"

    Flat keys, not a nested table, so they survive the app rewriting the
    config. A route's provider takes its preset (key, concurrency, ...); a
    route with no model uses that preset's default model. A reasoning model
    on a route may need more room than the task asks for, and longer:
    `min_tokens_<task>` and `timeout_<task>` set both (G5 measured GLM-5.3
    as a reviewer spending 16k tokens reasoning and answering nothing, and
    answering correctly with 32k)."""
    provider = str(settings.get("provider") or "")
    routes: dict[str, Endpoint] = {}
    for key, value in settings.items():
        if not key.startswith("route_") or not str(value).strip():
            continue
        target, _, model = str(value).strip().partition(":")
        if target not in PRESETS:
            raise ClerkUnavailable(f"{key}: {target!r} is not a clerk provider "
                                   f"({', '.join(sorted(PRESETS))})")
        task = key[len("route_"):]
        extra = {name: int(settings[f"{name}_{task}"]) for name in ("min_tokens", "timeout")
                 if str(settings.get(f"{name}_{task}") or "").strip()}
        routes[task] = _endpoint(target, {**({"model": model} if model else {}), **extra})
    default = _endpoint(provider, settings) if provider else None
    if not routes:
        return default
    return Router(default, routes)


class Router(Endpoint):
    """One clerk made of several endpoints: each task kind may go to its own
    (`route_<task>`), the rest to the default. `run` groups tasks by the
    endpoint that will serve them, so each keeps its own concurrency - a
    local model still gets one task at a time while an API route runs
    several. With no default, a task no route covers waits in the queue."""

    def __init__(self, default: Endpoint | None, routes: dict[str, Endpoint]):
        self.default = default
        self.routes = routes
        self.name = "router(" + ", ".join(
            [f"default={getattr(default, 'name', 'none')}"] +
            [f"{task}={getattr(ep, 'name', '?')}" for task, ep in sorted(routes.items())]) + ")"

    @property
    def base_url(self) -> str:
        """The default's: whether this clerk counts as local (`is_local`,
        the ten-minute rule) is decided by where the bulk of its work runs."""
        return str(getattr(self.default, "base_url", "") or "")

    def for_task(self, task_name: str) -> Endpoint | None:
        return self.routes.get(task_name.split(":")[0], self.default)

    def complete(self, payload: dict[str, Any], repair: str = "") -> tuple[str, str]:
        endpoint = self.for_task(payload["task"])
        if endpoint is None:
            raise ClerkUnavailable(f"no clerk endpoint for {payload['task']!r}: no default "
                                   f"provider, and no route for it")
        return endpoint.complete(payload, repair)


# ------------------------------------------------------------------ running

def run_one(task: Task, endpoint: Endpoint) -> Result:
    payload = task.payload()
    problems = ""
    model = ""
    for attempt in range(REPAIR_ATTEMPTS + 1):
        try:
            raw, model = endpoint.complete(payload, problems)
        except ClerkUnavailable:
            raise
        except Exception as exc:                            # noqa: BLE001
            return Result(task.kind.name, task.id, "error",
                          problems=f"{type(exc).__name__}: {exc}"[:400], model=model,
                          attempts=attempt + 1)
        value, problems = parse(raw, task.kind.schema)
        if not problems:
            status, value, dropped = verify(task, value)
            return Result(task.kind.name, task.id, status, value, dropped, model=model,
                          attempts=attempt + 1)
    return Result(task.kind.name, task.id, "refused", problems=problems, model=model,
                  attempts=REPAIR_ATTEMPTS + 1)


def run(tasks: Sequence[Task], endpoint: Endpoint | None,
        queue_dir: Path | None = None) -> list[Result]:
    """Every task, in order of the input. A task a clerk agent has already
    answered uses that answer; the rest go to the endpoint. With no endpoint (or
    one that is unreachable) they are queued, never handed to another model."""
    answered = Answered(queue_dir / "answers") if queue_dir is not None else None
    results: dict[int, Result] = {}
    rest: list[int] = []
    for i, task in enumerate(tasks):
        if answered is not None and answered.has(task.payload()):
            results[i] = run_one(task, answered)
            (queue_dir / f"{task_key(task.payload())}.json").unlink(missing_ok=True)
        else:
            rest.append(i)
    for i, result in zip(rest, _run(tasks=[tasks[i] for i in rest], endpoint=endpoint,
                                    queue_dir=queue_dir)):
        results[i] = result
    return [results[i] for i in range(len(tasks))]


def _run(tasks: Sequence[Task], endpoint: Endpoint | None,
         queue_dir: Path | None) -> list[Result]:
    if not tasks:
        return []
    if endpoint is None:
        return [_queue(t, queue_dir, "no clerk endpoint is configured") for t in tasks]
    if isinstance(endpoint, Router):
        # Each group on its own endpoint, at that endpoint's own concurrency,
        # answers put back in the order the tasks came in.
        groups: dict[int, tuple[Endpoint | None, list[int]]] = {}
        for i, task in enumerate(tasks):
            target = endpoint.for_task(task.kind.name)
            groups.setdefault(id(target), (target, []))[1].append(i)
        out: dict[int, Result] = {}
        for target, indexes in groups.values():
            for i, result in zip(indexes, _run([tasks[i] for i in indexes], target, queue_dir)):
                out[i] = result
        return [out[i] for i in range(len(tasks))]
    try:
        if endpoint.concurrency <= 1 or len(tasks) <= 1:
            return [run_one(t, endpoint) for t in tasks]
        with ThreadPoolExecutor(max_workers=endpoint.concurrency) as pool:
            return list(pool.map(lambda t: run_one(t, endpoint), tasks))
    except ClerkUnavailable as exc:
        return [_queue(t, queue_dir, str(exc)) for t in tasks]


def task_key(payload: dict[str, Any]) -> str:
    """A task's identity is its content: the same question on the same text is
    the same task, however many times the owning review is re-run."""
    content = {k: payload[k] for k in ("task", "system", "user", "schema")}
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()[:16]


def _queue(task: Task, queue_dir: Path | None, why: str) -> Result:
    if queue_dir is not None:
        queue_dir.mkdir(parents=True, exist_ok=True)
        payload = task.payload()
        (queue_dir / f"{task_key(payload)}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return Result(task.kind.name, task.id, "queued", problems=why)


# ------------------------------------------------------- the clerk agent route

class Answered(Endpoint):
    """Answers a clerk agent submitted for queued tasks (the Cowork plugin's
    `clerk` subagent, which sees each task and nothing else). They are checked
    at use like any reply: shape, grounding, quotes."""

    name = "clerk-agent"

    def __init__(self, answers_dir: Path):
        self.dir = answers_dir

    def _path(self, payload: dict[str, Any]) -> Path:
        return self.dir / f"{task_key(payload)}.json"

    def has(self, payload: dict[str, Any]) -> bool:
        return self.dir.is_dir() and self._path(payload).is_file()

    def complete(self, payload: dict[str, Any], repair: str = "") -> tuple[str, str]:
        stored = json.loads(self._path(payload).read_text(encoding="utf-8"))
        return json.dumps(stored["answer"]), stored.get("by") or self.name


def next_task(queue_dir: Path) -> dict[str, Any] | None:
    """The oldest waiting task, exactly as it would leave for an endpoint."""
    waiting = sorted(queue_dir.glob("*.json"), key=lambda p: (p.stat().st_mtime, p.name)) \
        if queue_dir.is_dir() else []
    if not waiting:
        return None
    payload = json.loads(waiting[0].read_text(encoding="utf-8"))
    return {"key": waiting[0].stem, **{k: payload[k] for k in ("task", "system", "user",
                                                                 "schema")},
            "waiting": len(waiting)}


def submit(queue_dir: Path, key: str, answer: dict[str, Any], by: str = "") -> dict[str, Any]:
    """Store an answer for a waiting task once its shape is right; the owning
    review uses it the next time it runs."""
    path = queue_dir / f"{key}.json"
    if not re.fullmatch(r"[0-9a-f]{16}", key or "") or not path.is_file():
        raise LookupError(f"no waiting clerk task {key!r}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    problems = _check(answer, payload["schema"]) if isinstance(answer, dict) else \
        ["the answer is not a JSON object"]
    if problems:
        return {"accepted": False, "key": key, "problems": problems[:10]}
    answers = queue_dir / "answers"
    answers.mkdir(parents=True, exist_ok=True)
    (answers / f"{key}.json").write_text(json.dumps({"answer": answer, "by": by},
                                                    ensure_ascii=False), encoding="utf-8")
    path.unlink()
    return {"accepted": True, "key": key,
            "waiting": len(list(queue_dir.glob("*.json")))}
