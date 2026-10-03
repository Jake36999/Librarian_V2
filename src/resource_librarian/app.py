"""The core's local API: what the interface talks to, in the website and in the
Obsidian view alike.

`resource-librarian app` serves the interface and a JSON API on loopback. One
process holds everything the interface must not: the keys, the permission
broker, the agent loop and the vault. The interface holds none of it and asks.

**The boundary.** V1's chat found that the `Host` check stops DNS rebinding
but not a page on another site posting to `127.0.0.1` from the person's own
browser. So every `/api/` request needs:
- a loopback `Host`;
- the per-process page token (header `X-Librarian-Token`, or `?token=` for the
  event stream, which a browser cannot give headers), which only a same-origin
  page (it is in the served page) or the host that started the core (it
  passed it in) can know;
- for a write, an `Origin`, when the browser sends one, that is this server
  or an allowed host (`app://obsidian.md`).

**Who is calling.** The interface's own buttons are the person: they call
tools at `curate` through the registry (`/api/tool/<name>`), since a click is
the person's decision. The chat's model runs at `contribute` through the loop,
and every action it takes is decided by the broker in the current mode. Queued
actions are pipelines the person starts; their steps go through the broker too.

**Events.** One stream (`/api/events`, server-sent events): the loop's steps,
permission requests and decisions, mode changes, action progress. Each has a
sequence number, so a page that reconnects misses nothing recent.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from . import __version__, doctor, notes, workflows
from . import tools  # noqa: F401  (registers the tools)
from .broker import ANSWERS, MODES, Broker
from .index import Index
from .keys import KeyStore, config_dir
from .loop import LENGTHS, STANCES, Loop, ProviderEndpoint
from .providers import DASHBOARDS, PRESETS, Provider, ProviderError, from_settings
from .registry import REGISTRY, Context
from .rules import Refusal
from .staging import StagingStore
from .session import SessionStore
from .tools.sessions import Waiters
from .vault import DEFAULT_CONFIG, Vault, now_iso

LOOPBACK = {"127.0.0.1", "localhost", "::1", "[::1]"}
HOST_ORIGINS = {"app://obsidian.md"}
MAX_BODY = 1_000_000
MAX_UPLOAD = 40_000_000
QUEUED = ("clear-enrichment-backlog", "deep-read-staged", "review-conversation", "review-due",
          "weekly-review")
PROVIDER_LABELS = {"deepinfra": "DeepInfra", "openai": "OpenAI", "anthropic": "Anthropic",
                   "local": "Local server"}
SCRIPT_SUFFIXES = {".py": "python", ".sh": "shell"}      # what the pane may run (sandbox.py)
DEFAULTS = {"working_context": "", "reply_length": "long", "stance": "answer", "tiers": [],
            "mode": "ask", "base_urls": {}, "effort": 4}


class ApiError(Exception):
    def __init__(self, status: int, message: str, **extra: Any):
        super().__init__(message)
        self.status = status
        self.body = {"error": message, **extra}


# ------------------------------------------------------------------- events

class Hub:
    """Fan-out of events to every open stream, with a short memory."""

    def __init__(self, keep: int = 500):
        self._lock = threading.Lock()
        self._seq = 0
        self._recent: deque[dict[str, Any]] = deque(maxlen=keep)
        self._listeners: list[Callable[[dict[str, Any]], None]] = []

    def publish(self, event: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._seq += 1
            stamped = {"seq": self._seq, "at": round(time.time(), 3), **event}
            self._recent.append(stamped)
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(stamped)
            except Exception:                               # noqa: BLE001
                pass
        return stamped

    def last(self) -> int:
        with self._lock:
            return self._seq

    def since(self, seq: int) -> list[dict[str, Any]]:
        with self._lock:
            return [e for e in self._recent if e["seq"] > seq]

    def subscribe(self, listener: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def stop() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)
        return stop


# ---------------------------------------------------------------- settings

class Settings:
    """The interface's own settings, in `.librarian/app.json`: the working
    context, reply length, model tiers and mode. Never a key.

    The model choices (`SHARED`) are the person's, not one library's (owner, 2026-10-03:
    a new library had no models, so its ingest queued everything for a clerk that was
    never chosen). Each change is also kept in the user's config directory, and a library
    that has not chosen its own starts from them."""

    SHARED = ("tiers", "lead_overrides", "effort")

    def __init__(self, vault: Vault):
        self.path = vault.librarian / "app.json"
        self.data = dict(DEFAULTS)
        own: dict[str, Any] = {}
        if self.path.is_file():
            try:
                own = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                own = {}
        shared = self._shared()
        self.data.update({k: v for k, v in shared.items() if k in self.SHARED and k not in own})
        self.data.update(own)
        self.inherited = sorted(k for k in shared if k in self.SHARED and k not in own)

    @staticmethod
    def _shared_path() -> Path:
        from .keys import config_dir
        return config_dir() / "app-defaults.json"

    def _shared(self) -> dict[str, Any]:
        try:
            data = json.loads(self._shared_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def update(self, **changes: Any) -> None:
        self.data.update(changes)
        self.path.write_text(json.dumps(self.data, indent=1, ensure_ascii=False),
                             encoding="utf-8")
        mine = {k: v for k, v in changes.items() if k in self.SHARED}
        if mine:
            try:
                path = self._shared_path()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({**self._shared(), **mine}, indent=1,
                                           ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass                    # a read-only config dir never stops a choice


@dataclass
class Action:
    id: str
    name: str
    status: str = "running"
    steps: int = 0
    run: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    cancel: threading.Event = field(default_factory=threading.Event)

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "status": self.status,
                "steps": self.steps, "run": self.run,
                **({"at": self.result.get("at"), "reason": self.result.get("reason")}
                   if self.status == "paused" else {})}


PROFILE_FIELDS = ("modality", "best_for", "license_class", "suggested_tier", "context_length",
                  "price_input_per_1m", "price_output_per_1m", "tool_calling", "reasoning")


def _shipped_profiles() -> dict[tuple[str, str], dict[str, Any]]:
    """The model catalogues shipped with the package (standard/model_catalog/*.json)."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted((Path(__file__).parent / "standard" / "model_catalog").glob("*.json")):
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for row in rows if isinstance(rows, list) else []:
            fields = (row or {}).get("fields") or {}
            key = (str(fields.get("provider") or "").lower(), str(fields.get("model_id") or "").lower())
            if key[1]:
                out[key] = {k: fields.get(k) for k in PROFILE_FIELDS}
    return out


def _profiles_path() -> Path:
    from .keys import config_dir
    return config_dir() / "model-profiles.json"


def _remembered_profiles() -> dict[tuple[str, str], dict[str, Any]]:
    try:
        data = json.loads(_profiles_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {tuple(k.split("|", 1)): v for k, v in data.items()
            if isinstance(v, dict) and "|" in k}


def _remember_profiles(own: dict[tuple[str, str], dict[str, Any]]) -> None:
    """Keep this library's model profiles where every library can see them."""
    if not own:
        return
    known = {f"{p}|{m}": v for (p, m), v in _remembered_profiles().items()}
    fresh = {f"{p}|{m}": {k: v.get(k) for k in PROFILE_FIELDS} for (p, m), v in own.items()}
    if all(known.get(k) == v for k, v in fresh.items()):
        return
    try:
        path = _profiles_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({**known, **fresh}, indent=0, default=str), encoding="utf-8")
    except OSError:
        pass


def ELIGIBLE_LEADS() -> list[dict[str, Any]]:            # noqa: N802 - a read-only table
    """The leads M0 found to complete research tasks (standard/eligible_leads.json)."""
    path = Path(__file__).parent / "standard" / "eligible_leads.json"
    try:
        return list(json.loads(path.read_text(encoding="utf-8")).get("eligible") or [])
    except (OSError, json.JSONDecodeError):
        return []


# --------------------------------------------------------------------- app

class App:
    def __init__(self, vault: Vault, token: str = "", keys: KeyStore | None = None,
                 provider_for: Callable[[dict[str, Any]], Provider | None] | None = None,
                 allowed_origins: set[str] | None = None, broker_timeout: float = 600.0,
                 mcp: Any = None):
        self.vault = vault
        self.broker_timeout = broker_timeout
        self.token = token or secrets.token_urlsafe(24)
        self.keys = keys or KeyStore()
        self.settings = Settings(vault)
        self.hub = Hub()
        self.broker = Broker(mode=self.settings.data.get("mode", "ask"),
                             timeout=broker_timeout)
        self.broker.subscribe(self.hub.publish)
        self.waiters = Waiters(timeout=broker_timeout)
        self.waiters.subscribe(self.hub.publish)
        self.allowed_origins = set(HOST_ORIGINS | (allowed_origins or set()))
        self._provider_for = provider_for or self._configured_provider
        self._lock = threading.Lock()
        self.busy = False
        self._turn_cancel: threading.Event | None = None
        self.loop: Loop | None = None
        self._tts_plans: dict[str, tuple[str, list[str]]] = {}   # slot 5's readings
        self.actions: dict[str, Action] = {}
        if mcp is not None:
            # Switching library: outside servers are configured per person, not
            # per library (mcp.json), and their tools are registered once,
            # globally - so the running manager carries over, and only the new
            # library's own broker is seeded with their default (Ask).
            self.mcp = mcp
            mcp.attach_broker(self.broker)
            mcp.use_library(vault.librarian)       # this library's own choices
            threading.Thread(target=mcp.sync, daemon=True, name="mcp-sync").start()
            return
        try:
            from .mcp_client import McpManager
        except ImportError:
            self.mcp = None                  # needs `pip install resource-librarian[mcp]`
        else:
            self.mcp = McpManager(config_dir(), broker=self.broker)
            self.mcp.use_library(vault.librarian)
            threading.Thread(target=self.mcp.sync, daemon=True, name="mcp-sync").start()

    # -- switching library ---------------------------------------------------
    def running(self) -> dict[str, Any]:
        """What would still be working here if this library were switched away
        from: a chat turn, workflows mid-run, questions waiting on a person."""
        actions = [a.public() for a in self.actions.values() if a.status == "running"]
        return {k: v for k, v in {"turn": self.busy, "actions": actions,
                                  "waiting_on_person": len(self.broker.pending())}.items() if v}

    def retire(self, patience: float = 3600.0, poll: float = 2.0) -> None:
        """Close this library gracefully once it is no longer the open one: let
        a chat turn and running workflows finish (they write to this library's
        own sessions, which stay resumable), and let questions waiting on a
        person time out - an unanswered permission parks its session, since
        silence is never approval. Then drop the conversation. Outside servers
        are shared with the library that replaced this one, so they stay up."""
        deadline = time.monotonic() + patience
        while (self.busy or any(a.status == "running" for a in self.actions.values())) \
                and time.monotonic() < deadline:
            time.sleep(poll)
        self.hub.publish({"type": "library_closed", "vault": self.vault.root.name})
        if self.loop is not None:
            self.loop.messages.clear()
            self.loop.ctx.session = None

    # -- models -----------------------------------------------------------
    def _configured_provider(self, choice: dict[str, Any]) -> Provider | None:
        settings = dict(choice)
        base = self.settings.data.get("base_urls", {}).get(choice.get("provider", ""))
        if base and not settings.get("base_url"):
            settings["base_url"] = base
        return from_settings(settings)

    def tier(self, n: int) -> Provider | None:
        """Tier n, falling back to the one above it when empty."""
        tiers = self.settings.data.get("tiers") or []
        for i in range(min(n, len(tiers)) - 1, -1, -1):
            if tiers[i]:
                return self._provider_for(tiers[i])
        return None

    def _extras(self) -> dict[str, Any]:
        from . import effort
        level = effort.profile(self.settings.data.get("effort"))
        extras: dict[str, Any] = {"broker": self.broker, "waiters": self.waiters,
                                  "mcp": self.mcp,
                                  # the person's effort setting, and the tiers a delegate runs on
                                  # (a ceiling: the lead may choose less with set_effort)
                                  "effort": level, "effort_ceiling": level,
                                  "agent_provider": self.tier}
        clerk = self.tier(3)
        if clerk is not None:
            extras["clerk_fallback"] = ProviderEndpoint(clerk)
        scribe = self.tier(2)
        if scribe is not None:
            extras["scribe_fallback"] = ProviderEndpoint(scribe)
        lead = self.lead_status()
        if lead["status"] != "none":           # carried into every call's trace (R10)
            extras["lead_status"] = lead["status"] + (f": {lead.get('reason', '')}"
                                                      if lead["status"] == "override" else "")
        return extras

    def _loop(self) -> Loop:
        provider = self.tier(1)
        if provider is None:
            raise ApiError(409, "choose a chat model first (Model: tier 1)")
        data = self.settings.data
        if self.loop is None:
            self.loop = Loop(self.vault, provider, working_context=data["working_context"],
                             reply_length=data["reply_length"], stance=data["stance"],
                             extras=self._extras(), on_event=self.hub.publish)
        else:
            self.loop.provider = provider
            self.loop.working_context = data["working_context"]
            self.loop.reply_length = data["reply_length"]
            self.loop.stance = data["stance"]
            self.loop.ctx.extras.update(self._extras())
        level = self.loop.ctx.extras["effort"]
        self.loop.max_steps, self.loop.turn_seconds = level["turn_steps"], level["turn_seconds"]
        return self.loop

    def set_effort(self, level: Any) -> dict[str, Any]:
        """The effort slider: kept with the app's settings, applied from the next step, and
        written into an open session so its budgets follow (and the trace shows why)."""
        from . import effort
        from .session import SessionStore
        chosen = effort.profile(level)
        self.settings.update(effort=chosen["level"])
        if self.loop is not None:
            self.loop.ctx.extras["effort"] = chosen
            self.loop.max_steps, self.loop.turn_seconds = (chosen["turn_steps"],
                                                           chosen["turn_seconds"])
            if self.loop.ctx.session:
                try:
                    SessionStore(self.vault).append(self.loop.ctx.session, {
                        "type": "effort", "level": chosen["level"],
                        "budget_scale": chosen["budget_scale"]})
                except Exception:                           # noqa: BLE001
                    pass                                    # a closed or missing session
        return chosen

    # -- chat -------------------------------------------------------------
    def chat(self, text: str) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            raise ApiError(400, "an empty message")
        with self._lock:
            if self.busy:
                raise ApiError(409, "the librarian is still answering; wait, or cancel")
            loop = self._loop()
            self.busy = True
            cancel = threading.Event()
            self._turn_cancel = cancel

        def turn() -> None:
            try:
                result = loop.send(text, cancel=cancel)
                self._touch_desk(text)
                event = {"type": "turn_done", **result.to_dict(), "session": self.session_view()}
            except Exception as exc:                        # noqa: BLE001
                event = {"type": "error", "error": f"{type(exc).__name__}: {exc}"}
            # Free before announcing: a person who sends the moment the reply
            # lands must not be told the librarian is still answering.
            with self._lock:
                self.busy = False
                self._turn_cancel = None
            self.hub.publish(event)
            if event["type"] == "turn_done" and event.get("reply"):
                self._review_reply(loop, str(event["reply"]))
        threading.Thread(target=turn, daemon=True, name="librarian-turn").start()
        return {"accepted": True}

    def cancel_turn(self) -> dict[str, Any]:
        with self._lock:
            if not self.busy or self._turn_cancel is None:
                return {"cancelling": False}
            self._turn_cancel.set()
        return {"cancelling": True}

    WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")

    def _review_reply(self, loop: Loop, reply: str) -> None:
        """§4 G3 on chat replies (`reply_review`): after the reply, never
        before it; the verdict is its own event, and a challenge waits for the
        lead model's next prompt."""
        from . import effort, reply_review
        level = effort.profile(self.settings.data.get("effort"))
        if not (reply_review.enabled(self.vault) or level["review_replies"]):
            return
        from .tools.staging import clerk_endpoint
        ctx = Context(tier="contribute", vault=self.vault, extras=self._extras())

        def run() -> None:
            try:
                out = reply_review.review_reply(self.vault, reply, clerk_endpoint(ctx),
                                                max_claims=max(1, level["review_claims"]))
            except Exception as exc:                        # noqa: BLE001
                out = {"status": f"error: {type(exc).__name__}", "held": 0, "unchecked": 0,
                       "challenged": []}
            if out is None:
                return
            loop.challenges = list(out.get("challenged") or [])
            self.hub.publish({"type": "reply_reviewed", **out})
        threading.Thread(target=run, daemon=True, name="librarian-reply-review").start()

    def _touch_desk(self, text: str) -> None:
        """Notes a person linked in a message (the paperclip inserts `[[...]]`)
        go on the desk of the thread's pursuit (roadmap §2 B, deferred; §4 D3),
        as opening one in the pane already does. Only notes that exist, and
        only when the thread has a pursuit; never an error for the turn."""
        if self.loop is None or not self.loop.ctx.session:
            return
        try:
            project = SessionStore(self.vault).load(self.loop.ctx.session).project
            if not project:
                return
            from .desk import DeskStore
            wanted = {m.strip().rsplit("/", 1)[-1].removesuffix(".md").casefold()
                      for m in self.WIKILINK.findall(text)}
            if not wanted:
                return
            store = DeskStore(self.vault)
            for path in notes.iter_paths(self.vault.root):       # the files, not a stale index
                if path.stem.casefold() in wanted and path.stem != project:
                    store.touch(project, path.stem)
        except Exception:                                   # noqa: BLE001
            pass                                            # the desk is a convenience

    def reset(self) -> dict[str, Any]:
        if self.busy:
            raise ApiError(409, "the librarian is still answering")
        if self.loop is not None:
            self.loop.messages.clear()
            self.loop.ctx.session = None
        self.hub.publish({"type": "conversation_reset"})
        return {"reset": True}

    def attach(self, session_id: str) -> dict[str, Any]:
        """Continue a thread in the chat: the person picked it from Sessions."""
        loop = self._loop()
        result = REGISTRY.call("resume_session", {"session_id": session_id},
                               Context(tier="curate", vault=self.vault))
        if "error" in result:
            raise ApiError(400, result.get("detail") or result["error"], result=result)
        loop.ctx.session = session_id
        # Otherwise the person sees the old conversation replayed while the
        # model itself remembers none of it - it would greet them as a
        # stranger on the very next turn.
        loop.restore(result.get("messages") or [])
        self.hub.publish({"type": "session_attached", "session": self.session_view()})
        return {"attached": session_id, "session": self.session_view()}

    def session_view(self) -> dict[str, Any] | None:
        session = self.loop.ctx.session if self.loop is not None else None
        if not session:
            return None
        try:
            return SessionStore(self.vault).load(session).to_dict(self.vault)
        except Exception:                                   # noqa: BLE001
            return None

    # -- the person's own calls ---------------------------------------------
    def person_call(self, name: str, arguments: dict[str, Any], session: str = ""
                    ) -> dict[str, Any]:
        ctx = Context(tier="curate", vault=self.vault, session=session or None,
                      extras={k: v for k, v in self._extras().items() if k != "broker"})
        result = REGISTRY.call(name, arguments, ctx)
        if name in ("answer", "staging_decide", "promote_offering") and "error" not in result:
            self.hub.publish({"type": "person_acted", "tool": name})
        if name == "rewind_session" and "error" not in result and self.loop is not None \
                and self.loop.ctx.session == ctx.session:
            # The tool truncated the log itself; the running loop's own
            # in-memory context still has to forget the same messages, or the
            # very next turn would answer as if nothing had been discarded.
            self.loop.rewind_to(result["rewound_to"])
        return result

    def decide_offering(self, offering: str, decision: str) -> dict[str, Any]:
        from .tools.sessions import decide_offering
        ctx = Context(tier="curate", vault=self.vault,
                      extras={k: v for k, v in self._extras().items() if k != "broker"})
        try:
            result = decide_offering(ctx, offering, decision)
        except TypeError as exc:
            return {"error": "invalid_arguments", "detail": str(exc)}
        self.hub.publish({"type": "person_acted", "tool": "promote_offering"})
        return result

    # -- queued actions -----------------------------------------------------
    def start_action(self, name: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        from .tools.workflows import _library, _router
        action = Action(secrets.token_hex(4), name)
        extras = {**self._extras(), "cancel": action.cancel}

        def progress(event: dict[str, Any]) -> None:
            action.steps += 1
            action.run = event["run"]
            self.hub.publish({"type": "action_progress", **action.public()})
        extras["progress"] = progress
        ctx = Context(tier="contribute", vault=self.vault, extras=extras)
        library = _library(ctx)
        library.get(name)                                   # unknown names fail now, loudly
        self.actions[action.id] = action

        def run() -> None:
            try:
                runner = workflows.Runner(library, ctx, _router(ctx))
                action.result = runner.start(name, inputs or {})
                action.run = action.result.get("run", action.run)
                action.status = action.result.get("status", "finished")
            except (Refusal, workflows.DefinitionError, KeyError) as exc:
                action.status = "failed"
                action.result = {"error": str(exc)}
            except Exception as exc:                        # noqa: BLE001
                action.status = "failed"
                action.result = {"error": f"{type(exc).__name__}: {exc}"}
            self.hub.publish({"type": "action_done", **action.public(),
                              "result": action.result})
        self.hub.publish({"type": "action_started", **action.public()})
        threading.Thread(target=run, daemon=True, name=f"action-{name}").start()
        return action.public()

    def cancel_action(self, action_id: str) -> dict[str, Any]:
        action = self.actions.get(action_id)
        if action is None:
            raise ApiError(404, f"no action {action_id!r}")
        action.cancel.set()
        return {"cancelling": action_id}

    # -- MCP servers (Co-work Roadmap §3, Phase 1) ---------------------------
    def _mcp(self) -> Any:
        if self.mcp is None:
            raise ApiError(409, "outside MCP servers need the `mcp` extra: "
                                "pip install resource-librarian[mcp]")
        return self.mcp

    def mcp_status(self) -> dict[str, Any]:
        mcp = self._mcp()
        from .mcp_client import redacted_args
        status = mcp.status()
        servers = mcp.servers()
        return {"servers": {name: {**status.get(name, {}), "command": d.get("command", ""),
                                   "args": redacted_args(d.get("args") or []),
                                   "env": sorted((d.get("env") or {}).keys()),
                                   "tool_names": mcp.tool_names(name)}
                            for name, d in servers.items()},
                "config_dir": str(mcp.config_dir),
                "tool_settings": dict(self.broker.settings)}

    def mcp_save_config(self, servers: Any) -> dict[str, Any]:
        mcp = self._mcp()
        if not isinstance(servers, dict):
            raise ApiError(400, "mcpServers is a JSON object")
        mcp.save_config({"mcpServers": servers})
        mcp.sync()
        return self.mcp_status()

    def mcp_accept(self, name: str) -> dict[str, Any]:
        mcp = self._mcp()
        try:
            mcp.accept(name)
        except ValueError as exc:
            raise ApiError(404, str(exc)) from exc
        mcp.sync()
        return self.mcp_status()

    def mcp_add_server(self, name: str, definition: Any) -> dict[str, Any]:
        """One server, added or replaced - a skills-registry install, or a
        person's own hand-configured entry. Saving it here *is* the accept
        gesture: the person just supplied these connection details themselves,
        so there is nothing left to confirm."""
        mcp = self._mcp()
        if not name:
            raise ApiError(400, "name is required")
        if not isinstance(definition, dict):
            raise ApiError(400, "server is a JSON object")
        mcp.set_server(name, definition)
        mcp.accept(name)
        # Installed from inside this library, so it is on here - and only here:
        # every other library still decides for itself (off until it does).
        mcp.set_library_enabled(name, True)
        mcp.sync()
        return self.mcp_status()

    def mcp_set_library_enabled(self, name: str, enabled: bool) -> dict[str, Any]:
        mcp = self._mcp()
        try:
            mcp.set_library_enabled(name, bool(enabled))
        except KeyError:
            raise ApiError(404, f"no server {name!r}") from None
        mcp.sync()
        return self.mcp_status()

    def mcp_set_enabled(self, name: str, enabled: bool) -> dict[str, Any]:
        mcp = self._mcp()
        servers = mcp.servers()
        if name not in servers:
            raise ApiError(404, f"no server {name!r}")
        mcp.set_server(name, {**servers[name], "enabled": bool(enabled)})
        mcp.sync()
        return self.mcp_status()

    def mcp_remove_server(self, name: str) -> dict[str, Any]:
        mcp = self._mcp()
        mcp.remove_server(name)
        mcp.sync()
        return self.mcp_status()

    def mcp_registry_search(self, query: str) -> dict[str, Any]:
        return self._mcp().search_registry(query)

    # -- settings pages ------------------------------------------------------
    def save_key(self, provider: str, key: str, overwrite: bool = False) -> dict[str, Any]:
        from .keys import SEARCH_KEYS
        if provider not in PRESETS and provider not in SEARCH_KEYS:
            raise ApiError(400, f"unknown provider {provider!r}")
        before = self.keys.status(provider)
        if before.get("saved") and not overwrite:
            label = PROVIDER_LABELS.get(provider, provider.capitalize())
            raise ApiError(409, "a key is already saved", confirm=(
                f"Replace the saved {label} key? The old key is removed and can't be "
                f"recovered from here."))
        try:
            status = self.keys.save(provider, key)
        except ValueError as exc:
            raise ApiError(400, str(exc)) from exc
        return {**status, "check": self.check(provider)}

    def usage(self, provider: str) -> dict[str, Any]:
        """One best-effort read of account balance/usage, and the provider's
        own dashboard either way. Never raises: a failure here is answered,
        not surfaced as a 500, since it is expected for most providers."""
        dashboard = DASHBOARDS.get(provider, "")
        try:
            made = self._provider_for({"provider": provider})
        except ProviderError as exc:
            return {"ok": False, "error": str(exc), "dashboard": dashboard}
        if made is None:
            return {"ok": False, "error": f"{provider} is not configured", "dashboard": dashboard}
        try:
            data = made.usage()
        except ProviderError as exc:
            return {"ok": False, "error": str(exc), "dashboard": dashboard}
        out: dict[str, Any] = {"ok": True, "dashboard": dashboard, "unofficial": True}
        if provider == "deepinfra" and isinstance(data, dict) and "stripe_balance" in data:
            out.update(balance=data.get("stripe_balance"), currency="USD",
                      suspended=bool(data.get("suspended")),
                      billing_type=str(data.get("billing_type") or ""))
        return out

    def check(self, provider: str) -> dict[str, Any]:
        from .keys import SEARCH_KEYS
        if provider == "github":
            return {"ok": True, "status": "Saved. Repository intake now reads GitHub's API "
                                          "with it (a much higher rate limit)"}
        if provider in SEARCH_KEYS:
            # Not called out to: a test search would spend one of the key's searches.
            from . import websearch
            used = websearch.backend(self.vault)
            return {"ok": True, "status": f"Saved. Web search now uses {used.capitalize()}"
                                          + ("" if used == provider else
                                             " (Brave is used first when both are set)")}
        try:
            made = self._provider_for({"provider": provider})
        except ProviderError as exc:
            return {"ok": False, "error": str(exc)}
        if made is None:
            return {"ok": False, "error": "not configured"}
        return made.check()

    def _model_sources(self) -> dict[tuple[str, str], dict[str, Any]]:
        """Every catalogued model Source, keyed by (provider, model_id), both
        lowercased so a live listing's id matches regardless of case."""
        try:
            index = Index(self.vault)
            rows = list(index.conn.execute(
                "SELECT path, frontmatter FROM note WHERE shape = 'source' AND kind = 'model'"))
        except Exception:                                   # noqa: BLE001 - no index yet
            return {}
        out: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            fm = json.loads(row["frontmatter"])
            key = (str(fm.get("provider") or "").lower(), str(fm.get("model_id") or "").lower())
            if key[1]:
                out[key] = {**fm, "_path": row["path"]}
        return out

    def _pending_models(self) -> set[tuple[str, str]]:
        """Model ids already queued for a person's review in staging, so the
        tile can say so instead of offering to profile them again."""
        try:
            items = StagingStore(self.vault).items("source")
        except Exception:                                   # noqa: BLE001
            return set()
        return {(str(i.get("fields", {}).get("provider") or "").lower(),
                str(i.get("fields", {}).get("model_id") or "").lower())
                for i in items if i.get("source_kind") == "model" and
                i["status"] in ("staged", "deferred")}

    def models(self, provider: str) -> dict[str, Any]:
        try:
            made = self._provider_for({"provider": provider})
            listed = made.models() if made is not None else []
        except ProviderError as exc:
            status = "offline" if provider == "local" else \
                "no key" if "is not set" in str(exc) else "error"
            return {"provider": provider, "status": status, "error": str(exc)[:300],
                    "models": []}
        chosen = {(t or {}).get("model"): i + 1
                  for i, t in enumerate(self.settings.data.get("tiers") or [])
                  if (t or {}).get("provider") == provider}
        own = self._model_sources()
        # A profile is knowledge about a model, not about a library (owner, 2026-10-03):
        # this library's own notes, else what any library has profiled (kept in the user's
        # config directory), else the catalogue shipped with the package.
        _remember_profiles(own)
        profiles = {**_shipped_profiles(), **_remembered_profiles(), **own}
        pending = self._pending_models()
        out = []
        for m in listed:
            entry: dict[str, Any] = {"id": m, "tier": chosen.get(m)}
            profile = profiles.get((provider, m.lower()))
            if profile:
                entry["profile"] = {
                    "path": profile.get("_path", ""), "modality": profile.get("modality"),
                    "shared": not profile.get("_path"),
                    "best_for": profile.get("best_for") or [],
                    "license_class": profile.get("license_class"),
                    "suggested_tier": profile.get("suggested_tier"),
                    "context_length": profile.get("context_length"),
                    "price_input_per_1m": profile.get("price_input_per_1m"),
                    "price_output_per_1m": profile.get("price_output_per_1m"),
                    "tool_calling": bool(profile.get("tool_calling")),
                    "reasoning": bool(profile.get("reasoning"))}
            elif (provider, m.lower()) in pending:
                entry["profiling"] = "queued"
            out.append(entry)
        return {"provider": provider, "status": "ready", "models": out}

    def set_tiers(self, tiers: list[dict[str, Any]], override: str = "") -> dict[str, Any]:
        if not isinstance(tiers, list) or len(tiers) > 3:
            raise ApiError(400, "tiers is a list of up to three {provider, model}")
        clean = []
        for t in tiers:
            if not isinstance(t, dict) or t.get("provider") not in PRESETS or not t.get("model"):
                raise ApiError(400, "each tier needs a known provider and a model id")
            clean.append({"provider": t["provider"], "model": str(t["model"])})
        # Requirements Addendum R10: benchmark tiers screen; completing tasks (M0) qualifies.
        # A lead that has not is taken only on a person's recorded override.
        lead = self.lead_status(clean)
        if lead["status"] == "ineligible":
            if not override.strip():
                raise ApiError(409, f"{lead['model']} has not completed the M0 completion suite "
                                    f"as a lead, so it is not known to finish research tasks. "
                                    f"Use it anyway only as a recorded choice.",
                               needs_override=True, lead=lead["model"])
            overrides = dict(self.settings.data.get("lead_overrides") or {})
            overrides[lead["model"]] = {"reason": override.strip()[:300], "at": now_iso()}
            self.settings.update(lead_overrides=overrides)
        self.settings.update(tiers=clean)
        self.hub.publish({"type": "tiers_changed", "tiers": clean})
        return {"tiers": clean, "lead": self.lead_status(clean)}

    def lead_status(self, tiers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        tiers = self.settings.data.get("tiers") or [] if tiers is None else tiers
        if not tiers:
            return {"status": "none"}
        key = f"{tiers[0]['provider']}/{tiers[0]['model']}"
        listed = {f"{e.get('provider')}/{e.get('model')}": e for e in ELIGIBLE_LEADS()}
        if key in listed:
            return {"status": "eligible", "model": key, "result": listed[key].get("result", "")}
        override = (self.settings.data.get("lead_overrides") or {}).get(key)
        if override:
            return {"status": "override", "model": key, **override}
        return {"status": "ineligible", "model": key}

    def set_context(self, working_context: str | None = None,
                    reply_length: str | None = None, stance: str | None = None
                    ) -> dict[str, Any]:
        changes: dict[str, Any] = {}
        if working_context is not None:
            changes["working_context"] = str(working_context)[:8000]
        if reply_length is not None:
            if reply_length not in LENGTHS and len(reply_length) > 300:
                raise ApiError(400, "a custom reply length is a short instruction")
            changes["reply_length"] = reply_length
        if stance is not None:
            if stance not in STANCES:
                raise ApiError(400, f"stance is one of {sorted(STANCES)}")
            changes["stance"] = stance
        self.settings.update(**changes)
        return {k: self.settings.data[k] for k in ("working_context", "reply_length", "stance")}

    def set_mode(self, mode: str) -> dict[str, Any]:
        if mode not in MODES:
            raise ApiError(400, f"mode is one of {MODES}")
        self.settings.update(mode=mode)
        return self.broker.set_mode(mode)

    def library(self) -> dict[str, Any]:
        config = self.vault.config()
        return {"promotion": config.get("promotion", {}), "usage": config.get("usage", {}),
                "clerk": {k: v for k, v in config.get("clerk", {}).items()
                          if "key" not in k.lower()},
                "search": config.get("search", {}),
                "doctor": [c.to_dict() for c in doctor.checks(self.vault, self.mcp)]}

    # -- service models (Requirements Addendum R17): slots 4-6, kept per library ----
    SERVICE_SLOTS = (("ocr", 4, "OCR", "reads PDF pages that have no text layer"),
                     ("tts", 5, "Text to speech", "reads a note or a reply aloud"),
                     ("embeddings", 6, "Embeddings", "the vectors search uses"))

    def services(self) -> dict[str, Any]:
        from . import ocr
        import tomllib
        own: dict[str, Any] = {}
        if self.vault.config_path.is_file():
            with self.vault.config_path.open("rb") as handle:
                own = tomllib.load(handle).get("services") or {}
        chosen = ocr.choice(self.vault)
        slots = []
        for name, number, label, job in self.SERVICE_SLOTS:
            row: dict[str, Any] = {"slot": name, "number": number, "label": label, "job": job}
            if name == "ocr":
                # `default`: still the value a new library starts with (init writes it)
                row.update(chosen or {"provider": "", "model": ""}, built=True,
                           default=own.get("ocr", DEFAULT_CONFIG["services"]["ocr"]) ==
                           DEFAULT_CONFIG["services"]["ocr"])
            elif name == "embeddings":
                row.update(self._embeddings_status(), built=True)
            elif name == "tts":
                from . import tts
                row.update(tts.choice(self.vault) or {"provider": "", "model": ""}, built=True,
                           default=own.get("tts", tts.DEFAULT) == tts.DEFAULT,
                           spent_usd=round(tts.spent(), 4), cap_usd=tts.CAP_USD)
            else:
                row.update(provider="", model="", built=False)       # planned (P4b)
            slots.append(row)
        return {"slots": slots}

    def _embeddings_status(self) -> dict[str, Any]:
        """Slot 6: the model, how much of the library it has embedded, what the rest would
        take, which intents use it, and the last lexical-vs-hybrid measurement."""
        from . import embed
        from .index import Index
        spec = embed.spec_for(self.vault)
        out: dict[str, Any] = {"provider": "", "model": "", "spec": spec,
                               "vector_intents": self.vault.setting("search", "vector_intents")}
        if not spec:
            return out
        kind, _, rest = spec.partition(":")
        provider, model = (rest.split(":", 1) if kind == "api" else (kind, rest))
        out.update(provider=provider, model=model,
                   legacy=not self.vault.setting("services", "embeddings"))
        name = f"hash:{int(rest or 256)}" if kind == "hash" else spec   # as embed stores it
        index = Index(self.vault)
        index.refresh()                                   # count what is there now
        price = None
        if kind == "api":
            profile = self._model_sources().get((provider, model.lower())) or {}
            price = profile.get("price_input_per_1m")
        out["chunks"] = int(index.conn.execute(
            "SELECT COUNT(DISTINCT hash) FROM chunk WHERE role != 'document'").fetchone()[0])
        out["embedded"] = int(index.conn.execute(
            "SELECT COUNT(*) FROM embedding WHERE model = ?", (name,)).fetchone()[0])
        out["estimate"] = embed.estimate(index, name, price)
        out["hosted"] = kind == "api"
        compared = self.vault.work("eval") / "vectors.json"
        if compared.is_file():
            try:
                out["comparison"] = json.loads(compared.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return out

    def set_service(self, slot: str, provider: str, model: str) -> dict[str, Any]:
        from . import embed
        if slot == "embeddings":
            local = provider in embed.LOCAL_KINDS
            if model and not local and (provider not in PRESETS or
                                        PRESETS[provider].get("protocol") != "openai"):
                raise ApiError(400, "embeddings come from a local encoder (model2vec, "
                                    "fastembed) or an OpenAI-compatible /embeddings provider")
            # a new model starts with no intents using it: a person turns them on after
            # measuring (SM-8), and nothing is embedded until they start it (R17)
            self.vault.set_setting("services", "embeddings", f"{provider}:{model}" if model else "")
            self.vault.set_setting("search", "vector_intents", [])
            return self.services()
        if slot == "tts":
            from . import tts
            if model and (provider != "deepinfra" or model not in tts.PRICES):
                raise ApiError(400, f"text to speech runs on DeepInfra with a model whose price "
                                    f"is known, so its ${tts.CAP_USD:.2f} cap holds: "
                                    f"{', '.join(sorted(tts.PRICES))}")
            self.vault.set_setting("services", "tts", f"{provider}:{model}" if model else "")
            return self.services()
        if slot != "ocr":
            raise ApiError(400, f"slot {slot!r} is not built yet")
        if model and (provider not in PRESETS or PRESETS[provider].get("protocol") != "openai"):
            raise ApiError(400, "OCR needs an OpenAI-compatible provider (a vision chat model)")
        self.vault.set_setting("services", "ocr", f"{provider}:{model}" if model else "")
        return self.services()

    def set_vector_intents(self, intents: list[str]) -> dict[str, Any]:
        from .search import INTENTS
        unknown = [i for i in intents if i not in INTENTS]
        if unknown:
            raise ApiError(400, f"not search intents: {unknown}")
        self.vault.set_setting("search", "vector_intents", list(dict.fromkeys(intents)))
        return self.services()

    def test_service(self, slot: str) -> dict[str, Any]:
        """One small, real call: the OCR model reads a sample line (R17's Test action)."""
        from . import ocr
        if slot == "embeddings":
            return self._test_embeddings()
        if slot == "tts":
            from . import tts
            try:
                out = tts.speak(self.vault, "Testing the read-aloud voice.", "test")
            except tts.TtsError as exc:
                return {"ok": False, "error": str(exc)[:300]}
            return {"ok": True, "read": "Testing the read-aloud voice.", "audio": out["audio"],
                    "cost_usd": out["cost_usd"]}
        if slot != "ocr":
            raise ApiError(400, f"slot {slot!r} is not built yet")
        try:
            reader = ocr.endpoint(self.vault)
            if reader is None:
                return {"ok": False, "error": "no OCR model is chosen"}
            got = reader.page_text(ocr.sample_png())
        except (ocr.OcrError, ProviderError) as exc:
            return {"ok": False, "error": str(exc)[:300]}
        return {"ok": "librarian reads this page" in got.lower(), "read": got[:300],
                "model": getattr(reader, "name", "")}

    # -- text to speech (slot 5): a reply (mode A) or the open document (mode B) ------
    def tts_plan(self, text: str = "", path: str = "") -> dict[str, Any]:
        """Cut a reply, or the note at `path`, into the chunks it will be read in; nothing
        is spoken (or spent) until a chunk is asked for."""
        from . import tts
        if path:
            text, mode = self.read_file(path)["text"], "document"
        else:
            mode = "message"
        if not text.strip():
            raise ApiError(400, "nothing to read")
        chosen = tts.choice(self.vault)
        planned = tts.plan(text, chosen.get("model", ""))
        if not planned["chunks"]:
            raise ApiError(400, "nothing speakable in it")
        plan_id = hashlib.sha256(("\n".join(planned["chunks"]) + mode).encode()
                                 ).hexdigest()[:16]
        self._tts_plans[plan_id] = (mode, planned["chunks"])
        while len(self._tts_plans) > 20:
            self._tts_plans.pop(next(iter(self._tts_plans)))
        return {"plan": plan_id, "mode": mode, "count": len(planned["chunks"]),
                **{k: planned[k] for k in ("chars", "estimate_usd", "spent_usd", "cap_usd")}}

    def tts_chunk(self, plan_id: str, index: int) -> dict[str, Any]:
        from . import tts
        if plan_id not in self._tts_plans:
            raise ApiError(404, "that reading has expired: start it again")
        mode, parts = self._tts_plans[plan_id]
        if not 0 <= index < len(parts):
            raise ApiError(400, f"chunk {index} is not one of 0-{len(parts) - 1}")
        try:
            out = tts.speak(self.vault, parts[index], mode)
        except tts.TtsError as exc:
            raise ApiError(402 if "cap" in str(exc) else 400, str(exc)) from exc
        return {"index": index, "count": len(parts), **out}

    def _test_embeddings(self) -> dict[str, Any]:
        """Slot 6's Test: two close sentences and a far one, embedded - the dimension, and
        whether the close pair is closer than the far one."""
        from . import embed
        spec = embed.spec_for(self.vault)
        if not spec:
            return {"ok": False, "error": "no embedding model is chosen"}
        try:
            import numpy as np
            _, encode = embed.load_encoder(spec)
            vectors = np.asarray(encode(["a cat sat on the mat", "a kitten sat on a mat",
                                         "quarterly tax filing deadlines"]), dtype="float32")
        except Exception as exc:                            # noqa: BLE001 - key, network, lib
            return {"ok": False, "error": str(exc)[:300]}
        unit = vectors / (np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9)
        near, far = float(unit[0] @ unit[1]), float(unit[0] @ unit[2])
        return {"ok": near > far, "dimension": int(vectors.shape[1]),
                "read": f"close pair {near:.2f}, far pair {far:.2f}", "model": spec}

    # -- project access (Research Pipeline §6): a person's controls, never the model's --
    def projects(self) -> dict[str, Any]:
        from . import projects
        data = projects.state(self.vault)
        for r in data["roots"]:
            r["exists"] = Path(r["path"]).is_dir()
        return data

    def set_projects_enabled(self, on: bool) -> dict[str, Any]:
        from . import projects
        projects.set_enabled(self.vault, on)
        return self.projects()

    def add_project_root(self, path: str, project: str) -> dict[str, Any]:
        from . import projects
        try:
            projects.add_root(self.vault, path, project)
        except TypeError as exc:
            raise ApiError(400, str(exc)) from exc
        return self.projects()

    def set_project_writes(self, root_id: str, allowed: bool) -> dict[str, Any]:
        from . import projects
        try:
            projects.set_writes(self.vault, root_id, allowed)
        except TypeError as exc:
            raise ApiError(404, str(exc)) from exc
        return self.projects()

    def remove_project_root(self, root_id: str) -> dict[str, Any]:
        from . import projects
        projects.remove_root(self.vault, root_id)
        return self.projects()

    def scan_project_root(self, root_id: str) -> dict[str, Any]:
        from . import projects
        entry = next((r for r in projects.state(self.vault)["roots"] if r["id"] == root_id), None)
        if entry is None:
            raise ApiError(404, f"no project root {root_id!r}")
        if not Path(entry["path"]).is_dir():
            raise ApiError(409, f"{entry['path']} has moved or gone: add it again")
        out = projects.scan(self.vault, Path(entry["path"]), entry.get("project") or "")
        return {**self.projects(), "scanned": out}

    def set_library(self, promotion_mode: str = "",
                    review: dict[str, bool] | None = None) -> dict[str, Any]:
        """Settings -> Library: the promotion mode, and the review gate (§4 G3) on replies
        and on drafted offerings - `review_replies` / `review_offerings` under [clerk]."""
        if promotion_mode:
            if promotion_mode not in ("person", "agent"):
                raise ApiError(400, "promotion mode is 'person' or 'agent'")
            self.vault.set_setting("promotion", "mode", promotion_mode)
        for key, on in (review or {}).items():
            if key not in ("review_replies", "review_offerings"):
                raise ApiError(400, f"no review setting {key!r}")
            self.vault.set_setting("clerk", key, bool(on))
        return self.library()

    # -- the document pane: the vault's own notes, read-only ---------------
    def _visible(self, rel: str) -> Path:
        try:
            return self.vault.safe_relative(rel)
        except Refusal as exc:
            raise ApiError(403, exc.detail) from exc

    def list_files(self, rel: str = "") -> dict[str, Any]:
        folder = self._visible(rel)
        if not folder.is_dir():
            raise ApiError(404, f"no folder {rel!r}")
        root = self.vault.root.resolve()
        entries = []
        for child in sorted(folder.iterdir(), key=lambda c: (not c.is_dir(), c.name.lower())):
            if child.name.startswith("."):
                continue
            if child.is_dir():
                entries.append({"name": child.name, "kind": "dir",
                                "path": child.resolve().relative_to(root).as_posix()})
            elif child.suffix.lower() == ".md":
                entries.append({"name": child.stem, "kind": "file",
                                "path": child.resolve().relative_to(root).as_posix()})
            elif child.suffix.lower() in SCRIPT_SUFFIXES:     # opened as code; runnable
                entries.append({"name": child.name, "kind": "file", "script": True,
                                "path": child.resolve().relative_to(root).as_posix()})
        here = folder.relative_to(root).as_posix()
        return {"dir": "" if here == "." else here, "entries": entries}

    def read_file(self, rel: str) -> dict[str, Any]:
        """A note by vault path (with or without `.md`), or by bare name when
        the name is unique enough to find: what a [[link]] in the chat holds."""
        rel = (rel or "").strip()
        if Path(rel).suffix.lower() in SCRIPT_SUFFIXES:
            # A script is shown as code, never rendered - and only a script can be run
            # (the pane's Run button, EXECUTION_SANDBOX_ONLY).
            target = self._visible(rel)
            if not target.is_file():
                raise ApiError(404, f"no file {rel!r}")
            if target.stat().st_size > 2_000_000:
                raise ApiError(413, "that file is too large to show here")
            root = self.vault.root.resolve()
            return {"path": target.resolve().relative_to(root).as_posix(), "name": target.name,
                    "text": target.read_text(encoding="utf-8", errors="replace"),
                    "script": SCRIPT_SUFFIXES[target.suffix.lower()],
                    "modified": round(target.stat().st_mtime)}
        candidates = [rel if rel.lower().endswith(".md") else f"{rel}.md"]
        path = None
        for candidate in candidates:
            target = self._visible(candidate)
            if target.is_file():
                path = target
                break
        if path is None and "/" not in rel:
            wanted = f"{rel}.md".lower() if not rel.lower().endswith(".md") else rel.lower()
            for found in sorted(self.vault.root.rglob("*.md")):
                relative = found.relative_to(self.vault.root)
                if found.name.lower() == wanted and \
                        not any(p.startswith(".") for p in relative.parts):
                    path = found
                    break
        if path is None:
            raise ApiError(404, f"no note {rel!r}")
        if path.stat().st_size > 2_000_000:
            raise ApiError(413, "that note is too large to show here")
        root = self.vault.root.resolve()
        return {"path": path.resolve().relative_to(root).as_posix(), "name": path.stem,
                "text": path.read_text(encoding="utf-8", errors="replace"),
                "modified": round(path.stat().st_mtime)}

    def upload_file(self, dir_rel: str, filename: str, data: bytes) -> dict[str, Any]:
        """The composer's paperclip: a file the person had on their own machine,
        saved into the vault (Inbox/ unless they chose to browse elsewhere) so
        `ingest` can reach it by the same vault-relative path a person dropping
        it in by hand would use."""
        folder = self._visible(dir_rel or "Inbox")
        folder.mkdir(parents=True, exist_ok=True)
        name = notes.safe_name(filename) or "attachment"
        target = folder / name
        stem, suffix = target.stem, target.suffix
        n = 1
        while target.exists():
            target = folder / f"{stem} ({n}){suffix}"
            n += 1
        target.write_bytes(data)
        root = self.vault.root.resolve()
        return {"path": target.resolve().relative_to(root).as_posix(), "name": target.name}

    def state(self) -> dict[str, Any]:
        data = self.settings.data
        return {"version": __version__, "vault": self.vault.root.name,
                "vault_name": self.vault.title, "vault_path": str(self.vault.root),
                "mode": self.broker.mode, "pending": self.broker.pending(),
                "tool_settings": dict(self.broker.settings),
                "busy": self.busy, "tiers": data.get("tiers") or [],
                "lead": self.lead_status(),
                "working_context": data["working_context"],
                "reply_length": data["reply_length"], "stance": data["stance"],
                "effort": self._effort_view(),
                "keys": self.keys.all(), "key_backend": self.keys.backend,
                "session": self.session_view(),
                "actions": [a.public() for a in self.actions.values()],
                "queued_actions": list(QUEUED), "queued_inputs": self.queued_inputs(),
                "last_event": self.hub.last()}

    def _effort_view(self) -> dict[str, Any]:
        from . import effort
        return effort.profile(self.settings.data.get("effort"))

    def queued_inputs(self) -> dict[str, dict[str, Any]]:
        """For each one-click action, the inputs a person must give before it
        can start (roadmap §4 D1) - a required input with no default, like
        weekly-review's `project`. The queue popover asks for these first."""
        library = workflows.Library(self.vault)
        out: dict[str, dict[str, Any]] = {}
        for name in QUEUED:
            try:
                inputs = library.get(name).data.get("inputs") or {}
            except workflows.DefinitionError:
                continue
            needed = {key: {"type": (spec or {}).get("type", "string")}
                      for key, spec in inputs.items()
                      if not isinstance(spec, dict) or "default" not in spec}
            if needed:
                out[name] = needed
        return out


# -------------------------------------------------------------------- HTTP

def _asset(name: str) -> bytes | None:
    try:
        path = resources.files("resource_librarian").joinpath("ui", name)
        return path.read_bytes() if path.is_file() else None
    except (FileNotFoundError, ModuleNotFoundError):
        return None


TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}


def make_handler(app: App) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "librarian"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:     # quiet: no request logs
            return

        # -- the boundary ----------------------------------------------------
        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            return host in LOOPBACK

        def _origin_ok(self) -> bool:
            origin = self.headers.get("Origin")
            if not origin:
                return True
            own = {f"http://{self.headers.get('Host')}"}
            return origin in own or origin in app.allowed_origins

        def _token_ok(self, query: dict[str, list[str]]) -> bool:
            given = self.headers.get("X-Librarian-Token") or (query.get("token") or [""])[0]
            return secrets.compare_digest(given, app.token)

        def _send(self, status: int, body: bytes, kind: str, extra: dict[str, str] | None = None
                  ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in {**self._cors(), **(extra or {})}.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _cors(self) -> dict[str, str]:
            """Only a host origin (the Obsidian view) is let read across origins;
            a page on any other site gets no CORS headers, so its browser
            refuses it the response."""
            origin = self.headers.get("Origin") or ""
            if origin in app.allowed_origins:
                return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
            return {}

        def do_OPTIONS(self) -> None:                       # noqa: N802
            if not self._host_ok() or not self._cors():
                return self._json(403, {"error": "refused"})
            self._send(204, b"", "text/plain", {
                "Access-Control-Allow-Methods": "GET, POST",
                "Access-Control-Allow-Headers": "Content-Type, X-Librarian-Token",
                "Access-Control-Max-Age": "600"})

        def _json(self, status: int, payload: Any) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False, default=str)
                       .encode("utf-8"), "application/json; charset=utf-8")

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ApiError(413, "request too large")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw or b"{}")
            except json.JSONDecodeError as exc:
                raise ApiError(400, f"invalid JSON: {exc}") from exc
            if not isinstance(data, dict):
                raise ApiError(400, "the body is a JSON object")
            return data

        # -- routes ----------------------------------------------------------
        def do_GET(self) -> None:                           # noqa: N802
            url = urlparse(self.path)
            query = parse_qs(url.query)
            if not self._host_ok():
                return self._json(403, {"error": "refused: not a loopback host"})
            if not url.path.startswith("/api/"):
                return self._static(url.path)
            if not self._token_ok(query):
                return self._json(403, {"error": "refused: missing or stale page token; "
                                                 "reload the page"})
            try:
                if url.path == "/api/events":
                    return self._events(int((query.get("since") or ["0"])[0] or 0))
                if url.path == "/api/state":
                    return self._json(200, app.state())
                if url.path == "/api/tools":
                    return self._json(200, {"tools": [
                        {"name": s.name, "purpose": s.card.purpose, "effect": s.effect,
                         "tier": s.tier, "schema": s.json_schema()}
                        for s in sorted(REGISTRY.for_tier("curate"), key=lambda s: s.name)]})
                if url.path == "/api/models":
                    return self._json(200, app.models((query.get("provider") or [""])[0]))
                if url.path == "/api/library":
                    return self._json(200, app.library())
                if url.path == "/api/services":
                    return self._json(200, app.services())
                if url.path == "/api/projects":
                    return self._json(200, app.projects())
                if url.path == "/api/offerings/staged":
                    from .tools.sessions import staged_offering, staged_offerings
                    wanted = (query.get("id") or [""])[0]
                    if wanted:
                        try:
                            return self._json(200, staged_offering(app.vault, wanted))
                        except TypeError as exc:
                            raise ApiError(404, str(exc)) from exc
                    return self._json(200, {"offerings": staged_offerings(app.vault)})
                if url.path == "/api/claims/runs":
                    from . import claim_run
                    return self._json(200, {"runs": claim_run.RunnableStore(app.vault).list(),
                                            "docker": claim_run.docker_status()[1]})
                if url.path == "/api/libraries":
                    from . import libraries
                    return self._json(200, {"libraries": libraries.known(app.vault),
                                            "current": str(app.vault.root)})
                if url.path == "/api/files":
                    return self._json(200, app.list_files((query.get("dir") or [""])[0]))
                if url.path == "/api/file":
                    return self._json(200, app.read_file((query.get("path") or [""])[0]))
                if url.path == "/api/usage":
                    return self._json(200, app.usage((query.get("provider") or [""])[0]))
                if url.path == "/api/keys":
                    return self._json(200, {"keys": app.keys.all(),
                                            "backend": app.keys.backend})
                if url.path == "/api/mcp":
                    return self._json(200, app.mcp_status())
                if url.path == "/api/mcp/registry":
                    return self._json(200, app.mcp_registry_search(
                        (query.get("q") or [""])[0]))
                return self._json(404, {"error": f"no route {url.path}"})
            except ApiError as exc:
                return self._json(exc.status, exc.body)

        def do_POST(self) -> None:                          # noqa: N802
            url = urlparse(self.path)
            if not self._host_ok():
                return self._json(403, {"error": "refused: not a loopback host"})
            if not self._origin_ok():
                return self._json(403, {"error": "refused: a page on another origin"})
            if not self._token_ok(parse_qs(url.query)):
                return self._json(403, {"error": "refused: missing or stale page token; "
                                                 "reload the page"})
            try:
                if url.path == "/api/attach":
                    return self._attach(parse_qs(url.query))
                body = self._body()
                return self._json(200, self._post(url.path, body))
            except ApiError as exc:
                return self._json(exc.status, exc.body)
            except Exception as exc:                        # noqa: BLE001
                return self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

        def _attach(self, query: dict[str, list[str]]) -> None:
            """Raw bytes, not JSON: a file from the composer's paperclip is too
            large, and the wrong shape, for `_body()`'s JSON cap."""
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                raise ApiError(400, "no file was sent")
            if length > MAX_UPLOAD:
                raise ApiError(413, f"that file is over the attachment limit "
                                    f"({MAX_UPLOAD // 1_000_000}MB); place it in the vault's "
                                    f"Inbox/ folder directly instead")
            data = self.rfile.read(length)
            name = (query.get("name") or [""])[0]
            if not name:
                raise ApiError(400, "name is required")
            folder = (query.get("dir") or ["Inbox"])[0]
            return self._json(200, app.upload_file(folder, name, data))

        def _post(self, path: str, body: dict[str, Any]) -> Any:
            if path == "/api/chat":
                return app.chat(str(body.get("text") or ""))
            if path == "/api/chat/cancel":
                return app.cancel_turn()
            if path == "/api/chat/reset":
                return app.reset()
            if path == "/api/chat/attach":
                return app.attach(str(body.get("session_id") or ""))
            if path.startswith("/api/tool/"):
                name = path[len("/api/tool/"):]
                arguments = body.get("arguments") or {}
                if not isinstance(arguments, dict):
                    raise ApiError(400, "arguments is a JSON object")
                return app.person_call(name, arguments, str(body.get("session") or ""))
            if path == "/api/mode":
                return app.set_mode(str(body.get("mode") or ""))
            if path == "/api/permission":
                answer = str(body.get("answer") or "")
                if answer not in ANSWERS:
                    raise ApiError(400, f"answer is one of {ANSWERS}")
                try:
                    return app.broker.answer(str(body.get("id") or ""), answer)
                except LookupError as exc:
                    raise ApiError(404, str(exc)) from exc
            if path == "/api/tool-setting":
                try:
                    app.broker.set_tool(str(body.get("tool") or ""),
                                        str(body.get("setting") or ""))
                except ValueError as exc:
                    raise ApiError(400, str(exc)) from exc
                return {"tool_settings": dict(app.broker.settings)}
            if path == "/api/keys":
                return app.save_key(str(body.get("provider") or ""), str(body.get("key") or ""),
                                    bool(body.get("overwrite")))
            if path == "/api/keys/remove":
                if not body.get("confirm"):
                    raise ApiError(409, "confirm removal", confirm=(
                        "Remove the saved key? It can't be recovered from here."))
                return app.keys.remove(str(body.get("provider") or ""))
            if path == "/api/keys/check":
                return app.check(str(body.get("provider") or ""))
            if path == "/api/mcp/config":
                return app.mcp_save_config(body.get("mcpServers"))
            if path == "/api/mcp/accept":
                return app.mcp_accept(str(body.get("name") or ""))
            if path == "/api/mcp/server":
                return app.mcp_add_server(str(body.get("name") or ""), body.get("server"))
            if path == "/api/mcp/library":
                return app.mcp_set_library_enabled(str(body.get("name") or ""),
                                                   bool(body.get("enabled")))
            if path == "/api/mcp/enable":
                return app.mcp_set_enabled(str(body.get("name") or ""), bool(body.get("enabled")))
            if path == "/api/mcp/remove":
                return app.mcp_remove_server(str(body.get("name") or ""))
            if path == "/api/tiers":
                return app.set_tiers(body.get("tiers") or [], str(body.get("override") or ""))
            if path == "/api/sandbox/run_file":
                # A person's "Run this script" (EXECUTION_SANDBOX_ONLY): their own call
                return app.person_call("sandbox_run_file", {"path": str(body.get("path") or "")})
            if path == "/api/tts/plan":
                return app.tts_plan(str(body.get("text") or ""), str(body.get("path") or ""))
            if path == "/api/tts/chunk":
                return app.tts_chunk(str(body.get("plan") or ""), int(body.get("index") or 0))
            if path == "/api/effort":
                return app.set_effort(body.get("level"))
            if path == "/api/context":
                return app.set_context(body.get("working_context"), body.get("reply_length"),
                                       body.get("stance"))
            if path == "/api/library":
                review = body.get("review")
                return app.set_library(str(body.get("promotion_mode") or ""),
                                       review if isinstance(review, dict) else None)
            if path == "/api/services":
                return app.set_service(str(body.get("slot") or ""), str(body.get("provider") or ""),
                                       str(body.get("model") or ""))
            if path == "/api/services/test":
                return app.test_service(str(body.get("slot") or ""))
            if path == "/api/projects/enable":
                return app.set_projects_enabled(bool(body.get("enabled")))
            if path == "/api/projects/add":
                return app.add_project_root(str(body.get("path") or ""),
                                            str(body.get("project") or ""))
            if path == "/api/offerings/decide":
                # The person's Promote / Decline on a staged offering (Staging -> Offerings)
                return app.decide_offering(str(body.get("id") or ""),
                                           str(body.get("decision") or ""))
            if path == "/api/claims/run":
                # A person's "Run it" (EXECUTION_SANDBOX_ONLY): the curate-tier tool, through
                # the person's own call - never the model's
                return app.person_call("run_claim_input", {"run_id": str(body.get("id") or "")})
            if path == "/api/projects/writes":
                return app.set_project_writes(str(body.get("id") or ""), bool(body.get("allowed")))
            if path == "/api/projects/remove":
                return app.remove_project_root(str(body.get("id") or ""))
            if path == "/api/projects/scan":
                return app.scan_project_root(str(body.get("id") or ""))
            if path == "/api/services/vector_intents":
                return app.set_vector_intents([str(i) for i in body.get("intents") or []])
            if path == "/api/library/switch":
                return self.server.board.switch(str(body.get("path") or ""),  # type: ignore[attr-defined]
                                                force=bool(body.get("force")))
            if path == "/api/libraries/forget":
                from . import libraries
                return {"forgotten": libraries.forget(str(body.get("path") or ""))}
            if path == "/api/actions":
                try:
                    return app.start_action(str(body.get("name") or ""), body.get("inputs"))
                except workflows.DefinitionError as exc:
                    raise ApiError(404, str(exc)) from exc
            if path.startswith("/api/actions/") and path.endswith("/cancel"):
                return app.cancel_action(path.split("/")[3])
            raise ApiError(404, f"no route {path}")

        def _static(self, path: str) -> None:
            name = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
            if "/" in name or name.startswith("."):
                return self._json(404, {"error": "not found"})
            data = _asset(name)
            if data is None:
                if name == "index.html":
                    data = (b"<!doctype html><title>Librarian</title><p>The interface is not "
                            b"built in this install. The API is running.</p>")
                else:
                    return self._json(404, {"error": "not found"})
            if name == "index.html":
                data = data.replace(b"__LIBRARIAN_TOKEN__", app.token.encode())
            kind = TYPES.get(Path(name).suffix, "application/octet-stream")
            self._send(200, data, kind, {
                "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; "
                                           "style-src 'self' 'unsafe-inline'; "
                                           "frame-ancestors 'none'",
                "Referrer-Policy": "no-referrer"})

        def _events(self, since: int) -> None:
            waiting: deque[dict[str, Any]] = deque()
            ready = threading.Event()

            def listener(event: dict[str, Any]) -> None:
                waiting.append(event)
                ready.set()
            stop = app.hub.subscribe(listener)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            for k, v in self._cors().items():
                self.send_header(k, v)
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            try:
                for event in app.hub.since(since):
                    self._event(event)
                while not self.server.closing:                  # type: ignore[attr-defined]
                    if not ready.wait(15):
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
                        continue
                    ready.clear()
                    while waiting:
                        self._event(waiting.popleft())
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                stop()
                self.close_connection = True

        def _event(self, event: dict[str, Any]) -> None:
            data = json.dumps(event, ensure_ascii=False, default=str)
            self.wfile.write(f"id: {event['seq']}\nevent: {event['type']}\n"
                             f"data: {data}\n\n".encode("utf-8"))
            self.wfile.flush()

    return Handler


class Switchboard:
    """Which library the running server serves, and switching it in place -
    the same port and token, like switching vaults in Obsidian. The new
    library is loaded first, then swapped in atomically; the one it replaces
    retires in the background (`App.retire`) rather than being cut off."""

    def __init__(self, app: App):
        self.app = app
        self._lock = threading.Lock()
        self.retiring: list[App] = []

    def switch(self, path: str, force: bool = False) -> dict[str, Any]:
        from . import libraries
        try:
            vault = libraries.resolve(path)
        except ValueError as exc:
            raise ApiError(400, str(exc)) from exc
        with self._lock:
            old = self.app
            if vault.root == old.vault.root:
                return {"switched": False, "vault": vault.title, "reason": "already open"}
            running = old.running()
            if running and not force:
                raise ApiError(409, f"{old.vault.title} still has work in progress; "
                                    f"switch anyway and let it finish in the background?",
                               running=running)
            own = getattr(old._provider_for, "__self__", None) is old
            new = App(vault, token=old.token, keys=old.keys,
                      provider_for=None if own else old._provider_for,
                      allowed_origins=old.allowed_origins,
                      broker_timeout=old.broker_timeout, mcp=old.mcp)
            self.app = new
        libraries.remember(old.vault)          # so it can always be switched back to
        libraries.remember(vault)
        old.hub.publish({"type": "library_switched", "to": vault.title})
        self.retiring.append(old)

        def retire() -> None:
            old.retire()
            self.retiring.remove(old)
        threading.Thread(target=retire, daemon=True, name="library-retire").start()
        return {"switched": True, "vault": vault.title, "from": old.vault.title,
                "finishing_in_background": running}


class _Current:
    """The handler's view of `App`: every attribute read goes to whichever
    library the switchboard holds right now."""

    def __init__(self, board: Switchboard):
        object.__setattr__(self, "_board", board)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._board.app, name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._board.app, name, value)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    closing = False
    board: Switchboard

    def shutdown(self) -> None:
        self.closing = True
        super().shutdown()


def build(app: App, port: int = 0) -> Server:
    board = Switchboard(app)
    server = Server(("127.0.0.1", port), make_handler(_Current(board)))  # type: ignore[arg-type]
    server.board = board
    return server


def serve(vault_path: str | None, port: int = 8323, token: str = "",
          open_browser: bool = False) -> int:
    import os
    import sys
    try:
        vault = Vault.find(vault_path or os.environ.get("LIBRARIAN_VAULT") or None)
    except Refusal:
        from .library_picker import serve_picker
        return serve_picker(port, open_browser)
    app = App(vault, token=token or os.environ.get("LIBRARIAN_TOKEN", ""))
    from . import libraries
    try:
        libraries.remember(vault)
    except OSError:
        pass                                  # a read-only config dir never stops the app
    server = build(app, port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    # The host that started the core reads this line to find the port.
    print(json.dumps({"listening": url, "vault": str(vault.root)}), flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    if os.environ.get("LIBRARIAN_EXIT_WITH_STDIN"):
        # A host that started the core (the Obsidian plugin) holds stdin open;
        # when the host goes, even by crashing, the core goes with it.
        def watch() -> None:
            sys.stdin.read()
            server.closing = True
            threading.Thread(target=server.shutdown, daemon=True).start()
        threading.Thread(target=watch, daemon=True, name="host-watch").start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.closing = True
        server.server_close()
        if server.board.app.mcp is not None:
            server.board.app.mcp.stop()
    return 0
