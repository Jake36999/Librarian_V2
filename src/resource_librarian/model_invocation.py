"""Safe, model-aware invocation planning around the legacy provider ABI.

This module is intentionally a *translation seam*, not a second agent loop.
The existing :mod:`resource_librarian.providers` implementations still own
their wire format, transport, retries, and ``Reply`` compatibility contract.
This layer adds the pieces that are needed before model-card expectations can
become executable safely:

* immutable, non-secret invocation plans;
* declarative expectation records with tri-state capabilities;
* a small, trusted protocol-adapter registry;
* a legacy adapter which delegates to ``Provider.chat`` unchanged; and
* an in-memory, redacted runtime trace.

It deliberately receives no vault, writer, SQLite, broker, tool executor, or
route-selection authority.  A tool call remains a proposal in ``Reply`` for
the Core loop to validate and execute.  The first V2 slice supports the
existing non-streaming Chat Completions and Messages paths.  Responses,
streaming, native reasoning controls, and direct Transformers rendering need
their own reviewed adapters rather than being smuggled through this bridge.
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import re
import secrets
import threading
import time
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from importlib import resources
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from .providers import (Anthropic, OpenAICompatible, Provider, ProviderCancelledError,
                        ProviderError, Reply, ToolDef, _safe_request_id, _safe_usage,
                        provider_failure_category)


ADAPTER_ABI_VERSION = 1
EXPECTATION_PACK_SCHEMA_VERSION = 1

CAPABILITIES = frozenset({
    "tool_use", "tool_results", "system_message", "structured_output",
    "streaming", "continuation", "native_reasoning",
})
TRI_STATES = frozenset({"true", "false", "unknown"})
OUTCOMES = frozenset({"completed", "tool_calls", "failed", "cancelled"})
MODEL_IDENTITY_VERDICTS = frozenset({
    "matched", "absent", "mismatched", "not_applicable",
})


def _bounded(value: Any, limit: int = 160) -> str:
    """Return a small, single-line identifier without pretending it is a secret.

    This is used only for route/configuration metadata.  Prompts, message
    content, headers, provider request bodies, and credentials never enter a
    plan or its trace in the first place.
    """
    return str(value or "").replace("\x00", "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def _slug(value: Any, fallback: str, limit: int = 80) -> str:
    text = re.sub(r"[^a-z0-9_.:-]+", "-", _bounded(value, limit).casefold()).strip("-.")
    return text[:limit] or fallback


def _canonical(value: Any) -> str:
    """Canonical JSON for *configuration* hashes only.

    Callers deliberately pass small declarative data.  ``default=str`` keeps
    a malformed third-party schema from crashing diagnostics, while never
    being used for prompt/message content.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=str)


def model_identity_verdict(requested_model: Any, observed_model: Any) -> str:
    """Classify one provider attempt's exact-model evidence.

    The requested route is an exact identifier when one is configured.  A
    provider response can then confirm it (``matched``), omit it
    (``absent``), or identify a different route (``mismatched``).  The
    ``(unselected)`` sentinel is deliberately not treated as an exact route:
    an observed model cannot prove or disprove a model that was never
    selected, so its verdict is ``not_applicable``.

    This is intentionally an exact, case-sensitive comparison.  Treating a
    provider alias, version suffix, or casing rewrite as a match would allow
    a route to borrow evidence for a different deployed model.
    """
    requested = _bounded(requested_model, 300)
    observed = _bounded(observed_model, 300)
    if not requested or requested in {"(unselected)", "*"}:
        return "not_applicable"
    if not observed:
        return "absent"
    return "matched" if observed == requested else "mismatched"


def digest(value: Any, length: int = 24) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:length]


def _copy_messages(messages: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    # The payload is ephemeral, but make it independent of a caller that may
    # append a tool result immediately after handing it to the runtime.
    return tuple(copy.deepcopy(dict(message)) for message in messages)


def _copy_tools(tools: list[ToolDef] | tuple[ToolDef, ...]) -> tuple[ToolDef, ...]:
    return tuple(ToolDef(_bounded(tool.name), _bounded(tool.description, 4_000),
                         copy.deepcopy(tool.parameters)) for tool in tools)


def tool_contract_fingerprint(tools: tuple[ToolDef, ...]) -> str:
    """Hash the offered tool contract without retaining it in a trace."""
    return digest({"tools": [
        {"name": tool.name, "description": tool.description, "parameters": tool.parameters}
        for tool in tools
    ]})


@dataclass(frozen=True)
class AdapterDescriptor:
    """A first-party protocol translator contract.

    ``capabilities`` describe the translator, not a particular model.  A
    route/model expectation can narrow these claims but can never expand
    them.  The legacy adapters intentionally do not claim native structured
    output, streaming, or provider reasoning controls.
    """
    id: str
    version: str
    abi_version: int
    protocol: str
    capabilities: frozenset[str] = field(default_factory=frozenset)

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    @property
    def fingerprint(self) -> str:
        return digest({"id": self.id, "version": self.version,
                       "abi": self.abi_version, "protocol": self.protocol,
                       "capabilities": sorted(self.capabilities)})


LEGACY_OPENAI_CHAT = AdapterDescriptor(
    "legacy_openai_chat", "1", ADAPTER_ABI_VERSION, "openai_chat_completions",
    frozenset({"tool_use", "tool_results", "system_message", "continuation"}),
)
LEGACY_ANTHROPIC_MESSAGES = AdapterDescriptor(
    "legacy_anthropic_messages", "1", ADAPTER_ABI_VERSION, "anthropic_messages",
    frozenset({"tool_use", "tool_results", "system_message", "continuation"}),
)
LEGACY_PROVIDER_CHAT = AdapterDescriptor(
    "legacy_provider_chat", "1", ADAPTER_ABI_VERSION, "legacy_chat",
    # A custom/Scripted Provider has the same neutral tool proposal surface;
    # this is not a claim about any remote endpoint's native capabilities.
    frozenset({"tool_use", "tool_results", "system_message", "continuation"}),
)


@dataclass(frozen=True)
class ExactRoute:
    """A non-secret route identity used in a plan and qualification evidence."""
    host_id: str
    protocol: str
    endpoint_fingerprint: str
    model_id: str

    @classmethod
    def from_provider(cls, provider: Provider) -> "ExactRoute":
        """Derive a stable route identity without inspecting credentials.

        ``LimitedProvider`` exposes ``host`` and wraps a native provider in
        ``provider``.  Unwrapping only identifies the protocol/model; the
        returned route still represents the outer, limited execution path.
        """
        carrier: Any = provider
        host = getattr(carrier, "host", None)
        seen: set[int] = set()
        while getattr(carrier, "provider", None) is not None and id(carrier) not in seen:
            seen.add(id(carrier))
            carrier = getattr(carrier, "provider")
        if host is None:
            host = getattr(carrier, "host", None)
        if host is not None:
            host_id = _bounded(getattr(host, "id", "")) or _bounded(getattr(host, "display_name", ""))
            protocol = _slug(getattr(host, "protocol", ""), "legacy")
            endpoint = _bounded(getattr(host, "endpoint_fingerprint", ""))
            base_url = _bounded(getattr(host, "base_url", ""), 1_000)
        else:
            host_id = _bounded(getattr(carrier, "name", "")) or "legacy"
            protocol = "anthropic" if isinstance(carrier, Anthropic) else \
                "openai" if isinstance(carrier, OpenAICompatible) else "legacy"
            endpoint = ""
            base_url = _bounded(getattr(carrier, "base_url", ""), 1_000)
        model = _bounded(getattr(carrier, "model", "")) or _bounded(getattr(provider, "model", ""))
        return cls(
            host_id=_slug(host_id, "legacy"),
            protocol=_slug(protocol, "legacy"),
            endpoint_fingerprint=endpoint or digest({"protocol": protocol, "base_url": base_url}),
            model_id=model or "(unselected)",
        )


@dataclass(frozen=True)
class TaskContract:
    """What the task needs, independent of provider-native controls."""
    id: str = "legacy"
    kind: str = "chat"
    interaction: str = "single_turn"  # single_turn | tool_loop | qualification_probe
    required_capabilities: frozenset[str] = field(default_factory=frozenset)
    output_contract: str = "text"     # text | prompted_json | native_json

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _slug(self.id, "legacy"))
        object.__setattr__(self, "kind", _slug(self.kind, "chat"))
        object.__setattr__(self, "interaction", _slug(self.interaction, "single_turn"))
        object.__setattr__(self, "output_contract", _slug(self.output_contract, "text"))
        needs = frozenset(_slug(item, "") for item in self.required_capabilities if _slug(item, ""))
        unknown = sorted(needs - CAPABILITIES)
        if unknown:
            raise ValueError("unknown invocation capability: " + ", ".join(unknown))
        object.__setattr__(self, "required_capabilities", needs)


@dataclass(frozen=True)
class InvocationScope:
    """Role/workflow context which Core supplies to a protocol adapter."""
    role: str = "legacy"
    task: TaskContract = field(default_factory=TaskContract)
    phase: str = ""
    session_id: str = ""
    behavior_mode: str = "provider_default"
    reasoning_intent: str = "balanced"  # economical | balanced | thorough

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", _slug(self.role, "legacy"))
        object.__setattr__(self, "phase", _slug(self.phase, "", 80))
        object.__setattr__(self, "session_id", _bounded(self.session_id, 160))
        object.__setattr__(self, "behavior_mode", _slug(self.behavior_mode, "provider_default"))
        intent = _slug(self.reasoning_intent, "balanced")
        if intent not in {"economical", "balanced", "thorough"}:
            raise ValueError("reasoning intent is economical, balanced or thorough")
        object.__setattr__(self, "reasoning_intent", intent)


# Dialect dimensions that a reviewed expectation record may declare.
# A dimension whose vocabulary is only "provider_default" is a recognised
# dimension whose interpreter lands with a reviewed fixture; extending the
# set of values for any dimension is a Core change, not a pack change.
DIALECT_VOCABULARY: dict[str, frozenset[str]] = {
    "reasoning_replay": frozenset({"provider_default", "replay_on_tool_turn", "never_replay"}),
    "output_headroom": frozenset({"provider_default", "reasoning_reserve"}),
    "tool_call_in_content": frozenset({"provider_default"}),
    "tool_schema": frozenset({"provider_default"}),
    "tool_result_shape": frozenset({"provider_default"}),
    "sampling_profile": frozenset({"provider_default", "deterministic"}),
}
REASONING_RESERVE_TOKENS = 1024


@dataclass(frozen=True)
class ModelExpectation:
    """A reviewed, declarative expectation record loaded from a pack.

    There are deliberately no executable templates, prompt fragments, raw
    request fields, or secrets here.  A matching expectation supplies an
    evidence-backed constraint; it does not authorize a model route.
    """
    id: str
    version: str
    status: str
    protocol: str
    adapter_id: str
    adapter_abi: int
    model_id: str = "*"
    host_id_or_family: str = "*"
    endpoint_fingerprint: str = ""
    capabilities: tuple[tuple[str, str], ...] = ()
    behavior_modes: tuple[str, ...] = ("provider_default",)
    dialect: tuple[tuple[str, str], ...] = ()
    source_url: str = ""
    source_revision: str = ""
    source_kind: str = ""
    source_evidence_id: str = ""
    pack_id: str = ""
    pack_fingerprint: str = ""
    fingerprint: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _slug(self.id, "expectation"))
        object.__setattr__(self, "version", _bounded(self.version, 80) or "1")
        status = _slug(self.status, "draft")
        if status not in {"draft", "reviewed", "deprecated"}:
            raise ValueError("expectation status is draft, reviewed or deprecated")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "protocol", _slug(self.protocol, "legacy"))
        object.__setattr__(self, "adapter_id", _slug(self.adapter_id, "legacy_provider_chat"))
        try:
            abi = int(self.adapter_abi)
        except (TypeError, ValueError) as exc:
            raise ValueError("expectation adapter ABI is an integer") from exc
        object.__setattr__(self, "adapter_abi", abi)
        object.__setattr__(self, "model_id", _bounded(self.model_id, 300) or "*")
        object.__setattr__(self, "host_id_or_family", _slug(self.host_id_or_family, "*", 120) or "*")
        object.__setattr__(self, "endpoint_fingerprint", _bounded(self.endpoint_fingerprint, 160))
        states: dict[str, str] = {}
        for raw_name, raw_state in self.capabilities:
            name = _slug(raw_name, "")
            if name not in CAPABILITIES:
                raise ValueError(f"unknown expectation capability {name!r}")
            state = "true" if raw_state is True else "false" if raw_state is False else \
                _slug(raw_state, "unknown")
            if state not in TRI_STATES:
                raise ValueError(f"capability {name!r} is true, false or unknown")
            states[name] = state
        object.__setattr__(self, "capabilities", tuple(sorted(states.items())))
        modes = tuple(dict.fromkeys(_slug(item, "") for item in self.behavior_modes if _slug(item, "")))
        if "provider_default" not in modes:
            modes = ("provider_default",) + modes
        object.__setattr__(self, "behavior_modes", modes)
        # Validate dialect: every dimension must be known and its value
        # must be in the declared vocabulary.  Entries whose value is
        # "provider_default" are dropped so the stored tuple only carries
        # non-default overrides.
        dialect_entries: dict[str, str] = {}
        for raw_name, raw_value in self.dialect:
            name = _slug(raw_name, "")
            if name not in DIALECT_VOCABULARY:
                raise ValueError(f"unknown dialect dimension {name!r}")
            value = _slug(raw_value, "")
            if value not in DIALECT_VOCABULARY[name]:
                raise ValueError(f"dialect {name!r} does not support {value!r}")
            if value != "provider_default":
                dialect_entries[name] = value
        object.__setattr__(self, "dialect", tuple(sorted(dialect_entries.items())))
        object.__setattr__(self, "source_url", _bounded(self.source_url, 1_000))
        object.__setattr__(self, "source_revision", _bounded(self.source_revision, 300))
        object.__setattr__(self, "source_kind", _slug(self.source_kind, "", 80))
        object.__setattr__(self, "source_evidence_id", _bounded(self.source_evidence_id, 160))
        object.__setattr__(self, "pack_id", _slug(self.pack_id, ""))
        object.__setattr__(self, "pack_fingerprint", _bounded(self.pack_fingerprint, 80))
        if not self.fingerprint:
            # Content-addressed: the hash covers this record's own claims
            # only.  The pack id and pack digest are provenance, kept beside
            # the record but outside its hash, so adding or editing an
            # unrelated record never changes this route's qualification
            # fingerprint.
            digest_payload: dict[str, Any] = {
                "id": self.id, "version": self.version, "status": self.status,
                "protocol": self.protocol, "adapter": self.adapter_id,
                "abi": self.adapter_abi, "model": self.model_id,
                "host": self.host_id_or_family, "endpoint": self.endpoint_fingerprint,
                "capabilities": self.capabilities, "behavior_modes": self.behavior_modes,
                "source": self.source_url, "revision": self.source_revision,
            }
            # Only include dialect in the fingerprint when it carries
            # non-default overrides, so every existing record keeps its
            # exact fingerprint.
            if self.dialect:
                digest_payload["dialect"] = self.dialect
            if self.source_kind:
                digest_payload["source_kind"] = self.source_kind
            if self.source_evidence_id:
                digest_payload["source_evidence_id"] = self.source_evidence_id
            object.__setattr__(self, "fingerprint", digest(digest_payload))

    def capability(self, name: str) -> str:
        return dict(self.capabilities).get(name, "unknown")

    def dialect_value(self, name: str) -> str:
        """Return the declared value for *name* or ``"provider_default"``."""
        return dict(self.dialect).get(name, "provider_default")

    @classmethod
    def from_row(cls, row: Mapping[str, Any], *, pack_id: str, pack_fingerprint: str) -> "ModelExpectation":
        identity = row.get("identity") if isinstance(row.get("identity"), Mapping) else {}
        prompt = row.get("prompt_contract") if isinstance(row.get("prompt_contract"), Mapping) else {}
        provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
        caps = row.get("capabilities") if isinstance(row.get("capabilities"), Mapping) else {}
        modes = row.get("behavior_modes", row.get("native_behavior_modes", ["provider_default"]))
        if not isinstance(modes, (list, tuple)):
            raise ValueError("behavior_modes is a list")
        protocol = row.get("protocol", prompt.get("runtime_target", "legacy"))
        # Hosted runtime names are a registry vocabulary, not raw provider
        # parameters.  The matcher maps them conservatively below.
        if protocol == "hosted_openai":
            protocol = "openai"
        # Dialect must be a Mapping if present; the loader rejects
        # anything else so a pack cannot smuggle executable structures.
        dialect_raw = row.get("dialect")
        if dialect_raw is not None:
            if not isinstance(dialect_raw, Mapping):
                raise ValueError("dialect is an object")
            dialect = tuple(dialect_raw.items())
        else:
            dialect = ()
        return cls(
            id=str(row.get("id") or ""), version=str(row.get("version") or "1"),
            status=str(row.get("status") or "draft"), protocol=str(protocol),
            adapter_id=str(row.get("adapter_id") or prompt.get("adapter_id") or "legacy_provider_chat"),
            adapter_abi=row.get("adapter_abi", prompt.get("adapter_abi", ADAPTER_ABI_VERSION)),
            model_id=str(row.get("model_id") or identity.get("provider_model_id") or "*"),
            host_id_or_family=str(row.get("host_id_or_family") or identity.get("host_id_or_family") or "*"),
            endpoint_fingerprint=str(row.get("endpoint_fingerprint") or identity.get("endpoint_fingerprint") or ""),
            capabilities=tuple(caps.items()), behavior_modes=tuple(str(item) for item in modes),
            dialect=dialect,
            source_url=str(row.get("source_url") or provenance.get("source_url") or ""),
            source_revision=str(row.get("source_revision") or provenance.get("source_revision") or ""),
            source_kind=str(row.get("source_kind") or provenance.get("source_kind") or ""),
            source_evidence_id=str(row.get("source_evidence_id") or
                                   provenance.get("source_evidence_id") or ""),
            pack_id=pack_id, pack_fingerprint=pack_fingerprint,
        )


def effective_dialect(expectation: ModelExpectation | None) -> dict[str, str]:
    """Return the effective dialect for an invocation.

    Every dimension defaults to ``"provider_default"``.  A reviewed, exact
    record (status ``"reviewed"`` and ``model_id != "*"``) may override
    specific dimensions.  A draft or wildcard record never changes behaviour.
    """
    dialect: dict[str, str] = {dim: "provider_default" for dim in DIALECT_VOCABULARY}
    if (
        expectation is not None
        and expectation.status == "reviewed"
        and expectation.model_id != "*"
    ):
        for name, value in expectation.dialect:
            dialect[name] = value
    return dialect


class ExpectationPackError(ValueError):
    """A shipped/personal declarative expectation pack is malformed."""


# The complete vocabulary the loader understands.  Anything else is rejected
# rather than ignored: a field the Core does not read cannot be reviewed as a
# claim, and silently dropping it would let a pack look more expressive than
# it is.  Extending the vocabulary is a Core change, not a pack change.
PACK_FIELDS = frozenset({"schema_version", "pack_id", "records"})
RECORD_FIELDS = frozenset({
    "id", "version", "status", "protocol", "adapter_id", "adapter_abi", "model_id",
    "host_id_or_family", "endpoint_fingerprint", "capabilities", "behavior_modes",
    "native_behavior_modes", "source_url", "source_revision",
    "source_kind", "source_evidence_id",
    "identity", "prompt_contract", "provenance", "dialect",
})
NESTED_RECORD_FIELDS = {
    "identity": frozenset({"provider_model_id", "host_id_or_family", "endpoint_fingerprint"}),
    "prompt_contract": frozenset({"runtime_target", "adapter_id", "adapter_abi"}),
    "provenance": frozenset({"source_url", "source_revision", "source_kind",
                              "source_evidence_id"}),
}
# Keys that would turn a data pack into an unreviewed executable prompt or
# template channel.  Checked at every depth, so a nested object cannot carry
# one either.
FORBIDDEN_PACK_KEYS = frozenset({
    "template", "chat_template", "prompt", "system_prompt", "code", "script", "command",
})


def _forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            name = str(key).casefold()
            if name in FORBIDDEN_PACK_KEYS:
                found.add(name)
            found |= _forbidden_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            found |= _forbidden_keys(item)
    return found


def _check_record_fields(row: Mapping[str, Any]) -> None:
    label = _bounded(row.get("id"), 80) or "(no id)"
    unknown = sorted(str(key) for key in row if key not in RECORD_FIELDS)
    if unknown:
        raise ExpectationPackError(
            f"expectation record {label!r} has unknown field(s): " + ", ".join(unknown))
    if "behavior_modes" in row and "native_behavior_modes" in row:
        raise ExpectationPackError(
            f"expectation record {label!r} gives both behavior_modes and native_behavior_modes")
    for name, allowed in NESTED_RECORD_FIELDS.items():
        if name not in row:
            continue
        nested = row[name]
        if not isinstance(nested, Mapping):
            raise ExpectationPackError(f"expectation record {label!r}: {name} is an object")
        unknown = sorted(str(key) for key in nested if key not in allowed)
        if unknown:
            raise ExpectationPackError(
                f"expectation record {label!r}: {name} has unknown field(s): " + ", ".join(unknown))
    if "capabilities" in row and not isinstance(row["capabilities"], Mapping):
        raise ExpectationPackError(f"expectation record {label!r}: capabilities is an object")
    # Dialect is a strict declarative object; unknown dimensions or
    # unsupported values fail closed so a pack cannot invent behaviour.
    if "dialect" in row:
        dialect_raw = row["dialect"]
        if not isinstance(dialect_raw, Mapping):
            raise ExpectationPackError(f"expectation record {label!r}: dialect is an object")
        for name, value in dialect_raw.items():
            name_slug = _slug(str(name), "")
            if name_slug not in DIALECT_VOCABULARY:
                raise ExpectationPackError(
                    f"expectation record {label!r}: unknown dialect dimension {name_slug!r}")
            value_slug = _slug(str(value), "")
            if value_slug not in DIALECT_VOCABULARY[name_slug]:
                raise ExpectationPackError(
                    f"expectation record {label!r}: dialect {name_slug!r} does not support {value_slug!r}")


class ExpectationRegistry:
    """Read-only expectation records; no pack can execute code.

    ``load_error`` is set when the bundled pack could not be read.  The
    registry then holds no records, so every route resolves as ``unknown``
    (never as verified), and :meth:`status` says why for diagnostics.
    """

    def __init__(self, records: tuple[ModelExpectation, ...] = (), *, pack_id: str = "",
                 pack_fingerprint: str = "", load_error: str = "") -> None:
        self.records = tuple(records)
        self.pack_id = _slug(pack_id, "")
        self.pack_fingerprint = _bounded(pack_fingerprint, 80)
        self.load_error = _bounded(load_error, 400)

    def status(self) -> dict[str, Any]:
        """Non-secret pack state for doctor, readiness and the model tile."""
        return {"ok": not self.load_error, "pack_id": self.pack_id,
                "fingerprint": self.pack_fingerprint, "records": len(self.records),
                "error": self.load_error}

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ExpectationRegistry":
        if not isinstance(payload, Mapping):
            raise ExpectationPackError("expectation pack is an object")
        present = _forbidden_keys(payload)
        if present:
            raise ExpectationPackError("expectation records may not contain " + ", ".join(sorted(present)))
        unknown = sorted(str(key) for key in payload if key not in PACK_FIELDS)
        if unknown:
            raise ExpectationPackError("expectation pack has unknown field(s): " + ", ".join(unknown))
        if int(payload.get("schema_version") or 0) != EXPECTATION_PACK_SCHEMA_VERSION:
            raise ExpectationPackError(
                f"expectation pack schema is {EXPECTATION_PACK_SCHEMA_VERSION}")
        raw_records = payload.get("records")
        if not isinstance(raw_records, list):
            raise ExpectationPackError("expectation pack records is a list")
        for row in raw_records:
            if not isinstance(row, Mapping):
                raise ExpectationPackError("expectation record is an object")
            _check_record_fields(row)
        fingerprint = digest(payload, 64)
        pack_id = _slug(payload.get("pack_id"), "expectations")
        try:
            records = tuple(ModelExpectation.from_row(row, pack_id=pack_id,
                                                      pack_fingerprint=fingerprint)
                            for row in raw_records)
        except (TypeError, ValueError) as exc:
            raise ExpectationPackError(str(exc)) from exc
        ids = [record.id for record in records]
        if len(ids) != len(set(ids)):
            raise ExpectationPackError("expectation record ids are unique")
        return cls(records, pack_id=pack_id, pack_fingerprint=fingerprint)

    @classmethod
    def bundled(cls) -> "ExpectationRegistry":
        """Load the minimal trusted Core pack, or an empty conservative registry.

        Development source trees and old editable installs may not have the
        new data file yet.  Failing to load it must not imply a model supports
        a feature, so an empty registry gives only ``unknown`` capability
        states rather than a fabricated default record.
        """
        try:
            node = resources.files("resource_librarian").joinpath(
                "standard", "model_expectations", "core.json")
            payload = json.loads(node.read_text(encoding="utf-8"))
            return cls.from_payload(payload)
        except (FileNotFoundError, ModuleNotFoundError):
            return cls(load_error="the bundled model expectation pack is missing; "
                                  "every route is treated as unreviewed")
        except (OSError, json.JSONDecodeError, ExpectationPackError) as exc:
            # The runtime remains available to preserve a current configured
            # route.  The lack of a reviewed record is observable as unknown,
            # not silently treated as verified capability evidence, and the
            # reason is kept for doctor and readiness rather than swallowed.
            return cls(load_error=f"the bundled model expectation pack could not be loaded "
                                  f"({type(exc).__name__}: {_bounded(exc, 240)}); "
                                  f"every route is treated as unreviewed")

    @classmethod
    def active(cls, path: Path | None = None) -> "ExpectationRegistry":
        """Layer the reviewed personal pack over the shipped baseline.

        The personal artifact is declarative and non-secret. A malformed
        artifact is visible in status while known-good bundled records remain
        usable. Draft staging items never reach this loader.
        """
        baseline = cls.bundled()
        if baseline.load_error:
            return baseline
        if path is None:
            from .keys import config_dir
            path = config_dir() / "model-expectations.json"
        if not path.is_file():
            return baseline
        try:
            personal = cls.from_payload(json.loads(path.read_text(encoding="utf-8")))
            if personal.pack_id != "librarian-personal-model-expectations":
                raise ExpectationPackError(
                    "the active personal model expectation pack has the wrong pack id")
            for record in personal.records:
                if record.status != "reviewed":
                    raise ExpectationPackError(
                        "the active personal pack contains a non-reviewed record")
                # The authoring tool enforces these constraints before writing,
                # but the loader is the actual trust boundary: a hand-edited or
                # copied artifact must not bypass exact-route review or introduce
                # a behavior-changing dialect without qualification.
                if record.model_id == "*" or record.host_id_or_family == "*":
                    raise ExpectationPackError(
                        "personal expectation records require an exact model and host")
                if record.dialect:
                    raise ExpectationPackError(
                        "personal expectation dialect changes require qualification")
                if (
                    record.source_kind != "model_card"
                    or not record.source_url
                    or not record.source_revision
                    or not record.source_evidence_id
                ):
                    raise ExpectationPackError(
                        "personal expectation records require model-card provenance")
            baseline_ids = {record.id for record in baseline.records}
            duplicate_ids = sorted(baseline_ids.intersection(record.id for record in personal.records))
            if duplicate_ids:
                raise ExpectationPackError(
                    "personal expectation records may not replace bundled ids: " +
                    ", ".join(duplicate_ids))
            def route_key(record: ModelExpectation) -> tuple[str, int, str, str, str, str]:
                return (record.adapter_id, record.adapter_abi, record.protocol,
                        record.model_id.casefold(), record.host_id_or_family.casefold(),
                        record.endpoint_fingerprint)
            exact: dict[tuple[str, int, str, str, str, str], str] = {
                route_key(record): record.id for record in baseline.records
                if record.model_id != "*" and record.status != "deprecated"}
            for record in personal.records:
                if record.model_id == "*" or record.status == "deprecated":
                    continue
                prior = exact.get(route_key(record))
                if prior:
                    raise ExpectationPackError(
                        f"exact route is already described by expectation record {prior}")
                exact[route_key(record)] = record.id
            records = (*personal.records, *baseline.records)
            return cls(records, pack_id=f"{baseline.pack_id}+{personal.pack_id}",
                       pack_fingerprint=digest({"baseline": baseline.pack_fingerprint,
                                                "personal": personal.pack_fingerprint}, 64))
        except (OSError, json.JSONDecodeError, ExpectationPackError) as exc:
            return cls(baseline.records, pack_id=baseline.pack_id,
                       pack_fingerprint=baseline.pack_fingerprint,
                       load_error=f"the personal model expectation pack could not be loaded "
                                  f"({type(exc).__name__}: {_bounded(exc, 240)})")

    @staticmethod
    def _protocol_matches(expectation_protocol: str, route_protocol: str) -> bool:
        aliases = {
            "openai": {"openai", "openai_compatible", "openai_chat_completions"},
            "anthropic": {"anthropic", "anthropic_messages"},
            "legacy": {"legacy", "legacy_chat"},
        }
        return route_protocol in aliases.get(expectation_protocol, {expectation_protocol})

    @staticmethod
    def _host_matches(expectation_host: str, route_host: str) -> tuple[bool, bool]:
        """Match an exact host, including only the built-in preset aliases.

        The compatibility picker still uses ``deepinfra``/``openai`` as its
        2.x provider labels, while the host registry uses
        ``preset-deepinfra``/``preset-openai``.  They are the same shipped
        endpoint—not a wildcard for a custom host with a similar name.  Keep
        the alias narrow so an expectation never leaks onto an arbitrary
        OpenAI-compatible server.
        """
        expected, actual = expectation_host.casefold(), route_host.casefold()
        if expected == "*":
            return True, False
        if expected == actual:
            return True, True
        aliases = {
            "deepinfra": "preset-deepinfra",
            "openai": "preset-openai",
            "anthropic": "preset-anthropic",
            "local": "preset-local",
        }
        return (aliases.get(expected) == actual or aliases.get(actual) == expected,
                aliases.get(expected) == actual or aliases.get(actual) == expected)

    def match(self, route: ExactRoute, descriptor: AdapterDescriptor) -> ModelExpectation | None:
        candidates: list[tuple[tuple[int, int, int], ModelExpectation]] = []
        route_model = route.model_id.casefold()
        route_host = route.host_id.casefold()
        for record in self.records:
            if record.status == "deprecated" or record.adapter_id != descriptor.id or \
                    record.adapter_abi != descriptor.abi_version:
                continue
            if not self._protocol_matches(record.protocol, route.protocol):
                continue
            model_exact = record.model_id.casefold() == route_model
            if record.model_id != "*" and not model_exact:
                continue
            host_matches, host_exact = self._host_matches(record.host_id_or_family, route_host)
            if not host_matches:
                continue
            endpoint_exact = bool(record.endpoint_fingerprint and
                                  record.endpoint_fingerprint == route.endpoint_fingerprint)
            if record.endpoint_fingerprint and not endpoint_exact:
                continue
            candidates.append(((int(model_exact), int(host_exact), int(endpoint_exact)), record))
        return max(candidates, key=lambda row: row[0])[1] if candidates else None


def legacy_structured_output_policy(model_id: str, *, provider_id: str = "",
                                    base_url: str = "",
                                    expectations: ExpectationRegistry | None = None
                                    ) -> dict[str, str | bool]:
    """Return the safe constrained-output policy for the legacy Clerk path.

    Clerk predates the normal ``Provider`` adapter boundary and asks for an
    OpenAI-style JSON schema directly.  It must still consume the same
    evidence pack: a known rejection means do not send a paid strict-schema
    attempt; an unknown route preserves the established strict-then-fallback
    UX; and a positively reviewed schema contract treats a rejection as
    endpoint drift instead of silently weakening the request.

    ``deepinfra`` is a legacy provider label while normal selected routes use
    the seeded host identifier ``preset-deepinfra``.  Map only this published
    preset alias; custom compatible endpoints remain unknown unless their own
    route has an exact expectation record.
    """
    raw_host = _slug(provider_id, "legacy", 120)
    host_id = "preset-deepinfra" if raw_host in {"deepinfra", "preset-deepinfra"} else raw_host
    route = ExactRoute(
        host_id=host_id,
        protocol="openai",
        endpoint_fingerprint=digest({"protocol": "openai", "base_url": _bounded(base_url, 1_000)}),
        model_id=_bounded(model_id, 300) or "(unselected)",
    )
    record = (expectations or ExpectationRegistry.active()).match(route, LEGACY_OPENAI_CHAT)
    state = record.capability("structured_output") if record is not None else "unknown"
    return {
        "state": state,
        "expectation_id": record.id if record is not None else "",
        "strict_attempt": state != "false",
        # Compatibility fallback is safe only for a route whose strict-schema
        # support is unmeasured.  A reviewed yes must surface contract drift.
        "fallback_on_rejection": state == "unknown",
    }


@dataclass(frozen=True)
class CompatibilityResult:
    """Resolver result before a provider can receive an invocation payload."""
    accepted: bool
    disposition: str  # compatible | experimental | incompatible
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    expectation_id: str = ""


class InvocationCompatibilityError(ProviderError):
    """A plan was rejected before a provider/endpoint was contacted."""

    def __init__(self, result: CompatibilityResult, *, category: str = "route_configuration") -> None:
        self.compatibility = result
        detail = "; ".join(result.errors) or "the selected route is incompatible with this task"
        super().__init__(detail, category=category)


@dataclass(frozen=True)
class InvocationPlan:
    """Immutable, serialisable, non-secret invocation configuration.

    ``config_hash`` deliberately excludes ``plan_id`` and ``session_id`` so
    it can identify the same effective model contract across turns without
    correlating prompt contents or secrets.
    """
    plan_id: str
    adapter_id: str
    adapter_version: str
    adapter_abi: int
    protocol: str
    host_id: str
    endpoint_fingerprint: str
    model_id: str
    role: str
    task_id: str
    task_kind: str
    interaction: str
    phase: str
    session_id: str
    output_contract: str
    required_capabilities: tuple[str, ...]
    tool_schema_fingerprint: str
    max_output_tokens: int
    behavior_mode: str
    reasoning_intent: str
    dialect: tuple[tuple[str, str], ...] = ()
    expectation_id: str = ""
    expectation_fingerprint: str = ""
    config_hash: str = ""

    def __post_init__(self) -> None:
        if self.adapter_abi != ADAPTER_ABI_VERSION:
            raise ValueError(f"unsupported adapter ABI {self.adapter_abi}")
        object.__setattr__(self, "required_capabilities", tuple(sorted(set(self.required_capabilities))))
        object.__setattr__(self, "max_output_tokens", max(1, int(self.max_output_tokens)))
        if not self.config_hash:
            config_payload: dict[str, Any] = {
                "adapter": {"id": self.adapter_id, "version": self.adapter_version,
                            "abi": self.adapter_abi, "protocol": self.protocol},
                "route": {"host": self.host_id, "endpoint": self.endpoint_fingerprint,
                          "model": self.model_id},
                "scope": {"role": self.role, "task": self.task_id,
                          "kind": self.task_kind, "interaction": self.interaction,
                          "phase": self.phase, "output": self.output_contract,
                          "needs": self.required_capabilities},
                "tools": self.tool_schema_fingerprint,
                "limits": {"max_output_tokens": self.max_output_tokens},
                "behaviour": {"mode": self.behavior_mode, "reasoning": self.reasoning_intent},
                "expectation": {"id": self.expectation_id,
                                "fingerprint": self.expectation_fingerprint},
            }
            # Only include dialect in the hash when it carries non-default
            # overrides, so every existing plan keeps its exact config_hash.
            if self.dialect:
                config_payload["dialect"] = dict(self.dialect)
            object.__setattr__(self, "config_hash", digest(config_payload))

    def trace(self) -> dict[str, Any]:
        """The only representation suitable for UI diagnostics or persistence."""
        return {
            "plan_id": self.plan_id, "config_hash": self.config_hash,
            "adapter": {"id": self.adapter_id, "version": self.adapter_version,
                        "abi": self.adapter_abi, "protocol": self.protocol},
            "route": {"host_id": self.host_id, "endpoint_fingerprint": self.endpoint_fingerprint,
                      "requested_model": self.model_id},
            "scope": {"role": self.role, "task_id": self.task_id, "task_kind": self.task_kind,
                      "interaction": self.interaction, "phase": self.phase,
                      "output_contract": self.output_contract,
                      "required_capabilities": list(self.required_capabilities)},
            "tool_schema_fingerprint": self.tool_schema_fingerprint,
            "max_output_tokens": self.max_output_tokens,
            "behavior_mode": self.behavior_mode, "reasoning_intent": self.reasoning_intent,
            "dialect": dict(self.dialect),
            "expectation": {"id": self.expectation_id,
                            "fingerprint": self.expectation_fingerprint},
        }


@dataclass(frozen=True, repr=False)
class InvocationPayload:
    """Ephemeral legacy request data.  It deliberately has no public serializer."""
    system: str
    messages: tuple[dict[str, Any], ...]
    tools: tuple[ToolDef, ...]
    max_tokens: int
    temperature: float | None = None

    @classmethod
    def from_legacy(cls, system: str, messages: list[dict[str, Any]], tools: list[ToolDef],
                    *, max_tokens: int = 4096, temperature: float | None = None) -> "InvocationPayload":
        return cls(str(system), _copy_messages(messages), _copy_tools(tools),
                   max(1, int(max_tokens)), temperature)

    def legacy_messages(self) -> list[dict[str, Any]]:
        return [copy.deepcopy(message) for message in self.messages]

    def legacy_tools(self) -> list[ToolDef]:
        return [ToolDef(tool.name, tool.description, copy.deepcopy(tool.parameters))
                for tool in self.tools]


def apply_dialect(plan: InvocationPlan, payload: InvocationPayload) -> InvocationPayload:
    """Return a new payload with dialect-driven adjustments applied.

    The payload is frozen; this returns a shallow copy with the necessary
    replacements.  Only non-default dialect entries in *plan* take effect.
    """
    dialect = dict(plan.dialect)

    # reasoning_replay: "never_replay" strips reasoning_content from every
    # assistant message.  "replay_on_tool_turn" and provider_default leave
    # messages as-is (the adapters already replay only on the tool-call
    # message).
    if dialect.get("reasoning_replay") == "never_replay":
        new_messages = []
        for msg in payload.messages:
            if msg.get("role") == "assistant" and "reasoning_content" in msg:
                msg = {k: v for k, v in msg.items() if k != "reasoning_content"}
            new_messages.append(msg)
        payload = dataclasses.replace(payload, messages=tuple(new_messages))

    # output_headroom: "reasoning_reserve" adds a fixed token reserve so
    # the model has room for internal reasoning without stealing from the
    # visible output budget.
    if dialect.get("output_headroom") == "reasoning_reserve":
        payload = dataclasses.replace(payload, max_tokens=payload.max_tokens + REASONING_RESERVE_TOKENS)

    # sampling_profile: "deterministic" sets temperature to 0 only when the
    # payload does not already specify an explicit temperature.
    if dialect.get("sampling_profile") == "deterministic" and payload.temperature is None:
        payload = dataclasses.replace(payload, temperature=0.0)

    return payload


@dataclass(frozen=True)
class NormalizedToolCall:
    """A tool-call summary.  Arguments stay with the Core's ``Reply``."""
    provider_call_id: str
    name: str
    arguments_state: str  # decoded | unparsed | unavailable

    def trace(self) -> dict[str, str]:
        # A provider call ID must survive inside the live ``Reply`` for a
        # continuation, but a self-hosted compatible server can return an
        # arbitrary string.  Do not place that raw response field in a
        # diagnostic trace.
        return {"provider_call_fingerprint": digest({"call_id": self.provider_call_id}), "name": self.name,
                "arguments_state": self.arguments_state}


@dataclass(frozen=True)
class AdapterFailure:
    category: str
    retryable: bool
    safe_message: str

    @classmethod
    def from_error(cls, error: ProviderError) -> "AdapterFailure":
        category = provider_failure_category(error)
        messages = {
            "credentials": "provider credentials are unavailable or were rejected",
            "route_configuration": "the selected route is not configured for this request",
            "provider_rate_limited": "the provider rate-limited this request",
            "provider_transient": "the provider is temporarily unavailable",
            "provider_transport": "the provider endpoint could not be reached",
            "provider_rejected": "the provider rejected this request",
            "output_budget": "the model reached its output budget before returning a usable result",
            "model_identity_mismatch": "the provider returned a different model than the selected route",
            "cancelled": "the provider request was cancelled",
            "local_environment": "the local environment blocked this provider request",
            "unknown": "the provider request failed",
        }
        return cls(category=category, retryable=category in {"provider_rate_limited", "provider_transient"},
                   safe_message=messages.get(category, messages["unknown"]))


@dataclass(frozen=True)
class InvocationResult:
    """Normalized safe result metadata; neither text nor raw arguments are retained."""
    plan_id: str
    config_hash: str
    adapter_id: str
    adapter_version: str
    requested_model: str
    observed_model: str
    outcome: str
    stop_reason: str
    elapsed_ms: int
    tool_calls: tuple[NormalizedToolCall, ...] = ()
    failure: AdapterFailure | None = None
    usage: dict[str, int] = field(default_factory=dict)
    request_id: str = ""
    model_identity: str = ""

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"unknown invocation outcome {self.outcome!r}")
        object.__setattr__(self, "requested_model", _bounded(self.requested_model, 300))
        object.__setattr__(self, "observed_model", _bounded(self.observed_model, 300))
        object.__setattr__(self, "stop_reason", _bounded(self.stop_reason, 160))
        object.__setattr__(self, "elapsed_ms", max(0, int(self.elapsed_ms)))
        object.__setattr__(self, "usage", _safe_usage(self.usage))
        object.__setattr__(self, "request_id", _safe_request_id(self.request_id))
        derived_verdict = model_identity_verdict(self.requested_model, self.observed_model)
        verdict = self.model_identity or derived_verdict
        if verdict not in MODEL_IDENTITY_VERDICTS:
            raise ValueError(f"unknown model identity verdict {verdict!r}")
        # The only result with no provider attempt is the route rejection
        # created before ``LegacyProviderAdapter.invoke``.  It records
        # ``not_applicable`` rather than claiming a provider omitted an
        # identity.  A response-bearing adapter cannot override a derived
        # mismatch into a match and evade the Runtime policy gate.
        no_provider_attempt = (
            verdict == "not_applicable" and self.outcome == "failed" and
            not self.observed_model and self.failure is not None and
            self.failure.category == "route_configuration"
        )
        if verdict != derived_verdict and not no_provider_attempt:
            raise ValueError("model identity verdict does not match requested/observed models")
        object.__setattr__(self, "model_identity", verdict)

    def trace(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "plan_id": self.plan_id, "config_hash": self.config_hash,
            "adapter": {"id": self.adapter_id, "version": self.adapter_version},
            "requested_model": self.requested_model, "observed_model": self.observed_model,
            "model_identity": self.model_identity,
            "conformance": {"model_identity": self.model_identity},
            "outcome": self.outcome, "stop_reason": self.stop_reason,
            "elapsed_ms": self.elapsed_ms,
            "tool_calls": [call.trace() for call in self.tool_calls],
            # The bounded, normalized fields below are the only response
            # telemetry retained. Prompts, raw provider bodies, and hidden
            # reasoning continuations never enter this trace.
            "telemetry": {"usage": dict(self.usage) if self.usage else "unavailable",
                          "request_id": self.request_id or "unavailable",
                          "inner_attempts": "unavailable"},
        }
        if self.failure is not None:
            row["failure"] = {"category": self.failure.category,
                              "retryable": self.failure.retryable,
                              "message": self.failure.safe_message}
        return row


class ModelIdentityMismatchError(InvocationCompatibilityError):
    """A response was blocked because it identifies a different exact model.

    ``reply`` is intentionally live-only.  A qualification probe may inspect
    its normalized tool proposal to record why it failed, but no normal Loop
    caller receives it and it never enters the redacted trace.  ``result`` is
    the trace-safe typed outcome retained by the runtime.
    """

    def __init__(self, compatibility: CompatibilityResult, result: InvocationResult,
                 reply: Reply | None) -> None:
        if result.model_identity != "mismatched":
            raise ValueError("model identity mismatch errors require a mismatched result")
        self.result = result
        self.reply = reply
        # ``invocation_result`` keeps generic diagnostic callers compatible
        # with the provider-error attachment used by LegacyProviderAdapter.
        self.invocation_result = result
        super().__init__(compatibility, category="model_identity_mismatch")


@dataclass(frozen=True)
class InvocationBinding:
    """Route/adapter/expectation snapshot pinned for one model walk."""
    route: ExactRoute
    descriptor: AdapterDescriptor
    expectation: ModelExpectation | None = None


class ProtocolAdapter:
    """Trusted translator interface; it never receives Core authority."""
    descriptor: AdapterDescriptor

    def invoke(self, plan: InvocationPlan, payload: InvocationPayload,
               provider: Provider, *,
               cancel: threading.Event | None = None) -> tuple[Reply, InvocationResult]:
        raise NotImplementedError


class LegacyProviderAdapter(ProtocolAdapter):
    """Bridge the current neutral ``Provider.chat`` ABI without changing it."""

    def __init__(self, descriptor: AdapterDescriptor) -> None:
        self.descriptor = descriptor

    def invoke(self, plan: InvocationPlan, payload: InvocationPayload,
               provider: Provider, *,
               cancel: threading.Event | None = None) -> tuple[Reply, InvocationResult]:
        if plan.adapter_id != self.descriptor.id or plan.adapter_abi != self.descriptor.abi_version:
            raise InvocationCompatibilityError(CompatibilityResult(
                False, "incompatible", ("adapter contract does not match the invocation plan",)))
        # The route's reviewed dialect shapes the request (ADAPT-08).
        payload = apply_dialect(plan, payload)
        started = time.monotonic()
        try:
            # Do not send ``temperature=None``.  Existing custom/test
            # Providers correctly implement the historical four-argument
            # shape and may not accept that optional keyword.
            kwargs: dict[str, Any] = {"max_tokens": payload.max_tokens}
            if payload.temperature is not None:
                kwargs["temperature"] = payload.temperature
            cancellable = getattr(provider, "chat_cancellable", None)
            if callable(cancellable):
                reply = cancellable(
                    payload.system, payload.legacy_messages(), payload.legacy_tools(),
                    cancel=cancel, **kwargs)
            else:
                # Duck-typed legacy integrations predate Provider's optional
                # cancellation method. Preserve that public ABI while still
                # observing cancellation immediately before and after their
                # synchronous call; only first-party transports promise an
                # in-flight socket abort.
                if cancel is not None and cancel.is_set():
                    raise ProviderCancelledError()
                reply = provider.chat(
                    payload.system, payload.legacy_messages(), payload.legacy_tools(), **kwargs)
                if cancel is not None and cancel.is_set():
                    raise ProviderCancelledError()
        except ProviderError as error:
            failure = AdapterFailure.from_error(error)
            result = InvocationResult(
                plan.plan_id, plan.config_hash, plan.adapter_id, plan.adapter_version,
                plan.model_id, _bounded(getattr(error, "observed_model", ""), 300),
                "cancelled" if failure.category == "cancelled" else "failed",
                _bounded(getattr(error, "stop_reason", ""), 160),
                round((time.monotonic() - started) * 1_000),
                usage=_safe_usage(getattr(error, "usage", {})),
                request_id=_safe_request_id(getattr(error, "request_id", "")),
                failure=failure,
            )
            # Preserve the original error/message/category for current UX and
            # host retry logic.  The attachment is private and safe-only.
            setattr(error, "invocation_result", result)
            raise
        calls = tuple(NormalizedToolCall(
            _bounded(getattr(call, "id", ""), 300), _bounded(getattr(call, "name", ""), 300),
            "unparsed" if isinstance(getattr(call, "arguments", None), dict) and
            "_unparsed" in getattr(call, "arguments", {}) else
            "decoded" if isinstance(getattr(call, "arguments", None), dict) else "unavailable",
        ) for call in reply.tool_calls)
        result = InvocationResult(
            plan.plan_id, plan.config_hash, plan.adapter_id, plan.adapter_version,
            plan.model_id, _bounded(reply.model, 300),
            "tool_calls" if calls else "completed", _bounded(reply.stop, 160),
            round((time.monotonic() - started) * 1_000), calls,
            usage=_safe_usage(reply.usage), request_id=_safe_request_id(reply.request_id),
        )
        return reply, result


class AdapterRegistry:
    """Small trusted adapter family; model packs select only from this set."""

    def __init__(self, descriptors: tuple[AdapterDescriptor, ...] | None = None) -> None:
        rows = descriptors or (LEGACY_OPENAI_CHAT, LEGACY_ANTHROPIC_MESSAGES, LEGACY_PROVIDER_CHAT)
        self._descriptors = {row.id: row for row in rows}

    def get(self, adapter_id: str) -> AdapterDescriptor:
        try:
            return self._descriptors[adapter_id]
        except KeyError as exc:
            raise KeyError(f"no trusted model adapter {adapter_id!r}") from exc

    def for_provider(self, provider: Provider) -> AdapterDescriptor:
        carrier: Any = provider
        host = getattr(carrier, "host", None)
        seen: set[int] = set()
        while getattr(carrier, "provider", None) is not None and id(carrier) not in seen:
            seen.add(id(carrier))
            carrier = getattr(carrier, "provider")
        protocol = _slug(getattr(host, "protocol", ""), "") if host is not None else ""
        if protocol == "anthropic" or isinstance(carrier, Anthropic):
            return LEGACY_ANTHROPIC_MESSAGES
        if protocol == "openai" or isinstance(carrier, OpenAICompatible):
            return LEGACY_OPENAI_CHAT
        return LEGACY_PROVIDER_CHAT


def _resolve_plan(scope: InvocationScope, binding: InvocationBinding,
                  payload: InvocationPayload, *, plan_id: str,
                  pack_error: str = "") -> tuple[InvocationPlan, CompatibilityResult]:
    descriptor, route, expectation = binding.descriptor, binding.route, binding.expectation
    errors: list[str] = []
    warnings: list[str] = [pack_error] if pack_error else []
    if descriptor.abi_version != ADAPTER_ABI_VERSION:
        errors.append("adapter ABI is not supported by this Core")
    if expectation is not None:
        if expectation.adapter_id != descriptor.id or expectation.adapter_abi != descriptor.abi_version:
            errors.append("expectation record targets a different adapter contract")
        if scope.behavior_mode not in expectation.behavior_modes:
            errors.append(f"behaviour mode {scope.behavior_mode!r} is not reviewed for this route")
    elif scope.behavior_mode != "provider_default":
        errors.append(f"behaviour mode {scope.behavior_mode!r} needs a reviewed model expectation")
    for capability in sorted(scope.task.required_capabilities):
        if not descriptor.supports(capability):
            errors.append(f"adapter {descriptor.id!r} cannot provide {capability!r}")
            continue
        state = expectation.capability(capability) if expectation is not None else "unknown"
        if state == "false":
            errors.append(f"the model expectation explicitly does not support {capability!r}")
        elif state == "unknown":
            warnings.append(f"{capability!r} is not yet verified for this exact route")
    if expectation is None:
        warnings.append("no reviewed model expectation matches this exact route")
    if expectation is not None and expectation.status != "reviewed":
        warnings.append(f"expectation {expectation.id!r} is {expectation.status}")
    compatibility = CompatibilityResult(
        accepted=not errors,
        disposition="incompatible" if errors else "experimental" if warnings else "compatible",
        errors=tuple(errors), warnings=tuple(warnings),
        expectation_id=expectation.id if expectation is not None else "",
    )
    plan = InvocationPlan(
        plan_id=plan_id, adapter_id=descriptor.id, adapter_version=descriptor.version,
        adapter_abi=descriptor.abi_version, protocol=descriptor.protocol,
        host_id=route.host_id, endpoint_fingerprint=route.endpoint_fingerprint,
        model_id=route.model_id, role=scope.role, task_id=scope.task.id,
        task_kind=scope.task.kind, interaction=scope.task.interaction,
        phase=scope.phase, session_id=scope.session_id,
        output_contract=scope.task.output_contract,
        required_capabilities=tuple(scope.task.required_capabilities),
        tool_schema_fingerprint=tool_contract_fingerprint(payload.tools),
        max_output_tokens=payload.max_tokens, behavior_mode=scope.behavior_mode,
        reasoning_intent=scope.reasoning_intent,
        dialect=tuple(sorted((k, v) for k, v in effective_dialect(expectation).items()
                             if v != "provider_default")),
        expectation_id=expectation.id if expectation is not None else "",
        expectation_fingerprint=expectation.fingerprint if expectation is not None else "",
    )
    return plan, compatibility


def _model_identity_mismatch_compatibility(
        compatibility: CompatibilityResult) -> CompatibilityResult:
    """Return the post-response compatibility decision for a route mismatch.

    Plan resolution can only validate the route the caller selected.  The
    provider's returned identity is evidence that arrives after spend, so it
    must turn that provisional decision into an explicit incompatibility
    before a Reply can reach the Loop or a tool executor.
    """
    return CompatibilityResult(
        accepted=False,
        disposition="incompatible",
        errors=(*compatibility.errors,
                "the provider returned a model identity that does not match the selected route"),
        warnings=compatibility.warnings,
        expectation_id=compatibility.expectation_id,
    )


def _model_identity_mismatch_result(result: InvocationResult) -> InvocationResult:
    """Keep safe response evidence while making the Core-visible outcome fail."""
    return replace(
        result,
        outcome="failed",
        failure=AdapterFailure(
            "model_identity_mismatch", False,
            "the provider returned a different model than the selected route",
        ),
    )


class InvocationRuntime:
    """Resolve and trace one model invocation at a time, safely across threads.

    The ContextVar is useful for compatibility facades and background work,
    but normal callers should pass an explicit scope.  The in-memory trace is
    bounded and contains only ``InvocationPlan.trace``/``InvocationResult.trace``
    values, so it cannot turn a research vault into a raw prompt archive.
    """

    def __init__(self, *, adapters: AdapterRegistry | None = None,
                 expectations: ExpectationRegistry | None = None,
                 trace_sink: Callable[[dict[str, Any]], None] | None = None,
                 max_records: int = 200,
                 id_factory: Callable[[], str] | None = None) -> None:
        self.adapters = adapters or AdapterRegistry()
        self.expectations = expectations or ExpectationRegistry.active()
        self.trace_sink = trace_sink
        self._scope: ContextVar[InvocationScope | None] = ContextVar("librarian_invocation_scope", default=None)
        self._records: deque[dict[str, Any]] = deque(maxlen=max(1, int(max_records)))
        self._lock = threading.Lock()
        self._id_factory = id_factory or (lambda: secrets.token_hex(10))

    @contextmanager
    def bind_scope(self, scope: InvocationScope) -> Iterator[None]:
        token = self._scope.set(scope)
        try:
            yield
        finally:
            self._scope.reset(token)

    def binding_for(self, provider: Provider) -> InvocationBinding:
        descriptor = self.adapters.for_provider(provider)
        route = ExactRoute.from_provider(provider)
        return InvocationBinding(route, descriptor, self.expectations.match(route, descriptor))

    def adapter_summary(self, provider: Provider, *, model_id: str = "") -> dict[str, Any]:
        """Return passive, non-secret model-tile information.

        This does not discover models, queue qualification, contact a
        provider, or alter a route.  It is intentionally small enough for the
        existing picker to render later without becoming a second selection
        system.
        """
        binding = self.binding_for(provider)
        route = binding.route
        if _bounded(model_id, 300):
            route = ExactRoute(route.host_id, route.protocol, route.endpoint_fingerprint,
                               _bounded(model_id, 300))
        expectation = self.expectations.match(route, binding.descriptor)
        # A wildcard protocol baseline describes the Core renderer, not the
        # selected model.  Do not let the picker call that a model-specific
        # reviewed expectation.  Wildcard records can still constrain the
        # resolver (for example an explicitly unsafe protocol feature), but
        # only an exact model record is presented as evidence for a tile.
        exact_expectation = expectation if expectation is not None and expectation.model_id != "*" else None
        capabilities = {name: exact_expectation.capability(name) if exact_expectation is not None else "unknown"
                        for name in sorted(CAPABILITIES)}
        return {
            "id": binding.descriptor.id, "version": binding.descriptor.version,
            "abi": binding.descriptor.abi_version, "protocol": binding.descriptor.protocol,
            "default_behavior": "provider_default",
            "expectation": {
                "id": exact_expectation.id if exact_expectation is not None else "",
                "status": exact_expectation.status if exact_expectation is not None else "unreviewed",
                "fingerprint": exact_expectation.fingerprint if exact_expectation is not None else "",
            },
            "capabilities": capabilities,
            "pack": {"ok": not self.expectations.load_error,
                     "error": self.expectations.load_error},
        }

    def plan_for(self, provider: Provider, payload: InvocationPayload, *,
                 scope: InvocationScope | None = None,
                 binding: InvocationBinding | None = None) -> tuple[InvocationPlan, CompatibilityResult, InvocationBinding]:
        chosen_scope = scope or self._scope.get() or InvocationScope()
        chosen_binding = binding or self.binding_for(provider)
        plan, compatibility = _resolve_plan(chosen_scope, chosen_binding, payload,
                                            plan_id=_bounded(self._id_factory(), 80) or secrets.token_hex(10),
                                            pack_error=self.expectations.load_error)
        return plan, compatibility, chosen_binding

    def _record(self, plan: InvocationPlan, result: InvocationResult,
                compatibility: CompatibilityResult) -> None:
        row = {"plan": plan.trace(), "compatibility": {
            "accepted": compatibility.accepted, "disposition": compatibility.disposition,
            "errors": list(compatibility.errors), "warnings": list(compatibility.warnings),
            "expectation_id": compatibility.expectation_id,
        }, "result": result.trace()}
        with self._lock:
            self._records.append(copy.deepcopy(row))
        if self.trace_sink is not None:
            try:
                self.trace_sink(copy.deepcopy(row))
            except Exception:  # noqa: BLE001 - diagnostics never break a model call
                pass

    def recent(self, limit: int = 25) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(list(self._records)[-max(0, int(limit)):])

    def _blocked_model_identity(self, plan: InvocationPlan, result: InvocationResult,
                                compatibility: CompatibilityResult,
                                reply: Reply | None) -> ModelIdentityMismatchError:
        """Trace and reject a mismatched response before it reaches Core work.

        The route was valid before the provider call, but a different returned
        model cannot consume that route's expectation or qualification
        evidence.  Recording the final incompatibility here makes the
        post-response policy decision auditable rather than leaving a warning
        beside a Reply that the Loop might still execute tools from.
        """
        final_compatibility = _model_identity_mismatch_compatibility(compatibility)
        final_result = _model_identity_mismatch_result(result)
        self._record(plan, final_result, final_compatibility)
        return ModelIdentityMismatchError(final_compatibility, final_result, reply)

    def invoke(self, provider: Provider, payload: InvocationPayload, *,
               scope: InvocationScope | None = None,
               binding: InvocationBinding | None = None,
               cancel: threading.Event | None = None) -> Reply:
        plan, compatibility, chosen_binding = self.plan_for(provider, payload, scope=scope,
                                                             binding=binding)
        if not compatibility.accepted:
            failure = AdapterFailure("route_configuration", False,
                                     "the selected route is incompatible with this task")
            result = InvocationResult(plan.plan_id, plan.config_hash, plan.adapter_id,
                                      plan.adapter_version, plan.model_id, "", "failed", "", 0,
                                      failure=failure, model_identity="not_applicable")
            self._record(plan, result, compatibility)
            raise InvocationCompatibilityError(compatibility)
        adapter = LegacyProviderAdapter(chosen_binding.descriptor)
        try:
            reply, result = adapter.invoke(plan, payload, provider, cancel=cancel)
        except ProviderError as error:
            result = getattr(error, "invocation_result", None)
            if not isinstance(result, InvocationResult):
                result = InvocationResult(
                    plan.plan_id, plan.config_hash, plan.adapter_id, plan.adapter_version,
                    plan.model_id, "", "failed", "", 0,
                    failure=AdapterFailure.from_error(error),
                )
            if result.model_identity == "mismatched":
                raise self._blocked_model_identity(plan, result, compatibility, None) from error
            self._record(plan, result, compatibility)
            raise
        if result.model_identity == "mismatched":
            raise self._blocked_model_identity(plan, result, compatibility, reply)
        self._record(plan, result, compatibility)
        return reply


class AdapterBackedProvider(Provider):
    """Optional backwards-compatible Provider facade for integrations.

    The Core loop uses :class:`InvocationRuntime` directly so it can pin a
    binding for a whole walk.  This facade is for a caller that has the same
    legacy ``Provider`` surface but wants the adapter trace.  It exposes
    ``replace_provider`` explicitly: application code must not cache a stale
    selected route when the person chooses another model.
    """

    def __init__(self, provider: Provider, runtime: InvocationRuntime | None = None,
                 scope: InvocationScope | None = None) -> None:
        self.provider = provider
        self.runtime = runtime or InvocationRuntime()
        self.scope = scope
        self.name, self.model = provider.name, provider.model

    def replace_provider(self, provider: Provider) -> None:
        self.provider = provider
        self.name, self.model = provider.name, provider.model

    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolDef],
             max_tokens: int = 4096, temperature: float | None = None) -> Reply:
        return self.chat_cancellable(system, messages, tools, max_tokens=max_tokens,
                                     temperature=temperature)

    def chat_cancellable(self, system: str, messages: list[dict[str, Any]],
                         tools: list[ToolDef], max_tokens: int = 4096,
                         temperature: float | None = None,
                         cancel: threading.Event | None = None) -> Reply:
        payload = InvocationPayload.from_legacy(system, messages, tools,
                                                max_tokens=max_tokens, temperature=temperature)
        return self.runtime.invoke(self.provider, payload, scope=self.scope, cancel=cancel)

    def models(self) -> list[str]:
        return self.provider.models()

    def usage(self) -> dict[str, Any]:
        return self.provider.usage()

    def check(self) -> dict[str, Any]:
        return self.provider.check()
