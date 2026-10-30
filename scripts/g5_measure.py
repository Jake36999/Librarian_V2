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

A paid route needs --confirm-paid and a budget. The runner stops at the budget,
and stops if the provider reports no usage, because then spend cannot be
bounded. A dry run passes `provider_for` from code (tests) and spends nothing.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import threading
from pathlib import Path
from typing import Any, Callable

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
             answer_questions: str | None = FIXED_ANSWER) -> dict[str, Any]:
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


class Ledger:
    """The G5 spend ledger: one cap across every run that uses it. A run holds an
    exclusive lock for its whole length, so two runs never spend against the same
    remainder at once (Codex review: separate invocations shared no cap)."""

    def __init__(self, path: Path, cap: float):
        self.path, self.lock = Path(path), Path(path).with_suffix(".lock")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise SystemExit(f"refusing: {self.lock} exists; another G5 run holds the "
                             "ledger (remove the lock only if that run has ended)") from None
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        self.data = (json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file()
                     else {"cap_usd": cap, "spent_usd": 0.0, "entries": []})
        if abs(float(self.data["cap_usd"]) - cap) > 1e-9:
            self.release()
            raise SystemExit(f"refusing: the ledger's cap is ${self.data['cap_usd']}, not ${cap}")

    @property
    def remaining(self) -> float:
        return max(0.0, float(self.data["cap_usd"]) - float(self.data["spent_usd"]))

    def record(self, label: str, usd: float) -> None:
        self.data["spent_usd"] = round(float(self.data["spent_usd"]) + usd, 5)
        self.data["entries"].append({"label": label, "usd": round(usd, 5)})
        self.path.write_text(json.dumps(self.data, indent=1) + "\n", encoding="utf-8")

    def release(self) -> None:
        self.lock.unlink(missing_ok=True)


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
                        help="the spend ledger every G5 run shares")
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
    sys.path.insert(0, str(Path(__file__).parent))
    from delegate_deepinfra import RATE_CARDS
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
    ledger = Ledger(Path(args.ledger), args.ledger_cap)
    rows, spent = [], 0.0
    try:
        for task in tasks:
            remaining = min(args.budget_usd - spent, ledger.remaining)
            if remaining <= 0:
                rows.append({"task": task["id"], "route": args.route,
                             "stopped": "budget_exhausted"})
                continue
            row = run_task(task, library=Path(args.library), run_dir=run_dir,
                           route={"provider": provider, "model": model}, card=card,
                           budget_usd=remaining, max_turns=args.max_turns)
            cost = (row.get("spend") or {}).get("usd", 0.0)
            spent += cost
            ledger.record(f"{run_dir.name}/{task['id']} ({args.route})", cost)
            rows.append(row)
            (run_dir / "results.json").write_text(json.dumps(
                {"rows": rows, "totals": totals(rows)}, indent=1, default=str),
                encoding="utf-8")
    finally:
        ledger.release()
    print(json.dumps(totals(rows), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
