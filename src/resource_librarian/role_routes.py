"""Vault-scoped, non-secret bindings from a role to one model route.

The older three-position picker remains a 2.x compatibility projection.  This
store is deliberately narrower: it records which route a role is meant to
use, but it never holds provider credentials, starts a provider, or decides
whether a route is qualified.  Those decisions stay with ``App``,
``HostRegistry`` and the qualification store.

Mutating callers must serialize ``save`` through ``VaultWriter``.  The store
does not own a writer because it is also used by offline/direct callers and a
nested writer submission would deadlock a coordinated Core.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from .coordination import atomic_write_text
from .vault import Vault, now_iso


SCHEMA_VERSION = 1
ROLES = ("lead", "scribe", "clerk", "research_helper", "ocr", "tts", "stt", "embeddings")
CHAT_ROLES = ("lead", "scribe", "clerk", "research_helper")
SOURCES = frozenset({"explicit", "legacy_tier", "legacy_service", "inherited", "unconfigured"})
_FIELDS = frozenset({"role", "host_id", "model_id", "protocol", "endpoint_fingerprint",
                     "adapter_id", "evidence_kind", "source", "inherits_from", "revision",
                     "updated_at"})


class RoleRouteStoreError(ValueError):
    """A route binding is absent, malformed, or cannot be resolved safely."""


@dataclass(frozen=True)
class RoleRouteBinding:
    """Non-secret route facts for a single role.

    A binding with ``inherits_from`` intentionally contains no route facts.
    That makes legacy tier fallback explicit while allowing a later Lead
    change to flow to an unconfigured Scribe or Clerk without replacing an
    independently selected binding.
    """

    role: str
    host_id: str = ""
    model_id: str = ""
    protocol: str = ""
    endpoint_fingerprint: str = ""
    adapter_id: str = ""
    evidence_kind: str = ""
    source: str = "explicit"
    inherits_from: str = ""
    revision: int = 1
    updated_at: str = ""

    def public(self) -> dict[str, Any]:
        """A non-secret JSON-ready view for Core state and adapter metadata."""
        return asdict(self)


class RoleRouteStore:
    """Strict versioned persistence for canonical role-route bindings."""

    def __init__(self, vault: Vault):
        self.vault = vault
        self.path = vault.librarian / "agents" / "routes.json"

    def exists(self) -> bool:
        """Whether any path occupies the binding-store location.

        ``exists`` deliberately treats a directory collision as existing so
        ``initialize_if_absent`` cannot overwrite an unexpected state path.
        ``raw`` then reports the collision as a fail-closed error.
        """
        return self.path.exists()

    def raw(self) -> dict[str, RoleRouteBinding]:
        """Load and fully validate persisted bindings.

        A missing store means no vault-local choice has been made yet and is
        the only condition that permits legacy migration.  A present but
        unreadable, incompatible, cyclic, or incomplete store is an error;
        silently reconstructing it could reroute a model without a person.
        """
        if not self.path.exists():
            return {}
        if not self.path.is_file():
            raise RoleRouteStoreError("role route store exists but is not a file")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RoleRouteStoreError("role route store is unreadable or invalid JSON") from exc
        rows = self._decode_payload(payload)
        self._validate_graph(rows)
        return rows

    def resolve(self, role: str, rows: Mapping[str, RoleRouteBinding] | None = None
                ) -> RoleRouteBinding | None:
        """Resolve a role through persisted inheritance without route fallback.

        ``None`` means the requested role is not bound at all.  An inherited
        target that is missing, cyclic, or malformed is a fail-closed error.
        The returned row's role is always the *requested* role so callers do
        not accidentally apply Lead qualification/policy to Clerk work.
        """
        self._require_role(role, "role")
        current = self.raw() if rows is None else self._validate_rows(rows)
        wanted, seen = role, set()
        while True:
            if wanted in seen:
                chain = " -> ".join([*sorted(seen), wanted])
                raise RoleRouteStoreError(f"role route inheritance cycle: {chain}")
            seen.add(wanted)
            binding = current.get(wanted)
            if binding is None:
                if wanted == role:
                    return None
                raise RoleRouteStoreError(
                    f"role route {role!r} inherits from missing role {wanted!r}")
            if not binding.inherits_from:
                return replace(binding, role=role)
            wanted = binding.inherits_from

    def save(self, rows: Mapping[str, RoleRouteBinding]) -> dict[str, RoleRouteBinding]:
        """Atomically replace the complete binding set after strict validation."""
        bindings = self._validate_rows(rows)
        self._validate_graph(bindings)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "bindings": {role: asdict(binding) for role, binding in sorted(bindings.items())},
        }
        atomic_write_text(self.path, json.dumps(payload, indent=2, ensure_ascii=False,
                                                 sort_keys=True) + "\n")
        return dict(bindings)

    def initialize_if_absent(self, rows: Mapping[str, RoleRouteBinding]
                             ) -> dict[str, RoleRouteBinding]:
        """Persist migration rows only when no store exists yet.

        Callers hold the vault writer when coordinated.  This method does not
        try to repair an existing file: a person should inspect a corrupt
        route store rather than have an implicit migration erase evidence.
        """
        if self.exists():
            return self.raw()
        prepared = {
            role: replace(binding, updated_at=binding.updated_at or now_iso())
            for role, binding in self._validate_rows(rows).items()
        }
        return self.save(prepared)

    @staticmethod
    def _text(value: Any, field: str, *, limit: int = 300) -> str:
        if not isinstance(value, str):
            raise RoleRouteStoreError(f"role route {field!r} must be a string")
        if value != value.strip() or "\x00" in value or len(value) > limit:
            raise RoleRouteStoreError(f"role route {field!r} is invalid")
        return value

    @classmethod
    def _require_role(cls, value: Any, field: str) -> str:
        role = cls._text(value, field, limit=80)
        if role not in ROLES:
            raise RoleRouteStoreError(f"role route {field!r} is not a known role: {role!r}")
        return role

    @classmethod
    def _validate_binding(cls, binding: RoleRouteBinding) -> RoleRouteBinding:
        if not isinstance(binding, RoleRouteBinding):
            raise RoleRouteStoreError("role route row is not a RoleRouteBinding")
        role = cls._require_role(binding.role, "role")
        values = {
            field: cls._text(getattr(binding, field), field)
            for field in ("host_id", "model_id", "protocol", "endpoint_fingerprint", "adapter_id",
                          "evidence_kind", "inherits_from", "updated_at")
        }
        source = cls._text(binding.source, "source", limit=80)
        if source not in SOURCES:
            raise RoleRouteStoreError(f"role route source is not supported: {source!r}")
        try:
            revision = int(binding.revision)
        except (TypeError, ValueError) as exc:
            raise RoleRouteStoreError("role route revision must be an integer") from exc
        if isinstance(binding.revision, bool) or revision < 1 or revision > 1_000_000:
            raise RoleRouteStoreError("role route revision is invalid")
        inherited = values["inherits_from"]
        if inherited:
            cls._require_role(inherited, "inherits_from")
            if inherited == role:
                raise RoleRouteStoreError(f"role route {role!r} cannot inherit from itself")
            route_values = (values["host_id"], values["model_id"], values["protocol"],
                            values["endpoint_fingerprint"], values["adapter_id"],
                            values["evidence_kind"])
            if any(route_values):
                raise RoleRouteStoreError(
                    f"inherited role route {role!r} cannot also contain route facts")
            if source != "inherited":
                raise RoleRouteStoreError(
                    f"inherited role route {role!r} must use source 'inherited'")
        return RoleRouteBinding(role=role, source=source, revision=revision, **values)

    @classmethod
    def _validate_rows(cls, rows: Mapping[str, RoleRouteBinding]) -> dict[str, RoleRouteBinding]:
        if not isinstance(rows, Mapping):
            raise RoleRouteStoreError("role route bindings must be an object")
        validated: dict[str, RoleRouteBinding] = {}
        for key, row in rows.items():
            role = cls._require_role(key, "binding key")
            binding = cls._validate_binding(row)
            if binding.role != role:
                raise RoleRouteStoreError(
                    f"role route key {role!r} does not match row role {binding.role!r}")
            validated[role] = binding
        return validated

    @classmethod
    def _decode_payload(cls, payload: Any) -> dict[str, RoleRouteBinding]:
        if not isinstance(payload, dict) or set(payload) != {"schema_version", "bindings"}:
            raise RoleRouteStoreError("role route store has an unsupported payload shape")
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise RoleRouteStoreError("role route store schema version is unsupported")
        raw_rows = payload.get("bindings")
        if not isinstance(raw_rows, dict):
            raise RoleRouteStoreError("role route store bindings must be an object")
        rows: dict[str, RoleRouteBinding] = {}
        for key, raw in raw_rows.items():
            role = cls._require_role(key, "binding key")
            if not isinstance(raw, dict) or set(raw) != _FIELDS:
                raise RoleRouteStoreError(f"role route {role!r} has unknown or missing fields")
            try:
                row = RoleRouteBinding(**raw)
            except TypeError as exc:
                raise RoleRouteStoreError(f"role route {role!r} is malformed") from exc
            rows[role] = cls._validate_binding(row)
            if rows[role].role != role:
                raise RoleRouteStoreError(
                    f"role route key {role!r} does not match row role {rows[role].role!r}")
        return rows

    @classmethod
    def _validate_graph(cls, rows: Mapping[str, RoleRouteBinding]) -> None:
        """Resolve every stored row once so a present bad file fails on load."""
        checked = cls._validate_rows(rows)
        for role in checked:
            # Avoid ``raw`` recursion by passing the already validated rows.
            cls._resolve_checked(role, checked)

    @classmethod
    def _resolve_checked(cls, role: str, rows: Mapping[str, RoleRouteBinding]) -> RoleRouteBinding | None:
        wanted, seen = role, []
        while True:
            if wanted in seen:
                chain = " -> ".join([*seen, wanted])
                raise RoleRouteStoreError(f"role route inheritance cycle: {chain}")
            seen.append(wanted)
            binding = rows.get(wanted)
            if binding is None:
                if wanted == role:
                    return None
                raise RoleRouteStoreError(
                    f"role route {role!r} inherits from missing role {wanted!r}")
            if not binding.inherits_from:
                return replace(binding, role=role)
            wanted = binding.inherits_from
