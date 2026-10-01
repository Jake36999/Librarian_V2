"""The review gate on chat replies (Co-work Roadmap §4 G3, second half).

After a turn, when a library turns it on (`review_replies = true` under
`[clerk]`), the claims a reply makes about the notes it links are checked:

1. `reply_claims` lists the claims that rest on a `[[note]]` the reply links
   (at most five); code keeps only notes the reply really links and that exist.
2. Each claim goes to the `review` task with that note's own text - never the
   reply around it (Chain-of-Verification) - and a `fails` counts only with a
   counter-quote found in the note.
3. Nothing is dropped in silence (Test Directive A5): a linked note no claim was
   listed about, and a claim past the limit, are each counted as unchecked, and
   the notes are named.

The verdict is shown to the person as one line under the reply, not woven
into it. A challenged claim is handed to the lead model in its next prompt
as a challenge to answer, not a veto (G1: judges dismiss sound claims far more
often than they wave through wrong ones). It runs after the reply, so it
never delays one.
"""
from __future__ import annotations

import re
from typing import Any

from . import clerk, notes
from .vault import Vault

MAX_CLAIMS = 5
NOTE_CHARS = 5000
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def enabled(vault: Vault) -> bool:
    return bool((vault.config().get("clerk") or {}).get("review_replies"))


def _key(name: str) -> str:
    return name.strip().rsplit("/", 1)[-1].removesuffix(".md").casefold()


def review_reply(vault: Vault, reply: str, endpoint: clerk.Endpoint | None,
                 max_claims: int = MAX_CLAIMS) -> dict[str, Any] | None:
    """The verdicts on a reply's note-backed claims, or None when it links no note."""
    raw_links = WIKILINK.findall(reply or "")
    if not raw_links:
        return None
    linked = {_key(m) for m in raw_links}
    # By file, not the search index: a note written a moment ago counts too.
    existing = {p.stem.casefold(): p for p in notes.iter_paths(vault.root)}
    out: dict[str, Any] = {"held": 0, "unchecked": 0, "challenged": []}
    # A link to a note that does not exist at all is checked here, not left
    # to the claim-by-claim loop below: that loop only ever looks up notes it
    # can load, so a reply that cites a note nobody wrote - the failure mode
    # that motivated this check - would otherwise be skipped in silence
    # rather than challenged.
    for name in sorted({m for m in raw_links if _key(m) not in existing}):
        out["challenged"].append({"claim": f"cites [[{name}]]", "note": name,
                                  "verdict": "not_found", "counter_quote": "",
                                  "reason": "no note by this name exists in the vault"})
    queue = vault.work("queue") / "clerk"
    listed = clerk.run([clerk.reply_claims(reply)], endpoint, queue)[0]
    if not listed.ok:
        return {**out, "status": listed.status}
    out["model"] = listed.model
    paths = {k: v for k, v in existing.items() if k in linked}
    # Only claims about a note the reply links and that exists; then the limit.
    usable = [item for item in listed.value.get("claims") or []
              if _key(str(item.get("note") or "")) in paths]
    claimed = {_key(str(item.get("note") or "")) for item in usable}
    silent = sorted(path.stem for key, path in paths.items() if key not in claimed)
    if silent:
        out["not_extracted"] = silent
        out["unchecked"] += len(silent)
    if len(usable) > max_claims:
        out["over_limit"] = len(usable) - max_claims
        out["unchecked"] += out["over_limit"]
    checks: list[tuple[str, str, clerk.Task]] = []
    for item in usable[:max_claims]:
        path = paths[_key(str(item.get("note") or ""))]
        body = notes.load(path).body
        checks.append((str(item.get("claim") or ""), path.stem,
                       clerk.review(str(item.get("claim") or ""), "", body[:NOTE_CHARS])))
    results = clerk.run([t for _, _, t in checks], endpoint, queue) if checks else []
    for (claim, note, _), result in zip(checks, results):
        verdict = result.value.get("verdict") if result.ok else "unchecked"
        if verdict == "holds":
            out["held"] += 1
        elif verdict in ("fails", "unsupported"):
            # `unsupported`: the note is silent on it - no quote can show that,
            # so it is said as "not found in the note", never as a contradiction.
            row = {"claim": claim, "note": note, "verdict": verdict,
                   "counter_quote": result.value.get("counter_quote", ""),
                   "reason": result.value.get("reason", "")}
            fi = result.value.get("failing_input")
            if fi:
                from . import claim_run
                try:
                    claim_run.repository_of(vault, note)
                    row["run_id"] = claim_run.RunnableStore(vault).add(
                        claim, note, fi, "reply", reason=row["reason"])
                    row["input"] = claim_run.shown(fi)
                except TypeError:
                    pass                      # not a repository: there is no code to run
            out["challenged"].append(row)
        else:
            out["unchecked"] += 1
    return out
