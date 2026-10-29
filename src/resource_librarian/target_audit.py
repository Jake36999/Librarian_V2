"""Protected-target snapshot and Tier A integrity audit (HARNESS-07).

A contract that can change the vault names its protected set: its write and
read targets, never the whole vault (unrelated edits elsewhere must not read
as a violation). The Core fingerprints that set when it admits the contract,
before anything writes, and records the snapshot. After execution, the audit
fingerprints the same set again and judges every difference:

| Difference | Integrity |
| --- | --- |
| a protected path outside the write targets changed | violation |
| a write target changed with no writer call of this contract naming it | suspect |
| an outside edit was recorded on a protected path since the snapshot | suspect |
| every change is a write target named by one of the contract's own calls | clean |

Integrity says the work stayed inside its contract; it says nothing about
whether the work is right. A contract that changes the vault completes only
with a clean audit and its planned verifiers' passes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .closure import _covered
from .coordination import MISSING, fingerprint
from .rules import Refusal
from .vault import Vault

MAX_PROTECTED = 2_000         # files in one snapshot; a larger set is not a bounded contract


def protected_paths(vault: Vault, contract: dict[str, Any]) -> list[str]:
    """The contract's protected files now: each named file, and every file under
    each named folder ('…/')."""
    root = vault.root.resolve()
    out: set[str] = set()
    for target in list(contract["write"]) + list(contract["read"]):
        rel = str(target).replace("\\", "/")
        if rel in ("", ".", "./", "/"):
            raise Refusal("CONTRACT_SCOPE", "a contract protects named targets, not the whole "
                                            "vault: name the files or folders it touches")
        if rel.endswith("/"):
            folder = (root / rel).resolve()
            if folder.is_dir():
                out.update(p.relative_to(root).as_posix() for p in folder.rglob("*")
                           if p.is_file())
        else:
            out.add(rel)
        if len(out) > MAX_PROTECTED:
            raise Refusal("CONTRACT_SCOPE", f"the protected set passes {MAX_PROTECTED} files: "
                                            "narrow the contract's targets")
    return sorted(out)


def snapshot(vault: Vault, contract: dict[str, Any]) -> dict[str, str]:
    """Fingerprint of every protected file; MISSING for a named file not there yet."""
    return {rel: fingerprint(vault.root / rel) for rel in protected_paths(vault, contract)}


def audit(vault: Vault, state: Any, contract_id: str,
          calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare the contract's snapshot with the protected set now."""
    contract = state.contracts[contract_id]
    snaps = [(ident, s) for ident, s in state.snapshots.items()
             if s["contract"] == contract_id and s["revision"] == contract["revision"]]
    if not snaps:
        raise Refusal("CONTRACT_SCOPE", f"contract {contract_id} has no pre-mutation snapshot "
                                        "to audit against")
    ident, snap = snaps[-1]
    before, now = snap["targets"], snapshot(vault, contract)
    changed = sorted(p for p in set(before) | set(now)
                     if before.get(p, MISSING) != now.get(p, MISSING))
    written = {t.replace("\\", "/") for c in calls for t in c.get("targets") or []}
    findings: list[tuple[str, str]] = []
    for path in changed:
        if not _covered(path, contract["write"]):
            findings.append(("violation", f"{path} changed but is not a write target"))
        elif path not in written:
            findings.append(("suspect", f"{path} changed with no writer call of contract "
                                        f"{contract_id} naming it"))
    for edit in state.external_edits:
        if edit["epoch"] > snap["epoch"] and (edit["path"] in before or edit["path"] in now):
            findings.append(("suspect", f"an outside edit to {edit['path']} was recorded"))
    allowed = set(contract["operations"])
    for call in calls:
        if call.get("class") not in allowed:
            findings.append(("violation", f"{call.get('tool')} ran as {call.get('class')}, "
                                          "which the contract does not allow"))
    kinds = {k for k, _ in findings}
    integrity = "violation" if "violation" in kinds else "suspect" if kinds else "clean"
    return {"snapshot": ident, "integrity": integrity, "changed": changed,
            "findings": [f for _, f in findings]}
