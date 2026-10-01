"""Deep read: a staged source's whole text, chunk by chunk.

Intake reads a window (the first few thousand characters of a README, an
abstract, or a document) so that staging stays fast. A deep read goes through
all of it - every page of an attached PDF, all of a fetched page or README -
the way V1's lens scan did:

- the text is packed into chunks of whole paragraphs, never splitting one (a
  quote cut across a chunk boundary could never be verified), each chunk
  keeping the pages it came from;
- every chunk gets `points` (what it claims, argues or explains), `limits`
  (what it says about its own limits), `terms` (recorded as term-usage
  evidence) and the first step of the lens chain;
- a chunk that teaches a reasoning stance, with a verbatim quote to prove it,
  goes on through the rest of the chain and is staged as a lens proposal for
  a person to accept or reject.

The chain is perspective -> attention -> challenge -> role -> probe ->
synthesize (E1-E11 in `internal docs/Literature Alignment - Agentic AI Trust
and Architecture 2026-09-26.md`, in V1's part of the vault):

- `perspective` drafts the stance from the whole chunk, grounded in a quote
  (`clerk.verify`);
- `attention` says what it weighs and lets fade, each weighed item grounded
  in its own quote (E2);
- `challenge` is blind (E11, rebuilt 2026-09-27): the model sees the
  passage and three unlabelled candidates - the proposed stance, a real
  stance from elsewhere, and the passage's topic dressed as a stance - and
  says which the passage teaches, each with a quote; Python scores it
  (`clerk.discrimination`). Told "someone proposed this, try to disprove
  it", models returned one verdict whatever they were shown (a guard
  against the "stochastic mirror" that itself mirrored); not being told
  which is proposed removes the cue. A stance the blind judgement does not
  find is discarded here, before the more expensive steps run on it;
- `role` casts the stance as a briefing, and must also name two situations
  outside the source's own subject where the same stance transfers - a
  stance whose only "transfer" restates the passage's own topic is
  discarded as a topic, not a stance (E4);
- `probe` asks for the concrete, falsifiable questions this stance should
  prompt and the failure they catch, each question grounded in its own
  quote; a stance with no surviving probe is not staged (E1, E2);
- `synthesize` turns all of this into one instruction, screened afterwards
  for injected instructions, verbatim copying, and whether it actually
  reflects what the chain extracted (E5).

From `attention` onward, a step reads a window centred on the verified quote
rather than the chunk's own opening slice, which a smaller `chunk_chars` can
miss in a chunk larger than that step's own limit (E3).

Every task is an ordinary clerk task: unframed, checked, and queued rather
than handed to another model when no clerk is available.

It is bounded and resumable. One call reads at most `max_chunks` chunks and
stages at most `max_lenses` lenses per source; progress is kept on the staged
item, so the next call carries on where the last stopped. A chunk any of
whose tasks was queued is not counted as read: the next call raises the same
tasks (a task is named by its content) and uses the clerk agent's answers.
Every discard - an ungrounded quote, a failed challenge, a topic mistaken for
a stance, a screened-out instruction - is logged on the item with its step
and reason (E7), and a lens that recurs across chunks is reconciled rather
than duplicated: the stronger version is kept, a weaker repeat is dropped,
and a shared name covering two real failure modes is kept as two lenses (E6,
after GSW's Reconciler, arXiv 2406.04555).

The item's own sections are rebuilt from everything read so far, each bullet
carrying the pages it came from, so a person reviewing it sees the whole
text's claims and limits, not just its opening.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Callable

from . import clerk, text
from .evidence import EvidenceStore
from .lenses import LensStore, provenance
from .staging import StagingStore
from .vault import Vault, now_iso

CHUNK_CHARS = 6000                 # the lens chain's first step reads this much, as in V1
WINDOW_RADIUS = 1500                # E3: how far either side of a quote a later step reads
MAX_CHUNKS = 12                     # per call
# On a model running on this machine, one part per call. A part is at most
# about nine clerk tasks (points, limits, terms, then the lens chain), and at
# the ~50 s a local 4B takes per task that keeps a call under ten minutes -
# long enough that a person is likely to interrupt it by accident otherwise.
# The read is resumable, so the next call carries on where this one stopped.
LOCAL_MAX_CHUNKS = 1
MAX_LENSES = 12                     # per source, over every call (V1's `limit`)
SECTION_BULLETS = 40                # per rebuilt section; the rest stay in the record
MAX_DISCARDS = 200                  # kept on the item; older ones roll off
TEXT_KEYS = ("text",)               # what an evidence record's payload holds as prose


@dataclass
class Chunk:
    index: int
    text: str
    first_page: int = 0            # 0: the text has no pages (a README, a web page)
    last_page: int = 0

    @property
    def locator(self) -> str:
        if not self.first_page:
            return f"part {self.index + 1}"
        if self.first_page == self.last_page:
            return f"p. {self.first_page}"
        return f"pp. {self.first_page}-{self.last_page}"


# ------------------------------------------------------------------ the text

def source_units(vault: Vault, item: dict[str, Any]) -> list[tuple[int, str]]:
    """(page, text) for the item's whole text: an attached file's pages, else
    the prose its evidence records hold (page 0: no page numbers). Never the
    item's own `sections` - those may already carry an agent's own writing,
    and a lens is mined from the source, not from a machine's account of it
    (E8)."""
    for key in ("clean_file", "file"):                  # a cleaned copy first (P3b)
        if not item.get(key):
            continue
        path = vault.root / item[key]
        if path.is_file():
            result = text.extract(path, vault.derived / "text")
            if not result.error:
                return [(n, page) for n, page in enumerate(result.pages, 1) if page.strip()]
    store = EvidenceStore(vault)
    units: list[tuple[int, str]] = []
    for ref in item.get("evidence") or []:
        record = store.get(ref.get("id", ""))
        if record is None:
            continue
        for key in TEXT_KEYS:
            prose = record.payload.get(key)
            if isinstance(prose, str) and prose.strip():
                units.append((0, prose))
    return units


def chunk(units: list[tuple[int, str]], size: int = 0) -> list[Chunk]:
    """Whole paragraphs packed up to `size`, each chunk knowing its pages. A
    single paragraph longer than `size` is split on sentence ends, never
    mid-sentence where it can be helped."""
    size = size or CHUNK_CHARS
    out: list[Chunk] = []
    current: list[str] = []
    pages: list[int] = []

    def flush() -> None:
        if current:
            out.append(Chunk(len(out), "\n\n".join(current),
                             min(pages) if pages else 0, max(pages) if pages else 0))
            current.clear()
            pages.clear()

    for page, prose in units:
        for para in re.split(r"\n\s*\n", prose):
            para = para.strip()
            if not para:
                continue
            for piece in _pieces(para, size):
                if current and sum(len(c) + 2 for c in current) + len(piece) > size:
                    flush()
                current.append(piece)
                if page:
                    pages.append(page)
    flush()
    return out


def _pieces(para: str, size: int) -> list[str]:
    if len(para) <= size:
        return [para]
    sentences = re.split(r"(?<=[.!?])\s+", para)
    pieces, current = [], ""
    for sentence in sentences:
        while len(sentence) > size:                  # no sentence ends at all
            pieces.append(sentence[:size])
            sentence = sentence[size:]
        if current and len(current) + len(sentence) + 1 > size:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def _window(chunk_text: str, quote: str, radius: int = WINDOW_RADIUS) -> str:
    """The verified quote's neighbourhood (E3), so a chain step after the
    first reads the passage that actually taught the stance rather than the
    chunk's own opening slice."""
    idx = _locate(chunk_text, quote)
    if idx == -1:
        return chunk_text
    start = max(0, idx - radius)
    end = min(len(chunk_text), idx + len(quote) + radius)
    return chunk_text[start:end]


def _locate(chunk_text: str, quote: str) -> int:
    quote = (quote or "").strip()
    if not quote:
        return -1
    idx = chunk_text.find(quote)
    if idx != -1:
        return idx
    return clerk.locate(quote, chunk_text)      # as `quoted` matched it: case, dashes, hyphens


# ------------------------------------------------------------------ the read

def deep_read(vault: Vault, item_id: str, endpoint: clerk.Endpoint | None, *,
              max_chunks: int = MAX_CHUNKS, lenses: bool = True,
              max_lenses: int = MAX_LENSES, sections_of: dict[str, str] | None = None
              ) -> dict[str, Any]:
    """Read up to `max_chunks` more chunks of a staged source. Returns what was
    read, what waits, and which lenses were staged."""
    store = StagingStore(vault)
    item = store.load(item_id)
    if item["kind"] != "source":
        raise TypeError(f"{item_id} is a {item['kind']}; only a staged source is deep-read")
    if item["status"] not in ("staged", "deferred", "approved", "processing"):
        raise TypeError(f"{item_id} is already {item['status']}")
    local = clerk.is_local(endpoint)
    if local:
        max_chunks = min(max_chunks, LOCAL_MAX_CHUNKS)
    chunks = chunk(source_units(vault, item))
    if not chunks:
        raise TypeError(f"{item_id} has no text to read: no attached file with a text layer, "
                        f"and no prose in its evidence")
    record = item.get("deep_read") or {}
    if record.get("chunks") != len(chunks):              # the text changed: start over
        record = {"chunks": len(chunks), "read": {}, "lenses": []}
    record.setdefault("discards", [])                     # E7; older records predate it
    read: dict[str, Any] = record["read"]
    todo = [c for c in chunks if str(c.index) not in read][:max(1, max_chunks)]
    queue = vault.work("queue") / "clerk"
    evidence = EvidenceStore(vault)
    discards: list[dict[str, str]] = []

    def discard(c: Chunk, step: str, reason: str) -> None:
        discards.append({"chunk": c.locator, "step": step, "reason": reason})

    # Step 1, every chunk at once: what it says, its limits, its terms, and
    # whether it teaches a stance.
    first: list[tuple[Chunk, str, clerk.Task]] = []
    for c in todo:
        first += [(c, "points", clerk.points(c.text)), (c, "limits", clerk.limits(c.text)),
                  (c, "terms", clerk.terms(c.text))]
        if lenses:
            first.append((c, "lens", clerk.lens_perspective(c.text)))
    results = clerk.run([t for _, _, t in first], endpoint, queue)
    waiting: set[int] = set()
    notes: dict[int, dict[str, Any]] = {c.index: {"locator": c.locator, "points": [],
                                                   "limits": []} for c in todo}
    stances: dict[int, dict[str, Any]] = {}
    terms_by_chunk: dict[int, list[str]] = {}
    for (c, label, _), result in zip(first, results):
        if result.status == "queued":
            waiting.add(c.index)
        elif label in ("points", "limits") and result.ok:
            notes[c.index][label] = result.value.get("bullets", [])
        elif label == "terms" and result.ok:
            term_list = result.value.get("terms", [])
            terms_by_chunk[c.index] = [t["term"] for t in term_list]
            for term in term_list:
                evidence.put("term_usage", item.get("canonical_url") or item_id,
                             {"term": term["term"], "sentence": term["sentence"]})
        elif label == "lens":
            if result.dropped:                # a stance was proposed but not grounded
                discard(c, "perspective", "; ".join(result.dropped))
            if result.ok and result.value.get("has_perspective"):
                stances[c.index] = dict(result.value)
                stances[c.index]["trace"] = {"perspective": result.model}

    # Steps 2-6, only for chunks that teach a stance, each fed the steps before.
    already = len(record["lenses"])
    room = max(0, max_lenses - already)
    chain = [c for c in todo if c.index in stances and c.index not in waiting][:room]
    staged: list[str] = []
    touched: list[str] = []
    corroborated: list[str] = []
    if chain:
        def alive() -> list[Chunk]:
            return [c for c in chain if c.index not in waiting and
                    not stances[c.index].get("failed")]

        _chain_step(chain, stances, waiting, endpoint, queue, "attention",
                    lambda c, s: clerk.lens_attention(
                        _window(c.text, s["source_quote"]), s["name"], s["explanation"]),
                    discard=discard)

        def _challenge(c: Chunk, s: dict[str, Any]) -> clerk.Task:
            candidates, proposed = _candidates(c, s, stances, terms_by_chunk.get(c.index, []),
                                               accepted_names)
            s["_blind"] = (proposed, len(candidates))
            return clerk.lens_discriminate(_window(c.text, s["source_quote"]), candidates)

        def _apply_challenge(c: Chunk, s: dict[str, Any], value: dict[str, Any]) -> None:
            proposed, n = s.pop("_blind")
            verdict, reason = clerk.discrimination(value, proposed, n)
            s["challenge"] = {"verdict": verdict, "reason": reason}
            if verdict == "fails":
                s["failed"] = "challenge"
                discard(c, "challenge", reason)

        accepted_names = [(row["name"], row.get("role_purpose", ""))
                          for row in LensStore(vault).list(limit=50)]
        _chain_step(chain, stances, waiting, endpoint, queue, "challenge", _challenge,
                    handle=_apply_challenge, discard=discard)
        _chain_step(chain, stances, waiting, endpoint, queue, "role",
                    lambda c, s: clerk.lens_role(
                        _window(c.text, s["source_quote"]), s["name"], s["explanation"],
                        s.get("attends_to", []), s.get("deprioritizes", [])),
                    discard=discard)
        _chain_step(chain, stances, waiting, endpoint, queue, "probe",
                    lambda c, s: clerk.lens_probe(
                        _window(c.text, s["source_quote"]), s["name"], s["explanation"],
                        s.get("attends_to", []), s.get("deprioritizes", []),
                        s.get("role_purpose", "")),
                    discard=discard)

        for c in alive():
            s = stances[c.index]
            bare = {clerk.normal(t) for t in terms_by_chunk.get(c.index, [])}
            # E4: a stance *named* after one of the chunk's own extracted terms
            # is the topic, not a way of reasoning about it. (Only the name:
            # `catches`/`applies_when` are sentences and never equal a term.)
            hit = "name" if bare and clerk.normal(s.get("name", "")) in bare else ""
            if hit:
                s["failed"] = "topic_not_stance"
                discard(c, "topic_not_stance",
                       f"{hit} '{s.get(hit)}' is just one of this chunk's own extracted terms")

        _chain_step(chain, stances, waiting, endpoint, queue, "synthesize",
                    lambda c, s: clerk.lens_synthesize(
                        _window(c.text, s["source_quote"]), s["name"], s["explanation"],
                        s.get("attends_to", []), s.get("deprioritizes", []),
                        s.get("role_purpose", ""), s.get("role_capabilities", []),
                        s.get("role_expectations", []), s.get("probes", []),
                        s.get("catches", "")),
                    discard=discard)

        for c in alive():
            s = stances[c.index]
            referenced = [p.get("question", "") for p in s.get("probes", [])] + \
                        [w.get("what", "") for w in s.get("attends_to", [])]
            reason = clerk.screen_instruction(s.get("prompt_fragment", ""), c.text, referenced)
            if reason:                                                  # E5
                s["failed"] = "instruction_screen"
                discard(c, "instruction_screen", reason)

        accepted = [LensStore(vault).get(row["id"]) for row in LensStore(vault).list(limit=500)]
        accepted = [lens for lens in accepted if lens]
        for c in alive():
            s = stances[c.index]
            if not s.get("prompt_fragment") or not s.get("role_purpose"):
                continue
            lens_id, action = _reconcile_and_stage(store, item, c, s, accepted)
            touched.append(lens_id)
            if action == "corroborated":
                corroborated.append(lens_id)
            else:
                staged.append(lens_id)

    for c in todo:
        if c.index not in waiting:
            read[str(c.index)] = notes[c.index]
    # C4: once the whole text is read, one pass over all of it.
    document: dict[str, Any] = {}
    if lenses and len(read) == len(chunks) and \
            (record.get("document") or {}).get("chunks") != len(chunks):
        document = _document_pass(store, item, record, chunks, endpoint, queue, discard)
        if document.pop("done", False):
            record["document"] = {"chunks": len(chunks), "at": now_iso(), **document}
        touched += document.get("staged", []) + document.get("corroborated", [])
        staged += document.get("staged", [])
    record["lenses"] = list(dict.fromkeys(record["lenses"] + touched))
    record["discards"] = (record["discards"] + discards)[-MAX_DISCARDS:]
    record["updated_at"] = now_iso()
    item["deep_read"] = record
    rebuilt = _rebuild_sections(item, chunks, sections_of or {})
    store.save(item)
    return {"id": item_id, "chunks": len(chunks), "read": len(read),
            "remaining": len(chunks) - len(read), "this_call": len(todo) - len(waiting),
            "waiting_on_clerk": len(waiting), "lenses_staged": staged,
            "lenses_corroborated": corroborated,
            "lenses_total": len(record["lenses"]), "discards": len(discards),
            "sections": rebuilt, **({"document": document} if document else {}),
            **({"note": "a local model reads one part per call, so each call stays short; "
                        "call again to carry on"} if local and len(read) < len(chunks) else {})}


# Plausible stances that belong to no particular passage: the fallback decoys
# when a read has no other stance and the vault no accepted lens to borrow.
GENERIC_DECOYS = (
    ("Cheapest-change first", "prioritise whichever part is cheapest to change, whatever the "
                              "passage argues"),
    ("Strict chronology", "read everything strictly in the order events happened"),
    ("Audience first", "ask who the text was written for before weighing what it says"),
    ("Worst case first", "judge any design by the single worst failure it permits"),
)


def _candidates(c: Chunk, s: dict[str, Any], stances: dict[int, dict[str, Any]],
                terms: list[str], accepted: list[tuple[str, str]]
                ) -> tuple[list[tuple[str, str]], int]:
    """The proposed stance and two decoys, in a fixed but unguessable order,
    for the blind challenge (E11): one decoy is a real stance from elsewhere
    (another chunk of this read, else an accepted lens, else a generic one),
    the other the passage's topic dressed as a stance - the exact confusion
    E4 exists to catch. Returns (candidates, index of the proposed one)."""
    mine = (s["name"], s["explanation"])
    others = [(o["name"], o["explanation"]) for i, o in stances.items()
              if i != c.index and not _same_stance(o, s)]
    others += [(n, e or n) for n, e in accepted if not _same_stance({"name": n}, s)]
    seed = int(hashlib.sha256(f"{c.index}|{s['name']}".encode()).hexdigest(), 16)
    elsewhere = others[seed % len(others)] if others else GENERIC_DECOYS[seed % len(GENERIC_DECOYS)]
    term = next((t for t in terms if t.strip()), "")
    topic = ((f"Understanding {term}", f"know what {term} is and describe how it works")
             if term else ("Plain summary", "restate what the passage describes, in order"))
    candidates = [mine, elsewhere, topic]
    order = sorted(range(3), key=lambda i: hashlib.sha256(f"{seed}|{i}".encode()).hexdigest())
    shuffled = [candidates[i] for i in order]
    return shuffled, order.index(0)


def _chain_step(chain: list[Chunk], stances: dict[int, dict[str, Any]], waiting: set[int],
                endpoint: clerk.Endpoint | None, queue, step: str,
                build: Callable[[Chunk, dict[str, Any]], clerk.Task],
                handle: Callable[[Chunk, dict[str, Any], dict[str, Any]], None] | None = None,
                discard: Callable[[Chunk, str, str], None] | None = None) -> None:
    live = [c for c in chain if c.index not in waiting and not stances[c.index].get("failed")]
    results = clerk.run([build(c, stances[c.index]) for c in live], endpoint, queue)
    for c, result in zip(live, results):
        if result.status == "queued":
            waiting.add(c.index)
        elif result.ok:
            stances[c.index].setdefault("trace", {})[step] = result.model
            if handle:
                handle(c, stances[c.index], result.value)
            else:
                stances[c.index].update(result.value)
        else:
            stances[c.index]["failed"] = step
            if discard:
                reason = "; ".join(result.dropped) or result.problems or "not confident"
                discard(c, step, reason)


# ------------------------------------------------------------ lens staging

def _overlaps(a: str, b: str, share: float = 0.4, empty: bool = True) -> bool:
    """Whether two short descriptions are close enough in wording to call
    the same failure mode (E6: 'keep both' is only for a real split).
    `empty` is the answer when either side has nothing to compare."""
    words_a = {w for w in re.findall(r"[a-z0-9][a-z0-9_.\-/]+", clerk.normal(a)) if len(w) >= 4}
    words_b = {w for w in re.findall(r"[a-z0-9][a-z0-9_.\-/]+", clerk.normal(b)) if len(w) >= 4}
    if not words_a or not words_b:
        return empty
    return len(words_a & words_b) / min(len(words_a), len(words_b)) >= share


GENERIC_NAME_WORDS = {"analysis", "lens", "stance", "first", "approach", "framework",
                      "thinking", "reasoning", "based", "method", "perspective", "view",
                      "driven", "oriented", "centric", "principle"}


def _name_stems(name: str) -> set[str]:
    """A stance name's distinctive words, stemmed crudely (first five letters)
    so "structure"/"structural" and "earliest"/"early" meet, with the words
    every stance name uses ("analysis", "lens", "first"...) left out."""
    words = re.findall(r"[a-z0-9]+", clerk.normal(name))
    return {(w[:-1] if len(w) > 4 and w.endswith("s") else w)[:5]      # rules/rule meet
            for w in words if len(w) >= 4 and w not in GENERIC_NAME_WORDS}


def _similar_names(a: str, b: str) -> bool:
    stems_a, stems_b = _name_stems(a), _name_stems(b)
    if not stems_a or not stems_b:
        return False
    return len(stems_a & stems_b) / min(len(stems_a), len(stems_b)) >= 0.5


def _same_stance(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Whether two drafts are the same stance under different wording (GSW's
    stability requirement, App. B.1(2)): names that share most of their
    words, or - when the names differ - a failure caught and an explanation
    that both overlap. A model names one stance differently from a passage
    and from its paraphrase ("Structure-first analysis" / "Early structural
    failure analysis", measured 2026-09-27), so an exact name match misses
    most repeats."""
    name_a, name_b = clerk.normal(a.get("name", "")), clerk.normal(b.get("name", ""))
    if name_a and name_a == name_b:
        return True
    # A similar name is the same stance unless what each catches says otherwise.
    if _similar_names(name_a, name_b) and _overlaps(a.get("catches", ""), b.get("catches", ""),
                                                    share=0.4, empty=True):
        return True
    return (_overlaps(a.get("catches", ""), b.get("catches", ""), share=0.4, empty=False) and
            _overlaps(a.get("explanation") or a.get("perspective", ""),
                      b.get("explanation") or b.get("perspective", ""), share=0.3, empty=False))


CONTEXT_CHARS = 240                    # B2: text either side of a quote, shown at review


def _quote(chunk_text: str, quote: str, locator: str) -> dict[str, str]:
    """A verified quote with the passage around it (B2), so a person reviewing
    the lens checks the stance against its context, not a lifted sentence."""
    entry = {"quote": quote, "locator": locator}
    at = clerk.locate(quote, chunk_text)
    if at == -1:
        return entry
    end = at + len(quote)
    before = chunk_text[max(0, at - CONTEXT_CHARS):at]
    after = chunk_text[end:end + CONTEXT_CHARS]
    if at > CONTEXT_CHARS and " " in before:
        before = before.split(" ", 1)[1]                 # start on a whole word
    if end + CONTEXT_CHARS < len(chunk_text) and " " in after:
        after = after.rsplit(" ", 1)[0]                   # end on one
    return {**entry, "before": before, "after": after}


def _lens_fields(s: dict[str, Any], quotes: list[dict[str, str]]) -> dict[str, Any]:
    fields = _lens_body(s, quotes)
    return {**fields, "provenance": provenance(fields)}


def _lens_body(s: dict[str, Any], quotes: list[dict[str, str]]) -> dict[str, Any]:
    return {"quotes": quotes, "source_quote": quotes[0]["quote"], "locator": quotes[0]["locator"],
            "perspective": s["explanation"], "attends_to": s.get("attends_to", []),
            "deprioritizes": s.get("deprioritizes", []), "role_purpose": s.get("role_purpose", ""),
            "role_capabilities": s.get("role_capabilities", []),
            "role_expectations": s.get("role_expectations", []),
            "transfers_to": s.get("transfers_to", []), "probes": s.get("probes", []),
            "catches": s.get("catches", ""), "applies_when": s.get("applies_when", ""),
            "not_when": s.get("not_when", ""), "prompt_fragment": s.get("prompt_fragment", ""),
            "topic_warning": bool(s.get("topic_warning")),
            "challenge": s.get("challenge", {}), "trace": s.get("trace", {})}


def _reconcile_and_stage(store: StagingStore, item: dict[str, Any], c: Chunk,
                         s: dict[str, Any], accepted: list[dict[str, Any]] | None = None
                         ) -> tuple[str, str]:
    """Stage a lens candidate, reconciling it with a staged lens of the same
    stance from this source (E6, after GSW's Reconciler, arXiv 2406.04555):

    - **kept_both**: a name in common but a different failure caught - two
      stances (GSW's label 2, "important and unrelated");
    - **replaced**: the same stance, and the new draft is fuller (more probe
      questions) - its fields replace the old ones;
    - **corroborated**: the same stance, not fuller - the old draft stays.

    Either way the new passage *joins* the lens's quotes with its own locator:
    a stance met again elsewhere in the text is stronger evidence, never a
    discard. (GSW itself has no merge label - one side wins - so accumulating
    quotes is this catalogue's own addition.) A candidate that resembles an
    already-*accepted* lens is staged with `resembles` naming it, so the
    reviewer sees the likely duplicate. Returns `(lens_id, action)`."""
    new_quote = _quote(c.text, s["source_quote"], c.locator)
    staged = [cand for cand in store.items(kind="lens", status="staged")
              if cand.get("source_item") == item["id"]]
    existing = next((cand for cand in staged if _same_stance(cand, s)), None)
    if existing is None:
        near = next((lens for lens in accepted or [] if _same_stance(lens, s)), None)
        extra = {"resembles": {"id": near["id"], "name": near["name"]}} if near else {}
        return _create_lens(store, item, c, s, [new_quote], extra=extra), "created"
    if clerk.normal(existing.get("name", "")) == clerk.normal(s["name"]) and \
            not _overlaps(existing.get("catches", ""), s.get("catches", "")):
        return _create_lens(store, item, c, s, [new_quote], disambiguate=True), "kept_both"
    quotes = [q for q in existing.get("quotes") or []
              if (q.get("quote"), q.get("locator")) != (new_quote["quote"], new_quote["locator"])]
    if len(s.get("probes") or []) > len(existing.get("probes") or []):
        # The fuller draft's fields, with its own passage first so the card's
        # source_quote and locator are the ones those fields were drawn from.
        existing.update(_lens_fields(s, [new_quote] + quotes))
        action = "replaced"
    else:
        existing["quotes"] = quotes + [new_quote]
        action = "corroborated"
    store.save(existing)
    return existing["id"], action


def _create_lens(store: StagingStore, item: dict[str, Any], c: Chunk, s: dict[str, Any],
                 quotes: list[dict[str, str]], disambiguate: bool = False,
                 extra: dict[str, Any] | None = None) -> str:
    """A lens proposal in staging, with its passage(s) and where they came
    from. Named by its source, stance and (only when two stances share a
    name) the failure it catches, so reconciling never collides two real
    stances into one id."""
    slug_of = f"{s['name']}-{s.get('catches', '')}" if disambiguate else s["name"]
    slug = re.sub(r"[^a-z0-9]+", "-", slug_of.lower()).strip("-")[:40] or "lens"
    key = f"{item['id']}|{slug}|{c.index}"
    lens_id = f"lens-{slug}-{hashlib.sha256(key.encode()).hexdigest()[:6]}"
    try:
        store.load(lens_id)
        return lens_id                                     # staged (or decided) before
    except TypeError:
        pass
    store.add({"id": lens_id, "kind": "lens", "name": s["name"], "source": item.get("name", ""),
              "source_item": item["id"], "proposed_by": "deep_read",
              "sensitivity": item.get("sensitivity", "normal"), **_lens_fields(s, quotes),
              **(extra or {})})
    return lens_id


DOCUMENT_MIN_PARTS = 3            # fewer parts with claims: nothing spans the text
DOCUMENT_LISTING_CHARS = 8500     # the claims shown to the document pass
SUPPORT_PARTS = 3                 # parts asked for a verbatim quote, per stance


def _document_pass(store: StagingStore, item: dict[str, Any], record: dict[str, Any],
                   chunks: list[Chunk], endpoint: clerk.Endpoint | None, queue,
                   discard) -> dict[str, Any]:
    """Roadmap §4 C4 (review P1-L7): a stance a book teaches across its parts -
    the kind no single passage states, which the per-part chain cannot find -
    and GSW's question resolution (arXiv 2406.04555) for the probes already
    staged. Three kinds of call, each short (so a local clerk keeps to the
    ten-minute rule): `lens_document` over the claims every part made, with
    the claims each stance rests on checked by code; `lens_support` for a
    verbatim quote from each cited part, so a document-level stance is staged
    only with the source's own words from two or more places; `probe_answers`
    marking a staged probe that another part of the text answers. Returns
    `done` False only when the clerk is not there yet (tasks queued)."""
    claims: list[tuple[str, Chunk, str]] = []
    for c in chunks:
        for bullet in (record["read"].get(str(c.index)) or {}).get("points", []):
            claims.append((f"C{len(claims) + 1}", c, bullet))
    if len({c.index for _, c, _ in claims}) < DOCUMENT_MIN_PARTS:
        return {"done": True, "skipped": "fewer than three parts made claims"}
    by_id = {cid: (c, text) for cid, c, text in claims}
    own = [x for x in store.items(kind="lens") if x.get("source_item") == item["id"]
           and x.get("status") == "staged"]
    lines, used = [], 0
    for cid, c, text in claims:
        line = f"{cid} ({c.locator}): {text}"
        if used + len(line) > DOCUMENT_LISTING_CHARS:
            break
        lines.append(line)
        used += len(line) + 1
    listing = "Claims, part by part:\n" + "\n".join(lines)
    if own:
        listing += "\n\nStances already found inside single parts:\n" + "\n".join(
            f"- {x['name']}: {x.get('perspective', '')[:160]}" for x in own)
    first = clerk.run([clerk.lens_document(listing)], endpoint, queue)[0]
    if first.status == "queued":
        return {"done": False}
    # Loud either way: "none proposed" and "the answer was refused" must not
    # look alike in the record (FAILURE_MUST_BE_LOUD).
    offered = (first.value.get("stances") or []) if first.ok else []
    out: dict[str, Any] = {"done": True, "staged": [], "corroborated": [], "probes_confirmed": 0,
                           "model": first.model, "proposed": len(offered),
                           **({} if first.ok else {"status": first.status,
                                                   "problems": str(first.problems)[:200]})}
    proposals = []
    for s in offered:
        cited = [by_id[x] for x in s.get("claims") or [] if x in by_id]
        parts = list({c.index: c for c, _ in cited}.values())
        if len(parts) < 2:
            discard(parts[0] if parts else chunks[0], "document",
                    f"'{s.get('name', '')}' rests on claims from fewer than two parts")
            continue
        proposals.append((s, cited, parts[:SUPPORT_PARTS]))
    tasks = [(i, c, clerk.lens_support(c.text, s["name"], s["explanation"]))
             for i, (s, _, parts) in enumerate(proposals) for c in parts]
    results = clerk.run([t for _, _, t in tasks], endpoint, queue) if tasks else []
    support: dict[int, list[dict[str, str]]] = {}
    supported_parts: dict[int, set[int]] = {}
    models: dict[int, str] = {}
    for (i, c, _), r in zip(tasks, results):
        if r.ok and r.value.get("quote"):
            support.setdefault(i, []).append(_quote(c.text, r.value["quote"], c.locator))
            supported_parts.setdefault(i, set()).add(c.index)
            models[i] = r.model
    for i, (s, cited, parts) in enumerate(proposals):
        quotes = support.get(i, [])
        if len(supported_parts.get(i, set())) < 2:          # parts, not pages: a page holds several
            discard(parts[0], "document", f"'{s['name']}': no verbatim support in two parts")
            continue
        reason = clerk.screen_instruction(s.get("prompt_fragment", ""),
                                          "\n".join(c.text for c in parts),
                                          [text for _, text in cited])
        if reason:
            discard(parts[0], "document", f"'{s['name']}': {reason}")
            continue
        stance = {**s, "trace": {"document": first.model, "support": models.get(i, "")}}
        same = next((x for x in own if _same_stance(x, stance)), None)
        if same is not None:                                # the whole text corroborates it
            have = {(q.get("quote"), q.get("locator")) for q in same.get("quotes") or []}
            same["quotes"] = (same.get("quotes") or []) + [
                q for q in quotes if (q["quote"], q.get("locator")) not in have]
            same["document_level"] = True
            store.save(same)
            out["corroborated"].append(same["id"])
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", s["name"].lower()).strip("-")[:40] or "lens"
        lens_id = f"lens-doc-{slug}-" + hashlib.sha256(
            f"{item['id']}|{slug}|document".encode()).hexdigest()[:6]
        try:
            store.load(lens_id)
            continue                                        # staged (or decided) before
        except TypeError:
            pass
        store.add({"id": lens_id, "kind": "lens", "name": s["name"],
                   "source": item.get("name", ""), "source_item": item["id"],
                   "proposed_by": "deep_read:document", "level": "document",
                   "sensitivity": item.get("sensitivity", "normal"),
                   "rests_on": [f"{text} ({c.locator})" for c, text in cited],
                   **_lens_fields(stance, quotes)})
        out["staged"].append(lens_id)
    out["probes_confirmed"] = _resolve_probes(store, item, claims, by_id, endpoint, queue)
    return out


def _resolve_probes(store: StagingStore, item: dict[str, Any],
                    claims: list[tuple[str, Chunk, str]],
                    by_id: dict[str, tuple[Chunk, str]], endpoint, queue) -> int:
    """GSW's question resolution, for the probes of this source's staged
    lenses: a probe another part of the text answers is marked `confirmed_by`
    that claim - evidence the question matters, shown at review. Nothing is
    removed; a probe answered only in its own passage does not count."""
    lenses = [x for x in store.items(kind="lens") if x.get("source_item") == item["id"]
              and x.get("status") == "staged" and x.get("probes")]
    if not lenses:
        return 0
    ids: dict[str, tuple[dict[str, Any], int]] = {}
    lines = []
    for n, lens in enumerate(lenses, 1):
        for k, probe in enumerate(lens["probes"], 1):
            question = probe.get("question", "") if isinstance(probe, dict) else str(probe)
            ids[f"L{n}.P{k}"] = (lens, k - 1)
            lines.append(f"L{n}.P{k}: {question}")
    claim_lines, used = [], 0
    for cid, c, text in claims:
        line = f"{cid} ({c.locator}): {text}"
        if used + len(line) > DOCUMENT_LISTING_CHARS:
            break
        claim_lines.append(line)
        used += len(line) + 1
    result = clerk.run([clerk.probe_answers("Questions:\n" + "\n".join(lines)
                                            + "\n\nClaims:\n" + "\n".join(claim_lines))],
                       endpoint, queue)[0]
    if not result.ok:
        return 0
    changed: dict[str, dict[str, Any]] = {}
    confirmed = 0
    for pair in result.value.get("answered") or []:
        target, claim = ids.get(pair.get("probe", "")), by_id.get(pair.get("claim", ""))
        if not target or not claim:
            continue
        lens, k = target
        chunk_of, text = claim
        probe = lens["probes"][k]
        own_part = any(clerk.locate(q.get("quote", ""), chunk_of.text) >= 0
                       for q in lens.get("quotes") or [])
        if own_part or not isinstance(probe, dict) or \
                probe.get("confirmed_by"):
            continue
        probe["confirmed_by"] = {"claim": text, "locator": chunk_of.locator}
        changed[lens["id"]] = lens
        confirmed += 1
    for lens in changed.values():
        store.save(lens)
    return confirmed


def _rebuild_sections(item: dict[str, Any], chunks: list[Chunk],
                      sections_of: dict[str, str]) -> dict[str, int]:
    """The item's claims and limits sections, from every chunk read so far,
    in reading order, each bullet with the pages it came from."""
    kind = item.get("source_kind", "")
    points_to = "Claims" if "Claims" in sections_of else "Reading Notes"
    limits_to = "Evidence & Limits" if "Evidence & Limits" in sections_of else "Reading Notes"
    if kind == "repository" and "Claims" not in sections_of:
        points_to = "Reading Notes"
    collected: dict[str, list[str]] = {}
    read = item["deep_read"]["read"]
    for c in chunks:
        note = read.get(str(c.index))
        if not note:
            continue
        for label, heading in (("points", points_to), ("limits", limits_to)):
            collected.setdefault(heading, []).extend(
                f"- {b} ({note['locator']})" for b in note.get(label, []))
    sections = item.setdefault("sections", {})
    counts: dict[str, int] = {}
    for heading, bullets in collected.items():
        if not bullets:
            continue
        shown = bullets[:SECTION_BULLETS]
        more = len(bullets) - len(shown)
        if more:
            shown.append(f"- … and {more} more from later in the text (kept in the staged "
                         f"item's deep-read record)")
        sections[heading] = "\n".join(shown)
        counts[heading] = len(bullets)
    return counts
