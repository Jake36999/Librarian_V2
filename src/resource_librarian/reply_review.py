"""The review gate on chat replies (Co-work Roadmap §4 G3, second half).

After a turn, when a library turns it on (`review_replies = true` under
`[clerk]`), the claims a reply makes about the notes it links are checked:

1. `reply_claims` lists the claims that rest on a `[[note]]` the reply links
   (at most `max_claims`). Code keeps only notes the reply really links and that
   exist.
2. Each claim goes to the `review` task with that note's own text, never the
   reply around it (Chain-of-Verification). A `fails` counts only with a
   counter-quote found in the note.
3. Nothing is dropped in silence (Test Directive A5). Each of these is counted as
   unchecked, and the notes are named:
   - a linked note no claim was listed about;
   - a claim past the limit;
   - an ambiguous link.

**Bound to its reply and to the exact note** (MF-027a; spec U-B2):
- **Which note.** A link is resolved to one root-relative path. `[[Folder/Note]]`
  must match that path. A bare `[[Note]]` must match exactly one note in the
  library. If two notes share the name, the link is ambiguous and left unchecked:
  a basename is never a guess.
- **What was checked.** Every row about a real note carries its `note_path`, the
  `source_revision` (fingerprint) of the bytes checked, and `coverage`: the span
  checked, out of the note's length.
- **Silence is not a finding.** Only the first NOTE_CHARS characters are read. A
  note longer than that that is "silent" on a claim may say it further on, so that
  is reported as partly checked, never as unsupported. A counter-quote is still a
  real contradiction.
- **One cap.** Challenges for missing notes count against the same cap as claim
  checks, so a reply with a flood of invented links cannot flood the next prompt.
- **Which reply.** The result names its `reply_id` and `turn_id`. The app keeps it
  in the session's own log, and carries a challenge into the next prompt only if
  no newer turn has started (`app._review_reply`).

The verdict is shown to the person as advice beside the reply, never woven into it.
A challenged claim is handed to the lead model in its next prompt as a challenge to
answer, not a veto (G1: judges dismiss sound claims far more often than they wave
through wrong ones). It runs after the reply, so it never delays one.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import clerk, notes
from .coordination import fingerprint_bytes
from .vault import Vault

MAX_CLAIMS = 5
NOTE_CHARS = 5000
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def enabled(vault: Vault) -> bool:
    return bool((vault.config().get("clerk") or {}).get("review_replies"))


def _clean(name: str) -> str:
    return name.strip().replace("\\", "/").removesuffix(".md")


class _Notes:
    """The library's notes, by root-relative path and by name."""

    def __init__(self, vault: Vault) -> None:
        self.root = vault.root
        self.by_path: dict[str, Path] = {}
        self.by_name: dict[str, list[Path]] = {}
        for path in notes.iter_paths(vault.root):        # by file: a note just written counts
            rel = path.relative_to(vault.root).as_posix().removesuffix(".md")
            self.by_path[rel.casefold()] = path
            self.by_name.setdefault(path.stem.casefold(), []).append(path)

    def resolve(self, link: str) -> tuple[Path | None, str]:
        """(path, "") for exactly one note; (None, "missing" | "ambiguous") otherwise."""
        name = _clean(link)
        if "/" in name:
            path = self.by_path.get(name.casefold())
            return (path, "") if path else (None, "missing")
        matches = self.by_name.get(name.casefold(), [])
        if len(matches) == 1:
            return matches[0], ""
        return None, "ambiguous" if matches else "missing"

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()


def review_reply(vault: Vault, reply: str, endpoint: clerk.Endpoint | None,
                 max_claims: int = MAX_CLAIMS, *, reply_id: str = "",
                 turn_id: str = "") -> dict[str, Any] | None:
    """The verdicts on a reply's note-backed claims, or None when it links no note."""
    raw_links = WIKILINK.findall(reply or "")
    if not raw_links:
        return None
    library = _Notes(vault)
    resolved = {_clean(link): library.resolve(link) for link in raw_links}
    out: dict[str, Any] = {"held": 0, "unchecked": 0, "challenged": [], "advisory": True,
                           **({"reply_id": reply_id} if reply_id else {}),
                           **({"turn_id": turn_id} if turn_id else {})}
    budget = max(1, int(max_claims))
    # A link to a note that does not exist at all is challenged here, not left to
    # the claim-by-claim loop below: that loop only looks up notes it can load, so a
    # reply citing a note nobody wrote would otherwise be skipped in silence. These
    # challenges spend the same cap as claim checks.
    missing = sorted(name for name, (_, problem) in resolved.items() if problem == "missing")
    for name in missing[:budget]:
        out["challenged"].append({"claim": f"cites [[{name}]]", "note": name,
                                  "verdict": "not_found", "counter_quote": "",
                                  "reason": "no note by this name exists in the vault"})
    over = max(0, len(missing) - budget)
    budget -= min(budget, len(missing))
    ambiguous = sorted(name for name, (_, problem) in resolved.items() if problem == "ambiguous")
    if ambiguous:
        out["ambiguous"] = ambiguous
        out["unchecked"] += len(ambiguous)
    linked = {library.rel(path): path for path, problem in resolved.values() if path is not None}
    if not linked:
        if over:
            out["over_limit"] = over
            out["unchecked"] += over
        return out
    queue = vault.work("queue") / "clerk"
    listed = clerk.run([clerk.reply_claims(reply)], endpoint, queue)[0]
    if not listed.ok:
        return {**out, "status": listed.status}
    out["model"] = listed.model
    # Only claims about a note the reply links, resolved the same way; then the cap.
    usable: list[tuple[str, str]] = []
    for item in listed.value.get("claims") or []:
        path, problem = library.resolve(str(item.get("note") or ""))
        if path is not None and not problem and library.rel(path) in linked:
            usable.append((str(item.get("claim") or ""), library.rel(path)))
    claimed = {rel for _, rel in usable}
    silent = sorted(Path(rel).stem for rel in linked if rel not in claimed)
    if silent:
        out["not_extracted"] = silent
        out["unchecked"] += len(silent)
    over += max(0, len(usable) - budget)
    if over:
        out["over_limit"] = over
        out["unchecked"] += over
    checks: list[tuple[str, str, dict[str, Any], clerk.Task]] = []
    for claim, rel in usable[:budget]:
        raw = linked[rel].read_bytes()
        body = notes.parse(raw.decode("utf-8", "replace"))[1]
        checked = body[:NOTE_CHARS]
        seen = {"note_path": rel, "source_revision": fingerprint_bytes(raw),
                "coverage": {"unit": "characters", "checked_spans": [[0, len(checked)]],
                             "total_length": len(body), "complete": len(body) <= NOTE_CHARS,
                             "truncated": len(body) > NOTE_CHARS}}
        checks.append((claim, rel, seen, clerk.review(claim, "", checked)))
    results = clerk.run([task for *_, task in checks], endpoint, queue) if checks else []
    partly = []
    for (claim, rel, seen, _), result in zip(checks, results):
        verdict = result.value.get("verdict") if result.ok else "unchecked"
        if verdict == "holds":
            out["held"] += 1
        elif verdict == "unsupported" and seen["coverage"]["truncated"]:
            # Silence in the part read is not silence in the note.
            out["unchecked"] += 1
            partly.append({"claim": claim, **seen,
                           "reason": f"not found in the first {NOTE_CHARS} characters checked; "
                                     f"the rest of the note was not read"})
        elif verdict in ("fails", "unsupported"):
            # `unsupported`: the note is silent on it, so no quote can show that. It
            # is said as "not found in the note", never as a contradiction.
            row = {"claim": claim, "note": Path(rel).stem, **seen, "verdict": verdict,
                   "counter_quote": result.value.get("counter_quote", ""),
                   "reason": result.value.get("reason", "")}
            fi = result.value.get("failing_input")
            if fi:
                from . import claim_run
                try:
                    claim_run.repository_of(vault, Path(rel).stem)
                    row["run_id"] = claim_run.RunnableStore(vault).add(
                        claim, Path(rel).stem, fi, "reply", reason=row["reason"])
                    row["input"] = claim_run.shown(fi)
                except TypeError:
                    pass                      # not a repository: there is no code to run
            out["challenged"].append(row)
        else:
            out["unchecked"] += 1
    if partly:
        out["partly_checked"] = partly
    return out
