"""Typed, evidence-backed adapters for non-chat model services.

Agent chat is deliberately handled by :mod:`model_invocation`.  OCR, text to
speech, speech to text and embeddings have different request/response
contracts, so treating their model cards as if they were chat prompts was both
misleading and unsafe.  This module is the small, declarative service boundary:

* packs contain only reviewed identifiers and fixed protocol facts;
* adapters own the request shape -- a pack cannot inject arbitrary parameters;
* a representation policy is part of an embedding namespace, so vectors
  produced with different model-card prefixes are never mixed; and
* unknown models remain selectable where legacy UX allowed them, but are
  explicitly unreviewed rather than silently treated as compatible.

The module contains no credentials, vault authority, prompt text, or transport
implementation.  Individual service modules retain their existing cost,
cache, retry, and file-handling policies.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from importlib import resources
from typing import Any, Mapping


SERVICE_ADAPTER_ABI_VERSION = 1
SERVICE_EXPECTATION_SCHEMA_VERSION = 1
SERVICE_KINDS = frozenset({"ocr", "tts", "stt", "embeddings"})
STATUSES = frozenset({"reviewed", "observed", "unreviewed", "deprecated"})


class ServiceContractError(ValueError):
    """A service cannot safely use the selected provider/model contract."""


def _compact(value: Any, limit: int = 500) -> str:
    return str(value or "").replace("\x00", "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def _prefix(value: Any, limit: int = 800) -> str:
    """Retain intentional spacing in a reviewed embedding representation.

    Prefixes are fixed declarative literals, not free-form prompt templates.
    A trailing separator (for example ``"query: "``) is semantically part of
    the model-card representation and must not be erased by generic field
    normalization.
    """
    return str(value or "").replace("\x00", "").replace("\r", " ").replace("\n", " ")[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any, length: int = 16) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:length]


@dataclass(frozen=True)
class ServiceAdapterDescriptor:
    id: str
    version: str
    abi_version: int
    services: tuple[str, ...]

    @property
    def fingerprint(self) -> str:
        return _digest({"id": self.id, "version": self.version, "abi": self.abi_version,
                        "services": self.services})


DESCRIPTORS: dict[str, ServiceAdapterDescriptor] = {
    "openai_vision_chat_v1": ServiceAdapterDescriptor(
        "openai_vision_chat_v1", "1", SERVICE_ADAPTER_ABI_VERSION, ("ocr",)),
    "deepinfra_inference_tts_v1": ServiceAdapterDescriptor(
        "deepinfra_inference_tts_v1", "1", SERVICE_ADAPTER_ABI_VERSION, ("tts",)),
    "deepinfra_inference_stt_v1": ServiceAdapterDescriptor(
        "deepinfra_inference_stt_v1", "1", SERVICE_ADAPTER_ABI_VERSION, ("stt",)),
    "openai_embeddings_v1": ServiceAdapterDescriptor(
        "openai_embeddings_v1", "1", SERVICE_ADAPTER_ABI_VERSION, ("embeddings",)),
}


@dataclass(frozen=True)
class ServiceExpectation:
    """A compact, non-executable record from the shipped service pack."""

    id: str
    version: str
    status: str
    service: str
    provider: str
    model_id: str
    adapter_id: str
    adapter_abi: int
    request_shape: str
    response_shape: str
    input_field: str = ""
    output_format: str = ""
    default_voice: str = ""
    representation_version: str = ""
    document_prefix: str = ""
    query_prefix: str = ""
    dimension: int = 0
    max_input_tokens: int = 0
    price_per_million: float | None = None
    price_as_of: str = ""
    price_expires_on: str = ""
    source_url: str = ""
    source_revision: str = ""
    l1_probe: str = ""
    fingerprint: str = ""

    def __post_init__(self) -> None:
        service = _compact(self.service, 40).casefold()
        if service not in SERVICE_KINDS:
            raise ServiceContractError(f"unknown service {service!r}")
        status = _compact(self.status, 40).casefold() or "unreviewed"
        if status not in STATUSES:
            raise ServiceContractError(f"unknown service expectation status {status!r}")
        if self.adapter_id not in DESCRIPTORS:
            raise ServiceContractError(f"unknown trusted service adapter {self.adapter_id!r}")
        descriptor = DESCRIPTORS[self.adapter_id]
        if self.adapter_abi != descriptor.abi_version:
            raise ServiceContractError("service expectation targets an unsupported adapter ABI")
        if service not in descriptor.services:
            raise ServiceContractError("service expectation targets an adapter for another service")
        object.__setattr__(self, "service", service)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "provider", _compact(self.provider, 120).casefold() or "*")
        object.__setattr__(self, "model_id", _compact(self.model_id, 300) or "*")
        object.__setattr__(self, "request_shape", _compact(self.request_shape, 120))
        object.__setattr__(self, "response_shape", _compact(self.response_shape, 120))
        object.__setattr__(self, "input_field", _compact(self.input_field, 80))
        object.__setattr__(self, "output_format", _compact(self.output_format, 80))
        object.__setattr__(self, "default_voice", _compact(self.default_voice, 120))
        object.__setattr__(self, "representation_version",
                           _compact(self.representation_version, 120))
        object.__setattr__(self, "document_prefix", _prefix(self.document_prefix, 800))
        object.__setattr__(self, "query_prefix", _prefix(self.query_prefix, 800))
        object.__setattr__(self, "dimension", max(0, int(self.dimension or 0)))
        object.__setattr__(self, "max_input_tokens", max(0, int(self.max_input_tokens or 0)))
        if self.price_per_million is not None:
            object.__setattr__(self, "price_per_million", max(0.0, float(self.price_per_million)))
        object.__setattr__(self, "price_as_of", _compact(self.price_as_of, 32))
        object.__setattr__(self, "price_expires_on", _compact(self.price_expires_on, 32))
        object.__setattr__(self, "source_url", _compact(self.source_url, 1_000))
        object.__setattr__(self, "source_revision", _compact(self.source_revision, 300))
        object.__setattr__(self, "l1_probe", _compact(self.l1_probe, 200))
        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", _digest({
                "id": self.id, "version": self.version, "status": self.status,
                "service": self.service, "provider": self.provider, "model": self.model_id,
                "adapter": self.adapter_id, "abi": self.adapter_abi,
                "request": self.request_shape, "response": self.response_shape,
                "input": self.input_field, "format": self.output_format,
                "voice": self.default_voice, "representation": self.representation_version,
                "document_prefix": self.document_prefix, "query_prefix": self.query_prefix,
                "dimension": self.dimension, "max_input_tokens": self.max_input_tokens,
                "price": self.price_per_million, "price_as_of": self.price_as_of,
                "price_expires": self.price_expires_on, "source": self.source_url,
                "source_revision": self.source_revision, "l1_probe": self.l1_probe,
            }))

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "ServiceExpectation":
        allowed = {
            "id", "version", "status", "service", "provider", "model_id", "adapter_id",
            "adapter_abi", "request_shape", "response_shape", "input_field",
            "output_format", "default_voice", "representation_version", "document_prefix",
            "query_prefix", "dimension", "max_input_tokens", "price_per_million",
            "price_as_of", "price_expires_on", "source_url", "source_revision", "l1_probe",
        }
        extra = sorted(set(row) - allowed)
        if extra:
            raise ServiceContractError("unsupported service expectation field: " + ", ".join(extra))
        return cls(
            id=_compact(row.get("id"), 120) or "service-expectation",
            version=_compact(row.get("version"), 80) or "1",
            status=_compact(row.get("status"), 40) or "unreviewed",
            service=_compact(row.get("service"), 40),
            provider=_compact(row.get("provider"), 120) or "*",
            model_id=_compact(row.get("model_id"), 300) or "*",
            adapter_id=_compact(row.get("adapter_id"), 120),
            adapter_abi=int(row.get("adapter_abi") or SERVICE_ADAPTER_ABI_VERSION),
            request_shape=_compact(row.get("request_shape"), 120),
            response_shape=_compact(row.get("response_shape"), 120),
            input_field=_compact(row.get("input_field"), 80),
            output_format=_compact(row.get("output_format"), 80),
            default_voice=_compact(row.get("default_voice"), 120),
            representation_version=_compact(row.get("representation_version"), 120),
            document_prefix=_prefix(row.get("document_prefix"), 800),
            query_prefix=_prefix(row.get("query_prefix"), 800),
            dimension=row.get("dimension") or 0,
            max_input_tokens=row.get("max_input_tokens") or 0,
            price_per_million=row.get("price_per_million"),
            price_as_of=_compact(row.get("price_as_of"), 32),
            price_expires_on=_compact(row.get("price_expires_on"), 32),
            source_url=_compact(row.get("source_url"), 1_000),
            source_revision=_compact(row.get("source_revision"), 300),
            l1_probe=_compact(row.get("l1_probe"), 200),
        )

    def price_is_current(self, today: date | None = None) -> bool:
        if self.price_per_million is None:
            return False
        if not self.price_expires_on:
            return False
        try:
            expiry = date.fromisoformat(self.price_expires_on)
            return (today or date.today()) <= expiry
        except ValueError:
            return False


@dataclass(frozen=True)
class ServiceBinding:
    service: str
    provider: str
    model_id: str
    descriptor: ServiceAdapterDescriptor | None
    expectation: ServiceExpectation | None

    @property
    def reviewed(self) -> bool:
        return bool(self.expectation and self.expectation.status == "reviewed")

    @property
    def status(self) -> str:
        return self.expectation.status if self.expectation else "unreviewed"

    @property
    def adapter_id(self) -> str:
        return self.descriptor.id if self.descriptor else ""

    def summary(self) -> dict[str, Any]:
        record = self.expectation
        return {
            "service": self.service, "provider": self.provider, "model": self.model_id,
            "status": self.status, "adapter": {
                "id": self.adapter_id,
                "version": self.descriptor.version if self.descriptor else "",
                "abi": self.descriptor.abi_version if self.descriptor else 0,
            },
            "expectation_id": record.id if record else "",
            "request_shape": record.request_shape if record else "",
            "response_shape": record.response_shape if record else "",
            "source_url": record.source_url if record else "",
            "l1_probe": record.l1_probe if record else "",
        }


class ServiceAdapterRegistry:
    """Read-only registry of first-party service contracts."""

    def __init__(self, records: tuple[ServiceExpectation, ...] = ()) -> None:
        self.records = tuple(records)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ServiceAdapterRegistry":
        if not isinstance(payload, Mapping):
            raise ServiceContractError("service expectation pack is an object")
        if int(payload.get("schema_version") or 0) != SERVICE_EXPECTATION_SCHEMA_VERSION:
            raise ServiceContractError(
                f"service expectation pack schema is {SERVICE_EXPECTATION_SCHEMA_VERSION}")
        rows = payload.get("records")
        if not isinstance(rows, list):
            raise ServiceContractError("service expectation pack records is a list")
        records = tuple(ServiceExpectation.from_row(row) for row in rows if isinstance(row, Mapping))
        if len(records) != len(rows):
            raise ServiceContractError("service expectation record is an object")
        ids = [row.id for row in records]
        if len(ids) != len(set(ids)):
            raise ServiceContractError("service expectation ids are unique")
        return cls(records)

    @classmethod
    def bundled(cls) -> "ServiceAdapterRegistry":
        try:
            node = resources.files("resource_librarian").joinpath(
                "standard", "service_expectations", "core.json")
            return cls.from_payload(json.loads(node.read_text(encoding="utf-8")))
        except (FileNotFoundError, ModuleNotFoundError):
            return cls()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            # A broken evidence pack must never fabricate compatibility.
            return cls()

    def resolve(self, service: str, provider: str, model_id: str) -> ServiceBinding:
        kind = _compact(service, 40).casefold()
        if kind not in SERVICE_KINDS:
            raise ServiceContractError(f"unknown service {service!r}")
        provider_key = _compact(provider, 120).casefold()
        model = _compact(model_id, 300)
        candidates: list[tuple[tuple[int, int], ServiceExpectation]] = []
        for row in self.records:
            if row.status == "deprecated" or row.service != kind:
                continue
            provider_exact = row.provider == provider_key
            model_exact = row.model_id.casefold() == model.casefold()
            if row.provider != "*" and not provider_exact:
                continue
            if row.model_id != "*" and not model_exact:
                continue
            candidates.append(((int(provider_exact), int(model_exact)), row))
        expectation = max(candidates, key=lambda item: item[0])[1] if candidates else None
        descriptor = DESCRIPTORS.get(expectation.adapter_id) if expectation else None
        return ServiceBinding(kind, provider_key, model, descriptor, expectation)


_BUNDLED: ServiceAdapterRegistry | None = None


def registry() -> ServiceAdapterRegistry:
    global _BUNDLED
    if _BUNDLED is None:
        _BUNDLED = ServiceAdapterRegistry.bundled()
    return _BUNDLED


def binding(service: str, provider: str, model_id: str) -> ServiceBinding:
    return registry().resolve(service, provider, model_id)


def require_binding(service: str, provider: str, model_id: str) -> ServiceBinding:
    row = binding(service, provider, model_id)
    if row.descriptor is None or row.expectation is None:
        raise ServiceContractError(
            f"{provider}:{model_id} has no reviewed {service} adapter contract")
    return row


def ocr_request(provider: str, model_id: str, prompt: str, image_url: str,
                *, max_tokens: int = 4_000) -> tuple[dict[str, Any], ServiceBinding]:
    """Build the only OCR request shape V2 currently supports."""
    row = binding("ocr", provider, model_id)
    if row.descriptor is not None and row.descriptor.id != "openai_vision_chat_v1":
        raise ServiceContractError("selected OCR model has a non-vision-chat adapter")
    return ({
        "model": model_id, "temperature": 0, "max_tokens": max(1, int(max_tokens)),
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]}],
    }, row)


def tts_request(provider: str, model_id: str, text: str) -> tuple[dict[str, Any], ServiceBinding]:
    """Build a reviewed DeepInfra native-inference TTS body.

    This intentionally has no speculative alternate-field retry.  A provider
    schema drift is a visible adapter/probe issue, not an extra paid request.
    """
    row = require_binding("tts", provider, model_id)
    contract = row.expectation
    assert contract is not None
    if row.descriptor is None or row.descriptor.id != "deepinfra_inference_tts_v1":
        raise ServiceContractError("selected TTS model has an unsupported adapter")
    if contract.input_field not in {"text", "input"}:
        raise ServiceContractError("TTS adapter has no safe input field")
    body: dict[str, Any] = {contract.input_field: text,
                            "output_format": contract.output_format or "mp3"}
    if contract.default_voice:
        body["preset_voice"] = contract.default_voice
    return body, row


def embedding_input(provider: str, model_id: str, text: str, *, kind: str,
                    title: str = "") -> tuple[str, ServiceBinding]:
    """Render one document or query under a model-specific representation."""
    if kind not in {"document", "query"}:
        raise ServiceContractError("embedding input kind is document or query")
    row = binding("embeddings", provider, model_id)
    contract = row.expectation
    if contract is None or not contract.representation_version:
        return text, row
    prefix = contract.document_prefix if kind == "document" else contract.query_prefix
    # A document title is deliberately not interpolated into a pack-defined
    # format: the current Core has no reliable per-chunk title contract.  The
    # explicit default title in the reviewed EmbeddingGemma record is safe.
    return prefix + text, row


def embedding_namespace(spec: str, provider: str, model_id: str) -> tuple[str, ServiceBinding]:
    """Return the stored-vector namespace for an embedding representation.

    A prefix or dimensional contract change must trigger a full re-embed.
    The raw configured spec remains unchanged for request routing/UI.
    """
    row = binding("embeddings", provider, model_id)
    contract = row.expectation
    if contract is None or not contract.representation_version:
        return spec, row
    tag = _digest({
        "adapter": row.adapter_id, "adapter_version": row.descriptor.version if row.descriptor else "",
        "record": contract.id, "version": contract.version,
        "representation": contract.representation_version,
        "document_prefix": contract.document_prefix, "query_prefix": contract.query_prefix,
        "dimension": contract.dimension,
    }, 12)
    return f"{spec}#repr-{tag}", row

