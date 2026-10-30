"""Profiles, compact tool bundles, and audited macro definitions.

The registry remains the final permission boundary.  This module changes what
an agent is offered and records why; it never grants a tool the registry,
broker, session phase, or caller would otherwise refuse.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .coordination import atomic_write_text
from .registry import REGISTRY, TIERS, Context, ToolSpec
from .vault import now_iso

MAX_BUNDLE_TOOLS = 12


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
                 rate_card: dict[str, Any] | None = None) -> None:
        profile.validate()
        self.endpoint = endpoint
        self.profile = profile
        self.gate = gate
        self.route_guard = route_guard
        self.rate_card = rate_card
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

    def _reserve(self, payload: dict[str, Any], rate_card: dict[str, Any] | None) -> dict[str, Any]:
        """Reserve a conservative one-call background-task budget."""
        try:
            requested = max(1, int(payload.get("max_tokens") or self.profile.output_budget))
        except (TypeError, ValueError):
            requested = self.profile.output_budget
        prepared = dict(payload)
        prepared["max_tokens"] = min(requested, self.profile.output_budget)
        prompt_tokens = self._token_estimate({key: value for key, value in prepared.items()
                                              if key != "max_tokens"})
        reserved_tokens = prompt_tokens + prepared["max_tokens"]
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
                reserved_cost = ((prompt_tokens * prices[0] + prepared["max_tokens"] * prices[1]) /
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
        prepared = self._reserve(payload, rate_card)
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
    "map": ToolBundle("map", "Map relevant sources and structure",
                       ("get_note", "search", "read_source_file", "dik_rebuild", "filters",
                        "record_assumptions", "advance", "ask_user")),
    "need": ToolBundle("need", "State and test the evidence needed next",
                        ("search", "get_note", "read_source_file", "record_assumptions",
                         "update_plan", "advance", "ask_user")),
    "search": ToolBundle("search", "Find, inspect, and rank evidence",
                          ("search", "get_note", "read_source_file", "web_search", "ingest",
                           "queue_source", "advance", "ask_user")),
    "judge": ToolBundle("judge", "Judge staged and source evidence",
                         ("get_note", "search", "staging_list", "staging_show", "staging_review",
                          "provenance_check", "advance", "ask_user")),
    "synthesise": ToolBundle("synthesise", "Record a grounded synthesis or identify the gap",
                              ("get_note", "search", "record_synthesis", "record_trace",
                               "draft_offering", "advance", "ask_user")),
    "check-out": ToolBundle("check-out", "Make a person-reviewed outcome concrete",
                             ("get_note", "draft_offering", "record_application", "close_session",
                              "ask_user", "staging_list")),
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
                           "stage_artifact", "ask_user", "advance")),
    "audit": ToolBundle("audit", "Check each planned predicate and the protected targets",
                        ("verify_grain", "audit_targets", "audit_projection", "ask_user",
                         "advance")),
    "reduce": ToolBundle("reduce", "Reduce the round's results to requirement statuses",
                         ("reduce_round", "audit_projection", "advance")),
    "research": ToolBundle("research", "Use the phase-specific research bundle", ()),
    "read": ToolBundle("read", "Read-only help", ("get_note", "search", "read_source_file",
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
    if phase_id != "frame" or purpose_id not in PROJECT_BOOTSTRAP_PURPOSES:
        return ()
    if not project.strip() or not project_exists:
        return ("create_project",)
    return ()


def select_bundle(tier: str, phase: str = "", *, projects_on: bool = True,
                  working: bool = False, profile: AgentProfile | None = None,
                  purpose: str = "", project: str = "",
                  project_exists: bool = False) -> list[ToolSpec]:
    """Return a compact, policy-compatible subset for a loop turn."""
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
    names = bundle.names
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
    for name in ("read_result", "macro_plan", "macro_run"):
        if name in by_name and name not in {spec.name for spec in selected}:
            selected.append(by_name[name])
    # A compact fallback gives a newly added phase usable reads without dumping
    # the whole registry into the prompt.
    if not selected:
        selected = sorted(by_name.values(), key=lambda s: s.name)[:MAX_BUNDLE_TOOLS]
    return selected[:MAX_BUNDLE_TOOLS]


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
    relevant = {key: value for key, value in inputs.items() if key != "checkpoint_id"}
    encoded = json.dumps({"inputs": relevant, "plan": _expanded_plan(macro, inputs)},
                         sort_keys=True, default=str, ensure_ascii=False)
    return f"macro:{macro.id}:v{macro.version}:{hashlib.sha256(encoded.encode()).hexdigest()[:16]}"


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
        if checkpoints is not None and checkpoint_id:
            try:
                checkpoint = checkpoints.get(checkpoint_id)
                approved = checkpoint.get("type") == "macro_expansion" and \
                    checkpoint.get("scope") == scope and checkpoint.get("resolution") == "approve" and \
                    not checkpoint.get("expired")
            except (KeyError, ValueError):
                approved = False
        if not approved:
            if checkpoints is not None:
                def ensure_checkpoint():
                    return checkpoints.ensure("macro_expansion", scope, evidence=plan,
                                              choices=["approve", "cancel"], default="cancel",
                                              requester=str(ctx.extras.get("caller") or "agent"))
                writer = ctx.extras.get("vault_writer")
                checkpoint = writer.submit(ensure_checkpoint, caller="macro-checkpoint") \
                    if writer is not None else ensure_checkpoint()
            return {"macro": plan, "status": "awaiting_checkpoint", "resumable": True,
                    "detail": "A person must approve this expanded write-capable macro before it starts.",
                    "checkpoint": checkpoint}
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
        for step in macro.steps:
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
            result = REGISTRY.call(step.tool, args, ctx)
            steps.append({"tool": step.tool, "arguments": args, "result": result})
            if "error" in result or "refused" in result or result.get("needs_person"):
                return {"macro": plan, "steps": steps, "status": "paused", "resumable": True,
                        "next_action": {"tool": step.tool, "arguments": args,
                                        "completed_steps": len(steps) - 1,
                                        "detail": "Resolve the refusal or question before retrying this step. "
                                                  "Restarting the whole macro reruns completed steps."},
                        **({"checkpoint": result["checkpoint"]}
                           if isinstance(result.get("checkpoint"), dict) else {})}
        return {"macro": plan, "steps": steps, "status": "completed"}
    finally:
        if previous_depth:
            ctx.extras["macro_expansion_depth"] = previous_depth
        else:
            ctx.extras.pop("macro_expansion_depth", None)
