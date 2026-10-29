#!/usr/bin/env python
"""Ledger tool for the DELEG-01 schema-2 ledger.

Subcommands: migrate, import-calls, reconcile, accept, summary, check-prices.
Reuses helpers from scripts/delegate_deepinfra.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import request as urllib_request

# Make the runner importable from the same directory.
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import delegate_deepinfra as runner  # noqa: E402


def _import_run_id(kind: str, source: str, index_or_name: str) -> str:
    """Deterministic run_id for imported entries, so re-imports are skipped."""
    raw = os.path.abspath(source) + "#" + index_or_name
    return f"import-{kind}-{runner.sha256(raw.encode('utf-8'))[:12]}"


def _default_entry(pool: str) -> dict[str, Any]:
    """Return a new entry with every field defaulted."""
    return {
        "run_id": "",
        "pool": pool,
        "task": "",
        "task_id": "",
        "role": "other",
        "agent": "",
        "host": "",
        "parent_run": "",
        "model": "",
        "request_sha256": "",
        "started_at": "",
        "timeout_s": 0.0,
        "attempt": 1,
        "status": "started",
        "acceptance": "not_reviewed",
        "acceptance_commit": "",
        "acceptance_by": "",
        "reserve_usd": 0.0,
        "charged_usd": 0.0,
        "cost_basis": "reserve",
        "truncated": False,
        "receipt": "",
    }


def legacy_entry(
    call: dict[str, Any], pool: str, receipt_or_none: dict[str, Any] | None
) -> dict[str, Any]:
    """Convert a schema-1 call dict into a schema-2 entry.

    *call* is a dict from a schema-1 ledger ``calls`` list.
    *receipt_or_none* is the parsed receipt JSON when available, else None.
    """
    entry = _default_entry(pool)
    entry["run_id"] = call.get("run_id", "")
    entry["task"] = call.get("task", "")
    entry["agent"] = call.get("agent", "")
    entry["charged_usd"] = float(call.get("charged_usd", 0.0))
    entry["receipt"] = call.get("receipt", "")
    status = call.get("status", "started")

    # Model / started_at from receipt when possible.
    if receipt_or_none is not None:
        entry["model"] = receipt_or_none.get("model", "")
        entry["started_at"] = receipt_or_none.get("started_at", "")
        entry["reserve_usd"] = float(
            receipt_or_none.get("preflight_reserve_usd", entry["charged_usd"])
        )
        entry["truncated"] = bool(
            receipt_or_none.get("truncated")
            or receipt_or_none.get("finish_reason") == "length"
        )
        # Schema-1 receipts hashed the packet, not the canonical request body,
        # so the duplicate guard cannot match them; keep the hash for joins.
        entry["packet_sha256"] = receipt_or_none.get("packet_sha256", "")
    else:
        entry["reserve_usd"] = entry["charged_usd"]

    # Status mapping.
    if status == "started":
        entry["status"] = "uncertain"
        entry["cost_basis"] = "reserve"
    elif status == "completed":
        entry["status"] = "completed"
        entry["cost_basis"] = (
            "metered_estimate" if receipt_or_none is not None else "imported_estimate"
        )
    elif status == "failed":
        entry["status"] = "failed"
        entry["cost_basis"] = "reserve"  # historical rule
    else:
        entry["status"] = status
        entry["cost_basis"] = "reserve"

    return entry


def imported_entry(
    kind: str,
    source: str,
    index_or_name: str,
    record: dict[str, Any],
    pool: str,
) -> dict[str, Any]:
    """Convert an import record into a schema-2 entry.

    *kind* is one of the supported import kinds.
    *source* is the original file/directory path.
    *index_or_name* is the list index (str) or file stem.
    *record* is the per-item dict.
    """
    entry = _default_entry(pool)
    entry["run_id"] = _import_run_id(kind, source, index_or_name)
    entry["imported_from"] = os.path.abspath(source)
    entry["imported_at"] = runner.utc_now()
    entry["task"] = record.get("task", "")
    entry["model"] = record.get("model", "")
    entry["charged_usd"] = float(record.get("cost", 0.0))
    entry["status"] = "completed"
    entry["cost_basis"] = "imported_estimate"
    entry["truncated"] = record.get("finish") == "length"
    return entry


# ---------------------------------------------------------------------------
# File I/O helpers (pure relative to the ledger).
# ---------------------------------------------------------------------------

def load_v2(path: Path) -> dict[str, Any]:
    """Load a schema-2 ledger, or return an empty one if missing."""
    if not path.exists():
        return {"schema": 2, "pools": {}, "calls": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise SystemExit(f"Ledger is unreadable: {path} ({exc})") from exc
    if data.get("schema") != 2:
        raise SystemExit(
            "Ledger schema is not 2.  Run 'scripts/delegate_ledger.py migrate' first."
        )
    return data


def write_v2(path: Path, ledger: dict[str, Any]) -> None:
    """Write a schema-2 ledger, recomputing each pool's committed_usd."""
    for pool_name, pool_obj in ledger.get("pools", {}).items():
        pool_obj["committed_usd"] = runner.pool_committed(ledger, pool_name)
    runner.atomic_json(path, ledger)


def _read_json(path: Path) -> dict[str, Any] | None:
    """A receipt or response file, or None when it is missing or unreadable."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _find(ledger: dict[str, Any], run_id: str) -> dict[str, Any]:
    for entry in ledger.get("calls", []):
        if entry["run_id"] == run_id:
            return entry
    raise SystemExit(f"Run ID '{run_id}' not found in ledger.")


# ---------------------------------------------------------------------------
# Subcommand implementations.
# ---------------------------------------------------------------------------

def _receipt_for(call: dict[str, Any]) -> dict[str, Any] | None:
    raw = call.get("receipt", "")
    return _read_json(Path(raw)) if raw else None


def _cmd_migrate(args: argparse.Namespace) -> int:
    target: Path = args.ledger.resolve()
    legacy_specs: list[tuple[str, Path]] = []
    for spec in args.legacy:
        if "=" not in spec:
            raise SystemExit(f"Invalid --legacy format (expected POOL=PATH): {spec}")
        pool, path_str = spec.split("=", 1)
        if not runner.SAFE_ID.fullmatch(pool):
            raise SystemExit(f"--legacy pool must be a safe identifier: {pool}")
        legacy_specs.append((pool, Path(path_str).resolve()))

    budget_overrides: dict[str, float] = {}
    for spec in args.budget:
        if "=" not in spec:
            raise SystemExit(f"Invalid --budget format (expected POOL=USD): {spec}")
        pool, usd_str = spec.split("=", 1)
        budget_overrides[pool] = float(usd_str)

    with runner.ledger_lock(target):
        existing = _read_json(target) if target.exists() else None
        if existing is not None and existing.get("schema") == 2:
            raise SystemExit(
                f"Target ledger {target} is already schema 2; refusing to overwrite."
            )

        new_ledger: dict[str, Any] = {"schema": 2, "pools": {}, "calls": []}
        legacy_sums: dict[str, float] = {}
        for pool, legacy_path in legacy_specs:
            legacy = _read_json(legacy_path)
            if legacy is None or legacy.get("schema") != 1:
                raise SystemExit(f"{legacy_path} is not a readable schema-1 ledger.")
            if pool in new_ledger["pools"]:
                raise SystemExit(f"Pool '{pool}' is given twice.")
            budget = budget_overrides.get(pool, float(legacy.get("budget_usd", 0.0)))
            new_ledger["pools"][pool] = {"budget_usd": budget}
            calls = legacy.get("calls", [])
            legacy_sums[pool] = sum(float(c.get("charged_usd", 0.0)) for c in calls)
            for call in calls:
                new_ledger["calls"].append(legacy_entry(call, pool, _receipt_for(call)))

        for pool, legacy_sum in legacy_sums.items():
            derived = runner.pool_committed(new_ledger, pool)
            if abs(derived - legacy_sum) > 0.0001:
                raise SystemExit(
                    f"Pool '{pool}' derived committed ${derived:.6f} does not match "
                    f"legacy charged sum ${legacy_sum:.6f}; nothing was written."
                )

        backups = [p.with_name(p.name + ".schema1.json") for _, p in legacy_specs]
        for backup in backups:
            if backup.exists():
                raise SystemExit(f"Backup already exists: {backup}; nothing was written.")
        # Renaming keeps each original byte for byte; the target is then rewritten.
        for (_, legacy_path), backup in zip(legacy_specs, backups):
            legacy_path.rename(backup)
        write_v2(target, new_ledger)

    for pool in new_ledger["pools"]:
        count = sum(1 for c in new_ledger["calls"] if c["pool"] == pool)
        committed = runner.pool_committed(new_ledger, pool)
        print(f"Pool '{pool}': {count} calls, committed ${committed:.6f}")
    return 0


def _scratchpad_log_records(source: Path) -> list[tuple[str, dict[str, Any]]]:
    if not source.is_dir():
        raise SystemExit(f"scratchpad-logs source is not a directory: {source}")
    records = []
    for log_file in sorted(source.glob("*.log")):
        try:
            rec = json.loads(log_file.read_text(encoding="utf-8").splitlines()[0])
        except (OSError, IndexError, ValueError):
            print(f"Skipping a log without a JSON first line: {log_file}")
            continue
        rec.setdefault("task", log_file.stem)
        card = runner.RATE_CARDS.get(rec.get("model", ""))
        if card is None:
            raise SystemExit(
                f"No rate card for model '{rec.get('model', '')}' in {log_file}; "
                "add it to RATE_CARDS in delegate_deepinfra.py."
            )
        rec["cost"] = round((
            int(rec.get("prompt_tokens", 0)) * float(card["input_per_1m"])
            + int(rec.get("completion_tokens", 0)) * float(card["output_per_1m"])
        ) / 1_000_000, 8)
        records.append((log_file.stem, rec))
    return records


def _cmd_import_calls(args: argparse.Namespace) -> int:
    ledger_path: Path = args.ledger.resolve()
    pool, kind, source = args.pool, args.kind, args.source

    # Build candidates before taking the lock; reading sources needs no lock.
    candidates: list[dict[str, Any]] = []
    if kind == "scratchpad-ledger":
        records = _read_json(Path(source))
        if not isinstance(records, list):
            raise SystemExit("scratchpad-ledger source must be a readable JSON list.")
        candidates = [imported_entry(kind, source, str(i), rec, pool)
                      for i, rec in enumerate(records)]
    elif kind == "scratchpad-logs":
        candidates = [imported_entry(kind, source, name, rec, pool)
                      for name, rec in _scratchpad_log_records(Path(source))]
    else:  # runner-ledger keeps the original run_id
        legacy = _read_json(Path(source))
        if legacy is None or legacy.get("schema") != 1:
            raise SystemExit("runner-ledger source is not a readable schema-1 ledger.")
        for call in legacy.get("calls", []):
            entry = legacy_entry(call, pool, _receipt_for(call))
            entry["imported_from"] = os.path.abspath(source)
            entry["imported_at"] = runner.utc_now()
            candidates.append(entry)

    with runner.ledger_lock(ledger_path):
        ledger = load_v2(ledger_path)
        pools = ledger.setdefault("pools", {})
        if pool not in pools:
            if args.budget is None:
                raise SystemExit(f"Pool '{pool}' does not exist and no --budget was given.")
            pools[pool] = {"budget_usd": float(args.budget)}

        existing_ids = {e["run_id"] for e in ledger.get("calls", [])}
        new_entries = [e for e in candidates if e["run_id"] not in existing_ids]
        skipped = len(candidates) - len(new_entries)

        if args.replace_run_id:
            target = _find(ledger, args.replace_run_id)
            imported_sum = sum(e["charged_usd"] for e in new_entries)
            if abs(float(target["charged_usd"]) - imported_sum) > 0.0001:
                raise SystemExit(
                    f"Replace target charged ${float(target['charged_usd']):.6f} "
                    f"does not match imported sum ${imported_sum:.6f}; nothing was written."
                )
            ledger["calls"] = [e for e in ledger["calls"]
                               if e["run_id"] != args.replace_run_id]

        ledger["calls"].extend(new_entries)
        write_v2(ledger_path, ledger)

    print(
        f"Imported {len(new_entries)} entries, skipped {skipped}. "
        f"Pool '{pool}' committed: ${runner.pool_committed(ledger, pool):.6f}"
    )
    return 0


def _metered_from_response(entry: dict[str, Any]) -> float:
    receipt = _receipt_for(entry)
    if receipt is None:
        raise SystemExit("No readable receipt and no --charged-usd; cannot determine cost.")
    response_raw = receipt.get("response_path", "")
    response = _read_json(Path(response_raw)) if response_raw else None
    if response is None:
        raise SystemExit(
            "No saved response for this run; give --charged-usd from the provider's "
            "usage page instead."
        )
    usage = (response.get("body") or {}).get("usage") or {}
    card = receipt.get("rate_card") or {}
    if not card:
        raise SystemExit("Receipt has no rate_card; cannot price usage.")
    return round((
        int(usage.get("prompt_tokens", 0)) * float(card["input_per_1m"])
        + int(usage.get("completion_tokens", 0)) * float(card["output_per_1m"])
    ) / 1_000_000, 8)


def _cmd_reconcile(args: argparse.Namespace) -> int:
    ledger_path: Path = args.ledger.resolve()
    with runner.ledger_lock(ledger_path):
        ledger = load_v2(ledger_path)
        entry = _find(ledger, args.run_id)
        if entry["status"] not in ("started", "uncertain"):
            raise SystemExit(
                f"Entry '{args.run_id}' has status '{entry['status']}'; "
                "only 'started' or 'uncertain' can be reconciled."
            )
        if args.charged_usd is not None:
            charged, basis = float(args.charged_usd), "manual"
        elif args.outcome == "completed":
            charged, basis = _metered_from_response(entry), "metered_estimate"
        else:
            charged, basis = 0.0, "none"
        entry.update({"status": args.outcome, "charged_usd": round(charged, 8),
                      "cost_basis": basis})

        receipt = _receipt_for(entry)
        if receipt is not None:
            receipt.update({"status": entry["status"], "charged_usd": entry["charged_usd"],
                            "cost_basis": basis, "reconciled_at": runner.utc_now()})
            runner.atomic_json(Path(entry["receipt"]), receipt)
        write_v2(ledger_path, ledger)

    print(f"Reconciled '{args.run_id}' -> {entry['status']}, charged ${entry['charged_usd']:.6f}")
    return 0


def _cmd_accept(args: argparse.Namespace) -> int:
    ledger_path: Path = args.ledger.resolve()
    with runner.ledger_lock(ledger_path):
        ledger = load_v2(ledger_path)
        entry = _find(ledger, args.run_id)
        if entry["status"] != "completed":
            raise SystemExit(
                f"Entry '{args.run_id}' has status '{entry['status']}'; "
                "only 'completed' entries can be accepted."
            )
        if entry.get("acceptance", "not_reviewed") != "not_reviewed":
            entry.setdefault("acceptance_history", []).append({
                "state": entry["acceptance"],
                "commit": entry.get("acceptance_commit", ""),
                "by": entry.get("acceptance_by", ""),
                "at": entry.get("acceptance_at", ""),
            })
        entry.update({"acceptance": args.state, "acceptance_commit": args.commit,
                      "acceptance_by": args.by, "acceptance_at": runner.utc_now()})
        write_v2(ledger_path, ledger)

    print(f"Recorded '{args.run_id}' as '{args.state}'")
    return 0


def pool_summary(ledger: dict[str, Any], pool: str) -> dict[str, Any]:
    budget = float(ledger["pools"][pool]["budget_usd"])
    committed = runner.pool_committed(ledger, pool)
    by_status: dict[str, int] = {}
    by_acceptance: dict[str, int] = {}
    open_runs = []
    for call in ledger.get("calls", []):
        if call["pool"] != pool:
            continue
        by_status[call["status"]] = by_status.get(call["status"], 0) + 1
        acceptance = call.get("acceptance", "not_reviewed")
        by_acceptance[acceptance] = by_acceptance.get(acceptance, 0) + 1
        if call["status"] in ("started", "uncertain"):
            open_runs.append({"run_id": call["run_id"], "task": call.get("task", ""),
                              "started_at": call.get("started_at", "")})
    return {"budget_usd": budget, "committed_usd": committed,
            "remaining_usd": round(budget - committed, 8),
            "calls_by_status": by_status, "calls_by_acceptance": by_acceptance,
            "open_runs": open_runs}


def _cmd_summary(args: argparse.Namespace) -> int:
    ledger = load_v2(args.ledger.resolve())
    pools = ledger.get("pools", {})
    if args.pool and args.pool not in pools:
        raise SystemExit(f"Pool '{args.pool}' not found in ledger.")
    result = {pool: pool_summary(ledger, pool)
              for pool in ([args.pool] if args.pool else sorted(pools))}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    for pool, s in result.items():
        print(f"Pool: {pool}")
        print(f"  Budget:     ${s['budget_usd']:.2f}")
        print(f"  Committed:  ${s['committed_usd']:.6f}")
        print(f"  Remaining:  ${s['remaining_usd']:.6f}")
        print(f"  By status:  {s['calls_by_status']}")
        print(f"  By accept:  {s['calls_by_acceptance']}")
        for r in s["open_runs"]:
            print(f"  Open: {r['run_id']}  {r['task']}  {r['started_at']}")
        print()
    return 0


def fetch_listing(url: str) -> Any:
    """Fetch the public model listing (testable via monkeypatch)."""
    req = urllib_request.Request(url, headers={"User-Agent": "delegate-ledger/1.0"})
    with urllib_request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _cmd_check_prices(args: argparse.Namespace) -> int:
    try:
        listing = fetch_listing(args.url)
    except Exception as exc:  # noqa: BLE001 - any fetch failure is reported the same way
        raise SystemExit(f"Failed to fetch model listing: {exc}") from exc

    items = listing if isinstance(listing, list) else listing.get("data", [])
    live: dict[str, tuple[float, float]] = {}
    for item in items:
        pricing = (item.get("metadata") or {}).get("pricing") or {}
        if item.get("id") and "input_tokens" in pricing and "output_tokens" in pricing:
            live[item["id"]] = (float(pricing["input_tokens"]), float(pricing["output_tokens"]))

    def close(card_value: float, live_value: float) -> bool:
        return abs(card_value - live_value) <= 0.01 * card_value + 1e-9

    stale = False
    for model, card in sorted(runner.RATE_CARDS.items()):
        if model not in live:
            print(f"NOT LISTED: {model}")
            stale = True
            continue
        live_in, live_out = live[model]
        card_in, card_out = float(card["input_per_1m"]), float(card["output_per_1m"])
        if close(card_in, live_in) and close(card_out, live_out):
            print(f"VERIFIED: {model}")
        else:
            print(f"STALE: {model}  card(in={card_in} out={card_out}) "
                  f"live(in={live_in} out={live_out})")
            stale = True
    return 1 if stale else 0


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_mig = sub.add_parser("migrate", help="Build a schema-2 ledger from schema-1 ledgers")
    p_mig.add_argument("--ledger", type=Path, default=runner.DEFAULT_LEDGER)
    p_mig.add_argument("--legacy", action="append", default=[], required=True,
                       help="POOL=PATH (repeatable)")
    p_mig.add_argument("--budget", action="append", default=[],
                       help="POOL=USD override (repeatable)")

    p_imp = sub.add_parser("import-calls", help="Append imported entries")
    p_imp.add_argument("--ledger", type=Path, default=runner.DEFAULT_LEDGER)
    p_imp.add_argument("--pool", required=True)
    p_imp.add_argument("--kind", required=True,
                       choices=["scratchpad-ledger", "scratchpad-logs", "runner-ledger"])
    p_imp.add_argument("--source", required=True)
    p_imp.add_argument("--budget", type=float, default=None)
    p_imp.add_argument("--replace-run-id", default=None)

    p_rec = sub.add_parser("reconcile", help="Resolve a started or uncertain entry")
    p_rec.add_argument("--ledger", type=Path, default=runner.DEFAULT_LEDGER)
    p_rec.add_argument("run_id")
    p_rec.add_argument("--outcome", required=True, choices=["completed", "failed"])
    p_rec.add_argument("--charged-usd", type=float, default=None)

    p_acc = sub.add_parser("accept", help="Record an acceptance decision")
    p_acc.add_argument("--ledger", type=Path, default=runner.DEFAULT_LEDGER)
    p_acc.add_argument("run_id")
    p_acc.add_argument("--state", required=True, choices=["accepted", "rejected", "partial"])
    p_acc.add_argument("--commit", default="")
    p_acc.add_argument("--by", default="")

    p_sum = sub.add_parser("summary", help="Show pool summaries")
    p_sum.add_argument("--ledger", type=Path, default=runner.DEFAULT_LEDGER)
    p_sum.add_argument("--pool", default=None)
    p_sum.add_argument("--json", action="store_true")

    p_chk = sub.add_parser("check-prices", help="Compare rate cards with the live listing")
    p_chk.add_argument("--url", default="https://api.deepinfra.com/v1/openai/models")

    args = parser.parse_args(argv)
    commands = {
        "migrate": _cmd_migrate,
        "import-calls": _cmd_import_calls,
        "reconcile": _cmd_reconcile,
        "accept": _cmd_accept,
        "summary": _cmd_summary,
        "check-prices": _cmd_check_prices,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
