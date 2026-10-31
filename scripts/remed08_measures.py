"""The REMED-08 pilot's declared measures, from run results, session logs and the ledger.

See docs/experiments/remed08-pilot-plan.md. Read-only.

    python scripts/remed08_measures.py --baseline tmp/g5/rerun-mimo --candidate tmp/g5/remed08-mimo
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))


def measures(run_dir: Path) -> dict[str, Any]:
    from resource_librarian import audit_events
    from resource_librarian.session import SessionStore
    from resource_librarian.vault import Vault
    data = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    rows = data["rows"]
    refused = [sum((r.get("refusals") or {}).values()) for r in rows]
    calls = sum((r.get("spend") or {}).get("calls", 0) for r in rows)
    usd = sum(float(r.get("ledger_usd", (r.get("spend") or {}).get("usd", 0.0))) for r in rows)
    tier_a = sum((r.get("grains") or {}).get("tier_a", 0) for r in rows)
    grains = sum((r.get("grains") or {}).get("grains", 0) for r in rows)
    kinds: dict[str, int] = {}
    parks, unnamed, verified = [], 0, 0
    for row in rows:
        for code, n in (row.get("refusals") or {}).items():
            kinds[code] = kinds.get(code, 0) + n
        sid = row.get("session")
        vault_root = run_dir / row["task"] / "vault"
        if not sid or not vault_root.is_dir():
            continue
        session = SessionStore(Vault(vault_root)).load(sid)
        audit = session.audit
        for reduction in audit.reductions:
            if reduction["status"] == "blocked" and "no progress" in reduction.get("reason", ""):
                parks.append(f"{row['task']}/{reduction['requirement']}")
            if reduction["status"] == "verified":
                verified += 1
                req = audit.requirements[reduction["requirement"]]
                for rid in reduction["results"]:
                    result = audit.results[rid]
                    if not audit_events.named_by_person(req, result["predicate"],
                                                        result["verifier"]):
                        unnamed += 1
    audits = [r.get("closure_audit") or {} for r in rows]
    return {
        "sessions": len(rows), "grains": grains, "tier_a": tier_a,
        "share": round(tier_a / grains, 3) if grains else None,
        "refused_total": sum(refused), "refused_median": statistics.median(refused) if refused
        else 0, "refused_by_code": dict(sorted(kinds.items())),
        "model_calls": calls,
        "calls_per_tier_a": round(calls / tier_a, 1) if tier_a else None,
        "usd": round(usd, 5), "usd_per_tier_a": round(usd / tier_a, 5) if tier_a else None,
        "max_turns": sum(1 for r in rows if r.get("stopped") == "max_turns"),
        "stops": [str(r.get("stopped"))[:60] for r in rows],
        "questions": sum(len(r.get("questions") or []) for r in rows),
        "stall_parks": parks,
        "invalid_histories": sum(1 for r in rows if r.get("invalid_history")),
        "restart_failures": sum(1 for r in rows
                                if not (r.get("restart") or {}).get("state_hash_equal", True)),
        "false_closures": sum(len(a.get("false_closures") or []) for a in audits),
        "closures_checked": sum(a.get("checked", 0) for a in audits),
        "verified_reductions": verified, "verified_without_named_verifier": unnamed,
        "rows": [{k: r.get(k) for k in ("task", "stopped", "turns", "grains", "refusals")}
                 for r in rows],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args(argv)
    out = {"baseline": measures(Path(args.baseline)), "candidate": measures(Path(args.candidate))}
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
