"""Run predeclared audited research sessions and measure Tier A (G5 readiness R3).

See docs/experiments/g5-measurement-plan.md. Each task runs on its own scratch
copy of the library, so the real library is never written. For each task the
runner:
1. opens an audited session through the real App and Lead loop;
2. sets the task's requirements as the person;
3. drives Lead turns until the session settles, stalls or reaches a cap;
4. forces one restart and checks the state hash survives it;
5. re-checks every Tier A closure (`closure_audit`).

    python scripts/g5_measure.py --library D:/Resource-Library/.librarian-app \
        --tasks docs/experiments/g5-tasks.json --run-dir tmp/g5/run-1 \
        --route deepinfra:deepseek-ai/DeepSeek-V4.1-Flash --budget-usd 1 --confirm-paid         --env-file D:/Resource-Library/.utility/.env

A paid route needs --confirm-paid and a budget. Every HTTP attempt to the
provider, retries included, holds a durable reservation on the shared
delegation ledger (pool `g5`) before it is sent, and is settled from the
usage that came back (REMED-05, `PaidDispatch`). An attempt whose cost is
unknown keeps its whole reservation and stops all further spending; a crash
leaves its reservations charged until a person reconciles them with
`scripts/delegate_ledger.py reconcile`. A dry run passes `provider_for` from
code (tests) and spends nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import secrets
import shutil
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).parent))
import delegate_deepinfra as delegation  # noqa: E402  (the shared ledger service)

SETTLED = {"complete_verified", "complete_with_human_acceptance", "failed", "blocked",
           "invalid_history", "integrity_violation", "needs_person"}
# The owner's decision (2026-10-30): a question the Lead asks mid-session gets
# this fixed, predeclared answer, so the session keeps running; each one is
# counted in the row's "questions".
FIXED_ANSWER = ("No further guidance: work from the requirements as set. If a predicate cannot "
                "be checked, say so rather than closing it.")
CONTINUE = ("Continue the audited session: read the projection, then work the next step of "
            "the round. Stop when the round is reduced or you need the person.")


def wilson(hits: int, total: int, z: float = 1.96) -> list[float] | None:
    if not total:
        return None
    p = hits / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return [round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)]


def copy_library(library: Path, target: Path) -> Path:
    """A scratch copy without the rebuildable index and without old sessions."""
    if target.exists():
        raise SystemExit(f"{target} already exists; choose a new --run-dir")
    shutil.copytree(library, target, ignore=lambda folder, names: [
        n for n in names if (Path(folder).name == ".librarian" and n in ("derived", "sessions"))])
    return target


class Meter:
    """Spend measured from the invocation runtime's own traces, one per model call.

    The App keeps these traces in memory only (it writes no model events to
    session logs, by design), so the runner attaches this meter as the
    runtime's trace sink. The G5 pilot found that reading session logs instead
    counted nothing. A call whose trace carries no usage makes the spend
    unknowable, so the run stops (fail closed).
    """

    def __init__(self, card: dict[str, float] | None = None):
        self.card = card
        self.calls = self.without_usage = self.input_tokens = self.output_tokens = 0

    def __call__(self, row: dict[str, Any]) -> None:
        self.calls += 1
        usage = ((row.get("result") or {}).get("telemetry") or {}).get("usage")
        if not isinstance(usage, dict) or not usage:
            self.without_usage += 1
            return
        self.input_tokens += int(usage.get("input_tokens") or 0)
        self.output_tokens += int(usage.get("output_tokens") or 0)

    @property
    def usd(self) -> float:
        if not self.card:
            return 0.0
        return round(self.input_tokens / 1e6 * self.card["input_per_1m"] +
                     self.output_tokens / 1e6 * self.card["output_per_1m"], 5)

    def to_dict(self) -> dict[str, Any]:
        return {"calls": self.calls, "without_usage": self.without_usage,
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                **({"usd": self.usd} if self.card else {})}


# The loop estimates tokens as characters/4; a provider cannot bill more input
# tokens than characters sent, so four times the estimate bounds the real cost.
PROMPT_MARGIN = 4.0


def guard(loop: Any, meter: "Meter", card: dict[str, float] | None,
          budget_usd: float | None) -> None:
    """Refuse a model call before it is sent when it could cross the cap, or when
    an earlier call reported no usage (the Codex review, 2026-10-30, found the cap
    was checked only after a whole multi-call turn). It wraps the loop's own
    pre-dispatch reservation, so a refusal stops the turn as a profile budget."""
    original = loop._reserve_profile_budget

    def reserve(system, messages, tools):
        if card is not None and meter.without_usage:
            return False, "G5 budget: a model call reported no usage, so spend is unbounded"
        if card is not None and budget_usd is not None:
            prompt = loop._token_estimate({"system": system, "messages": messages,
                                           "tools": [t.__dict__ for t in tools]})
            worst = (prompt * PROMPT_MARGIN * card["input_per_1m"] +
                     loop.profile_output_budget * card["output_per_1m"]) / 1_000_000
            if meter.usd + worst > budget_usd:
                return False, (f"G5 budget: the next call could cost ${worst:.4f} and only "
                               f"${max(0.0, budget_usd - meter.usd):.4f} of the cap remains")
        return original(system, messages, tools)

    loop._reserve_profile_budget = reserve


def run_task(task: dict[str, Any], *, library: Path, run_dir: Path, route: dict[str, str],
             provider_for: Callable | None = None, card: dict[str, float] | None = None,
             budget_usd: float | None = None, max_turns: int = 12,
             restart_after: int = 2, permission_wait: float = 5.0,
             answer_questions: str | None = FIXED_ANSWER,
             gate: "PaidDispatch | None" = None) -> dict[str, Any]:
    """One predeclared task, start to finish, on its own scratch library."""
    from resource_librarian import audit_events, closure_audit, research_grains
    from resource_librarian import tools  # noqa: F401
    from resource_librarian.app import App
    from resource_librarian.keys import KeyStore
    from resource_librarian.session import SessionStore
    from resource_librarian.vault import Vault

    vault = Vault(copy_library(library, run_dir / task["id"] / "vault"))
    store = SessionStore(vault)
    meter = Meter(card)
    asked: list[dict[str, Any]] = []
    current: dict[str, Any] = {"app": None, "session": ""}

    def answer(event: dict[str, Any]) -> None:
        """Answer the Lead's question as the person, with the fixed reply. It runs
        on its own thread: the Lead's turn is blocked inside ask_user."""
        if (event.get("type") != "question_asked" or answer_questions is None
                or event.get("session") != current["session"]):
            return
        asked.append({"id": event.get("question_id"), "question": str(event.get("question"))[:300],
                      "kind": event.get("kind")})
        threading.Thread(target=lambda: current["app"].person_call(
            "answer", {"question_id": event["question_id"], "answer": answer_questions},
            session=current["session"]), daemon=True).start()

    def open_app():
        # A short permission wait: with no person present, a question or a
        # permission request parks the session quickly, and the row says so.
        app = App(vault, keys=KeyStore(use_keyring=False), coordinate=True,
                  provider_for=provider_for, broker_timeout=permission_wait)
        app.invocation_runtime.trace_sink = meter
        app.waiters.subscribe(answer)
        current["app"] = app
        app.set_tiers([route], override="G5 measurement route")
        app.set_mode("auto")
        return app

    row: dict[str, Any] = {"task": task["id"], "route": f"{route['provider']}:{route['model']}"}
    app = open_app()
    try:
        # The person opens the session and sets its requirements before the
        # Lead's first turn. The G5 pilot let the Lead act first: with no
        # requirements it asked, waited and parked, and it proposed before any
        # requirement existed.
        sid = app.person_call("open_session", {"purpose": "audited",
                                               "question": task["question"]}).get("opened")
        if not sid:
            row["stopped"] = "no_audited_session"
            return row
        row["session"] = sid
        current["session"] = sid
        for requirement in task["requirements"]:
            args = {k: requirement[k] for k in ("requirement_id", "text", "closure", "predicates",
                                                "verifiers") if k in requirement}
            out = app.person_call("set_requirement", args, session=sid)
            if "refused" in out or "error" in out:
                row["stopped"] = f"requirement refused: {out}"
                return row
        loop = app._loop()
        loop.ctx.session = sid
        guard(loop, meter, card, budget_usd)
        idle, turns = 0, 0
        message = (f"This audited session is yours to work. Its question: {task['question']} "
                   f"The person has set its requirements. {CONTINUE}")
        while turns < max_turns:
            before_calls = meter.calls
            turn = loop.send(message)
            message = CONTINUE
            turns += 1
            idle = idle + 1 if not turn.calls else 0
            if turn.stopped == "profile_budget" and "G5 budget" in (turn.error or ""):
                row["stopped"] = f"budget: {turn.error}"
                break
            if gate is not None and gate.blocked:
                row["stopped"] = f"budget: G5 budget: {gate.blocked}"
                break
            if card is not None and (meter.without_usage or
                                     (turn.steps and meter.calls == before_calls)):
                row["stopped"] = "usage_unavailable"
                break
            if budget_usd is not None and meter.usd >= budget_usd:
                row["stopped"] = "budget"
                break
            if turns == restart_after and "restart" not in row:
                before = store.load(sid).state_hash()
                app.close_runtime()
                app = open_app()
                loop = app._loop()
                loop.ctx.session = sid
                guard(loop, meter, card, budget_usd)
                row["restart"] = {"after_turn": turns,
                                  "state_hash_equal": store.load(sid).state_hash() == before}
            outcome = audit_events.session_outcome(store.load(sid).audit)
            status = store.load(sid).status
            if outcome in SETTLED or status != "open":
                row["stopped"] = f"settled: {outcome}" if outcome in SETTLED else f"status: {status}"
                break
            if idle >= 2:
                row["stopped"] = "idle"
                break
        else:
            row["stopped"] = "max_turns"
        session = store.load(sid)
        summary = audit_events.summary(session.audit)
        verifiers: dict[str, dict[str, int]] = {}
        for result in session.audit.results.values():
            slot = verifiers.setdefault(result["verifier"], {"results": 0, "pass": 0})
            slot["results"] += 1
            slot["pass"] += result["outcome"] == "pass"
        refusals: dict[str, int] = {}
        for event in store.events(sid):
            code = event.get("refused") if event.get("type") == "call" else None
            if code:
                refusals[code] = refusals.get(code, 0) + 1
        row.update({
            "turns": turns, "rounds": session.audit_round, "outcome": summary["outcome"],
            "invalid_history": bool(session.audit.invalid),
            "grains": research_grains.grain_counts(session.audit),
            "no_suitable_tool": sum(1 for r in summary["requirements"].values()
                                    for o in r["predicates"].values() if o == "no_suitable_tool"),
            "integrity": {c: v["integrity"] for c, v in summary["contracts"].items()},
            "verifiers": verifiers, "refusals": refusals, "questions": asked,
        })
        return row
    except Exception as exc:  # noqa: BLE001 - one task's crash is a result, not the run's end
        row["stopped"] = f"error: {type(exc).__name__}: {str(exc)[:300]}"
        return row
    finally:
        row["spend"] = meter.to_dict()
        app.close_runtime()
        if row.get("session") and "grains" in row:
            # After the App has closed: the audit opens its own index of the
            # scratch library, so index.findable can be re-run (the full run's
            # first audit had none, and counted 8 unavailable re-runs as false).
            row["closure_audit"] = audit_offline(vault, row["session"])


def _registered() -> set[str]:
    from resource_librarian.closure import VERIFIERS
    return set(VERIFIERS)


def audit_offline(vault: Any, session_id: str) -> dict[str, Any]:
    """The closure audit of one finished session, with an index of its library."""
    from resource_librarian import closure_audit
    from resource_librarian.index import Index
    from resource_librarian.search import Engine
    from resource_librarian.session import SessionStore
    session = SessionStore(vault).load(session_id)
    with Index(vault) as index:
        index.refresh()
        heuristics = dict(vault.config().get("heuristics") or {})
        return closure_audit.audit(vault, session,
                                   index_run=lambda operation: operation(Engine(index, heuristics)))


POOL = "g5"


def adopt_ledger(path: Path, cap: float) -> None:
    """Move a first-format G5 ledger ({cap_usd, spent_usd, entries}) onto the shared
    delegation ledger (schema 2, pool `g5`), so G5 has no accounting policy of its
    own (REMED-05). Each earlier run becomes one completed entry at what it
    recorded; the old file is kept byte for byte beside it. Nothing changes when
    the ledger is already schema 2, or absent."""
    path = Path(path)
    if not path.is_file():
        return
    old = json.loads(path.read_text(encoding="utf-8"))
    if old.get("schema") == 2:
        return
    if "cap_usd" not in old:
        raise SystemExit(f"refusing: {path} is neither a G5 nor a schema-2 ledger")
    if abs(float(old["cap_usd"]) - cap) > 1e-9:
        raise SystemExit(f"refusing: the ledger's cap is ${old['cap_usd']}, not ${cap}")
    calls = []
    for n, item in enumerate(old.get("entries") or []):
        calls.append({"run_id": f"import-g5-{n + 1}", "pool": POOL, "task": item["label"],
                      "task_id": "", "status": "completed", "charged_usd": float(item["usd"]),
                      "reserve_usd": float(item["usd"]), "cost_basis": "imported_estimate",
                      "request_sha256": "", "attempt": 1, "truncated": False,
                      "imported_from": str(path.resolve())})
    ledger = {"schema": 2, "pools": {POOL: {"budget_usd": cap}}, "calls": calls}
    if abs(delegation.pool_committed(ledger, POOL) - float(old["spent_usd"])) > 0.0001:
        raise SystemExit(f"refusing: {path}'s entries do not add up to its spent_usd")
    backup = path.with_name(path.stem + ".g5v1.json")
    if backup.exists():
        raise SystemExit(f"refusing: {backup} already exists; nothing was changed")
    with delegation.ledger_lock(path):
        path.rename(backup)
        delegation._write_ledger_locked(path, ledger)


def committed(path: Path, cap: float, task_id: str = "") -> float:
    """What the pool (or one run, by its task id) has committed, reservations included."""
    with delegation.ledger_lock(path):
        ledger = delegation._load_ledger_locked(path, POOL, cap)
    return round(sum(float(c.get("charged_usd", 0.0)) for c in ledger.get("calls", [])
                     if c.get("pool") == POOL and (not task_id or c.get("task_id") == task_id)),
                 8)


class PaidDispatch(delegation.providers.DispatchGate):
    """The G5 runner's dispatch gate: each HTTP attempt to the provider, retries
    included, is reserved on the shared ledger before it is sent and settled
    from what came back, by the delegation service's own rules (REMED-05).

    - Reserve: the exact request bytes as an upper bound on input tokens (a
      token is at least one byte) plus `max_tokens` of output, at the rate card.
      The ledger refuses it past the pool's cap, past this run's budget, or
      for a request identical to one whose outcome is unknown.
    - Settle: a reply with usage is charged its metered cost (`completed`); an
      HTTP error or a refused connection, which the provider did not process,
      is `failed` at nothing; anything else (a timeout, a dropped connection,
      a reply without usage) is `uncertain` at the whole reservation, never
      refunded, and blocks later dispatches in that task. The next task may
      start against the remaining caps; structural budget failures still stop
      the whole run.
    - A crash between the two leaves the entry `started` at its reservation.
    """

    def __init__(self, ledger: Path, cap: float, card: dict[str, float], *, model: str,
                 run: str, task: str = "", run_budget: float | None = None,
                 call_cap: float = 0.25, host: str = "api.deepinfra.com") -> None:
        self.ledger, self.cap, self.card, self.model = Path(ledger), cap, card, model
        self.run, self.task, self.run_budget, self.call_cap = run, task, run_budget, call_cap
        self.host = host
        self.blocked = ""
        self.run_blocked = ""
        self.attempts = self.settled = 0

    def _stop(self, reason: str) -> None:
        self.run_blocked = self.run_blocked or reason
        raise delegation.providers.ProviderError(f"G5 budget: {reason}", category="budget")

    def begin_task(self, task: str) -> None:
        """Start one task without forgiving a run-wide safety failure."""
        self.task = task
        self.blocked = ""

    def before(self, method: str, url: str, body: Any, sent_bytes: int) -> Any:
        if body is None:
            return None                 # a listing or balance request: no model call
        if self.run_blocked:
            self._stop(self.run_blocked)
        if self.blocked:
            raise delegation.providers.ProviderError(
                f"G5 budget: {self.blocked}", category="budget")
        if self.host not in url:
            self._stop(f"a model request to {url.split('?')[0]} has no rate card here")
        limit = body.get("max_tokens") or body.get("max_completion_tokens") \
            if isinstance(body, dict) else None
        if not isinstance(limit, int) or limit <= 0:
            self._stop("a model request without max_tokens cannot be bounded")
        reserve = (sent_bytes * self.card["input_per_1m"] +
                   limit * self.card["output_per_1m"]) / 1_000_000
        raw = json.dumps(body).encode("utf-8")
        entry = {"run_id": f"g5-{secrets.token_hex(6)}", "pool": POOL, "task": self.task,
                 "task_id": self.run, "role": "evaluation", "model": self.model,
                 "request_sha256": hashlib.sha256(raw).hexdigest(),
                 "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                 "timeout_s": 180.0, "attempt": 1, "status": "started",
                 "reserve_usd": round(reserve, 8), "charged_usd": round(reserve, 8),
                 "cost_basis": "reserve", "truncated": False, "receipt": "",
                 "sent_bytes": sent_bytes, "max_tokens": limit}
        try:
            delegation.reserve_call(self.ledger, POOL, self.cap, entry, reserve, self.call_cap,
                                    task_cap_usd=self.run_budget)
        except SystemExit as exc:
            self._stop(f"the ledger refused the reservation: {exc}")
        self.attempts += 1
        return entry["run_id"], reserve

    def after(self, ticket: Any, error: BaseException | None, reply: Any) -> None:
        if ticket is None:
            return
        run_id, reserve = ticket
        usage = reply.get("usage") if error is None and isinstance(reply, dict) else None
        if error is None and isinstance(usage, dict) and usage:
            tokens_in = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
            tokens_out = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
            actual = (tokens_in * self.card["input_per_1m"] +
                      tokens_out * self.card["output_per_1m"]) / 1_000_000
            status, charged, basis = "completed", actual, "metered_estimate"
            if actual > reserve:
                # Billed past its bound: charge what was billed, and spend no more.
                self.run_blocked = self.run_blocked or "a call cost more than its reservation"
        elif error is not None and delegation.classify_failure(error, False) == "failed":
            status, charged, basis = "failed", 0.0, "none"
        else:
            status, charged, basis = "uncertain", reserve, "reserve"
            self.blocked = self.blocked or (
                "a model call's cost is unknown (no usage)" if error is None else
                f"a model call's outcome is unknown ({type(error).__name__}); reconcile it "
                f"with delegate_ledger.py reconcile {run_id}")
        delegation.settle_call(self.ledger, POOL, self.cap, run_id, status=status,
                               charged_usd=charged, cost_basis=basis, receipt_path="")
        self.settled += 1


def validate_tasks(data: dict[str, Any], library: Path | None = None) -> list[str]:
    """Problems with a task file, empty when it is runnable. With `library`,
    every task's named sources must exist there."""
    registered = _registered()
    problems = []
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return ["the file has no tasks"]
    seen = set()
    for task in tasks:
        tid = str(task.get("id") or "")
        if not tid or tid in seen:
            problems.append(f"task id {tid!r} is missing or repeated")
        seen.add(tid)
        if not str(task.get("question") or "").strip():
            problems.append(f"{tid}: no question")
        ids = [r.get("requirement_id") for r in task.get("requirements") or []]
        if not ids or len(set(ids)) != len(ids):
            problems.append(f"{tid}: requirement ids missing or repeated")
        for req in task.get("requirements") or []:
            closure = req.get("closure", "authoritative")
            if closure not in ("authoritative", "partial", "human_judgment"):
                problems.append(f"{tid} {req.get('requirement_id')}: closure {closure!r}")
            if closure == "authoritative" and not req.get("predicates"):
                problems.append(f"{tid} {req.get('requirement_id')}: authoritative needs predicates")
            if not str(req.get("text") or "").strip():
                problems.append(f"{tid} {req.get('requirement_id')}: no text")
            named = req.get("verifiers") or {}
            from resource_librarian.closure import SUBJECTS, binding
            for predicate, named_verifier in named.items():
                bound = binding(named_verifier)
                if predicate not in (req.get("predicates") or []):
                    problems.append(f"{tid} {req.get('requirement_id')}: verifier named for "
                                    f"{predicate!r}, which is not one of its predicates")
                if bound["verifier"] not in registered:
                    problems.append(f"{tid} {req.get('requirement_id')}: unknown verifier "
                                    f"{bound['verifier']!r}")
                elif closure == "authoritative":
                    missing = [k for k in SUBJECTS.get(bound["verifier"], ())
                               if k not in bound["params"]]
                    if missing:
                        problems.append(f"{tid} {req.get('requirement_id')}: {predicate!r} "
                                        f"binds no subject ({', '.join(missing)})")
            if closure == "authoritative":
                missing = [p for p in req.get("predicates") or [] if p not in named]
                if missing:
                    problems.append(f"{tid} {req.get('requirement_id')}: no verifier named for "
                                    f"{missing}")
        for rel in task.get("sources") or []:
            if library is not None and not (Path(library) / rel).is_file():
                problems.append(f"{tid}: source {rel} is not in the library")
    return problems


def totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pooled and per-route Tier A share, with Wilson 95% intervals."""
    def pool(selected):
        grains = sum((r.get("grains") or {}).get("grains", 0) for r in selected)
        tier_a = sum((r.get("grains") or {}).get("tier_a", 0) for r in selected)
        false = sum(len((r.get("closure_audit") or {}).get("false_closures", []))
                    for r in selected)
        return {"sessions": len(selected), "grains": grains, "tier_a": tier_a,
                "share": round(tier_a / grains, 3) if grains else None,
                "interval_95": wilson(tier_a, grains), "false_closures": false,
                "restart_failures": sum(1 for r in selected
                                        if r.get("restart", {}).get("state_hash_equal") is False),
                "invalid_histories": sum(1 for r in selected if r.get("invalid_history")),
                "usd": round(sum((r.get("spend") or {}).get("usd", 0.0) for r in selected), 4)}
    routes = sorted({r["route"] for r in rows})
    return {"pooled": pool(rows), "by_route": {k: pool([r for r in rows if r["route"] == k])
                                               for k in routes}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--library", required=True)
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--route", required=True, help="provider:model, e.g. deepinfra:...")
    parser.add_argument("--budget-usd", type=float, required=True,
                        help="hard cap for the whole run")
    parser.add_argument("--confirm-paid", action="store_true",
                        help="required: this run makes paid model calls")
    parser.add_argument("--only", action="append", default=[], help="run only these task ids")
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--ledger", default="tmp/g5/ledger.json",
                        help="the spend ledger every G5 run shares (delegation schema 2, "
                             "pool g5)")
    parser.add_argument("--call-cap-usd", type=float, default=0.25,
                        help="the most one model request may reserve")
    parser.add_argument("--ledger-cap", type=float, default=8.0,
                        help="the cap across all runs on this ledger (the approved $8)")
    parser.add_argument("--env-file", default="",
                        help="load DEEPINFRA_API_KEY from this file into this process only")
    args = parser.parse_args(argv)
    if args.env_file:
        for line in Path(args.env_file).read_text(encoding="utf-8").splitlines():
            name, sep, value = line.strip().partition("=")
            if sep and name.strip() == "DEEPINFRA_API_KEY":
                os.environ["DEEPINFRA_API_KEY"] = value.strip().strip('"').strip("'")
    if not args.confirm_paid:
        print("refusing: a real route makes paid calls; pass --confirm-paid", file=sys.stderr)
        return 2
    # The App keeps the person's model choices (tiers, overrides, profiles) in a
    # per-user config folder shared by every library. A measurement run must not
    # change the desktop app's routes, so it gets a config folder of its own.
    os.environ["LIBRARIAN_CONFIG_DIR"] = str(Path(args.run_dir).resolve() / "config")
    RATE_CARDS = delegation.RATE_CARDS
    provider, _, model = args.route.partition(":")
    card = RATE_CARDS.get(model)
    if card is None:
        print(f"refusing: no checked rate card for {model}; run delegate_ledger.py "
              "check-prices and add one", file=sys.stderr)
        return 2
    data = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    problems = validate_tasks(data, Path(args.library))
    if problems:
        print("refusing: the task file is not runnable:\n- " + "\n- ".join(problems),
              file=sys.stderr)
        return 2
    tasks = data["tasks"]
    if args.only:
        tasks = [t for t in tasks if t["id"] in args.only]
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    ledger = Path(args.ledger)
    adopt_ledger(ledger, args.ledger_cap)
    # This run's id on the ledger: its budget is a task cap there, and every
    # reservation is charged to it as it is made, not after a task ends.
    run_id = f"{run_dir.resolve().name}-{secrets.token_hex(3)}"
    gate = PaidDispatch(ledger, args.ledger_cap, card, model=model, run=run_id,
                        run_budget=args.budget_usd, call_cap=args.call_cap_usd)
    previous = delegation.providers.set_dispatch_gate(gate)
    rows = []

    def save() -> None:
        (run_dir / "results.json").write_text(json.dumps(
            {"rows": rows, "totals": totals(rows), "ledger_run": run_id}, indent=1,
            default=str), encoding="utf-8")

    try:
        for task in tasks:
            used = committed(ledger, args.ledger_cap, run_id)
            remaining = min(args.budget_usd - used,
                            args.ledger_cap - committed(ledger, args.ledger_cap))
            if remaining <= 0 or gate.run_blocked:
                # A task the run could not start is a result too: it is saved
                # with the reason (the REMED-08 pilot found these unrecorded).
                rows.append({"task": task["id"], "route": args.route,
                             "stopped": f"budget_exhausted{': ' + gate.run_blocked if gate.run_blocked else ''}"})
                save()
                continue
            gate.begin_task(f"{run_dir.name}/{task['id']} ({args.route})")
            row = run_task(task, library=Path(args.library), run_dir=run_dir,
                           route={"provider": provider, "model": model}, card=card,
                           budget_usd=remaining, max_turns=args.max_turns, gate=gate)
            row["ledger_usd"] = round(committed(ledger, args.ledger_cap, run_id) - used, 8)
            rows.append(row)
            save()
    finally:
        delegation.providers.set_dispatch_gate(previous)
    print(json.dumps(totals(rows), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
