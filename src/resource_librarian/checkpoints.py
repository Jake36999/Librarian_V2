"""Structured person checkpoints used by UI surfaces and agent prompts."""
from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .coordination import atomic_write_text
from .vault import now_iso


CHECKPOINT_TYPES = frozenset({
    "staging_promotion", "sensitive_source", "host_model_override", "cross_model_failover",
    "evaluation_spend", "macro_expansion", "write_conflict", "docker_execution",
    "non_isolated_execution", "forced_engagement_close", "operation_recovery",
})


@dataclass
class Checkpoint:
    id: str
    type: str
    scope: str
    evidence: dict[str, Any]
    choices: list[str]
    default: str
    requester: str
    created_at: str
    expires_at: str = ""
    resolution: str = ""
    resolved_at: str = ""


class CheckpointStore:
    def __init__(self, vault: Any) -> None:
        self.vault = vault
        self.path = vault.librarian / "checkpoints.json"

    def all(self, pending_only: bool = False) -> list[dict[str, Any]]:
        rows = self._load()
        if pending_only:
            rows = [row for row in rows if not row.resolution and not self._expired(row)]
        return [self._public(row) for row in rows]

    def create(self, type: str, scope: str, *, evidence: dict[str, Any] | None = None,
               choices: list[str] | None = None, requester: str = "core",
               expires_at: str = "", default: str = "") -> dict[str, Any]:
        type = str(type).strip()
        scope = str(scope).strip()
        if type not in CHECKPOINT_TYPES:
            raise ValueError(f"checkpoint type is one of {sorted(CHECKPOINT_TYPES)}")
        if not scope:
            raise ValueError("checkpoint scope is required")
        resolved_choices = list(dict.fromkeys(str(choice).strip() for choice in
                                              (choices or ["approve", "decline"])
                                              if str(choice).strip()))
        if not resolved_choices:
            raise ValueError("a checkpoint needs at least one choice")
        selected_default = str(default).strip() or resolved_choices[0]
        if selected_default not in resolved_choices:
            raise ValueError("checkpoint default must be one of its choices")
        row = Checkpoint(secrets.token_hex(8), type[:80], scope[:200], dict(evidence or {}),
                         resolved_choices, selected_default, requester[:80], now_iso(), expires_at[:40])
        rows = self._load()
        rows.append(row)
        self._save(rows)
        return self._public(row)

    def ensure(self, type: str, scope: str, **kwargs: Any) -> dict[str, Any]:
        """Return an existing pending decision for this exact operation or create one.

        A noisy adapter must not turn every render/retry into another decision
        card.  A resolved checkpoint is intentionally not reused: a later
        operation needs a fresh person decision.
        """
        for row in self._load():
            if row.type == type and row.scope == scope and not row.resolution and not self._expired(row):
                return self._public(row)
        return self.create(type, scope, **kwargs)

    def ensure_historical(self, type: str, scope: str, **kwargs: Any) -> dict[str, Any]:
        """Return the one durable disposition for a historical incident.

        Ordinary checkpoint scopes represent a fresh proposed operation, so
        ``ensure`` intentionally creates a new card after resolution.  A
        start-only writer operation is different: its resolution documents a
        past ambiguity, and recreating it on every Core restart would imply a
        new mutation.  Recovery therefore uses this separate, idempotent
        lookup which reuses both pending and resolved records.
        """
        for row in self._load():
            if row.type == type and row.scope == scope:
                return self._public(row)
        return self.create(type, scope, **kwargs)

    def get(self, checkpoint_id: str) -> dict[str, Any]:
        for row in self._load():
            if row.id == checkpoint_id:
                return self._public(row)
        raise KeyError(f"no checkpoint {checkpoint_id!r}")

    def resolve(self, checkpoint_id: str, choice: str) -> dict[str, Any]:
        rows = self._load()
        for row in rows:
            if row.id == checkpoint_id:
                if row.resolution:
                    return self._public(row)
                if self._expired(row):
                    raise ValueError("this checkpoint expired; review the current operation and create a new decision")
                if choice not in row.choices:
                    raise ValueError(f"choice is one of {row.choices}")
                row.resolution, row.resolved_at = choice, now_iso()
                self._save(rows)
                return self._public(row)
        raise KeyError(f"no checkpoint {checkpoint_id!r}")

    @staticmethod
    def _expired(row: Checkpoint, *, now: datetime | None = None) -> bool:
        """Treat malformed expiry metadata as expired rather than reusable.

        Checkpoints authorize a consequential human decision, so an adapter
        cannot keep a stale or manually-corrupted approval alive by emitting a
        bad timestamp.  Empty expiry remains intentionally non-expiring for
        durable choices such as staged promotion.
        """
        value = str(row.expires_at or "").strip()
        if not value:
            return False
        try:
            expiry = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return True
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry <= (now or datetime.now(timezone.utc))

    def _public(self, row: Checkpoint) -> dict[str, Any]:
        public = asdict(row)
        public["expired"] = self._expired(row)
        return public

    def _load(self) -> list[Checkpoint]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            rows = data.get("checkpoints", []) if isinstance(data, dict) else []
        except (OSError, ValueError):
            rows = []
        out = []
        for row in rows:
            try:
                # ``default`` was introduced after the first checkpoint
                # file format; old decisions remain readable and retain their
                # first available choice as a display default.
                if isinstance(row, dict) and "default" not in row:
                    row = {**row, "default": (row.get("choices") or [""])[0]}
                out.append(Checkpoint(**row))
            except TypeError:
                continue
        return out

    def _save(self, rows: list[Checkpoint]) -> None:
        atomic_write_text(self.path, json.dumps({"schema_version": 1,
                                                  "checkpoints": [asdict(row) for row in rows]}, indent=2,
                                                 ensure_ascii=False) + "\n")
