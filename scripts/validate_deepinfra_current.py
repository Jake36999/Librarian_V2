#!/usr/bin/env python
"""Run a bounded live DeepInfra delta validation against the current Core.

This is deliberately *not* a replacement for the release L3 qualification
suite.  It verifies the current, remediated runtime with real provider calls
while keeping both cost and state bounded:

* the API key stays only in this child process's environment;
* every case uses a newly initialised temporary vault and Core lease;
* all model-facing work goes through ``App`` and the host registry;
* requests are metered without retaining headers, prompts, or response text;
* a conservative estimated-cost cap stops new chat requests before spend;
* model discovery and schema-derived local fixtures must pass before the
  harness attributes a result to a model.

The JSON artifact is intentionally detailed enough for a reviewer to separate
provider availability, tool-call conformance, and agent/workflow behaviour.
It never claims a route has earned verified-release or verified-local status.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import shutil
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from resource_librarian import providers
from resource_librarian.app import App, ApiError
from resource_librarian.coordination import atomic_write_text
from resource_librarian.init import init
from resource_librarian.keys import KeyStore
from resource_librarian.providers import OpenAICompatible, ProviderError
from resource_librarian.session import SessionStore
from resource_librarian.validation_fixtures import (
    preflight_validation_source_fixture,
    write_validation_source_fixture,
)
from resource_librarian.vault import Vault


DEFAULT_MODELS = (
    "XiaomiMiMo/MiMo-V2.6-Flash",
    "deepseek-ai/DeepSeek-V4.1-Flash",
    "zai-org/GLM-5.3-Flash",
)

# Dated, transparent planning rates, not invoice data.  The report links to
# their official DeepInfra source and labels all costs as estimates.  An
# unpriced model is deliberately refused while a spend cap is active: silently
# excluding it would turn a stated cap into an unbounded paid experiment.
RATE_CARDS: dict[str, dict[str, Any]] = {
    "XiaomiMiMo/MiMo-V2.6-Flash": {
        "input_per_1m": 0.133,
        "output_per_1m": 0.266,
        "source": "https://deepinfra.com/XiaomiMiMo/MiMo-V2.6-Flash/api",
        "as_of": "2026-10-22",
    },
    "deepseek-ai/DeepSeek-V4.1-Flash": {
        "input_per_1m": 0.14,
        "output_per_1m": 0.42,
        "source": "https://deepinfra.com/blog/deepseek-v4-1-flash-model-overview-integration",
        "as_of": "2026-10-22",
    },
    "zai-org/GLM-5.3-Flash": {
        "input_per_1m": 0.075,
        "output_per_1m": 0.25,
        "source": "https://deepinfra.com/blog/glm-5-3-flash-documentation-integration-guide",
        "as_of": "2026-10-22",
    },
}


class BudgetStop(ProviderError):
    """Raised before a new paid request would exceed the local test cap."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_size_tokens(value: Any) -> int:
    """Conservative, provider-agnostic preflight token approximation."""
    try:
        encoded = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        encoded = repr(value)
    return max(1, math.ceil(len(encoded) / 3.5))


def _quantile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def _redacted_tool_calls(response: dict[str, Any]) -> tuple[list[str], bool | None]:
    """Return only function names plus the L1 probe argument verdict."""
    choice = (response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    names: list[str] = []
    probe_ok: bool | None = None
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        name = str(function.get("name") or "")
        if name:
            names.append(name)
        if name == "librarian_probe":
            try:
                args = json.loads(function.get("arguments") or "{}")
            except (TypeError, ValueError):
                args = None
            probe_ok = bool(isinstance(args, dict) and args.get("ok") is True and len(args) == 1)
    return names, probe_ok


class RequestMeter:
    """Temporarily intercept DeepInfra JSON responses for redacted telemetry."""

    def __init__(self, cap_usd: float) -> None:
        self.cap_usd = max(0.0, float(cap_usd))
        self.records: list[dict[str, Any]] = []
        self.actual_cost_usd = 0.0
        # Amount already committed against the cap.  A response without usage
        # is charged its preflight reserve, and a failed request remains
        # charged because a timeout can still have reached the provider.
        self.budget_committed_usd = 0.0
        self._original: Callable[..., dict[str, Any]] | None = None
        self._context: dict[str, Any] = {"case": "setup"}

    def set_context(self, **context: Any) -> None:
        self._context = {key: value for key, value in context.items() if value not in (None, "")}

    def __enter__(self) -> "RequestMeter":
        self._original = providers._request

        def metered(method: str, url: str, headers: dict[str, str], body: Any = None,
                    timeout: float = 120, sleep: Any = None) -> dict[str, Any]:
            is_deepinfra = "api.deepinfra.com" in url
            model = str(body.get("model") or "") if isinstance(body, dict) else ""
            card = RATE_CARDS.get(model)
            estimate_reserve = 0.0
            is_paid_chat = is_deepinfra and method.upper() == "POST"
            if is_paid_chat and card:
                max_tokens = max(0, int(body.get("max_tokens") or 0))
                prompt_guess = _json_size_tokens(body)
                estimate_reserve = ((prompt_guess * float(card["input_per_1m"]) +
                                    max_tokens * float(card["output_per_1m"])) / 1_000_000)
            if is_paid_chat and self.cap_usd and not card:
                raise BudgetStop(
                    f"validation budget cap cannot price {model or 'the selected model'}; "
                    "add a reviewed rate card or explicitly rerun with --cap-usd 0"
                )
            if is_paid_chat and self.cap_usd and self.budget_committed_usd + estimate_reserve > self.cap_usd:
                    raise BudgetStop(
                        f"validation budget cap ${self.cap_usd:.4f} would be exceeded by a "
                        f"conservative next-call reserve of ${estimate_reserve:.4f}"
                    )
            # Commit before the request.  It is intentionally not released on
            # a provider error: a network timeout is not proof that inference
            # did not begin or bill.
            if is_paid_chat and card:
                self.budget_committed_usd += estimate_reserve
            started = time.perf_counter()
            base = {
                **self._context,
                "request_index": len(self.records) + 1,
                "method": method.upper(),
                "endpoint": "/chat/completions" if "/chat/completions" in url else "/models",
                "model_requested": model,
                "tool_count": len(body.get("tools") or []) if isinstance(body, dict) else 0,
                "max_tokens": int(body.get("max_tokens") or 0) if isinstance(body, dict) else 0,
                "estimated_preflight_reserve_usd": round(estimate_reserve, 8),
                "budget_charge_usd": round(estimate_reserve, 8),
                "budget_committed_usd": round(self.budget_committed_usd, 8),
            }
            try:
                assert self._original is not None
                response = self._original(method, url, headers, body, timeout, sleep)
            except Exception as exc:  # the provider layer later renders the safe public error
                self.records.append({**base, "ok": False,
                                     "latency_ms": round((time.perf_counter() - started) * 1000),
                                     "error_class": type(exc).__name__, "error": str(exc)[:300]})
                raise
            usage = response.get("usage") if isinstance(response, dict) else {}
            usage = usage if isinstance(usage, dict) else {}
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            try:
                prompt_tokens = int(prompt_tokens) if prompt_tokens is not None else None
            except (TypeError, ValueError):
                prompt_tokens = None
            try:
                completion_tokens = int(completion_tokens) if completion_tokens is not None else None
            except (TypeError, ValueError):
                completion_tokens = None
            cost = None
            if card and prompt_tokens is not None and completion_tokens is not None:
                cost = ((prompt_tokens * float(card["input_per_1m"]) +
                         completion_tokens * float(card["output_per_1m"])) / 1_000_000)
                self.actual_cost_usd += cost
                # Replace this request's conservative reservation with the
                # provider's actual token-based estimate.  If no usage is
                # returned, the reservation remains in force.
                if is_paid_chat:
                    self.budget_committed_usd += cost - estimate_reserve
            tool_calls, probe_schema_ok = _redacted_tool_calls(response) if isinstance(response, dict) else ([], None)
            choice = ((response.get("choices") or [{}])[0] if isinstance(response, dict) else {})
            self.records.append({
                **base,
                "ok": True,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "model_returned": str(response.get("model") or "") if isinstance(response, dict) else "",
                "finish_reason": str(choice.get("finish_reason") or ""),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": usage.get("total_tokens"),
                "usage_present": bool(usage),
                "estimated_cost_usd": round(cost, 8) if cost is not None else None,
                "tool_calls": tool_calls,
                "l1_probe_schema_ok": probe_schema_ok,
            })
            return response

        providers._request = metered
        return self

    def __exit__(self, *_: Any) -> None:
        if self._original is not None:
            providers._request = self._original


def _load_key_from_file(path: Path) -> bool:
    """Copy a key from a known user-owned file into this process only.

    Nothing logs the value, and the temporary config directory prevents
    KeyStore from turning the inherited key into a new persistent credential.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "DEEPINFRA_API_KEY" and value.strip():
            os.environ["DEEPINFRA_API_KEY"] = value.strip().strip('"').strip("'")
            return True
    return False


def provision_key(key_file: str) -> str:
    if os.environ.get("DEEPINFRA_API_KEY"):
        return "environment"
    candidates = [Path(key_file)] if key_file else [Path(r"D:\Resource-Library\.utility\.env")]
    for candidate in candidates:
        if candidate.is_file() and _load_key_from_file(candidate):
            return "transient file injection"
    raise SystemExit(
        "DEEPINFRA_API_KEY is not available. Supply it through the process environment "
        "or pass --key-file to a user-owned dotenv file. No provider call was made."
    )


@contextlib.contextmanager
def scratch_app(scratch_root: Path, label: str) -> Iterator[tuple[App, Path]]:
    root = scratch_root / label
    init(root, name=f"DeepInfra validation {label}")
    app = App(Vault(root), keys=KeyStore(use_keyring=False), coordinate=True)
    try:
        yield app, root
    finally:
        app.close_runtime()


def write_source_fixture(root: Path, app: App) -> dict[str, Any]:
    """Create and preflight a local-only fixture before a model can see it."""
    vault = Vault(root)
    fixture = write_validation_source_fixture(vault, kind="page")
    return preflight_validation_source_fixture(vault, fixture, app.index_service)


def _safe_value(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


class Validation:
    def __init__(self, *, scratch_root: Path, meter: RequestMeter, l1_repeats: int,
                 host_timeout: int, on_case: Callable[[], None] | None = None) -> None:
        self.scratch_root = scratch_root
        self.meter = meter
        self.l1_repeats = l1_repeats
        self.host_timeout = host_timeout
        self.on_case = on_case
        self.cases: list[dict[str, Any]] = []
        self._counter = 0

    def _prepare(self, app: App) -> None:
        """Use the supported per-host timeout control in the temporary registry."""
        current = next((row for row in app.host_list().get("hosts") or []
                        if row.get("id") == "preset-deepinfra"), None)
        if not isinstance(current, dict):
            raise RuntimeError("the seeded DeepInfra host is unavailable in this Core")
        # ``host_upsert`` deliberately validates a complete Host record before
        # merging seeded settings.  Preserve that public identity and alter
        # only the transient host controls in this temporary config root.
        app.host_upsert({**current, "timeout": self.host_timeout, "concurrency_limit": 1})

    def case(self, model: str, name: str, run: int,
             action: Callable[[], tuple[bool, dict[str, Any]]]) -> dict[str, Any]:
        self._counter += 1
        case_id = f"{model.replace('/', '--').replace('.', '-')}-{name}-{run}-{self._counter}"
        start_index = len(self.meter.records)
        started = time.perf_counter()
        self.meter.set_context(case_id=case_id, model=model, test=name, run=run)
        try:
            passed, detail = action()
            status = "pass" if passed else "fail"
        except BudgetStop as exc:
            status, passed, detail = "budget_stopped", False, {"error": str(exc)}
        except Exception as exc:  # retain category only; raw provider messages stay redacted
            status, passed, detail = "harness_error", False, {
                "error_class": type(exc).__name__, "error": str(exc)[:500],
            }
        request_records = self.meter.records[start_index:]
        provider_failures = [row for row in request_records if not row.get("ok")]
        if status == "fail" and provider_failures:
            classification = "provider_or_transport"
        elif status == "fail":
            classification = "agent_or_workflow"
        elif status == "budget_stopped":
            classification = "budget_guard"
        elif status == "harness_error":
            # A setup/fixture error before a request cannot establish
            # anything about the model. Preserve the distinct case where a
            # harness exception followed a successful provider response too.
            classification = ("provider_or_transport" if provider_failures else
                              "harness_after_provider" if request_records else
                              "local_setup")
        else:
            classification = "pass"
        row = {
            "id": case_id,
            "model": model,
            "test": name,
            "run": run,
            "status": status,
            "classification": classification,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "provider_request_indices": [entry["request_index"] for entry in request_records],
            "provider_requests": len(request_records),
            "provider_failures": len(provider_failures),
            "detail": detail,
        }
        self.cases.append(row)
        print(f"[{row['status']}] {name} {model} run {run}: {row['duration_ms']} ms", flush=True)
        if self.on_case is not None:
            self.on_case()
        return row

    def l1_probe(self, model: str, run: int) -> tuple[bool, dict[str, Any]]:
        label = f"l1-{model.replace('/', '--').replace('.', '-')}-{run}"
        with scratch_app(self.scratch_root, label) as (app, _root):
            self._prepare(app)
            result = app.run_qualification("preset-deepinfra", model, "lead", "L1",
                                           confirm_spend=True,
                                           scenario=f"current-delta-l1-{run}")
        run_result = dict(result.get("run") or {})
        l1_requests = [entry for entry in self.meter.records if entry.get("test") == "l1_probe" and
                       entry.get("run") == run and entry.get("model") == model]
        schema = next((entry.get("l1_probe_schema_ok") for entry in reversed(l1_requests)
                       if entry.get("l1_probe_schema_ok") is not None), None)
        # The current Core L1 contract is strict: exact call count/name/args
        # and the provider-returned model identity must all be present.  Keep
        # the redacted wire observation as diagnostic evidence, but do not
        # allow a name-only historical result to count as a pass.
        probe_validation = run_result.get("probe_validation")
        strict_contract_ok = bool(isinstance(probe_validation, dict) and
                                  probe_validation.get("passed") is True)
        passed = bool(run_result.get("outcome") == "pass" and strict_contract_ok)
        return passed, {
            "core_l1_outcome": run_result.get("outcome"),
            "core_l1_detail": run_result.get("detail"),
            "observed_model": run_result.get("observed_model"),
            "core_duration_ms": run_result.get("duration_ms"),
            "strict_probe_arguments_ok": schema,
            "strict_probe_contract_ok": strict_contract_ok,
            "strict_probe_failure_codes": (
                list(probe_validation.get("failure_codes") or [])
                if isinstance(probe_validation, dict) else ["missing_probe_validation"]
            ),
            "qualification_status_after": result.get("status"),
        }

    def project_session_walk(self, model: str) -> tuple[bool, dict[str, Any]]:
        label = f"project-{model.replace('/', '--').replace('.', '-')}"
        project = "Validation Project"
        with scratch_app(self.scratch_root, label) as (app, root):
            self._prepare(app)
            app.set_mode("auto")
            app.set_effort(1)
            app.set_tiers([{"host_id": "preset-deepinfra", "model": model}],
                          override="current-system live validation in a disposable vault")
            loop = app._loop()
            turn = loop.send(
                "This is a disposable validation vault. Complete this bounded task without web search: "
                f"open an add_project session and create exactly one project named {project!r}, "
                "with stage planning and summary 'Synthetic current-system validation project.' "
                "Then advance the session exactly once to ingest and stop. Do not ingest a source, "
                "create another note, ask a person, or make any other change."
            )
            session = SessionStore(Vault(root)).load(loop.ctx.session) if loop.ctx.session else None
            note_exists = (root / "Projects" / f"{project}.md").is_file()
            tools = [str(call.get("tool") or "") for call in turn.calls]
            passed = bool(note_exists and session and session.purpose == "add_project" and
                          session.phase == "ingest" and "open_session" in tools and
                          "create_project" in tools and "advance" in tools)
            return passed, {
                "turn_steps": turn.steps,
                "turn_stopped": turn.stopped,
                "turn_error": turn.error,
                "tool_calls": tools,
                "project_note_exists": note_exists,
                "session_purpose": session.purpose if session else "",
                "session_phase": session.phase if session else "",
                "reply_excerpt": (turn.reply or "")[:300],
                "interpretation": (
                    "This checks the combined lead workflow and compact tool-surface sequence. "
                    "A failure is not automatically attributed to the model."
                ),
            }

    def grounded_read_walk(self, model: str) -> tuple[bool, dict[str, Any]]:
        label = f"grounded-{model.replace('/', '--').replace('.', '-')}"
        with scratch_app(self.scratch_root, label) as (app, root):
            self._prepare(app)
            write_source_fixture(root, app)
            app.set_mode("auto")
            app.set_effort(1)
            app.set_tiers([{"host_id": "preset-deepinfra", "model": model}],
                          override="current-system live validation in a disposable vault")
            app.run_qualification("preset-deepinfra", model, "research_helper", "L1",
                                  confirm_spend=True, scenario="current-delta-helper-l1")
            app.set_agent_profile("research_helper")
            loop = app._loop()
            turn = loop.send(
                "Use only the current vault. Find the source titled Validation Evidence and determine "
                "its unique validation marker. You must use the available read tools to locate and inspect "
                "the source before answering. Reply with the exact marker only. Do not create, edit, stage, "
                "or ingest anything."
            )
            tools = [str(call.get("tool") or "") for call in turn.calls]
            writes = {"create_project", "ingest", "queue_source", "record_synthesis", "draft_offering",
                      "macro_run", "note_move", "staging_decide"}
            passes_grounding = "ORCHID-47" in (turn.reply or "")
            used_read = bool(set(tools) & {"search", "get_note", "read_source_file"})
            no_write = not bool(set(tools) & writes)
            passed = bool(passes_grounding and used_read and no_write and not turn.error)
            return passed, {
                "turn_steps": turn.steps,
                "turn_stopped": turn.stopped,
                "turn_error": turn.error,
                "tool_calls": tools,
                "marker_returned": "ORCHID-47" in (turn.reply or ""),
                "used_grounding_read": used_read,
                "no_write_tool": no_write,
                "reply_excerpt": (turn.reply or "")[:300],
            }

    def macro_checkpoint_walk(self, model: str) -> tuple[bool, dict[str, Any]]:
        label = f"macro-{model.replace('/', '--').replace('.', '-')}"
        with scratch_app(self.scratch_root, label) as (app, root):
            self._prepare(app)
            write_source_fixture(root, app)
            app.set_mode("auto")
            app.set_effort(1)
            app.set_tiers([{"host_id": "preset-deepinfra", "model": model}],
                          override="current-system live validation in a disposable vault")
            loop = app._loop()
            turn = loop.send(
                "Use the audited inspect_map_source macro for the catalogued source named Validation Evidence. "
                "Show its plan, then begin it. Stop as soon as a person approval is required. Do not resolve "
                "or bypass any checkpoint, and do not take another action after the checkpoint."
            )
            tools = [str(call.get("tool") or "") for call in turn.calls]
            checkpoints = app.checkpoint_list(pending_only=True).get("checkpoints") or []
            macro_rows = [row for row in checkpoints if row.get("type") == "macro_expansion"]
            source_map = list((root / ".librarian" / "derived").rglob("*"))
            # The Core trace exposes macro_run only; a paused macro must not
            # run the contained dik_rebuild before approval.
            no_underlying_write = "dik_rebuild" not in tools and not any(
                path.is_file() and "Validation Evidence" in path.name for path in source_map
            )
            passed = bool("macro_plan" in tools and "macro_run" in tools and macro_rows and
                          no_underlying_write and not turn.error)
            return passed, {
                "turn_steps": turn.steps,
                "turn_stopped": turn.stopped,
                "turn_error": turn.error,
                "tool_calls": tools,
                "pending_macro_expansion_checkpoints": len(macro_rows),
                "no_underlying_write_before_approval": no_underlying_write,
                "reply_excerpt": (turn.reply or "")[:300],
            }


def _source_hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _summary(cases: list[dict[str, Any]], requests: list[dict[str, Any]]) -> dict[str, Any]:
    good = [row for row in cases if row["status"] == "pass"]
    latencies = [float(row["latency_ms"]) for row in requests
                 if row.get("ok") and row.get("endpoint") == "/chat/completions"]
    prompt_tokens = sum(int(row.get("prompt_tokens") or 0) for row in requests)
    completion_tokens = sum(int(row.get("completion_tokens") or 0) for row in requests)
    estimated_cost = sum(float(row.get("estimated_cost_usd") or 0) for row in requests)
    per_model: dict[str, dict[str, Any]] = {}
    for model in sorted({row["model"] for row in cases}):
        subset = [row for row in cases if row["model"] == model]
        reqs = [row for row in requests if row.get("model") == model and row.get("endpoint") == "/chat/completions"]
        per_model[model] = {
            "cases_passed": sum(row["status"] == "pass" for row in subset),
            "cases_total": len(subset),
            "l1_name_conformant": sum(row["status"] == "pass" for row in subset if row["test"] == "l1_probe"),
            "l1_total": sum(row["test"] == "l1_probe" for row in subset),
            "strict_l1_arguments_ok": sum(
                row["status"] == "pass" and row.get("detail", {}).get("strict_probe_arguments_ok") is True
                for row in subset if row["test"] == "l1_probe"
            ),
            "strict_l1_contract_ok": sum(
                row["status"] == "pass" and row.get("detail", {}).get("strict_probe_contract_ok") is True
                for row in subset if row["test"] == "l1_probe"
            ),
            "agent_walks_passed": sum(row["status"] == "pass" for row in subset if row["test"] != "l1_probe"),
            "agent_walks_total": sum(row["test"] != "l1_probe" for row in subset),
            "provider_requests": len(reqs),
            "provider_failures": sum(not row.get("ok") for row in reqs),
            "chat_latency_p50_ms": _quantile([float(row["latency_ms"]) for row in reqs if row.get("ok")], .5),
            "chat_latency_p95_ms": _quantile([float(row["latency_ms"]) for row in reqs if row.get("ok")], .95),
            "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in reqs),
            "completion_tokens": sum(int(row.get("completion_tokens") or 0) for row in reqs),
            "estimated_cost_usd": round(sum(float(row.get("estimated_cost_usd") or 0) for row in reqs), 8),
        }
    return {
        "cases_passed": len(good),
        "cases_total": len(cases),
        "case_pass_rate": round(len(good) / len(cases), 4) if cases else 0.0,
        "provider_requests": len(requests),
        "provider_failures": sum(not row.get("ok") for row in requests),
        "chat_requests": len(latencies),
        "chat_latency_p50_ms": _quantile(latencies, .5),
        "chat_latency_p95_ms": _quantile(latencies, .95),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "usage_coverage": round(sum(bool(row.get("usage_present")) for row in requests) / len(requests), 4)
        if requests else 0.0,
        "estimated_cost_usd": round(estimated_cost, 8),
        "by_model": per_model,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="*", default=list(DEFAULT_MODELS),
                        help="Exact DeepInfra model ids (defaults to focused historical candidates).")
    parser.add_argument("--l1-repeats", type=int, default=3,
                        help="Repeated current-Core L1 probes per available model (default: 3).")
    parser.add_argument("--cap-usd", type=float, default=1.00,
                        help="Conservative estimated spend ceiling; 0 disables it (default: 1.00).")
    parser.add_argument("--allow-without-discovery", action="store_true",
                        help="Run paid model cases even when model discovery failed (deliberate diagnostic override).")
    parser.add_argument("--host-timeout", type=int, default=15,
                        help="Temporary HostRegistry request timeout in seconds (default: 15).")
    parser.add_argument("--tests", nargs="+", default=["l1", "project", "grounded", "macro"],
                        choices=["l1", "project", "grounded", "macro"],
                        help="Logical cases to run (default: all four).")
    parser.add_argument("--key-file", default="",
                        help="Optional dotenv path used only to populate this process's environment.")
    parser.add_argument("--output", type=Path,
                        default=Path("reports/2026-10-22-deepinfra-current-system-validation.json"),
                        help="Machine-readable artifact path.")
    parser.add_argument("--keep-scratch", action="store_true",
                        help="Keep disposable vaults for local debugging (never enabled in normal runs).")
    args = parser.parse_args()
    if args.l1_repeats < 1:
        parser.error("--l1-repeats must be at least 1")
    if args.cap_usd < 0:
        parser.error("--cap-usd cannot be negative")
    if args.host_timeout < 1:
        parser.error("--host-timeout must be at least 1")

    credential_source = provision_key(args.key_file)
    started_at = _utc_now()
    work = Path(tempfile.mkdtemp(prefix="librarian-deepinfra-validation-"))
    config = work / "config"
    old_config = os.environ.get("LIBRARIAN_CONFIG_DIR")
    os.environ["LIBRARIAN_CONFIG_DIR"] = str(config)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "title": "Librarian V2 current-system DeepInfra delta validation",
        "started_at": started_at,
        "ended_at": "",
        "scope": {
            "live_provider": "DeepInfra OpenAI-compatible API",
            "credential_source": credential_source,
            "cap_usd": args.cap_usd,
            "host_timeout_seconds": args.host_timeout,
            "l1_repeats": args.l1_repeats,
            "tests": args.tests,
            "fixtures": "local disposable Markdown only; no web search or user-vault writes",
            "qualification_claim": (
                "This is an L1 plus focused agent-walk validation. It does not grant verified_local "
                "or verified_release status, and L2/L3 remain artifact-backed qualification work."
            ),
            "discovery_policy": (
                "Model-specific paid cases are skipped after failed discovery unless "
                "--allow-without-discovery is explicitly supplied."
            ),
        },
        "rate_cards": RATE_CARDS,
        "availability": {},
        "cases": [],
        "provider_requests": [],
        "summary": {},
        "environment": {
            "python": sys.version.split()[0],
            "script_sha256": _source_hash(Path(__file__)),
            "app_sha256": _source_hash(Path(__file__).resolve().parents[1] / "src" / "resource_librarian" / "app.py"),
            "loop_sha256": _source_hash(Path(__file__).resolve().parents[1] / "src" / "resource_librarian" / "loop.py"),
            "agent_runtime_sha256": _source_hash(Path(__file__).resolve().parents[1] / "src" / "resource_librarian" / "agent_runtime.py"),
        },
    }

    def checkpoint(validation: Validation | None = None, meter: RequestMeter | None = None) -> None:
        """Persist partial, redacted evidence after every completed logical case."""
        if validation is not None:
            artifact["cases"] = validation.cases
        if meter is not None:
            artifact["provider_requests"] = meter.records
            artifact["summary"] = _summary(artifact["cases"], meter.records)
            artifact["summary"]["meter_actual_estimated_cost_usd"] = round(meter.actual_cost_usd, 8)
            artifact["summary"]["meter_budget_committed_usd"] = round(meter.budget_committed_usd, 8)
        artifact["ended_at"] = _utc_now()
        atomic_write_text(args.output, json.dumps(artifact, indent=2, ensure_ascii=False,
                                                  default=_safe_value) + "\n")

    try:
        with RequestMeter(args.cap_usd) as meter:
            meter.set_context(case_id="model-discovery", test="model_discovery")
            listing_provider = OpenAICompatible(
                providers.PRESETS["deepinfra"]["base_url"],
                key_env="DEEPINFRA_API_KEY", name="deepinfra", timeout=args.host_timeout,
            )
            try:
                live_models = set(listing_provider.models())
                artifact["availability"] = {
                    "listing_ok": True,
                    "model_count": len(live_models),
                    "candidates": {model: model in live_models for model in args.models},
                }
            except ProviderError as exc:
                artifact["availability"] = {
                    "listing_ok": False,
                    "error": str(exc)[:500],
                    "model_cases_skipped": not args.allow_without_discovery,
                    "skip_reason": ("model_discovery_unavailable"
                                    if not args.allow_without_discovery else ""),
                }
                live_models = set()

            validation = Validation(scratch_root=work / "vaults", meter=meter,
                                    l1_repeats=args.l1_repeats,
                                    host_timeout=args.host_timeout,
                                    on_case=lambda: checkpoint(validation, meter))
            checkpoint(validation, meter)
            if artifact["availability"].get("listing_ok") or args.allow_without_discovery:
                for model in args.models:
                    if live_models and model not in live_models:
                        continue
                    if "l1" in args.tests:
                        for run in range(1, args.l1_repeats + 1):
                            validation.case(model, "l1_probe", run,
                                            lambda model=model, run=run: validation.l1_probe(model, run))
                    if "project" in args.tests:
                        validation.case(model, "project_session_walk", 1,
                                        lambda model=model: validation.project_session_walk(model))
                    if "grounded" in args.tests:
                        validation.case(model, "grounded_read_walk", 1,
                                        lambda model=model: validation.grounded_read_walk(model))
                    if "macro" in args.tests:
                        validation.case(model, "macro_checkpoint_walk", 1,
                                        lambda model=model: validation.macro_checkpoint_walk(model))
                    if meter.cap_usd and meter.budget_committed_usd >= meter.cap_usd:
                        break
            artifact["cases"] = validation.cases
            artifact["provider_requests"] = meter.records
            artifact["summary"] = _summary(validation.cases, meter.records)
            artifact["summary"]["meter_actual_estimated_cost_usd"] = round(meter.actual_cost_usd, 8)
            artifact["summary"]["meter_budget_committed_usd"] = round(meter.budget_committed_usd, 8)
    finally:
        checkpoint(locals().get("validation"), locals().get("meter"))
        if old_config is None:
            os.environ.pop("LIBRARIAN_CONFIG_DIR", None)
        else:
            os.environ["LIBRARIAN_CONFIG_DIR"] = old_config
        if not args.keep_scratch:
            shutil.rmtree(work, ignore_errors=True)

    print(json.dumps({"output": str(args.output), "summary": artifact["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
