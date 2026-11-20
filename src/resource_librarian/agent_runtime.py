"""Profiles, compact tool bundles, and audited macro definitions.

The registry remains the final permission boundary.  This module changes what
an agent is offered and records why; it never grants a tool the registry,
broker, session phase, or caller would otherwise refuse.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .coordination import atomic_write_text
from .registry import REGISTRY, TIERS, Context, ToolSpec
from .vault import now_iso

# A phase offers its declared bundle, up to two session-aware required actions and the three tail
# tools (read_result, macro_run, macro_plan). The cap clips from the end, so it must hold all of
# them: at 12, Map, Search and Judge would have silently lost their tail tools once the gate tools
# were added (tests/test_phase_bundles.py). 20 since the research phases gained up to six read-only
# Geo-Grapher tools (2026-11-20); 22 once request_budget joined the tail tools, the same day.
MAX_BUNDLE_TOOLS = 22


class ProfileCapacityError(RuntimeError):
    """The selected profile already has all of its permitted runs in flight."""


class ProfileRunGate:
    """A small, Core-local concurrency gate for versioned agent profiles.

    This is intentionally not a distributed scheduler: the VaultCoordinator
    owns the one mutable Core for a vault, so a process-local count is the
    correct final guard.  Keeping the count here makes the same policy usable
    by the chat loop, Clerk orchestration, and future first-party packs
    without teaching each caller how to manage semaphores.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: dict[str, int] = {}

    def acquire(self, profile: "AgentProfile") -> Callable[[], None]:
        """Reserve one slot and return its idempotent release callback.

        A changed profile limit applies to the next acquisition.  Existing
        work is allowed to finish rather than being terminated mid-session.
        """
        profile.validate()
        with self._lock:
            active = self._active.get(profile.id, 0)
            if active >= profile.concurrency_limit:
                raise ProfileCapacityError(
                    f"agent profile {profile.id!r} reached its concurrency limit "
                    f"({profile.concurrency_limit})")
            self._active[profile.id] = active + 1
        released = False

        def release() -> None:
            nonlocal released
            with self._lock:
                if released:
                    return
                released = True
                remaining = max(0, self._active.get(profile.id, 1) - 1)
                if remaining:
                    self._active[profile.id] = remaining
                else:
                    self._active.pop(profile.id, None)

        return release

    def status(self) -> dict[str, int]:
        with self._lock:
            return dict(self._active)


class ProfiledEndpoint:
    """A role-profile boundary around a Clerk/Scribe-compatible endpoint.

    Clerk tasks deliberately have no conversation or vault-writing surface,
    but they are still model calls.  Letting their older endpoint configuration
    bypass AgentProfile would make its qualification, route, concurrency and
    spend limits advisory.  This small duck-typed facade keeps the existing
    ``clerk.Endpoint`` contract (``concurrency`` and ``complete``) and routes
    every individual task through those controls.

    It intentionally is *not* a new model router: ``for_task`` still chooses
    an already configured legacy route, and a failed profile check becomes a
    ClerkUnavailable condition so work is queued rather than silently sent to
    another model.
    """

    def __init__(self, endpoint: Any, profile: "AgentProfile", *,
                 gate: ProfileRunGate | None = None,
                 route_guard: Callable[["AgentProfile", Any], dict[str, Any] | None] | None = None,
                 rate_card: dict[str, Any] | None = None,
                 read_route: dict[str, Any] | None = None) -> None:
        profile.validate()
        self.endpoint = endpoint
        self.profile = profile
        self.gate = gate
        self.route_guard = route_guard
        self.rate_card = rate_card
        self.read_route = dict(read_route or {})
        underlying_concurrency = max(1, int(getattr(endpoint, "concurrency", 1) or 1))
        # The effort slider can ask a legacy endpoint for more parallel work,
        # but a HostRegistry route has a hard personal ceiling.  Preserve that
        # fact separately from the mutable current setting so a later effort
        # increase never turns a local/model host limit into a suggestion.
        endpoint_ceiling = max(0, int(getattr(endpoint, "concurrency_ceiling", 0) or 0))
        if endpoint_ceiling:
            underlying_concurrency = min(underlying_concurrency, endpoint_ceiling)
        self.concurrency = min(underlying_concurrency, profile.concurrency_limit)
        self.name = f"profile:{profile.id}:{getattr(endpoint, 'name', 'endpoint')}"
        self._started = time.monotonic()
        self._reserved_tokens = 0
        self._reserved_cost = 0.0
        self._lock = threading.Lock()

    @staticmethod
    def _unavailable(detail: str) -> Exception:
        # Import lazily: Clerk intentionally has no dependency on profiles,
        # and this keeps its standalone/replay use untouched.
        from .clerk import ClerkUnavailable
        return ClerkUnavailable(detail)

    @staticmethod
    def _token_estimate(value: Any) -> int:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = repr(value)
        return max(1, (len(text) + 3) // 4)

    @staticmethod
    def _prices(rate_card: dict[str, Any] | None) -> tuple[float, float] | None:
        if not isinstance(rate_card, dict):
            return None
        raw_input = rate_card.get("input_per_1m", rate_card.get("price_input_per_1m"))
        raw_output = rate_card.get("output_per_1m", rate_card.get("price_output_per_1m"))
        if raw_input is None or raw_output is None:
            return None
        try:
            return max(0.0, float(raw_input)), max(0.0, float(raw_output))
        except (TypeError, ValueError):
            return None

    def _target(self, payload: dict[str, Any]) -> Any:
        selector = getattr(self.endpoint, "for_task", None)
        if callable(selector):
            return selector(str(payload.get("task") or ""))
        return self.endpoint

    def _reserve(self, payload: dict[str, Any], rate_card: dict[str, Any] | None,
                 headroom: int = 0) -> dict[str, Any]:
        """Reserve a conservative one-call background-task budget.

        ``headroom`` is output the route's reviewed dialect adds after this
        point (a reasoning reserve); it is spent, so it is reserved too.
        """
        try:
            requested = max(1, int(payload.get("max_tokens") or self.profile.output_budget))
        except (TypeError, ValueError):
            requested = self.profile.output_budget
        prepared = dict(payload)
        prepared["max_tokens"] = min(requested, self.profile.output_budget)
        prompt_tokens = self._token_estimate({key: value for key, value in prepared.items()
                                              if key != "max_tokens"})
        wire_output = prepared["max_tokens"] + max(0, int(headroom))
        reserved_tokens = prompt_tokens + wire_output
        with self._lock:
            if self.profile.token_budget and \
                    self._reserved_tokens + reserved_tokens > self.profile.token_budget:
                raise self._unavailable(
                    f"{self.profile.role} profile token budget ({self.profile.token_budget}) "
                    "would be exceeded by the next Clerk task")
            reserved_cost = 0.0
            if self.profile.cost_budget_usd:
                prices = self._prices(rate_card or self.rate_card or
                                      self.profile.route_policy.get("rate_card"))
                if prices is None:
                    raise self._unavailable(
                        f"{self.profile.role} profile has a cost budget but no input/output rate card")
                reserved_cost = ((prompt_tokens * prices[0] + wire_output * prices[1]) /
                                 1_000_000)
                if self._reserved_cost + reserved_cost > self.profile.cost_budget_usd + 1e-12:
                    raise self._unavailable(
                        f"{self.profile.role} profile cost budget (${self.profile.cost_budget_usd:.4f}) "
                        "would be exceeded by the next Clerk task")
            self._reserved_tokens += reserved_tokens
            self._reserved_cost += reserved_cost
        return prepared

    def complete(self, payload: dict[str, Any], repair: str = "") -> tuple[str, str]:
        if self.profile.time_budget_seconds and \
                time.monotonic() - self._started >= self.profile.time_budget_seconds:
            raise self._unavailable(
                f"{self.profile.role} profile time budget ({self.profile.time_budget_seconds}s) is exhausted")
        target = self._target(payload)
        if target is None:
            raise self._unavailable(f"no configured {self.profile.role} route covers {payload.get('task')!r}")
        try:
            rate_card = self.route_guard(self.profile, target) if self.route_guard else self.rate_card
        except Exception as exc:  # profile failures must queue, never silently fail over
            raise self._unavailable(f"{self.profile.role} profile cannot use this route: {exc}") from exc
        headroom = getattr(target, "output_headroom_tokens", None)
        prepared = self._reserve(payload, rate_card, headroom() if callable(headroom) else 0)
        minimum = max(0, int(getattr(target, "min_tokens", 0) or 0))
        if minimum > prepared["max_tokens"]:
            raise self._unavailable(
                f"{self.profile.role} profile output budget ({prepared['max_tokens']}) is below "
                f"the route's required minimum ({minimum})")
        release = lambda: None
        try:
            if self.gate is not None:
                release = self.gate.acquire(self.profile)
            return target.complete(prepared, repair)
        except ProfileCapacityError as exc:
            raise self._unavailable(str(exc)) from exc
        finally:
            release()


@dataclass
class AgentProfile:
    id: str
    role: str
    # Profiles name routing constraints but never provider credentials.  They
    # are consequently safe to keep in the vault alongside a workflow.
    route_policy: dict[str, Any] = field(default_factory=dict)
    required_qualification: str = "screened"
    allowed_bundles: list[str] = field(default_factory=list)
    permission_ceiling: str = "contribute"
    token_budget: int = 0
    output_budget: int = 4096
    cost_budget_usd: float = 0.0
    time_budget_seconds: int = 0
    retry_policy: str = "bounded"
    failover_policy: str = "ask"
    concurrency_limit: int = 1
    validation_rules: list[str] = field(default_factory=list)
    checkpoint_policy: dict[str, Any] = field(default_factory=lambda: {"surface": "ui"})
    schema_version: int = 1
    revision: int = 1

    def validate(self) -> "AgentProfile":
        """Normalise a vault-scoped profile without ever broadening access.

        The registry applies ``permission_ceiling`` again at call time.  This
        is a second line of defence for manually edited profile JSON, rather
        than trusting the Settings form alone.
        """
        # Underscores are part of the public default profile ids (notably
        # ``research_helper``), so retain them rather than saving a selector
        # value that no later ProfileStore lookup can resolve.
        self.id = re.sub(r"[^a-z0-9_-]+", "-", str(self.id).strip().lower().replace(" ", "-")) \
            .strip("-")[:80]
        self.role = str(self.role).strip().lower().replace(" ", "_")[:80]
        if not self.id or not self.role:
            raise ValueError("profile needs a non-empty id and role")
        if self.permission_ceiling not in TIERS:
            raise ValueError("permission ceiling is consult, contribute or curate")
        if self.required_qualification not in ("experimental", "screened", "verified_local",
                                               "verified_release"):
            raise ValueError("required qualification is experimental, screened, verified_local or verified_release")
        if not isinstance(self.route_policy, dict) or not isinstance(self.checkpoint_policy, dict):
            raise ValueError("route_policy and checkpoint_policy are objects")
        if "binding_role" in self.route_policy:
            from .role_routes import CHAT_ROLES
            if self.route_policy["binding_role"] not in CHAT_ROLES:
                raise ValueError(f"route_policy.binding_role is one of {CHAT_ROLES}")
        # Route policy is deliberately an allow-list, never a way to invent a
        # route.  Unknown keys remain available for future first-party
        # adapters, but the supported selector fields must be simple lists so
        # a hand-edited vault cannot turn a malformed value into a broad
        # match.  ``rate_card`` is only used to conservatively reserve a
        # profile cost budget; it has no bearing on provider authentication.
        for key in ("host_ids", "providers", "model_ids"):
            value = self.route_policy.get(key)
            if value is not None and (not isinstance(value, list) or
                                      not all(isinstance(item, str) and item.strip() for item in value)):
                raise ValueError(f"route_policy.{key} is a list of non-empty strings")
        # MF-011: the route's context window, when its catalogue entry has none
        # (a local or custom model). It only ever narrows what is sent.
        context_tokens = self.route_policy.get("context_tokens")
        temperature = self.route_policy.get('temperature')
        if temperature is not None and (type(temperature) not in (int,float) or
                                        not math.isfinite(temperature) or not 0<=temperature<=2):
            raise ValueError('route_policy.temperature is a finite number from 0 to 2')
        if context_tokens is not None and (isinstance(context_tokens, bool) or
                                           not isinstance(context_tokens, int) or context_tokens < 1024):
            raise ValueError("route_policy.context_tokens is a whole number of tokens, at least 1024")
        rate_card = self.route_policy.get("rate_card")
        if rate_card is not None and not isinstance(rate_card, dict):
            raise ValueError("route_policy.rate_card is an object")
        if isinstance(rate_card, dict):
            for key in ("input_per_1m", "output_per_1m", "price_input_per_1m", "price_output_per_1m"):
                if key in rate_card:
                    try:
                        if float(rate_card[key]) < 0:
                            raise ValueError
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"route_policy.rate_card.{key} is a non-negative number") from exc
        if not isinstance(self.allowed_bundles, list) or \
                not all(isinstance(name, str) and name in BUNDLES for name in self.allowed_bundles):
            raise ValueError(f"allowed bundles are known bundle ids: {sorted(BUNDLES)}")
        if self.retry_policy not in ("none", "bounded"):
            raise ValueError("retry policy is none or bounded")
        if self.failover_policy not in ("never", "ask"):
            raise ValueError("failover policy is never or ask")
        try:
            self.token_budget = max(0, min(int(self.token_budget or 0), 10_000_000))
            self.output_budget = max(1, min(int(self.output_budget or 4096), 200_000))
            self.cost_budget_usd = max(0.0, min(float(self.cost_budget_usd or 0.0), 1_000_000.0))
            self.time_budget_seconds = max(0, min(int(self.time_budget_seconds or 0), 604_800))
            self.concurrency_limit = max(1, min(int(self.concurrency_limit or 1), 32))
        except (TypeError, ValueError) as exc:
            raise ValueError("profile budgets and concurrency must be numbers") from exc
        if not isinstance(self.validation_rules, list) or not all(isinstance(x, str) for x in self.validation_rules):
            raise ValueError("validation_rules is a list of strings")
        self.allowed_bundles = list(dict.fromkeys(self.allowed_bundles))
        self.validation_rules = list(dict.fromkeys(x[:120] for x in self.validation_rules))[:12]
        self.schema_version = max(1, int(self.schema_version or 1))
        self.revision = max(1, int(self.revision or 1))
        return self

    def public(self) -> dict[str, Any]:
        return asdict(self)


def route_permitted(profile: AgentProfile, route: dict[str, Any]) -> tuple[bool, str]:
    """Check a profile's optional route allow-lists without selecting a route.

    A blank list means "no restriction".  Route changes themselves still go
    through the host registry, qualification, and explicit person controls;
    this merely stops an agent profile from using a route its vault policy
    did not allow.
    """
    policy = profile.route_policy or {}
    host = str(route.get("host_id") or "").strip().casefold()
    provider = str(route.get("provider") or "").strip().casefold()
    model = str(route.get("model") or "").strip().casefold()
    checks = (("host_ids", host, "host"), ("providers", provider, "provider"),
              ("model_ids", model, "model"))
    for key, actual, label in checks:
        raw = policy.get(key) or []
        allowed = {str(item).strip().casefold() for item in raw if str(item).strip()}
        if key == "providers":
            from .providers import PRESETS
            canonical = lambda value: "preset-" + value if value in PRESETS else value
            actual = canonical(actual) if not host or host.startswith("preset-") else actual
            allowed = {canonical(item) for item in allowed}
        if allowed and actual not in allowed:
            return False, f"profile {profile.id!r} does not allow {label} {actual or '(none)'!r}"
    return True, ""


DEFAULT_PROFILES = {
    'code-research': AgentProfile('code-research','lead',allowed_bundles=['session','research'],
                                  permission_ceiling='contribute',validation_rules=['grounded'],
                                  # answer_self_check (FP4) off: measured net harm in the final registered cycle (Review 5).
                                  route_policy={'binding_role':'lead','temperature':0.2,'answer_self_check':False}),
    "lead": AgentProfile("lead", "lead", allowed_bundles=["session", "research"],
                         permission_ceiling="contribute", validation_rules=["grounded"]),
    "scribe": AgentProfile("scribe", "scribe", allowed_bundles=["draft"],
                           permission_ceiling="contribute", validation_rules=["grounded"]),
    "clerk": AgentProfile("clerk", "clerk", allowed_bundles=["clerk"],
                           permission_ceiling="consult", concurrency_limit=4),
    "research_helper": AgentProfile("research_helper", "research_helper",
                                    allowed_bundles=["read"], permission_ceiling="consult",
                                    concurrency_limit=4),
}


def effective_tier(requested: str, profile: AgentProfile | None = None) -> str:
    """Return the least-privileged tier shared by a caller and its profile."""
    if requested not in TIERS:
        return requested
    if profile is None or profile.permission_ceiling not in TIERS:
        return requested
    return TIERS[min(TIERS.index(requested), TIERS.index(profile.permission_ceiling))]


class ProfileStore:
    """Versioned, reviewable profile data stored with a vault, never secrets."""

    def __init__(self, vault: Any) -> None:
        self.vault = vault
        self.path = vault.librarian / "agents" / "profiles.json"

    def all(self) -> list[dict[str, Any]]:
        own = self._load()
        rows = {name: profile.public() for name, profile in DEFAULT_PROFILES.items()}
        rows.update(own)
        return [rows[k] for k in sorted(rows)]

    def get(self, profile_id: str) -> AgentProfile:
        own = {row.get("id"): row for row in self._load().values() if isinstance(row, dict)}
        row = own.get(profile_id)
        if row:
            return AgentProfile(**{k: v for k, v in row.items()
                                   if k in AgentProfile.__dataclass_fields__}).validate()
        if profile_id in DEFAULT_PROFILES:
            # Do not expose a mutable shared default object to callers.
            return AgentProfile(**DEFAULT_PROFILES[profile_id].public()).validate()
        raise KeyError(f"no agent profile {profile_id!r}")

    def save(self, profile: AgentProfile) -> dict[str, Any]:
        profile.validate()
        payload = self._load_payload()
        data = payload["profiles"]
        previous = data.get(profile.id)
        baseline = previous
        if baseline is None and profile.id in DEFAULT_PROFILES:
            baseline = DEFAULT_PROFILES[profile.id].public()
        if isinstance(baseline, dict):
            try:
                profile.revision = max(profile.revision, int(baseline.get("revision") or 1) + 1)
            except (TypeError, ValueError):
                profile.revision = max(profile.revision, 2)
        data[profile.id] = profile.public()
        history = payload["history"]
        rows = history.setdefault(profile.id, [])
        if isinstance(rows, list):
            rows.append({"at": now_iso(), "revision": profile.revision, "profile": profile.public()})
        else:
            history[profile.id] = [{"at": now_iso(), "revision": profile.revision,
                                    "profile": profile.public()}]
        atomic_write_text(self.path, json.dumps({"schema_version": 2, "profiles": data,
                                                 "history": history}, indent=2,
                                                ensure_ascii=False) + "\n")
        return profile.public()

    def history(self, profile_id: str) -> list[dict[str, Any]]:
        """Return immutable prior profile snapshots, newest first."""
        rows = self._load_payload()["history"].get(profile_id, [])
        if not isinstance(rows, list):
            return []
        return [row for row in reversed(rows) if isinstance(row, dict)]

    def _load(self) -> dict[str, dict[str, Any]]:
        return self._load_payload()["profiles"]

    def _load_payload(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            rows = data.get("profiles", {}) if isinstance(data, dict) else {}
            history = data.get("history", {}) if isinstance(data, dict) else {}
            return {"profiles": rows if isinstance(rows, dict) else {},
                    "history": history if isinstance(history, dict) else {}}
        except (OSError, ValueError):
            return {"profiles": {}, "history": {}}


@dataclass(frozen=True)
class ToolBundle:
    id: str
    purpose: str
    names: tuple[str, ...]


# Names are deliberately filtered against the registry, so adding/removing a
# capability never breaks an old bundle definition.  A phase needs a compact
# affordance set, not the entire catalogue.
# The library's own Geo-Grapher, read-only, for research phases (owner, 2026-11-20: agents researching
# a 96-paper corpus never reached its knowledge graphs, because no phase bundle offered them). The
# paper graph is the access route for third-party papers (catalogue -> graph -> section), so these
# are the sanctioned way to read them. Names are filtered against the registry: a library without
# its Geo service simply does not offer them.
GRAPH_FIND = ("mcp__geo-grapher__list_graphs", "mcp__geo-grapher__paper_search_documents")
GRAPH_READ = ("mcp__geo-grapher__paper_get_section", "mcp__geo-grapher__paper_get_claim", "mcp__geo-grapher__search_entities",
              "mcp__geo-grapher__get_entity_content")
GRAPH_CHECK = ("mcp__geo-grapher__paper_get_section", "mcp__geo-grapher__paper_get_claim", "mcp__geo-grapher__get_entity_content")

BUNDLES = {
    "session": ToolBundle("session", "Open, inspect, advance or safely park a research session",
                           ("open_session", "resume_session", "session_status", "advance",
                            "ask_user", "answer", "park_session", "close_session",
                            # A project can be the explicit frame for a new
                            # session, so keep this one broker-gated action in
                            # the initial compact surface rather than forcing a
                            # model to invent an unoffered call.
                            "create_project")),
    "frame": ToolBundle("frame", "Frame a question and inspect the current library",
                         ("session_status", "get_note", "search", "topics_list", "filters",
                          "update_plan", "advance", "ask_user")),
    # Every phase's exit gate (`Session.missing`) names what the model must do to leave it. A bundle
    # that omits one of those tools can never be left: Map asked for update_plan, Need for
    # open_brief, Search for research_round/checkpoint, Judge for decide, Synthesise for
    # promote_offering, Check-out for close_brief (found 2026-11-18). `scripts/phase_walk.py` and
    # tests/test_phase_bundles.py check this for every phase of every purpose.
    "map": ToolBundle("map", "Map relevant sources and structure",
                       ("get_note", "search", "read_source_file", "source_verification_plan", "request_raw_source_access",
                        "record_assumptions", "update_plan", "advance", "ask_user", "dispatch_plan")),
    "need": ToolBundle("need", "State and test the evidence needed next",
                        ("search", "get_note", "read_source_file", "record_assumptions",
                         "open_brief", "update_plan", "advance", "ask_user",
                         *GRAPH_FIND)),
    "search": ToolBundle("search", "Find, inspect, and rank evidence",
                          ("search", "get_note", "read_source_file", "web_search", "ingest",
                           "queue_source", "research_round", "checkpoint", "advance", "ask_user",
                           *GRAPH_FIND, *GRAPH_READ)),
    "judge": ToolBundle("judge", "Judge staged and source evidence",
                         ("get_note", "search", "staging_list", "staging_show", "staging_review",
                          "provenance_check", "decide", "record_assumptions", "advance",
                          "ask_user", "session_status", "add_candidate", *GRAPH_CHECK)),
    "synthesise": ToolBundle("synthesise", "Record a grounded synthesis or identify the gap",
                              ("get_note", "search", "record_synthesis", "record_trace",
                               "draft_offering", "promote_offering", "advance", "ask_user",
                               *GRAPH_CHECK)),
    "check-out": ToolBundle("check-out", "Make a person-reviewed outcome concrete",
                             ("get_note", "draft_offering", "record_application", "close_brief",
                              "close_session", "update_plan", "ask_user", "staging_list",
                              # back to an earlier phase when the outcome needs redoing (ST-F12)
                              "advance")),
    # The phases of the other purposes. Without an entry here a phase fell back to the `session`
    # bundle (open/resume/advance/ask only), so none of its work could be done in the app.
    "ingest": ToolBundle("ingest", "Record and bring in what the person already has",
                          ("update_plan", "search", "get_note", "ingest", "queue_source",
                           "advance", "ask_user")),
    "check-in": ToolBundle("check-in", "Say what is being worked on and what is needed",
                            ("update_plan", "search", "get_note", "advance", "ask_user")),
    "find": ToolBundle("find", "Find, open and use sources for the work in hand",
                        ("search", "get_note", "read_source_file", "log_use", "update_plan",
                         "advance", "ask_user")),
    "inventory": ToolBundle("inventory", "Take the kind-specific inventory of a pursuit",
                             ("update_plan", "search", "get_note", "read_source_file",
                              "record_assumptions", "advance", "ask_user")),
    "plan": ToolBundle("plan", "Set the milestones and their dates",
                        ("update_plan", "task_add", "search", "get_note", "advance", "ask_user")),
    "seed": ToolBundle("seed", "Seed the library with what the pursuit needs",
                        ("update_plan", "ingest", "queue_source", "search", "get_note",
                         "advance", "ask_user")),
    "goal": ToolBundle("goal", "Learn: what they want to be able to do, and by when",
                        ("update_plan", "search", "get_note", "advance", "ask_user")),
    "baseline": ToolBundle("baseline", "Learn: what they already know",
                            ("update_plan", "get_note", "search", "advance", "ask_user")),
    "focus": ToolBundle("focus", "Learn: choose the concepts to focus on",
                         ("update_plan", "search", "get_note", "read_source_file", "advance",
                          "ask_user")),
    "practice": ToolBundle("practice", "Learn: practise each focus concept against a source",
                            ("update_plan", "understanding_record", "search", "get_note",
                             "read_source_file", "advance", "ask_user")),
    "consolidate": ToolBundle("consolidate", "Learn: consolidate in their own words",
                               ("update_plan", "understanding_record", "search", "get_note",
                                "read_source_file", "advance", "ask_user")),
    "next": ToolBundle("next", "Learn: schedule the review and propose a next session",
                        ("update_plan", "task_add", "get_note", "search", "close_session",
                         "ask_user", "advance")),       # back to practise again (ST-F12)
    "candidate": ToolBundle("candidate", "Name the capability candidate",
                             ("update_plan", "capability_candidates", "get_note", "advance",
                              "ask_user")),
    "assess": ToolBundle("assess", "Assess the candidate as a source",
                          ("update_plan", "ingest", "get_note", "read_source_file", "search",
                           "record_assumptions", "advance", "ask_user")),
    "propose": ToolBundle("propose", "Propose the exact capability definition",
                           ("capability_propose", "get_note", "advance", "ask_user")),
    "install": ToolBundle("install", "The person decides whether to install",
                           ("capability_install", "get_note", "advance", "ask_user")),
    # The audited purpose's round (HARNESS-03 to -07; G5 readiness R1). The
    # person's own controls - set_requirement, accept_artifact, reject_artifact,
    # request_evidence - are deliberately in no bundle: a model never sees them.
    "manage": ToolBundle("manage", "Read the session's state and propose one bounded step",
                         ("audit_projection", "update_plan", "search", "get_note",
                          "read_evidence", "ask_user", "advance")),
    "preflight": ToolBundle("preflight", "Ask the Core to admit the proposal as a contract",
                            ("admit_contract", "audit_projection", "ask_user", "advance")),
    "execute": ToolBundle("execute", "Do the contract's work within its targets",
                          ("search", "get_note", "read_evidence", "read_source_file",
                           "stage_artifact", "ask_user", "advance", "dispatch_plan",
                           "source_verification_plan", "request_raw_source_access")),
    "audit": ToolBundle("audit", "Check each planned predicate and the protected targets",
                        ("verify_grain", "audit_targets", "audit_projection", "ask_user",
                         "advance")),
    # close_session is how an audited session ends (Session.next_step says so after a round is
    # reduced, and when every requirement is accounted for): found missing 2026-11-19.
    "reduce": ToolBundle("reduce", "Reduce the round's results to requirement statuses",
                         ("reduce_round", "audit_projection", "advance", "close_session")),
    "research": ToolBundle("research", "Use the phase-specific research bundle", ()),
    "read": ToolBundle("read", "Read-only help", ("get_note", "search", "read_source_file",
                            "read_file", "read_source_section", "verify_source_pages",
                            "list_files", "session_status")),
    "draft": ToolBundle("draft", "Draft and review bounded text", ("get_note", "search",
                                                                       "record_trace", "ask_user")),
    "clerk": ToolBundle("clerk", "Submit and inspect small asynchronous work",
                          ("clerk_submit", "clerk_next", "session_status")),
}


PROJECT_BOOTSTRAP_PURPOSES = frozenset({"add_project", "suggest", "start_pursuit"})


def required_bundle_actions(phase: str = "", *, purpose: str = "", project: str = "",
                            project_exists: bool = False) -> tuple[str, ...]:
    """Return the small set of actions a compact bundle must not hide.

    A session phase normally determines its tool bundle.  That is deliberately
    not enough for the first ``frame`` turn of a project-oriented session:
    ``create_project`` is legal in Frame, and the session cannot advance until
    a Project note exists.  Keeping that one action available is *not* a
    general expansion of the Frame bundle; the registry, profile ceiling and
    phase gate still decide whether it can execute.

    ``project_exists`` is supplied by the Core from the vault, rather than
    trusted from model text.  The helper is public so the deterministic L0
    reachability suite can exercise the exact same rule as the live loop.
    """
    phase_id = phase.strip().lower().replace("_", "-")
    purpose_id = purpose.strip().lower().replace("-", "_")
    # `suggest` has no Need phase, so its brief is opened in Map (open_brief is gated to map and
    # need), and its Map phase reads the project's own files when project access is on. Both are
    # refused by the registry if not allowed, so offering them never widens authority.
    if purpose_id == "suggest" and phase_id == "map":
        return ("open_brief", "read_project")
    if phase_id != "frame" or purpose_id not in PROJECT_BOOTSTRAP_PURPOSES:
        return ()
    if not project.strip() or not project_exists:
        return ("create_project",)
    return ()


@dataclass(frozen=True)
class BundleSelection:
    """The one derived explanation of a compact runtime tool surface.

    ``offered`` is prompt/runtime reachability, not admission. Registry,
    phase, arguments and an executing audited contract still decide whether
    one offered call is admitted when it is made.
    """

    bundle_id: str
    purpose: str
    allowed: bool
    registered: tuple[str, ...]
    offered: tuple[ToolSpec, ...]
    fallback: str = ""


def bundle_selection(tier: str, phase: str = "", *, projects_on: bool = True,
                     working: bool = False, profile: AgentProfile | None = None,
                     purpose: str = "", project: str = "",
                     project_exists: bool = False) -> BundleSelection:
    """Return the exact compact surface and why it was selected."""
    from .loop import narrowed  # avoids the loop/runtime import cycle at module load
    # The UI surface and the execution boundary both cap the tier.  The
    # second check in Registry.call means a stale prompt can never turn this
    # display choice into more authority.
    allowed = narrowed(effective_tier(tier, profile), phase, projects_on, working)
    by_name = {s.name: s for s in allowed}
    # Session phases are stored in lower case, but callers from adapters may
    # carry a display label such as ``Check-out``.  Normalise the label before
    # deciding the task-sized surface.
    phase_id = phase.strip().lower().replace("_", "-")
    bundle_id = phase_id if phase_id in BUNDLES else "session" if not phase_id else "research"
    bundle = BUNDLES.get(bundle_id, BUNDLES["session"])
    declared_names = bundle.names
    names = declared_names
    if not names and phase_id:
        names = BUNDLES.get(phase_id, BUNDLES["session"]).names
    bundle_allowed = not (profile and profile.allowed_bundles and
                          bundle_id not in profile.allowed_bundles and
                          "research" not in profile.allowed_bundles)
    if not bundle_allowed:
        names = BUNDLES["read"].names
    selected = [by_name[name] for name in names if name in by_name]
    # A transition may require one legal next action which a phase's compact
    # generic bundle intentionally omits.  Add only that declared action and
    # only when the profile permits this bundle.  In particular, do not turn
    # every Frame turn into a broad project-write surface.
    if bundle_allowed:
        selected_names = {spec.name for spec in selected}
        for name in required_bundle_actions(phase_id, purpose=purpose, project=project,
                                            project_exists=project_exists):
            if name in by_name and name not in selected_names:
                selected.append(by_name[name])
                selected_names.add(name)
    # A macro is the single controlled expansion path.  Its contained calls
    # are still registry calls; exposing it does not expose an arbitrary
    # 60-tool catalogue to the model.
    # Oversized reads are projected to a loop-local handle.  Its bounded
    # reader belongs on every task surface so a result remains usable after a
    # phase transition without reopening the registry.
    # Prefer executable, registry-checked macros when a phase fills the cap;
    # Each expanded call still passes the registry and checkpoint guards;
    # source dispatch has its own explicit no-model dry run.
    # park_session and request_budget are what a spent budget tells the model to use
    # (Session.next_step), so they are offered in every phase; the registry still decides whether
    # they may run. 2026-11-20: a Lead in Judge with its budget spent was told to request_budget,
    # found no such tool, and asked with ask_user instead, which extends nothing.
    for name in ("read_result", "macro_run", "macro_plan", "park_session", "request_budget"):
        if name in by_name and name not in {spec.name for spec in selected}:
            selected.append(by_name[name])
    # A compact fallback gives a newly added phase usable reads without dumping
    # the whole registry into the prompt.
    if not selected:
        selected = sorted(by_name.values(), key=lambda s: s.name)[:MAX_BUNDLE_TOOLS]
    return BundleSelection(
        bundle_id=bundle_id, purpose=bundle.purpose, allowed=bundle_allowed,
        registered=tuple(name for name in declared_names if name in REGISTRY),
        offered=tuple(selected[:MAX_BUNDLE_TOOLS]),
        fallback="" if bundle_allowed else "profile_read_fallback",
    )


def select_bundle(tier: str, phase: str = "", *, projects_on: bool = True,
                  working: bool = False, profile: AgentProfile | None = None,
                  purpose: str = "", project: str = "",
                  project_exists: bool = False) -> list[ToolSpec]:
    """Return a compact, policy-compatible subset for a loop turn."""
    return list(bundle_selection(
        tier, phase, projects_on=projects_on, working=working, profile=profile,
        purpose=purpose, project=project, project_exists=project_exists).offered)


@dataclass(frozen=True)
class MacroStep:
    tool: str
    arguments: dict[str, str]


@dataclass(frozen=True)
class Macro:
    id: str
    version: int
    purpose: str
    steps: tuple[MacroStep, ...]
    write_capable: bool = False
    preconditions: tuple[str, ...] = ()
    checkpoints: tuple[str, ...] = ()


MACROS = {
    "inspect_map_source": Macro("inspect_map_source", 1, "Inspect a source then refresh its map",
                                 (MacroStep("get_note", {"name": "$source"}),
                                  MacroStep("dik_rebuild", {"source": "$source"})), True,
                                 ("catalogued_source",), ("write_conflict",)),
    "search_and_judge": Macro("search_and_judge", 1, "Search then inspect the chosen source",
                               (MacroStep("search", {"query": "$query", "intent": "$intent"}),
                                MacroStep("get_note", {"name": "$source"})), False,
                               ("query",), ()),
    "intake_to_stage": Macro("intake_to_stage", 1, "Ingest one reference into reviewed staging",
                              (MacroStep("ingest", {"ref": "$ref", "brief": "$brief"}),), True,
                              ("approved_intake",), ("sensitive_source", "write_conflict")),
    "evidence_to_claim_check": Macro("evidence_to_claim_check", 1,
                                       "Read a pinned source file before a claim check",
                                       (MacroStep("read_source_file", {"source": "$source",
                                                                         "path": "$path"}),), False,
                                       ("catalogued_source", "pinned_revision"), ()),
    "review_staged_candidate": Macro("review_staged_candidate", 1,
                                      "Review a staged candidate, then make the selected decision",
                                      (MacroStep("staging_review", {"item_id": "$item_id"}),
                                       MacroStep("staging_decide", {"item_ids": "$item_ids",
                                                                      "decision": "$decision",
                                                                      "reason": "$reason"})), True,
                                      ("staged_item",), ("staging_promotion",)),
}

# A paper-page variant of the reviewed evidence-to-claim path, using the same
# expansion, per-step registry gates and checkpoint machinery.
from dataclasses import replace as _macro_variant
MACROS['source_pages_to_claim_check'] = _macro_variant(
    MACROS['evidence_to_claim_check'], id='source_pages_to_claim_check',
    purpose='Read a located generated section, then check the original PDF pages',
    steps=(MacroStep('read_source_section', {'source': '$source', 'pages': '$pages'}),
           MacroStep('verify_source_pages', {'source': '$source', 'pages': '$pages', 'claim': '$claim'})),
    preconditions=('catalogued_source', 'original_page_targets'))


def macro_plan(macro_id: str) -> dict[str, Any]:
    macro = MACROS.get(macro_id)
    if macro is None:
        raise ValueError(f"no macro {macro_id!r}; known: {sorted(MACROS)}")
    return {"id": macro.id, "version": macro.version, "purpose": macro.purpose,
            "write_capable": macro.write_capable,
            "preconditions": list(macro.preconditions), "checkpoints": list(macro.checkpoints),
            "steps": [{"tool": s.tool, "arguments": s.arguments} for s in macro.steps]}


def _resolve(value: str, inputs: dict[str, Any]) -> Any:
    if value.startswith("$"):
        # The search tool's safe, documented default is ``donor``.  Keeping
        # it here makes a terse macro invocation valid without silently
        # broadening its search intent.
        if value == "$intent":
            return inputs.get("intent") or "donor"
        return inputs.get(value[1:], "")
    return value


def _expanded_plan(macro: Macro, inputs: dict[str, Any]) -> dict[str, Any]:
    """The exact registry calls a macro would make for this invocation."""
    plan = macro_plan(macro.id)
    plan["steps"] = [{"tool": step.tool,
                      "arguments": {key: _resolve(value, inputs)
                                    for key, value in step.arguments.items()}}
                     for step in macro.steps]
    return plan


def _precondition_error(macro: Macro, inputs: dict[str, Any]) -> str:
    """Check small, auditable input preconditions before any step runs."""
    requirements = {
        "catalogued_source": ("source",),
        "query": ("query",),
        "approved_intake": ("ref",),
        "pinned_revision": ("source", "path"),
        'original_page_targets': ('pages', 'claim'),
        "staged_item": ("item_id", "item_ids"),
    }
    missing: list[str] = []
    for condition in macro.preconditions:
        for key in requirements.get(condition, ()):
            if not inputs.get(key):
                missing.append(key)
    if missing:
        return "macro preconditions need " + ", ".join(sorted(set(missing)))
    return ""


def _checkpoint_scope(macro: Macro, inputs: dict[str, Any]) -> str:
    # A resolved approval belongs to one exact expanded plan.  The digest
    # keeps it short and prevents reuse after source/query arguments change.
    # `unknown_step` is a person's answer about an interrupted step, not part
    # of what was approved.
    relevant = {key: value for key, value in inputs.items()
                if key not in ("checkpoint_id", "unknown_step")}
    encoded = json.dumps({"inputs": relevant, "plan": _expanded_plan(macro, inputs)},
                         sort_keys=True, default=str, ensure_ascii=False)
    return f"macro:{macro.id}:v{macro.version}:{hashlib.sha256(encoded.encode()).hexdigest()[:16]}"


UNKNOWN_STEP_CHOICES = ("retry", "applied")

# Approved runs executing right now in this process (checkpoint ids), so one approval cannot
# be executed by two callers at once.
_RUNNING: set[str] = set()
_RUNNING_LOCK = threading.Lock()


class MacroJournal:
    """One approved write-capable macro run's step log (MF-018).

    Keyed by its approval checkpoint. A resolved checkpoint is never reused,
    so running the macro again with that checkpoint continues the same run.
    Each step logs `dispatch` before it runs and `done` (or `stopped`, for a
    refusal or question) after. A done step is reused, not repeated. A step
    dispatched with no outcome may or may not have taken effect.
    """

    def __init__(self, vault: Any, checkpoint_id: str):
        from .workflows import RunStore
        self.store = RunStore(vault)
        self.run_id = f"macro-{checkpoint_id}"

    def state(self) -> tuple[dict[int, dict[str, Any]], bool]:
        from .workflows import DefinitionError
        try:
            events = self.store.events(self.run_id)
        except DefinitionError:                     # no log yet: a fresh run
            return {}, False
        steps: dict[int, dict[str, Any]] = {}
        completed = False
        for event in events:
            kind = event.get("type")
            if kind == "dispatch":
                steps[int(event["index"])] = {"state": "dispatched"}
            elif kind == "done":
                steps[int(event["index"])] = {"state": "done", "result": event.get("result")}
            elif kind == "stopped":
                steps[int(event["index"])] = {"state": "stopped"}
            elif kind == "completed":
                completed = True
        return steps, completed

    def append(self, event: dict[str, Any]) -> None:
        self.store.append(self.run_id, event)

    def events(self) -> list[dict[str, Any]]:
        from .workflows import DefinitionError
        try:
            return self.store.events(self.run_id)
        except DefinitionError:
            return []


def _bound_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """The inputs a run was approved with: not the checkpoint, not a person's answer."""
    return {key: value for key, value in inputs.items()
            if key not in ("checkpoint_id", "unknown_step")}


def macro_status(vault: Any, checkpoint_id: str) -> dict[str, Any]:
    """Where an approved write-capable macro run stands, from its own step log.

    `outcome_unknown` is reported only when the run itself last returned it: a step
    still being sent looks the same in the log until then, and is never offered for a
    person's answer. The recovery handle names the run by its checkpoint and step; the
    inputs it resumes with are the ones its log recorded, never ones a client sends.
    """
    journal = MacroJournal(vault, checkpoint_id)
    events = journal.events()
    out: dict[str, Any] = {"checkpoint_id": checkpoint_id, "run": journal.run_id}
    if not events:
        return {**out, "status": "not_started"}
    started = next((e for e in events if e.get("type") == "started"), {})
    steps, finished = journal.state()
    out.update(macro=str(started.get("macro") or ""), version=started.get("version"),
               completed_steps=sum(1 for step in steps.values() if step["state"] == "done"),
               inputs_recorded=isinstance(started.get("inputs"), dict))
    last = events[-1]
    if finished:
        return {**out, "status": "completed"}
    if last.get("type") == "outcome_unknown":
        index = int(last.get("index", -1))
        return {**out, "status": "outcome_unknown", "step": index,
                "tool": str(last.get("tool") or ""), "options": list(UNKNOWN_STEP_CHOICES)}
    if last.get("type") == "stopped":
        return {**out, "status": "paused", "step": int(last.get("index", -1)),
                "tool": str(last.get("tool") or "")}
    return {**out, "status": "running_or_interrupted",
            "detail": "a step was sent and nothing has come back yet: if no run is going "
                      "on, run the macro again with this checkpoint_id to find out"}


def resolve_macro(ctx: Context, checkpoint_id: str, step: int, choice: str) -> dict[str, Any]:
    """A person's answer about a step whose outcome is unknown, applied to the run as
    its log recorded it (Codex UI ask 2). Refused if the run has moved on."""
    if choice not in UNKNOWN_STEP_CHOICES:
        raise TypeError(f"choice is one of {list(UNKNOWN_STEP_CHOICES)}")
    if ctx.tier != "curate":
        from .rules import Refusal
        raise Refusal("PERSON_CONFIRMS", "whether an interrupted step took effect is a "
                                         "person's call")
    current = macro_status(ctx.vault, checkpoint_id)
    if current["status"] != "outcome_unknown" or current.get("step") != int(step):
        return {"status": "changed", "current": current,
                "detail": "the run is no longer waiting on that step: look at its current "
                          "status before deciding anything"}
    started = next((e for e in MacroJournal(ctx.vault, checkpoint_id).events()
                    if e.get("type") == "started"), {})
    inputs = started.get("inputs")
    if not isinstance(inputs, dict) or current["macro"] not in MACROS:
        return {"status": "not_recoverable", "current": current,
                "detail": "this run's log does not record its inputs: run macro_run with "
                          "the original inputs, the same checkpoint_id and unknown_step"}
    return run_macro(ctx, current["macro"], {**inputs, "checkpoint_id": checkpoint_id,
                                             "unknown_step": choice})


def run_macro(ctx: Context, macro_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Execute an audited macro through the normal registry one step at a time."""
    from .coordination import on_writer_thread
    if on_writer_thread():
        return {"status": "paused", "resumable": True,
                "detail": "A macro orchestrates individual writes; call it outside the vault writer."}
    macro = MACROS[macro_id]
    error = _precondition_error(macro, inputs)
    if error:
        return {"macro": macro_plan(macro_id), "status": "paused", "resumable": True,
                "detail": error}
    plan = _expanded_plan(macro, inputs)
    if macro.write_capable:
        checkpoints = ctx.extras.get("checkpoints")
        scope = _checkpoint_scope(macro, inputs)
        checkpoint_id = str(inputs.get("checkpoint_id") or "")
        approved = False
        checkpoint: dict[str, Any] | None = None
        session = str(getattr(ctx, "session", "") or "")
        caller = str(ctx.extras.get("caller") or "agent")
        if checkpoints is not None and not checkpoint_id:
            # A person's approval belongs to this exact expanded plan (the scope is its digest).
            # A caller that asks again without the id still holds that approval: use it, rather
            # than minting a new card (`ensure` does, once a checkpoint is resolved) and leaving
            # the approved one orphaned. A different plan has a different scope, so it still asks.
            # Only the LATEST card for this plan counts (a later cancel withdraws an earlier
            # approval), it must have been asked for by this same session and caller, and a run
            # that has already finished is spent: running it again is a new decision.
            latest = next((row for row in reversed(checkpoints.all())
                           if row.get("type") == "macro_expansion" and row.get("scope") == scope), None)
            if latest is not None and latest.get("resolution") == "approve" and not latest.get("expired") \
                    and (latest.get("evidence") or {}).get("session", "") == session \
                    and latest.get("requester") == caller:
                spent = ctx.vault is not None and MacroJournal(ctx.vault, str(latest["id"])).state()[1]
                if not spent:
                    checkpoint_id = str(latest["id"])
                    inputs = {**inputs, "checkpoint_id": checkpoint_id}
        if checkpoints is not None and checkpoint_id:
            try:
                checkpoint = checkpoints.get(checkpoint_id)
                bound = str((checkpoint.get("evidence") or {}).get("session") or "")
                approved = checkpoint.get("type") == "macro_expansion" and \
                    checkpoint.get("scope") == scope and checkpoint.get("resolution") == "approve" and \
                    not checkpoint.get("expired") and \
                    (not bound or not session or bound == session)    # another session's approval is not this one's
            except (KeyError, ValueError):
                approved = False
        if not approved:
            if checkpoints is not None:
                def ensure_checkpoint():
                    return checkpoints.ensure("macro_expansion", scope,
                                              evidence={**plan, "session": session} if session else plan,
                                              choices=["approve", "cancel"], default="cancel",
                                              requester=caller)
                writer = ctx.extras.get("vault_writer")
                checkpoint = writer.submit(ensure_checkpoint, caller="macro-checkpoint") \
                    if writer is not None else ensure_checkpoint()
            return {"macro": plan, "status": "awaiting_checkpoint", "resumable": True,
                    "detail": "A person must approve this expanded write-capable macro before it starts.",
                    "checkpoint": checkpoint}
    # MF-018: an approved write-capable run keeps a durable step log, so a
    # stop part way never turns into blindly repeating a completed write.
    journal = MacroJournal(ctx.vault, checkpoint_id) \
        if macro.write_capable and ctx.vault is not None else None
    recorded, finished = journal.state() if journal is not None else ({}, False)
    unknown_choice = str(inputs.get("unknown_step") or "")
    if unknown_choice:
        if unknown_choice not in UNKNOWN_STEP_CHOICES:
            raise TypeError(f"unknown_step is one of {list(UNKNOWN_STEP_CHOICES)}")
        if ctx.tier != "curate":
            from .rules import Refusal
            raise Refusal("PERSON_CONFIRMS", "whether an interrupted step took effect is a "
                                             "person's call")
    if finished:
        return {"macro": plan, "status": "completed", "reused": True,
                "steps": [{"tool": step.tool, "result": (recorded.get(i) or {}).get("result"),
                           "reused": True} for i, step in enumerate(macro.steps)],
                "detail": "this approved run already completed; nothing was repeated"}
    # One approval is one run at a time: a second caller arriving while it executes is told so
    # rather than racing it (the journal alone only dedupes what has already been recorded).
    claimed = ""
    if journal is not None:
        with _RUNNING_LOCK:
            if checkpoint_id in _RUNNING:
                return {"macro": plan, "status": "paused", "resumable": True,
                        "detail": "this approved run is already executing; wait for it to finish "
                                  "(macro_status shows where it stands) instead of starting it again"}
            _RUNNING.add(checkpoint_id)
            claimed = checkpoint_id
    steps = []
    # Registry.call enforces the compact active bundle for ordinary model
    # calls.  A macro is the explicitly approved exception, so scope its
    # bypass to this synchronous fixed sequence only.  The counter supports a
    # future audited macro delegating to another audited macro without leaking
    # the exception into the next model turn.
    previous_depth = ctx.extras.get("macro_expansion_depth", 0)
    try:
        ctx.extras["macro_expansion_depth"] = int(previous_depth or 0) + 1
    except (TypeError, ValueError):
        ctx.extras["macro_expansion_depth"] = 1
    try:
        if journal is not None and not recorded:
            journal.append({"type": "started", "macro": macro.id, "version": macro.version,
                            "scope": scope, "inputs": _bound_inputs(inputs)})
        from .workflows import _summary
        for index, step in enumerate(macro.steps):
            if step.tool not in REGISTRY:
                return {"error": "macro_unavailable", "detail": f"{step.tool} is not registered"}
            # This is the audited bundle-expansion boundary: callers see only
            # macro_run, while this fixed registered sequence expands it.  Each
            # contained call still receives its usual tier, broker, phase, budget
            # and document-lease checks.
            args = {key: _resolve(value, inputs) for key, value in step.arguments.items()}
            # item_ids needs a list for the existing staging API.
            if step.tool == "staging_decide" and isinstance(args.get("item_ids"), str):
                args["item_ids"] = [args["item_ids"]]
            prior = recorded.get(index) or {}
            if prior.get("state") == "done":
                steps.append({"tool": step.tool, "arguments": args, "result": prior["result"],
                              "reused": True})
                continue
            if prior.get("state") == "dispatched" and journal is not None:
                spec = REGISTRY.get(step.tool)
                if unknown_choice == "applied":
                    result = {"outcome_unknown": True, "recorded_as": "applied", "by": "person"}
                    journal.append({"type": "done", "index": index, "tool": step.tool,
                                    "result": result})
                    steps.append({"tool": step.tool, "arguments": args, "result": result})
                    continue
                if not (spec.effect == "read" or spec.idempotent) and unknown_choice != "retry":
                    # Marked in the log, so a later look (another tab, a reconnect)
                    # knows the run is waiting on a person, not still sending.
                    journal.append({"type": "outcome_unknown", "index": index,
                                    "tool": step.tool})
                    return {"macro": plan, "steps": steps, "status": "outcome_unknown",
                            "resumable": True,
                            "recovery": {"checkpoint_id": checkpoint_id, "step": index,
                                         "tool": step.tool, "macro": macro.id,
                                         "options": list(UNKNOWN_STEP_CHOICES)},
                            "next_action": {
                                "tool": step.tool, "arguments": args,
                                "completed_steps": len(steps),
                                "options": list(UNKNOWN_STEP_CHOICES),
                                "detail": "This step was sent but its result was never "
                                          "recorded, so it may or may not have taken effect. A "
                                          "person checks, then runs the macro again with the "
                                          "same checkpoint_id and unknown_step 'retry' (send "
                                          "it again) or 'applied' (record it as done)."}}
            if journal is not None:
                journal.append({"type": "dispatch", "index": index, "tool": step.tool,
                                "arguments": args})
            result = REGISTRY.call(step.tool, args, ctx)
            steps.append({"tool": step.tool, "arguments": args, "result": result})
            if "error" in result or "refused" in result or result.get("needs_person"):
                if journal is not None:
                    journal.append({"type": "stopped", "index": index, "tool": step.tool})
                return {"macro": plan, "steps": steps, "status": "paused", "resumable": True,
                        "next_action": {"tool": step.tool, "arguments": args,
                                        "completed_steps": len(steps) - 1,
                                        "detail": "Resolve the refusal or question, then run "
                                                  "the macro again with the same "
                                                  "checkpoint_id: completed steps are reused, "
                                                  "not repeated."
                                                  if journal is not None else
                                                  "Resolve the refusal or question before "
                                                  "retrying this step. This macro only reads, "
                                                  "so running it again repeats only reads."},
                        **({"checkpoint": result["checkpoint"]}
                           if isinstance(result.get("checkpoint"), dict) else {})}
            if journal is not None:
                journal.append({"type": "done", "index": index, "tool": step.tool,
                                "result": _summary(result)})
        if journal is not None:
            journal.append({"type": "completed"})
        return {"macro": plan, "steps": steps, "status": "completed"}
    finally:
        if claimed:
            with _RUNNING_LOCK:
                _RUNNING.discard(claimed)
        if previous_depth:
            ctx.extras["macro_expansion_depth"] = previous_depth
        else:
            ctx.extras.pop("macro_expansion_depth", None)
