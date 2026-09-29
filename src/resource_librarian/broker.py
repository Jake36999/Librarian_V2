"""The permission broker: the Modes menu, enforced where every action runs.

The broker holds the current permission mode and each tool's setting, and
decides every gated action at the moment it runs (never once per reply):

| Mode | Reads | Writes | Open-web reads |
| --- | --- | --- | --- |
| plan | allowed | denied: propose, don't write | allowed |
| ask  | allowed | each one waits for a person | allowed unless the tool is set to Ask |
| auto | allowed | allowed (within tier, phase and vault settings) | allowed |

A tool setting (`allow`, `ask`, `deny`) sits on top; the strictest answer
wins, and neither can loosen anything the registry, the session or the vault
already refuses. The session harness's own tools (status, plan, questions)
are never gated, so a model in Plan mode can still plan.

**Ask** creates a pending request and the action waits on it. The surface
shows it (a `permission_request` event to every listener) and submits the
person's answer: allow once, allow for this session, or deny. **Switching mode
is an event too**: every waiting request is re-decided under the new mode, so
Auto releases what Auto permits and Plan denies waiting writes, with nothing
resubmitted. A request nobody answers expires, parks the session, and is never
approved by default.
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .registry import ToolSpec, clip
from .rules import Refusal

MODES = ("plan", "ask", "auto")
SETTINGS = ("allow", "ask", "deny")
ANSWERS = ("allow_once", "allow_session", "deny")


@dataclass
class Request:
    id: str
    tool: str
    effect: str
    summary: dict[str, str]
    session: str
    created: float
    open_world: bool = False
    event: threading.Event = field(default_factory=threading.Event)
    outcome: str = ""               # allowed | denied | expired
    reason: str = ""

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "tool": self.tool, "effect": self.effect,
                "arguments": self.summary, "session": self.session,
                "waiting_seconds": round(time.monotonic() - self.created, 1)}


class Broker:
    def __init__(self, mode: str = "ask", tool_settings: dict[str, str] | None = None,
                 timeout: float = 600.0, harness: frozenset[str] | None = None):
        if mode not in MODES:
            raise ValueError(f"mode is one of {MODES}")
        self._mode = mode
        self.settings: dict[str, str] = {}
        for tool, setting in (tool_settings or {}).items():
            self.set_tool(tool, setting)
        self.timeout = timeout
        self._lock = threading.RLock()
        self._pending: dict[str, Request] = {}
        self._session_grants: set[tuple[str, str]] = set()
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        if harness is None:
            from .session import HARNESS
            harness = HARNESS
        self.harness = harness

    # -- listening -------------------------------------------------------------
    def subscribe(self, listener: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def _emit(self, event: dict[str, Any]) -> None:
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:                               # noqa: BLE001
                pass                                        # a broken listener never blocks

    # -- settings ----------------------------------------------------------
    @property
    def mode(self) -> str:
        return self._mode

    def set_tool(self, tool: str, setting: str) -> None:
        if setting not in SETTINGS:
            raise ValueError(f"a tool setting is one of {SETTINGS}")
        self.settings[tool] = setting

    def set_mode(self, mode: str) -> dict[str, Any]:
        """Change mode and re-decide every waiting request under it."""
        if mode not in MODES:
            raise ValueError(f"mode is one of {MODES}")
        with self._lock:
            old, self._mode = self._mode, mode
            released, denied = [], []
            for request in list(self._pending.values()):
                verdict = self._policy(request.tool, request.effect, request.open_world,
                                       request.session)
                if verdict == "allow":
                    self._finish(request, "allowed", f"released by the switch to {mode}")
                    released.append(request.id)
                elif verdict == "deny":
                    self._finish(request, "denied", f"denied by the switch to {mode}")
                    denied.append(request.id)
        self._emit({"type": "mode_changed", "from": old, "to": mode,
                    "released": released, "denied": denied})
        return {"mode": mode, "released": released, "denied": denied}

    # -- deciding ------------------------------------------------------------
    def _policy(self, tool: str, effect: str, open_world: bool, session: str) -> str:
        if tool in self.harness:
            return "allow"
        setting = self.settings.get(tool, "")
        if setting == "deny":
            return "deny"
        writes = effect != "read"
        if self._mode == "plan" and writes:
            return "deny"
        if setting == "ask":
            return "ask"
        if not writes:
            return "allow"
        if (session, tool) in self._session_grants:
            return "allow"
        if self._mode == "auto" or setting == "allow":
            return "allow"
        return "ask"

    def check(self, spec: ToolSpec, arguments: dict[str, Any], ctx: Any) -> None:
        """Allow, refuse, or wait for a person. Called by `Registry.call`."""
        session = str(getattr(ctx, "session", "") or "")
        verdict = self._policy(spec.name, spec.effect, spec.open_world, session)
        if verdict == "allow":
            return
        if verdict == "deny":
            why = ("the tool is set to Deny" if self.settings.get(spec.name) == "deny" else
                   "Plan mode proposes and does not write; switch to Ask or Auto")
            raise Refusal("PERMISSION_DENIED", f"{spec.name}: {why}")
        request = Request(secrets.token_hex(4), spec.name, spec.effect,
                          {k: clip(v, 120) for k, v in (arguments or {}).items()},
                          session, time.monotonic(), spec.open_world)
        with self._lock:
            self._pending[request.id] = request
        self._emit({"type": "permission_request", **request.public()})
        if not request.event.wait(self.timeout):
            with self._lock:
                if not request.event.is_set():
                    self._finish(request, "expired", "nobody answered")
        if request.outcome == "allowed":
            return
        if request.outcome == "expired":
            if session and getattr(ctx, "vault", None) is not None:
                from .session import SessionStore
                SessionStore(ctx.vault).append(session, {
                    "type": "status", "status": "parked",
                    "note": f"a permission request for {spec.name} went unanswered"})
            raise Refusal("PERMISSION_UNANSWERED", f"{spec.name} waited "
                                                   f"{self.timeout:.0f}s for a person; "
                                                   f"the session is parked")
        raise Refusal("PERMISSION_DENIED", f"{spec.name}: {request.reason}")

    def answer(self, request_id: str, answer: str) -> dict[str, Any]:
        if answer not in ANSWERS:
            raise ValueError(f"an answer is one of {ANSWERS}")
        with self._lock:
            request = self._pending.get(request_id)
            if request is None:
                raise LookupError(f"no pending request {request_id!r}")
            if answer == "allow_session" and request.session:
                self._session_grants.add((request.session, request.tool))
            self._finish(request, "denied" if answer == "deny" else "allowed",
                         "denied by a person" if answer == "deny" else
                         f"allowed by a person ({answer})")
        return {"id": request_id, "outcome": request.outcome}

    def _finish(self, request: Request, outcome: str, reason: str) -> None:
        request.outcome, request.reason = outcome, reason
        self._pending.pop(request.id, None)
        request.event.set()
        self._emit({"type": "permission_decided", "id": request.id, "tool": request.tool,
                    "outcome": outcome, "reason": reason})

    def pending(self) -> list[dict[str, Any]]:
        with self._lock:
            return [r.public() for r in self._pending.values()]

    def state(self) -> dict[str, Any]:
        return {"mode": self._mode, "tool_settings": dict(self.settings),
                "pending": self.pending()}
