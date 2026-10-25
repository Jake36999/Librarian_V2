"""Write intents and revision tokens for replace-existing writes (CORE-05A).

A write that replaces a note must say which revision of it the caller read,
or a change made since - a person's edit in Obsidian after the editor's
quiet window, a script, a sync - is silently overwritten.  So a read hands
out a revision token, and a replace-existing write must bring it back; the
registry turns it into the writer's compare-and-swap precondition, and a
note that changed since is refused with a write-conflict checkpoint instead
(`PreconditionChangedError`).

A token is opaque and bound: to the vault, the note's canonical path, the
session and kind of caller that read it, and the fingerprint the note had
then, signed with a key this process holds.  It is never a raw fingerprint
anyone could compute from the file, it cannot be moved to another note,
session or caller, and it does not outlive the Core that issued it.

Every write tool that declares an intent resolves its targets before it is
queued; a note it cannot resolve to exactly one path is refused before
anything is written.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .rules import Refusal

PREFIX = "rev1."


@dataclass(frozen=True)
class WriteIntent:
    """What one write will touch, resolved before it is queued.

    `targets` are every vault-relative path the operation mutates (the
    writer's document-lease guard and operation log use them).  `replaces`
    is the existing note it rewrites, which needs the revision its caller
    read; a new file needs none, but `absent` names one that must still not
    exist when the operation starts (it was missing when resolved).  `note`
    is the note a fresh revision is issued for once the write is done, so
    the next edit needs no re-read.
    """
    targets: tuple[str, ...]
    replaces: str = ""
    note: str = ""
    absent: tuple[str, ...] = ()
    # Trusted dispatch-time snapshots for multi-target operations. These
    # protect the broker/queue interval; they do not claim a caller read token.
    observed: tuple[tuple[str, str], ...] = ()


def canonical(vault: Any, rel: str) -> str:
    """One spelling per path - what the writer's preconditions, its operation
    log and the document leases are keyed by.  A note resolves through the
    vault; the librarian's own state (a staged draft) keeps its relative
    spelling, slashes normalised."""
    try:
        return vault.safe_relative(rel).relative_to(vault.root).as_posix()
    except Refusal:
        return "/".join(part for part in str(rel).replace("\\", "/").split("/") if part)


def canonical_intent(vault: Any, intent: WriteIntent) -> WriteIntent:
    spell = lambda rel: canonical(vault, rel) if rel else ""
    return WriteIntent(tuple(spell(t) for t in intent.targets), spell(intent.replaces),
                       spell(intent.note), tuple(spell(t) for t in intent.absent),
                       tuple((spell(path), value) for path, value in intent.observed))


_KEYS: dict[str, bytes] = {}
_KEYS_GUARD = threading.Lock()


def _vault_key(vault: Any) -> str:
    return str(Path(vault.root).resolve()).casefold()


def _key(vault: Any) -> bytes:
    """A signing key per vault for this process's lifetime: a token never
    outlives the Core that issued it (after a restart, read the note again)."""
    with _KEYS_GUARD:
        return _KEYS.setdefault(_vault_key(vault), secrets.token_bytes(32))


def _holder(ctx: Any) -> dict[str, str]:
    return {"s": str(ctx.session or ""), "c": str(ctx.extras.get("caller_kind") or "agent")}


def _signature(vault: Any, payload: bytes) -> str:
    digest = hmac.new(_key(vault), _vault_key(vault).encode("utf-8") + b"\0" + payload,
                      hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest[:18]).decode("ascii")


def issue(ctx: Any, target: str, fingerprint: str) -> str:
    """A revision token for `target` as it was when `fingerprint` was read."""
    payload = json.dumps({"k": "note", "t": target, "f": fingerprint, **_holder(ctx)},
                         separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{PREFIX}{body}.{_signature(ctx.vault, payload)}"


def issue_current(ctx: Any, target: str) -> str:
    """A token for `target` as it is now (inside a writer operation: exact)."""
    from .coordination import fingerprint
    return issue(ctx, target, fingerprint(ctx.vault.safe_relative(target)))


def redeem(ctx: Any, token: str, target: str) -> str:
    """The fingerprint `token` vouches for, when it was issued for `target`
    to this session and caller; otherwise a refusal, never a guess."""
    try:
        if not token.startswith(PREFIX):
            raise ValueError("not a revision")
        body, signature = token[len(PREFIX):].rsplit(".", 1)
        payload = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        if not hmac.compare_digest(signature, _signature(ctx.vault, payload)):
            raise ValueError("not signed here")
        claims = json.loads(payload)
        if not isinstance(claims, dict):
            raise ValueError("not a revision")
    except (ValueError, TypeError):
        raise Refusal("REVISION_REFUSED",
                      "that revision was not issued by this Core (or it has restarted since): "
                      "read the note again for a current one") from None
    if claims.get("k") != "note" or claims.get("t") != target:
        raise Refusal("REVISION_REFUSED", f"that revision is for {claims.get('t')!r}, not "
                                          f"{target!r}: read {target} for its own")
    if {k: claims.get(k) for k in ("s", "c")} != _holder(ctx):
        raise Refusal("REVISION_REFUSED", "that revision was issued to another session or "
                                          "caller: read the note again in this one")
    return str(claims.get("f") or "")


def preconditions(ctx: Any, intent: WriteIntent, token: str) -> dict[str, str]:
    """The writer precondition a call brings for the note it replaces, and
    for any new file that must still be missing when the write runs."""
    from .coordination import MISSING
    expected = {**dict(intent.observed), **{target: MISSING for target in intent.absent}}
    if not intent.replaces:
        return expected               # a new file: there was nothing to read first
    if token:
        return {**expected, intent.replaces: redeem(ctx, token, intent.replaces)}
    if ctx.extras.get("caller_kind") == "person":
        return expected               # a person's own explicit action on the note before them
    raise Refusal("REVISION_REQUIRED",
                  f"{intent.replaces} already exists: read it first (get_note returns its "
                  f"`revision`; every write returns the next one) and pass that revision, so "
                  f"a change made since is never overwritten")


def check_now(ctx: Any, expected: dict[str, str]) -> None:
    """The writer's precondition, for a call made with no writer (offline)."""
    from .coordination import PreconditionChangedError, fingerprint, operation_path
    for target, wanted in expected.items():
        if fingerprint(operation_path(ctx.vault, target)) != wanted:
            raise PreconditionChangedError(target)
