"""Keep two libraries' combined model spend under one total (owner 2026-11-16: $30 in all).

Every minute:
  * Resource-Library's ceiling = total - Nonlinear Field Lab's spend - a reserve for that
    library's documents still to read (measured ~$0.006 per document; reserved at $0.012).
  * Nonlinear Field Lab's ceiling is lowered (never raised) to total - Resource-Library's spend.
  * When the combined spend reaches the total, both ceilings are pinned to what is spent.
Each library's Core enforces its own ceiling between items, so overshoot is at most one item each.
Writes one JSON line per change to budget-supervisor.jsonl beside this script.
"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, r"D:\Librarian_V2\src")
from resource_librarian.vault import Vault            # noqa: E402
from resource_librarian import usage_log              # noqa: E402

TOTAL = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
NFL = Vault(r"G:\Libraries\Nonlinear Field Lab")
RL = Vault(r"G:\Libraries\Resource-Library")
LOG = Path(__file__).with_name("budget-supervisor.jsonl")
PER_DOC_RESERVE = 0.012


def nfl_remaining_docs():
    """Documents in Nonlinear Field Lab's Source folders not yet queued, plus queued-but-unread."""
    from resource_librarian import folder_sources
    roots = json.loads((NFL.librarian / "content-roots.json").read_text(encoding="utf-8"))["roots"]
    ledger = NFL.librarian / "folder-sources.json"
    done = json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else {}
    left = 0
    for r in roots:
        if r.get("attached") and r.get("purpose") in ("own-docs", "research-docs", "third-party"):
            scope = (".pdf",) if r["purpose"] != "own-docs" else (".pdf", ".md")
            try:
                docs = folder_sources.documents(NFL, r["path"], scope)
            except ValueError:
                continue
            left += sum(1 for d in docs if d.resolve().as_posix() not in done)
    store = NFL.librarian / "staging" / "source"
    unread = sum(1 for p in store.glob("*.json")
                 if json.loads(p.read_text(encoding="utf-8")).get("status") in ("staged", "approved", "processing"))
    return left + unread


def note(**row):
    row["t"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(LOG, "a", encoding="utf-8") as h:
        h.write(json.dumps(row) + "\n")


last = None
while True:
    if not (NFL.config_path.is_file() and RL.config_path.is_file()):
        # Never create a library by writing its setting (2026-11-16: a moved vault's old path).
        note(error="a library's config.toml is missing; supervisor stopped",
             nfl=str(NFL.config_path), rl=str(RL.config_path))
        raise SystemExit(2)
    try:
        nfl, rl = usage_log.spent_usd(NFL), usage_log.spent_usd(RL)
        nfl_ceiling = NFL.setting("budget", "ceiling_usd")
        if nfl + rl >= TOTAL:
            rl_target, nfl_target = rl, min(nfl_ceiling or nfl, nfl)
        else:
            reserve = nfl_remaining_docs() * PER_DOC_RESERVE
            rl_target = max(rl, round(TOTAL - nfl - reserve, 4))
            nfl_target = nfl_ceiling if nfl_ceiling is not None and nfl_ceiling <= TOTAL - rl \
                else round(TOTAL - rl, 4)
        if RL.setting("budget", "ceiling_usd") != rl_target:
            RL.set_setting("budget", "ceiling_usd", rl_target)
        if nfl_ceiling is not None and nfl_target < nfl_ceiling:
            NFL.set_setting("budget", "ceiling_usd", nfl_target)
        state = (round(nfl, 3), round(rl, 3), rl_target, nfl_target)
        if state != last:
            note(nfl_spent=state[0], rl_spent=state[1], rl_ceiling=rl_target, nfl_ceiling=nfl_target,
                 total=TOTAL, combined=round(nfl + rl, 4))
            last = state
    except Exception as exc:                       # noqa: BLE001 - keep supervising; record why
        note(error=str(exc)[:300])
    time.sleep(60)
