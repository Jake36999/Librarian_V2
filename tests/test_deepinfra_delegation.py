"""The development delegation runner must fail closed before any paid call."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import urllib.error
from argparse import Namespace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("delegate_deepinfra", SCRIPTS / "delegate_deepinfra.py")
assert SPEC is not None and SPEC.loader is not None
delegate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(delegate)
# The ledger tool imports the runner by name; give it this same module object.
sys.modules["delegate_deepinfra"] = delegate
LEDGER_SPEC = importlib.util.spec_from_file_location("delegate_ledger", SCRIPTS / "delegate_ledger.py")
assert LEDGER_SPEC is not None and LEDGER_SPEC.loader is not None
ledger_tool = importlib.util.module_from_spec(LEDGER_SPEC)
LEDGER_SPEC.loader.exec_module(ledger_tool)

MODEL = "deepseek-ai/DeepSeek-V4.1-Flash-1017"


def entry(run_id, task="t", *, pool="p", sha="h-" + "0", status="started",
          charged=0.1, started_at=None, timeout_s=180.0, task_id=""):
    return {
        "run_id": run_id, "pool": pool, "task": task, "task_id": task_id,
        "role": "other", "agent": "test", "host": "", "parent_run": "", "model": MODEL,
        "request_sha256": sha, "started_at": started_at or delegate.utc_now(),
        "timeout_s": timeout_s, "attempt": 1, "status": status,
        "acceptance": "not_reviewed", "acceptance_commit": "", "acceptance_by": "",
        "reserve_usd": charged, "charged_usd": charged, "cost_basis": "reserve",
        "truncated": False, "receipt": "",
    }


def run_args(tmp_path, **overrides):
    values = dict(
        task="test", lens="correctness", model=MODEL, instruction="Hello",
        instruction_file=None, file=[], max_output_tokens=100, temperature=0.1,
        timeout=10, call_cap_usd=1.0, total_budget_usd=10.0, task_budget_usd=None,
        pool="shared", task_id="", role="other", parent_run="", allow_truncated=False,
        allow_stale_prices=False, ledger=tmp_path / "ledger.json",
        output_dir=tmp_path / "runs", key_file=tmp_path / ".env",
        max_file_bytes=500_000, max_packet_bytes=1_500_000, dry_run=False,
        agent="test-agent", work_package=None, export_root=None,
    )
    values.update(overrides)
    return Namespace(**values)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    repository = tmp_path / "repo"
    repository.mkdir()
    monkeypatch.setattr(delegate, "REPOSITORY", repository)
    monkeypatch.setenv("DEEPINFRA_API_KEY", "fake-key")
    return tmp_path


def fake_provider(monkeypatch, reply=None, error=None):
    """Patch the single provider request; returns the list of calls made."""
    calls = []

    def fake_request(method, url, headers, body, timeout, retries):
        calls.append(body)
        assert retries == ()
        if error is not None:
            raise error
        return reply or {
            "model": MODEL,
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        }

    monkeypatch.setattr(delegate.providers, "_request", fake_request)
    return calls


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --- packet export -----------------------------------------------------------------

def test_export_is_repository_confined_and_secret_scanned(tmp_path, monkeypatch):
    repository = tmp_path / "repo"
    repository.mkdir()
    safe = repository / "safe.py"
    safe.write_text("answer = 42\n", encoding="utf-8")
    secret = repository / "secret.py"
    secret.write_text('api_key = "this-is-a-secret-value"\n', encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("outside = True\n", encoding="utf-8")
    monkeypatch.setattr(delegate, "REPOSITORY", repository)

    assert delegate.resolve_export("safe.py") == safe.resolve()
    with pytest.raises(SystemExit, match="outside the repository"):
        delegate.resolve_export(str(outside))
    with pytest.raises(SystemExit, match="possible secret"):
        delegate.checked_text(secret, max_bytes=10_000)


def test_packet_manifest_hashes_exact_exported_bytes(tmp_path, monkeypatch):
    repository = tmp_path / "repo"
    repository.mkdir()
    source = repository / "module.py"
    source.write_bytes(b"value = 1\n")
    monkeypatch.setattr(delegate, "REPOSITORY", repository)
    args = Namespace(file=["module.py"], max_file_bytes=1000,
                     max_packet_bytes=1000, instruction="Review it.",
                     task="test-task", lens="correctness")

    payload, manifest = delegate.packet(args)

    assert '<file path="module.py">' in payload
    assert manifest == [{"path": "module.py", "bytes": 10,
                         "sha256": delegate.sha256(b"value = 1\n")}]


def test_preflight_reserve_uses_pinned_input_and_maximum_output_rates():
    body = {"max_tokens": 1000, "messages": [{"role": "user", "content": "x" * 3500}]}
    card = {"input_per_1m": 1.0, "output_per_1m": 2.0}

    input_guess, reserve = delegate.reserve_cost(body, card)

    assert input_guess >= 1000
    assert reserve >= 0.003


def test_instruction_file_read_and_secret_scanned(isolated, monkeypatch):
    inst_file = isolated / "instruction.txt"
    inst_file.write_text("Review the code.", encoding="utf-8")
    base = ["--task", "t", "--model", MODEL]

    with pytest.raises(SystemExit):
        delegate.parse_args(base + ["--instruction", "x", "--instruction-file", str(inst_file)])
    with pytest.raises(SystemExit):
        delegate.parse_args(base)
    args = delegate.parse_args(base + ["--instruction-file", str(inst_file)])
    assert args.instruction_file == inst_file

    secret_file = isolated / "secret_instruction.txt"
    secret_file.write_text('api_key = "this-is-a-secret-value"', encoding="utf-8")
    args = delegate.parse_args(base + ["--instruction-file", str(secret_file)])
    monkeypatch.setattr(delegate, "parse_args", lambda argv=None: args)
    with pytest.raises(SystemExit, match="possible secret"):
        delegate.main()


# --- ledger schema 2 ---------------------------------------------------------------

def test_schema1_ledger_is_refused_with_migration_hint(tmp_path):
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"schema": 1, "budget_usd": 10, "calls": []}), encoding="utf-8")
    with pytest.raises(SystemExit, match="migrate"):
        delegate.read_ledger(ledger, "p", 10.0)


def test_existing_pool_cannot_silently_change_its_ceiling(tmp_path):
    ledger = tmp_path / "ledger.json"
    delegate.atomic_json(ledger, {"schema": 2, "pools": {"p": {"budget_usd": 10.0}}, "calls": []})
    with pytest.raises(SystemExit, match=r"not requested \$12.00"):
        delegate.read_ledger(ledger, "p", 12.0)
    # Another pool in the same file has its own budget.
    assert "q" in delegate.read_ledger(ledger, "q", 3.0)["pools"]


def test_interleaved_reservations_settle_and_derive_committed(tmp_path):
    path = tmp_path / "ledger.json"
    delegate.reserve_call(path, "p", 10.0, entry("a", sha="ha", charged=0.5), 0.5, 1.0)
    delegate.reserve_call(path, "p", 10.0, entry("b", sha="hb", charged=0.3), 0.3, 1.0)
    delegate.settle_call(path, "p", 10.0, "a", status="completed", charged_usd=0.4,
                         cost_basis="metered_estimate", receipt_path="ra")
    delegate.settle_call(path, "p", 10.0, "b", status="failed", charged_usd=0.0,
                         cost_basis="none", receipt_path="rb")

    ledger = load(path)
    assert ledger["pools"]["p"]["committed_usd"] == pytest.approx(0.4)
    assert delegate.pool_committed(ledger, "p") == pytest.approx(0.4)
    by_id = {c["run_id"]: c for c in ledger["calls"]}
    assert by_id["a"]["status"] == "completed" and by_id["a"]["cost_basis"] == "metered_estimate"
    assert by_id["b"]["status"] == "failed" and by_id["b"]["charged_usd"] == 0.0
    assert by_id["b"]["attempt"] == 2  # same pool, same task


def test_pool_budget_is_checked_under_the_lock(tmp_path):
    path = tmp_path / "ledger.json"
    delegate.reserve_call(path, "p", 1.0, entry("a", sha="ha", charged=0.8), 0.8, 1.0)
    with pytest.raises(SystemExit, match="exceed total budget"):
        delegate.reserve_call(path, "p", 1.0, entry("b", sha="hb", charged=0.5), 0.5, 1.0)
    # A different pool is not charged for pool p's spend.
    delegate.reserve_call(path, "q", 1.0, entry("c", pool="q", sha="hc", charged=0.5), 0.5, 1.0)


def test_task_ceiling_counts_the_same_plan_task(tmp_path):
    path = tmp_path / "ledger.json"
    delegate.reserve_call(path, "p", 10.0, entry("a", "draft", sha="ha", task_id="ADAPT-05"),
                          0.1, 1.0, task_cap_usd=0.25)
    with pytest.raises(SystemExit, match="exceed task budget"):
        delegate.reserve_call(path, "p", 10.0, entry("b", "review", sha="hb", task_id="ADAPT-05"),
                              0.2, 1.0, task_cap_usd=0.25)
    delegate.reserve_call(path, "p", 10.0, entry("c", "other", sha="hc", task_id="ADAPT-06"),
                          0.2, 1.0, task_cap_usd=0.25)


@pytest.mark.parametrize("status,age_s,message", [
    ("started", 5, "still in flight"),
    ("started", 10_000, "reconcile"),
    ("uncertain", 5, "reconcile"),
])
def test_identical_request_is_refused_until_its_outcome_is_known(tmp_path, status, age_s, message):
    path = tmp_path / "ledger.json"
    started = (datetime.now(timezone.utc) - timedelta(seconds=age_s)).isoformat().replace("+00:00", "Z")
    delegate.atomic_json(path, {"schema": 2, "pools": {"p": {"budget_usd": 10.0}},
                                "calls": [entry("old", sha="same", status=status, started_at=started)]})
    with pytest.raises(SystemExit, match=message):
        delegate.reserve_call(path, "q", 10.0, entry("new", pool="q", sha="same"), 0.1, 1.0)


@pytest.mark.parametrize("status", ["completed", "failed"])
def test_settled_identical_request_may_be_sent_again(tmp_path, status):
    path = tmp_path / "ledger.json"
    delegate.atomic_json(path, {"schema": 2, "pools": {"p": {"budget_usd": 10.0}},
                                "calls": [entry("old", sha="same", status=status)]})
    delegate.reserve_call(path, "p", 10.0, entry("new", sha="same"), 0.1, 1.0)


def test_a_ledger_in_a_missing_folder_is_created(tmp_path):
    """E2' A0: a fresh worktree has no tmp/deepinfra-delegation/ yet."""
    path = tmp_path / "fresh" / "tmp" / "deepinfra-delegation" / "ledger.json"
    delegate.reserve_call(path, "p", 1.0, entry("a", sha="ha"), 0.1, 1.0)
    assert load(path)["calls"][0]["run_id"] == "a"


def test_stale_lock_broken_fresh_lock_times_out(tmp_path):
    ledger_path = tmp_path / "ledger.json"
    lock_path = ledger_path.with_suffix(ledger_path.suffix + ".lock")
    lock_path.write_text("stale")
    stale_mtime = time.time() - 200
    os.utime(str(lock_path), (stale_mtime, stale_mtime))
    with delegate.ledger_lock(ledger_path, timeout=1):
        pass
    assert not lock_path.exists()

    lock_path.write_text("fresh")
    with pytest.raises(SystemExit, match="Could not acquire ledger lock"):
        with delegate.ledger_lock(ledger_path, timeout=0.1):
            pass
    lock_path.unlink(missing_ok=True)


# --- failure classification and rate cards ------------------------------------------

def _provider_error(cause):
    try:
        raise delegate.providers.ProviderError("failed") from cause
    except delegate.providers.ProviderError as exc:
        return exc


def test_failure_classification_charges_only_possible_provider_work():
    http = urllib.error.HTTPError("u", 400, "bad", {}, None)
    refused = urllib.error.URLError(ConnectionRefusedError())
    assert delegate.classify_failure(_provider_error(http), False) == "failed"
    assert delegate.classify_failure(_provider_error(refused), False) == "failed"
    assert delegate.classify_failure(_provider_error(TimeoutError()), False) == "uncertain"
    assert delegate.classify_failure(KeyboardInterrupt(), False) == "uncertain"
    assert delegate.classify_failure(delegate.providers.ProviderCancelledError(), False) == "uncertain"
    # Once the provider has answered, the money may be spent whatever failed afterwards.
    assert delegate.classify_failure(_provider_error(http), True) == "uncertain"


def test_rate_card_age_is_counted_in_days():
    assert delegate.rate_card_age_days({"as_of": "2026-10-01"}, date(2026, 10, 31)) == 30


def test_stale_rate_card_refuses_before_any_call(isolated, monkeypatch):
    calls = fake_provider(monkeypatch)
    monkeypatch.setitem(delegate.RATE_CARDS, MODEL,
                        {**delegate.RATE_CARDS[MODEL], "as_of": "2020-01-01"})
    args = run_args(isolated)
    monkeypatch.setattr(delegate, "parse_args", lambda argv=None: args)
    with pytest.raises(SystemExit, match="check-prices"):
        delegate.main()
    assert calls == [] and not args.ledger.exists()


# --- one run end to end -------------------------------------------------------------

def test_main_makes_exactly_one_request_and_keeps_request_and_response(isolated, monkeypatch):
    calls = fake_provider(monkeypatch)
    args = run_args(isolated, pool="claude", task_id="DELEG-01", role="drafter", parent_run="r0")
    monkeypatch.setattr(delegate, "parse_args", lambda argv=None: args)

    assert delegate.main() == 0
    assert len(calls) == 1

    ledger = load(args.ledger)
    (call,) = ledger["calls"]
    assert call["status"] == "completed" and call["cost_basis"] == "metered_estimate"
    assert (call["pool"], call["task_id"], call["role"], call["parent_run"]) == (
        "claude", "DELEG-01", "drafter", "r0")
    assert call["request_sha256"] == delegate.canonical_body_sha256(calls[0])
    receipt = load(call["receipt"])
    assert receipt["schema"] == 2 and receipt["truncated"] is False
    assert load(receipt["request_path"])["body"] == calls[0]
    assert load(receipt["response_path"])["body"]["usage"]["prompt_tokens"] == 10


def test_truncated_reply_exits_non_zero_unless_allowed(isolated, monkeypatch):
    reply = {"model": MODEL,
             "choices": [{"message": {"content": "partial"}, "finish_reason": "length"}],
             "usage": {"prompt_tokens": 10, "completion_tokens": 100}}
    fake_provider(monkeypatch, reply=reply)
    args = run_args(isolated)
    monkeypatch.setattr(delegate, "parse_args", lambda argv=None: args)
    assert delegate.main() == 3
    call = load(args.ledger)["calls"][0]
    assert call["status"] == "completed" and call["truncated"] is True

    args.allow_truncated = True
    args.instruction = "Hello again"  # a different request, so not a duplicate
    assert delegate.main() == 0


def test_definite_provider_rejection_costs_nothing(isolated, monkeypatch):
    error = _provider_error(urllib.error.HTTPError("u", 400, "bad", {}, None))
    fake_provider(monkeypatch, error=error)
    args = run_args(isolated)
    monkeypatch.setattr(delegate, "parse_args", lambda argv=None: args)
    with pytest.raises(delegate.providers.ProviderError):
        delegate.main()
    call = load(args.ledger)["calls"][0]
    assert (call["status"], call["charged_usd"], call["cost_basis"]) == ("failed", 0.0, "none")


def test_interrupted_call_keeps_its_reserve_and_blocks_a_repeat(isolated, monkeypatch):
    """E14 in miniature: an interrupt neither loses the charge nor repeats the call."""
    calls = fake_provider(monkeypatch, error=KeyboardInterrupt())
    args = run_args(isolated)
    monkeypatch.setattr(delegate, "parse_args", lambda argv=None: args)
    with pytest.raises(KeyboardInterrupt):
        delegate.main()
    call = load(args.ledger)["calls"][0]
    assert call["status"] == "uncertain"
    assert call["charged_usd"] == call["reserve_usd"] > 0

    with pytest.raises(SystemExit, match="reconcile"):
        delegate.main()
    assert len(calls) == 1

    # Nothing was saved, so the operator states the outcome; then a resend is allowed.
    assert ledger_tool.main(["reconcile", call["run_id"], "--outcome", "failed",
                             "--ledger", str(args.ledger)]) == 0
    fake_provider(monkeypatch)
    assert delegate.main() == 0


def test_crash_after_the_reply_is_reconciled_from_the_saved_response(isolated, monkeypatch):
    fake_provider(monkeypatch, reply={
        "model": MODEL, "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 500}})

    def disk_failure(path, value):  # a crash after the HTTP reply was saved
        raise OSError("disk full")

    monkeypatch.setattr(delegate, "atomic_text", disk_failure)
    args = run_args(isolated)
    monkeypatch.setattr(delegate, "parse_args", lambda argv=None: args)
    with pytest.raises(OSError):
        delegate.main()
    call = load(args.ledger)["calls"][0]
    assert call["status"] == "uncertain"

    assert ledger_tool.main(["reconcile", call["run_id"], "--outcome", "completed",
                             "--ledger", str(args.ledger)]) == 0
    call = load(args.ledger)["calls"][0]
    card = delegate.RATE_CARDS[MODEL]
    expected = (1000 * card["input_per_1m"] + 500 * card["output_per_1m"]) / 1_000_000
    assert call["status"] == "completed" and call["cost_basis"] == "metered_estimate"
    assert call["charged_usd"] == pytest.approx(expected)
    assert load(call["receipt"])["status"] == "completed"


def test_dry_run_writes_nothing(isolated, monkeypatch):
    calls = fake_provider(monkeypatch)
    args = run_args(isolated, dry_run=True)
    monkeypatch.setattr(delegate, "parse_args", lambda argv=None: args)
    assert delegate.main() == 0
    assert calls == [] and not args.ledger.exists() and not args.output_dir.exists()


# --- work-package admission (DELEG-03) ----------------------------------------------

def work_package(tmp_path, **budget):
    wp = json.loads((SCRIPTS.parent / "docs" / "examples" / "work-package-ADAPT-05.json")
                    .read_text(encoding="utf-8"))
    del wp["completion"]
    wp["admission"]["read_targets"] = ["module.py"]
    wp["admission"]["budget"].update({"pool": "shared", **budget})
    path = tmp_path / "wp.json"
    path.write_text(json.dumps(wp), encoding="utf-8")
    return path, wp


def test_a_work_package_binds_the_call_and_records_conformance(isolated, monkeypatch):
    (delegate.REPOSITORY / "module.py").write_text("x = 1\n", encoding="utf-8")
    calls = fake_provider(monkeypatch)
    path, wp = work_package(isolated)
    args = run_args(isolated, work_package=path, file=["module.py"])
    monkeypatch.setattr(delegate, "parse_args", lambda argv=None: args)

    assert delegate.main() == 0
    assert len(calls) == 1
    call = load(args.ledger)["calls"][0]
    assert call["task_id"] == "ADAPT-05"  # taken from the package
    receipt = load(call["receipt"])
    assert receipt["work_package"]["package_id"] == "ADAPT-05-wp1"
    assert receipt["work_package"]["sha256"] == delegate.sha256(path.read_bytes())
    assert receipt["work_package"]["conformance"]["present"] == 9
    assert args.task_budget_usd == wp["admission"]["budget"]["task_usd"]


def test_a_failing_package_is_refused_before_any_call(isolated, monkeypatch):
    calls = fake_provider(monkeypatch)
    path, wp = work_package(isolated)
    wp["admission"]["roles"]["reviewer_model"] = "deepseek-ai/DeepSeek-V4.1-Flash"
    path.write_text(json.dumps(wp), encoding="utf-8")
    args = run_args(isolated, work_package=path)
    monkeypatch.setattr(delegate, "parse_args", lambda argv=None: args)
    with pytest.raises(SystemExit, match="same model family"):
        delegate.main()
    assert calls == [] and not args.ledger.exists()


@pytest.mark.parametrize("overrides,message", [
    ({"file": ["other.py"]}, "outside the package's read and write targets"),
    ({"pool": "claude"}, "differs from the package's pool"),
    ({"task_id": "ADAPT-06"}, "differs from the package's"),
])
def test_a_call_outside_the_package_is_refused(isolated, monkeypatch, overrides, message):
    (delegate.REPOSITORY / "other.py").write_text("y = 1\n", encoding="utf-8")
    calls = fake_provider(monkeypatch)
    path, _ = work_package(isolated)
    args = run_args(isolated, work_package=path, **overrides)
    monkeypatch.setattr(delegate, "parse_args", lambda argv=None: args)
    with pytest.raises(SystemExit, match=message):
        delegate.main()
    assert calls == []


def test_exports_can_come_from_a_worktree_inside_the_repository(isolated, monkeypatch):
    worktree = delegate.REPOSITORY / "tmp" / "wt"
    worktree.mkdir(parents=True)
    (worktree / "module.py").write_text("x = 2\n", encoding="utf-8")
    calls = fake_provider(monkeypatch)
    path, _ = work_package(isolated)
    args = run_args(isolated, work_package=path, file=["module.py"], export_root=worktree)
    monkeypatch.setattr(delegate, "parse_args", lambda argv=None: args)
    assert delegate.main() == 0
    content = calls[0]["messages"][-1]["content"]
    assert '<file path="module.py">' in content and "x = 2" in content

    args.export_root = isolated  # the repository's parent: outside it
    args.instruction = "another request"
    with pytest.raises(SystemExit, match="--export-root must be inside the repository"):
        delegate.main()


def test_the_package_call_limit_escalates(isolated, monkeypatch):
    calls = fake_provider(monkeypatch)
    path, _ = work_package(isolated, max_calls=1)
    args = run_args(isolated, work_package=path)
    monkeypatch.setattr(delegate, "parse_args", lambda argv=None: args)
    assert delegate.main() == 0
    args.instruction = "A different request"
    with pytest.raises(SystemExit, match="task call limit"):
        delegate.main()
    assert len(calls) == 1


# --- ledger tool --------------------------------------------------------------------

def legacy_ledger(path, budget, calls):
    path.write_text(json.dumps({"schema": 1, "budget_usd": budget,
                                "committed_usd": sum(c["charged_usd"] for c in calls),
                                "calls": calls}), encoding="utf-8")


def test_migrate_merges_legacy_ledgers_into_pools_and_keeps_backups(tmp_path):
    shared = tmp_path / "ledger.json"
    claude = tmp_path / "claude-ledger.json"
    receipt = tmp_path / "r.receipt.json"
    receipt.write_text(json.dumps({"model": MODEL, "started_at": "2026-10-28T00:00:00Z",
                                   "preflight_reserve_usd": 0.01, "finish_reason": "length",
                                   "packet_sha256": "abc"}), encoding="utf-8")
    legacy_ledger(shared, 12.0, [
        {"run_id": "s1", "task": "a", "status": "completed", "charged_usd": 0.002,
         "receipt": str(receipt)},
        {"run_id": "s2", "task": "b", "status": "started", "charged_usd": 0.006},
    ])
    legacy_ledger(claude, 8.0, [
        {"run_id": "c1", "task": "c", "agent": "claude", "status": "failed", "charged_usd": 0.02},
    ])

    assert ledger_tool.main(["migrate", "--ledger", str(shared),
                             "--legacy", f"shared={shared}", "--legacy", f"claude={claude}"]) == 0

    ledger = load(shared)
    assert ledger["schema"] == 2
    assert ledger["pools"]["shared"]["budget_usd"] == 12.0
    assert ledger["pools"]["shared"]["committed_usd"] == pytest.approx(0.008)
    assert ledger["pools"]["claude"]["committed_usd"] == pytest.approx(0.02)
    by_id = {c["run_id"]: c for c in ledger["calls"]}
    assert by_id["s1"]["model"] == MODEL and by_id["s1"]["truncated"] is True
    assert by_id["s1"]["packet_sha256"] == "abc" and by_id["s1"]["request_sha256"] == ""
    assert (by_id["s2"]["status"], by_id["s2"]["cost_basis"]) == ("uncertain", "reserve")
    assert by_id["c1"]["cost_basis"] == "reserve"  # historical failed-call charge kept
    assert not claude.exists()
    assert load(tmp_path / "claude-ledger.json.schema1.json")["budget_usd"] == 8.0
    assert load(tmp_path / "ledger.json.schema1.json")["schema"] == 1

    with pytest.raises(SystemExit, match="already schema 2"):
        ledger_tool.main(["migrate", "--ledger", str(shared), "--legacy", f"x={claude}"])


def test_import_replaces_a_lump_entry_only_when_totals_agree(tmp_path):
    path = tmp_path / "ledger.json"
    delegate.atomic_json(path, {"schema": 2, "pools": {"claude": {"budget_usd": 8.0}}, "calls": [
        {**entry("scratchpad-import", pool="claude", status="completed", charged=0.03)}]})
    source = tmp_path / "scratch.json"
    records = [{"task": "A", "model": MODEL, "prompt_tokens": 1, "completion_tokens": 2,
                "cost": 0.01, "secs": 1, "finish": "stop", "out": "a.md"},
               {"task": "B", "model": MODEL, "prompt_tokens": 1, "completion_tokens": 2,
                "cost": 0.02, "secs": 1, "finish": "length", "out": "b.md"}]
    source.write_text(json.dumps(records), encoding="utf-8")
    base = ["import-calls", "--ledger", str(path), "--pool", "claude",
            "--kind", "scratchpad-ledger", "--source", str(source)]

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(records[:1]), encoding="utf-8")
    with pytest.raises(SystemExit, match="does not match"):
        ledger_tool.main(base[:-1] + [str(bad), "--replace-run-id", "scratchpad-import"])

    assert ledger_tool.main(base + ["--replace-run-id", "scratchpad-import"]) == 0
    ledger = load(path)
    assert [c["task"] for c in ledger["calls"]] == ["A", "B"]
    assert ledger["pools"]["claude"]["committed_usd"] == pytest.approx(0.03)
    assert all(c["cost_basis"] == "imported_estimate" and c["imported_from"] for c in ledger["calls"])
    assert ledger["calls"][1]["truncated"] is True

    assert ledger_tool.main(base) == 0  # idempotent
    assert len(load(path)["calls"]) == 2


def test_import_prices_scratchpad_logs_and_needs_a_budget_for_a_new_pool(tmp_path):
    path = tmp_path / "ledger.json"
    delegate.atomic_json(path, {"schema": 2, "pools": {}, "calls": []})
    logs = tmp_path / "out"
    logs.mkdir()
    (logs / "paper_a.log").write_text(json.dumps(
        {"model": MODEL, "secs": 3, "prompt_tokens": 1_000_000, "completion_tokens": 1_000_000,
         "finish": "stop", "out": "paper_a.md"}) + "\nmore\n", encoding="utf-8")
    (logs / "broken.log").write_text("not json\n", encoding="utf-8")
    base = ["import-calls", "--ledger", str(path), "--pool", "claude",
            "--kind", "scratchpad-logs", "--source", str(logs)]

    with pytest.raises(SystemExit, match="no --budget"):
        ledger_tool.main(base)
    assert ledger_tool.main(base + ["--budget", "8"]) == 0
    (call,) = load(path)["calls"]
    card = delegate.RATE_CARDS[MODEL]
    assert call["task"] == "paper_a"
    assert call["charged_usd"] == pytest.approx(card["input_per_1m"] + card["output_per_1m"])


def test_import_runner_ledger_keeps_run_ids(tmp_path):
    path = tmp_path / "ledger.json"
    delegate.atomic_json(path, {"schema": 2, "pools": {}, "calls": []})
    source = tmp_path / "overseer.json"
    legacy_ledger(source, 5.0, [{"run_id": "o1", "task": "x", "status": "completed",
                                 "charged_usd": 0.03}])
    assert ledger_tool.main(["import-calls", "--ledger", str(path), "--pool", "codex-overseer",
                             "--budget", "5", "--kind", "runner-ledger",
                             "--source", str(source)]) == 0
    (call,) = load(path)["calls"]
    assert call["run_id"] == "o1" and call["imported_from"]


def test_acceptance_is_recorded_with_history_and_only_for_completed_runs(tmp_path):
    path = tmp_path / "ledger.json"
    delegate.atomic_json(path, {"schema": 2, "pools": {"p": {"budget_usd": 1.0}}, "calls": [
        entry("done", status="completed"), entry("open", sha="h2")]})
    base = ["accept", "--ledger", str(path)]
    with pytest.raises(SystemExit, match="only 'completed'"):
        ledger_tool.main(base + ["open", "--state", "accepted"])

    ledger_tool.main(base + ["done", "--state", "partial", "--by", "claude"])
    ledger_tool.main(base + ["done", "--state", "accepted", "--commit", "abc1234", "--by", "claude"])
    call = {c["run_id"]: c for c in load(path)["calls"]}["done"]
    assert (call["acceptance"], call["acceptance_commit"]) == ("accepted", "abc1234")
    assert [h["state"] for h in call["acceptance_history"]] == ["partial"]


def test_summary_lists_open_runs(tmp_path, capsys):
    path = tmp_path / "ledger.json"
    delegate.atomic_json(path, {"schema": 2, "pools": {"p": {"budget_usd": 1.0}}, "calls": [
        entry("done", status="completed", charged=0.2), entry("open", sha="h2", status="uncertain")]})
    assert ledger_tool.main(["summary", "--ledger", str(path), "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)["p"]
    assert summary["committed_usd"] == pytest.approx(0.3)
    assert [r["run_id"] for r in summary["open_runs"]] == ["open"]


def test_check_prices_reports_stale_and_unlisted_cards(monkeypatch, capsys):
    cards = {"a/live": {"input_per_1m": 1.0, "output_per_1m": 2.0},
             "b/stale": {"input_per_1m": 1.0, "output_per_1m": 2.0},
             "c/gone": {"input_per_1m": 1.0, "output_per_1m": 2.0}}
    monkeypatch.setattr(delegate, "RATE_CARDS", cards)
    listing = {"data": [
        {"id": "a/live", "metadata": {"pricing": {"input_tokens": 1.0, "output_tokens": 2.0}}},
        {"id": "b/stale", "metadata": {"pricing": {"input_tokens": 1.0, "output_tokens": 4.0}}},
    ]}
    monkeypatch.setattr(ledger_tool, "fetch_listing", lambda url: listing)
    assert ledger_tool.main(["check-prices"]) == 1
    out = capsys.readouterr().out
    assert "VERIFIED: a/live" in out and "STALE: b/stale" in out and "NOT LISTED: c/gone" in out
    del listing["data"][1]
    monkeypatch.setattr(delegate, "RATE_CARDS", {"a/live": cards["a/live"]})
    assert ledger_tool.main(["check-prices"]) == 0
