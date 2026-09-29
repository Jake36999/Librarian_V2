"""Actions, workflows and pipelines: automated work declared in YAML.

- An **action** is a registered tool, and the only thing that does anything.
- A **workflow** is a named, composite, standard set of actions: steps in
  order, one step's output bound into a later step's arguments. No model.
- A **pipeline** chains workflows, with **routing** between them: settled by a
  declared condition, or handed to a model as a closed choice.

There is no code between steps. A value in `args` is a literal or a reference
(`{from: "inputs.x"}`, `{from: "steps.<id>.<field>"}`, `{from: "item.<field>"}`),
and a condition compares a referenced value (`is`, `in`, `empty`). So a shared,
synced or agent-written definition can only call what the registry already
offers (`CLOSED_ACTION_REGISTRY`, `NO_ARBITRARY_SHELL`).

Every definition is validated when it is saved (`validate`): actions exist,
arguments are the action's own, required arguments are given, references
name declared inputs, earlier steps and (where the action declares what it
returns) real fields, routes name real workflows. An invalid definition is not
saved. Every step then runs through `Registry.call`, so tiers, bounds,
refusals, the session's phase gate and budget, and the permission broker
apply exactly as if a model had called it.

A run is an append-only log (`.librarian/runs/<id>.jsonl`). A routing step
whose model is unavailable pauses the run; `resume` continues it later, and a
person may choose the route by hand instead.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Callable

import yaml

from .evidence import FRAMING_KEYS
from .registry import REGISTRY, TIERS, Context, _json_type
from .rules import Refusal
from .vault import Vault, now_iso

REF = re.compile(r"^(inputs|steps|item)(\.[A-Za-z0-9_\-]+)*$")
CONDITIONS = ("is", "in", "empty")
MAX_EACH = 200
ITEM_CHARS = 3000
INPUT_TYPES = {"string": str, "integer": int, "boolean": bool, "list": list, "object": dict,
               "number": (int, float)}


class DefinitionError(TypeError):
    """An invalid workflow or pipeline. A `TypeError`, so the registry reports
    it as invalid arguments with every problem listed."""


# ------------------------------------------------------------------ loading

@dataclass
class Definition:
    kind: str                     # workflow | pipeline
    name: str
    data: dict[str, Any]
    origin: str                   # standard | vault
    text: str

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]


def parse(text: str) -> Definition:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise DefinitionError(f"not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise DefinitionError("a definition is a mapping with `workflow:` or `pipeline:`")
    kinds = [k for k in ("workflow", "pipeline") if k in data]
    if len(kinds) != 1:
        raise DefinitionError("a definition names exactly one of `workflow:` or `pipeline:`")
    name = str(data[kinds[0]] or "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9\-]{1,60}", name):
        raise DefinitionError(f"name {name!r}: lower-case letters, digits and hyphens")
    return Definition(kinds[0], name, data, "", text)


class Library:
    """The standard set shipped with the package, plus the vault's own."""

    def __init__(self, vault: Vault | None):
        self.vault = vault

    def _standard(self) -> list[Definition]:
        out = []
        root = resources.files("resource_librarian") / "standard"
        for folder in ("workflows", "pipelines"):
            node = root / folder
            if not node.is_dir():
                continue
            for child in sorted(node.iterdir(), key=lambda c: c.name):
                if child.name.endswith((".yaml", ".yml")):
                    d = parse(child.read_text(encoding="utf-8"))
                    d.origin = "standard"
                    out.append(d)
        return out

    def folder(self, kind: str) -> Path:
        assert self.vault is not None
        return self.vault.librarian / f"{kind}s"

    def _vault_defs(self) -> list[Definition]:
        if self.vault is None:
            return []
        out = []
        for kind in ("workflow", "pipeline"):
            folder = self.folder(kind)
            for path in sorted(folder.glob("*.y*ml")) if folder.is_dir() else []:
                try:
                    d = parse(path.read_text(encoding="utf-8"))
                except DefinitionError:
                    continue
                d.origin = "vault"
                out.append(d)
        return out

    def all(self) -> dict[str, Definition]:
        out: dict[str, Definition] = {}
        for d in self._standard() + self._vault_defs():
            out.setdefault(d.name, d)          # a vault can never shadow the standard set
        return out

    def get(self, name: str) -> Definition:
        found = self.all().get(name)
        if found is None:
            raise DefinitionError(f"no workflow or pipeline named {name!r}")
        return found

    # -- acceptance: a person's sign-off, tied to the exact text ---------------
    def _accepted_path(self) -> Path:
        assert self.vault is not None
        return self.vault.librarian / "workflows" / "accepted.json"

    def accepted(self) -> dict[str, str]:
        if self.vault is None or not self._accepted_path().exists():
            return {}
        return json.loads(self._accepted_path().read_text(encoding="utf-8"))

    def is_accepted(self, d: Definition) -> bool:
        return d.origin == "standard" or self.accepted().get(d.name) == d.digest

    def accept(self, name: str) -> dict[str, Any]:
        d = self.get(name)
        if d.origin == "standard":
            return {"name": name, "accepted": True, "note": "the standard set is accepted"}
        accepted = self.accepted()
        accepted[name] = d.digest
        path = self._accepted_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(accepted, indent=1), encoding="utf-8")
        return {"name": name, "accepted": True, "digest": d.digest}

    def save(self, text: str, accepted_by_person: bool) -> dict[str, Any]:
        d = parse(text)
        existing = self.all().get(d.name)
        if existing is not None and existing.origin == "standard":
            raise DefinitionError(f"{d.name!r} is a standard {existing.kind}; choose another name")
        report = validate(d, self)
        if report["errors"]:
            raise DefinitionError("not saved: " + "; ".join(report["errors"]))
        path = self.folder(d.kind) / f"{d.name}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        d.origin = "vault"
        if accepted_by_person:
            self.accept(d.name)
        return {"saved": path.relative_to(self.vault.root).as_posix(), "kind": d.kind,
                "accepted": accepted_by_person, "warnings": report["warnings"],
                "tier": report["tier"]}


# --------------------------------------------------------------- validation

def _param_schema(tool: str) -> dict[str, dict[str, Any]]:
    spec = REGISTRY.get(tool)
    hints = spec.hints()
    return {p.name: {**_json_type(hints.get(p.name, str)),
                     "required": p.default is p.empty} for p in spec.parameters()}


def validate(d: Definition, library: Library, _seen: tuple[str, ...] = ()) -> dict[str, Any]:
    """Every problem at once, so a definition can be fixed in one pass."""
    errors: list[str] = []
    warnings: list[str] = []
    data = d.data
    allowed_top = {d.kind, "purpose", "inputs", "steps", "outputs", "tier"}
    for key in set(data) - allowed_top:
        errors.append(f"unknown key {key!r} (allowed: {sorted(allowed_top)})")
    if not str(data.get("purpose") or "").strip():
        errors.append("a definition states its `purpose`")
    inputs = data.get("inputs") or {}
    if not isinstance(inputs, dict):
        errors.append("`inputs` is a mapping of name to {type, default}")
        inputs = {}
    for name, spec in inputs.items():
        if not isinstance(spec, dict) or spec.get("type") not in INPUT_TYPES:
            errors.append(f"input {name!r} needs a type from {sorted(INPUT_TYPES)}")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("`steps` is a non-empty list")
        steps = []
    tiers: list[str] = []
    returns: dict[str, tuple[str, ...]] = {}
    ids: list[str] = []
    phases: set[str] | None = None
    from .session import WRITES

    def check_ref(value: Any, where: str, has_item: bool) -> None:
        if isinstance(value, dict) and set(value) == {"from"}:
            ref = str(value["from"])
            if not REF.match(ref):
                errors.append(f"{where}: reference {ref!r} is not inputs.<name>, "
                              f"steps.<id>.<field> or item.<field>")
                return
            parts = ref.split(".")
            if parts[0] == "inputs" and (len(parts) < 2 or parts[1] not in inputs):
                errors.append(f"{where}: no declared input {parts[1] if len(parts) > 1 else ''!r}")
            if parts[0] == "item" and not has_item:
                errors.append(f"{where}: `item` is only defined inside `each`")
            if parts[0] == "steps":
                if len(parts) < 2 or parts[1] not in ids:
                    errors.append(f"{where}: {ref!r} names no earlier step")
                elif len(parts) > 2 and returns.get(parts[1]) and parts[2] not in returns[parts[1]]:
                    errors.append(f"{where}: step {parts[1]!r} returns "
                                  f"{sorted(returns[parts[1]])}, not {parts[2]!r}")
        elif isinstance(value, dict):
            for k, v in value.items():
                check_ref(v, f"{where}.{k}", has_item)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                check_ref(v, f"{where}[{i}]", has_item)

    def check_when(when: Any, where: str, has_item: bool) -> None:
        if when is None:
            return
        if not isinstance(when, dict) or "from" not in when or \
                len(set(when) & set(CONDITIONS)) != 1 or set(when) - {"from", *CONDITIONS}:
            errors.append(f"{where}: `when` is {{from: <reference>, is|in|empty: <value>}}")
            return
        check_ref({"from": when["from"]}, where, has_item)

    for i, step in enumerate(steps):
        where = f"step {i + 1}"
        if not isinstance(step, dict):
            errors.append(f"{where}: a step is a mapping")
            continue
        sid = str(step.get("id") or "")
        where = f"step {sid or i + 1}"
        if not re.fullmatch(r"[a-z0-9_\-]{1,40}", sid):
            errors.append(f"{where}: needs an `id` (lower-case, digits, - or _)")
        elif sid in ids:
            errors.append(f"{where}: duplicate id")
        each = step.get("each")
        if each is not None and not (isinstance(each, dict) and set(each) == {"from"}):
            errors.append(f"{where}: `each` is {{from: <reference>}}")
        elif each is not None:
            check_ref(each, f"{where}.each", False)
        has_item = each is not None
        check_when(step.get("when"), f"{where}.when", has_item)
        known = {"id", "action", "workflow", "route", "args", "each", "when", "on_error"}
        for key in set(step) - known:
            errors.append(f"{where}: unknown key {key!r}")
        what = [k for k in ("action", "workflow", "route") if k in step]
        if len(what) != 1:
            errors.append(f"{where}: exactly one of `action`, `workflow` or `route`")
        elif what[0] == "action":
            if d.kind == "pipeline":
                errors.append(f"{where}: a pipeline's steps are workflows or routes; wrap "
                              f"actions in a workflow")
            tool = str(step["action"])
            if tool not in REGISTRY:
                errors.append(f"{where}: {tool!r} is not a registered action "
                              f"(CLOSED_ACTION_REGISTRY)")
            elif tool.startswith(("run_", "save_workflow", "accept_workflow")):
                errors.append(f"{where}: {tool!r} cannot be a step (runs do not nest by action)")
            else:
                spec = REGISTRY.get(tool)
                tiers.append(spec.tier)
                returns[sid] = spec.returns
                params = _param_schema(tool)
                args = step.get("args") or {}
                if not isinstance(args, dict):
                    errors.append(f"{where}: `args` is a mapping")
                    args = {}
                for name in set(args) - set(params):
                    errors.append(f"{where}: {tool} takes no argument {name!r} "
                                  f"(accepted: {sorted(params)})")
                for name, p in params.items():
                    if p["required"] and name not in args:
                        errors.append(f"{where}: {tool} needs {name!r}")
                    if name in args and not isinstance(args[name], dict) and "enum" in p \
                            and args[name] not in p["enum"]:
                        errors.append(f"{where}: {name}={args[name]!r} is not one of {p['enum']}")
                check_ref(args, f"{where}.args", has_item)
                if tool in WRITES:
                    phases = set(WRITES[tool]) if phases is None else phases & WRITES[tool]
        elif what[0] == "workflow":
            if d.kind == "workflow":
                errors.append(f"{where}: a workflow's steps are actions; chain workflows "
                              f"in a pipeline")
            _check_workflow_ref(str(step["workflow"]), step.get("args") or {}, where, library,
                                errors, tiers, _seen + (d.name,))
            check_ref(step.get("args") or {}, f"{where}.args", has_item)
            returns[sid] = ("results", "outputs", "status")
        else:
            if d.kind == "workflow":
                errors.append(f"{where}: routes belong in pipelines")
            _check_route(step["route"], where, library, errors, tiers, _seen + (d.name,),
                         check_ref, check_when)
            returns[sid] = ("chosen", "results")
        if each is not None and sid:
            returns[sid] = ("results", "count", "considered", "truncated")
        if sid:
            ids.append(sid)
    for name, ref in (data.get("outputs") or {}).items():
        check_ref(ref, f"output {name}", False)
    tier = max(tiers or ["consult"], key=TIERS.index)
    declared = data.get("tier")
    if declared and declared not in TIERS:
        errors.append(f"`tier` is one of {TIERS}")
    elif declared and TIERS.index(declared) < TIERS.index(tier):
        errors.append(f"declared tier {declared!r} is below what its actions need ({tier!r})")
    if phases is not None and not phases:
        warnings.append("its writes are unlocked in different session phases, so inside a "
                        "session it can only run in parts; outside a session it runs whole")
    return {"name": d.name, "kind": d.kind, "valid": not errors, "errors": errors,
            "warnings": warnings, "tier": declared or tier,
            "session_phases": sorted(phases) if phases else []}


def _check_workflow_ref(name: str, args: Any, where: str, library: Library, errors: list[str],
                        tiers: list[str], seen: tuple[str, ...]) -> None:
    if name in seen:
        errors.append(f"{where}: {name!r} would run itself")
        return
    try:
        target = library.get(name)
    except DefinitionError:
        errors.append(f"{where}: no workflow named {name!r}")
        return
    if target.kind != "workflow":
        errors.append(f"{where}: {name!r} is a pipeline; pipelines are not nested")
        return
    inner = validate(target, library, seen)
    if inner["errors"]:
        errors.append(f"{where}: workflow {name!r} is itself invalid")
    tiers.append(inner["tier"])
    declared = target.data.get("inputs") or {}
    for key in set(args if isinstance(args, dict) else {}) - set(declared):
        errors.append(f"{where}: workflow {name!r} has no input {key!r}")
    for key, spec in declared.items():
        if "default" not in (spec or {}) and key not in (args or {}):
            errors.append(f"{where}: workflow {name!r} needs input {key!r}")


def _check_route(route: Any, where: str, library: Library, errors: list[str], tiers: list[str],
                 seen: tuple[str, ...], check_ref: Callable, check_when: Callable) -> None:
    if not isinstance(route, dict):
        errors.append(f"{where}: `route` is a mapping")
        return
    for key in set(route) - {"each", "decide", "question", "options", "otherwise"}:
        errors.append(f"{where}.route: unknown key {key!r}")
    decide = route.get("decide")
    if decide not in ("declared", "reason"):
        errors.append(f"{where}.route: `decide` is 'declared' or 'reason'")
    has_item = route.get("each") is not None
    if has_item:
        check_ref(route["each"], f"{where}.route.each", False)
    options = route.get("options")
    if not isinstance(options, dict) or len(options) < 2:
        errors.append(f"{where}.route: at least two `options`")
        return
    if decide == "reason" and not str(route.get("question") or "").strip():
        errors.append(f"{where}.route: a reasoned route asks a `question`")
    for option, spec in options.items():
        at = f"{where}.route.{option}"
        if not isinstance(spec, dict):
            errors.append(f"{at}: an option is a mapping")
            continue
        if spec.get("end"):
            pass
        elif "workflow" in spec:
            _check_workflow_ref(str(spec["workflow"]), spec.get("args") or {}, at, library,
                                errors, tiers, seen)
            check_ref(spec.get("args") or {}, f"{at}.args", has_item)
        else:
            errors.append(f"{at}: names a `workflow` or `end: true`")
        if decide == "reason" and not str(spec.get("when_to_choose") or "").strip():
            errors.append(f"{at}: a reasoned route explains `when_to_choose`")
        if decide == "declared":
            if "when" in spec:
                check_when(spec["when"], f"{at}.when", has_item)
            elif route.get("otherwise") != option:
                errors.append(f"{at}: a declared route's option has a `when` (or is `otherwise`)")
    if route.get("otherwise") and route["otherwise"] not in options:
        errors.append(f"{where}.route: `otherwise` names no option")


# ------------------------------------------------------------------ running

class RunPaused(Exception):
    def __init__(self, step: str, detail: dict[str, Any]):
        super().__init__(step)
        self.step = step
        self.detail = detail


class RunFailed(Exception):
    def __init__(self, step: str, result: dict[str, Any]):
        super().__init__(step)
        self.step = step
        self.result = result


def _lookup(ref: str, scope: dict[str, Any]) -> Any:
    parts = ref.split(".")
    value: Any = scope.get(parts[0])
    for part in parts[1:]:
        if isinstance(value, dict):
            if part not in value:
                raise KeyError(f"{ref}: no field {part!r} (has {sorted(value)[:12]})")
            value = value[part]
        elif isinstance(value, list) and part.isdigit():
            value = value[int(part)]
        else:
            raise KeyError(f"{ref}: cannot read {part!r} from {type(value).__name__}")
    return value


def resolve(value: Any, scope: dict[str, Any]) -> Any:
    if isinstance(value, dict) and set(value) == {"from"}:
        return copy.deepcopy(_lookup(str(value["from"]), scope))
    if isinstance(value, dict):
        return {k: resolve(v, scope) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, scope) for v in value]
    return value


def holds(when: dict[str, Any] | None, scope: dict[str, Any]) -> bool:
    if not when:
        return True
    try:
        value = _lookup(str(when["from"]), scope)
    except KeyError:
        value = None
    if "is" in when:
        return value == when["is"]
    if "in" in when:
        return value in (when["in"] or [])
    empty = value in (None, "", [], {}, 0)
    return empty if when["empty"] else not empty


def unframed(item: Any) -> Any:
    """An item as a routing model may see it: no project, brief, session, need
    or anything else that carries framing (`DATA_IS_UNFRAMED`)."""
    if isinstance(item, dict):
        return {k: unframed(v) for k, v in item.items()
                if str(k).lower() not in FRAMING_KEYS and k not in ("found_for", "history")}
    if isinstance(item, list):
        return [unframed(v) for v in item]
    return item


class Router:
    """Chooses a route by reasoning: a closed choice over the options, seeing
    only the question, each option's `when_to_choose`, and the item."""

    def __init__(self, endpoint: Any):
        self.endpoint = endpoint
        self.payloads: list[dict[str, Any]] = []

    def payload(self, question: str, options: dict[str, str], item: Any) -> dict[str, Any]:
        listing = "\n".join(f"- {name}: {why}" for name, why in options.items())
        shown = json.dumps(unframed(item), ensure_ascii=False, default=str)[:ITEM_CHARS]
        schema = {"type": "object", "required": ["option", "reason"], "properties": {
            "option": {"type": "string", "enum": sorted(options)},
            "reason": {"type": "string", "maxLength": 300}}}
        return {"task": "route",
                "system": ("You route one item to the next step of an automated process. "
                           "Choose exactly one option, using only the item shown. Reply with "
                           f"one JSON object matching this schema:\n{json.dumps(schema)}"),
                "user": f"{question}\n\nOptions:\n{listing}\n\nItem:\n---\n{shown}\n---",
                "schema": schema, "temperature": 0.0, "max_tokens": 300}

    def choose(self, question: str, options: dict[str, str], item: Any) -> tuple[str, str, str]:
        """(option, reason, model), or raise LookupError when no model can answer."""
        from . import clerk
        if self.endpoint is None:
            raise LookupError("no routing model is configured")
        payload = self.payload(question, options, item)
        self.payloads.append(payload)
        problems = ""
        for _attempt in range(2):
            try:
                raw, model = self.endpoint.complete(payload, problems)
            except clerk.ClerkUnavailable as exc:
                raise LookupError(str(exc)) from exc
            value, problems = clerk.parse(raw, payload["schema"])
            if not problems:
                return value["option"], value.get("reason", ""), model
        raise LookupError(f"the routing model did not return one of the options ({problems})")


class RunStore:
    def __init__(self, vault: Vault):
        self.folder = vault.librarian / "runs"

    def path(self, run_id: str) -> Path:
        return self.folder / f"{''.join(c for c in run_id if c.isalnum() or c in '-_')}.jsonl"

    def append(self, run_id: str, event: dict[str, Any]) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        with self.path(run_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"t": now_iso(), **event}, ensure_ascii=False,
                                    default=str) + "\n")

    def events(self, run_id: str) -> list[dict[str, Any]]:
        path = self.path(run_id)
        if not path.exists():
            raise DefinitionError(f"no run {run_id!r}")
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()]

    def status(self, run_id: str) -> dict[str, Any]:
        events = self.events(run_id)
        start = events[0]
        last = events[-1]
        done = [e for e in events if e["type"] == "done"]
        return {"run": run_id, "name": start["name"], "kind": start["kind"],
                "status": last["type"] if last["type"] in ("finished", "paused", "failed")
                else "running",
                "steps_done": len(done), "last": last,
                "routes": [e for e in events if e["type"] == "routed"]}


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    """What a run log keeps of a step's result: enough to bind and to resume."""
    text = json.dumps(result, ensure_ascii=False, default=str)
    return result if len(text) <= 20_000 else {"truncated": True, "keys": sorted(result)}


class Runner:
    def __init__(self, library: Library, ctx: Context, router: Router | None = None,
                 require_accepted: bool = True):
        self.library = library
        self.ctx = ctx
        self.router = router or Router(None)
        self.require_accepted = require_accepted
        self.store = RunStore(ctx.vault)
        self.run_id = ""
        self.memo: dict[str, Any] = {}           # step key -> logged result, for resume

    # -- entry points --------------------------------------------------------
    def start(self, name: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        d = self.library.get(name)
        report = validate(d, self.library)
        if report["errors"]:
            raise DefinitionError("invalid: " + "; ".join(report["errors"]))
        if self.require_accepted and not self.library.is_accepted(d):
            raise Refusal("PERSON_CONFIRMS", f"{name!r} has not been accepted by a person "
                                             f"(or was edited since); accept_workflow first")
        if TIERS.index(report["tier"]) > TIERS.index(self.ctx.tier):
            raise Refusal("TIER_REFUSED", f"{name!r} needs {report['tier']!r}; this caller "
                                          f"is at {self.ctx.tier!r}")
        values = self._inputs(d, inputs or {})
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.run_id = f"{stamp}-{name}-{secrets.token_hex(2)}"
        self.store.append(self.run_id, {"type": "started", "name": name, "kind": d.kind,
                                        "digest": d.digest, "inputs": values,
                                        "session": self.ctx.session or ""})
        return self._execute(d, values)

    def resume(self, run_id: str, choices: dict[str, str] | None = None) -> dict[str, Any]:
        events = self.store.events(run_id)
        start = events[0]
        if events[-1]["type"] in ("finished", "failed"):
            raise DefinitionError(f"run {run_id} is {events[-1]['type']}")
        d = self.library.get(start["name"])
        if d.digest != start["digest"]:
            raise DefinitionError(f"{start['name']!r} was edited after this run started; "
                                  f"start a new run")
        self.run_id = run_id
        for e in events:
            if e["type"] == "done":
                self.memo[e["key"]] = e["result"]
            if e["type"] == "routed":
                self.memo[f"route:{e['key']}"] = e["option"]
        for key, option in (choices or {}).items():
            self.memo[f"route:{key}"] = option
            self.store.append(run_id, {"type": "routed", "key": key, "option": option,
                                       "reason": "chosen by a person", "by": "person"})
        self.store.append(run_id, {"type": "resumed"})
        return self._execute(d, start["inputs"])

    # -- the engine ----------------------------------------------------------
    def _inputs(self, d: Definition, given: dict[str, Any]) -> dict[str, Any]:
        declared = d.data.get("inputs") or {}
        unknown = sorted(set(given) - set(declared))
        if unknown:
            raise DefinitionError(f"{d.name!r} has no input(s) {unknown}; inputs: "
                                  f"{sorted(declared)}")
        out = {}
        for name, spec in declared.items():
            if name in given:
                value = given[name]
            elif "default" in spec:
                value = spec["default"]
            else:
                raise DefinitionError(f"{d.name!r} needs input {name!r}")
            if not isinstance(value, INPUT_TYPES[spec["type"]]):
                raise DefinitionError(f"input {name!r} should be {spec['type']}")
            out[name] = value
        return out

    def _execute(self, d: Definition, inputs: dict[str, Any]) -> dict[str, Any]:
        try:
            scope = self._steps(d, inputs, prefix="")
        except RunPaused as paused:
            self.store.append(self.run_id, {"type": "paused", "step": paused.step,
                                            **paused.detail})
            return {"run": self.run_id, "status": "paused", "at": paused.step, **paused.detail,
                    "next": "configure a routing model and run_resume, or choose the route "
                            "by hand with run_resume(choices={...})"}
        except RunFailed as failed:
            self.store.append(self.run_id, {"type": "failed", "step": failed.step,
                                            "result": failed.result})
            return {"run": self.run_id, "status": "failed", "at": failed.step,
                    "result": failed.result}
        outputs = resolve(d.data.get("outputs") or {}, scope)
        self.store.append(self.run_id, {"type": "finished", "outputs": outputs})
        return {"run": self.run_id, "status": "finished", "outputs": outputs,
                "steps": {k: v for k, v in scope["steps"].items()}}

    def _steps(self, d: Definition, inputs: dict[str, Any], prefix: str) -> dict[str, Any]:
        scope: dict[str, Any] = {"inputs": inputs, "steps": {}}
        for step in d.data["steps"]:
            key = f"{prefix}{step['id']}"
            if step.get("each") is not None:
                # Inside `each`, `when` is judged per item: it filters the list.
                items = resolve(step["each"], scope)
                if not isinstance(items, list):
                    raise RunFailed(key, {"error": "failed", "detail": f"`each` of {key} is "
                                                                       f"not a list"})
                results = []
                for n, item in enumerate(items[:MAX_EACH]):
                    local = {**scope, "item": item}
                    if holds(step.get("when"), local):
                        results.append(self._one(step, local, f"{key}[{n}]"))
                scope["steps"][step["id"]] = {"results": results, "count": len(results),
                                              "considered": min(len(items), MAX_EACH),
                                              "truncated": len(items) > MAX_EACH}
                continue
            if not holds(step.get("when"), scope):
                scope["steps"][step["id"]] = {"skipped": True}
                continue
            scope["steps"][step["id"]] = self._one(step, scope, key)
        return scope

    def _one(self, step: dict[str, Any], scope: dict[str, Any], key: str) -> dict[str, Any]:
        if key in self.memo:
            return self.memo[key]
        # A surface may cancel a queued action between steps; the run pauses,
        # so what finished stays finished and it can be resumed.
        cancel = self.ctx.extras.get("cancel")
        if cancel is not None and cancel.is_set():
            raise RunPaused(key, {"reason": "cancelled by a person"})
        progress = self.ctx.extras.get("progress")
        if progress is not None:
            progress({"run": self.run_id, "step": key})
        if "action" in step:
            try:
                args = resolve(step.get("args") or {}, scope)
            except KeyError as exc:
                raise RunFailed(key, {"error": "failed", "detail": str(exc)}) from exc
            result = REGISTRY.call(step["action"], args, self.ctx)
            if "error" in result and step.get("on_error") != "continue":
                self.store.append(self.run_id, {"type": "step", "key": key,
                                                "action": step["action"], "ok": False})
                raise RunFailed(key, result)
            self._record(key, step["action"], result)
            return result
        if "workflow" in step:
            return self._workflow(step["workflow"], step.get("args") or {}, scope, key)
        return self._route(step["route"], scope, key)

    def _workflow(self, name: str, args: dict[str, Any], scope: dict[str, Any],
                  key: str) -> dict[str, Any]:
        target = self.library.get(name)
        values = self._inputs(target, resolve(args, scope))
        inner = self._steps(target, values, prefix=f"{key}/")
        result = {"status": "finished", "results": inner["steps"],
                  "outputs": resolve(target.data.get("outputs") or {}, inner)}
        self._record(key, f"workflow:{name}", result)
        return result

    def _route(self, route: dict[str, Any], scope: dict[str, Any], key: str) -> dict[str, Any]:
        items = [None]
        if route.get("each") is not None:
            items = resolve(route["each"], scope)
            if not isinstance(items, list):
                raise RunFailed(key, {"error": "failed", "detail": "route `each` is not a list"})
        results = []
        for n, item in enumerate(items[:MAX_EACH]):
            item_key = f"{key}[{n}]" if route.get("each") is not None else key
            local = {**scope, "item": item} if item is not None else scope
            option = self._decide(route, local, item, item_key)
            spec = route["options"][option]
            if spec.get("end"):
                results.append({"chosen": option})
                continue
            outcome = self._workflow(spec["workflow"], spec.get("args") or {}, local,
                                     f"{item_key}->{option}")
            results.append({"chosen": option, **outcome})
        return {"results": results, "chosen": [r["chosen"] for r in results]}

    def _decide(self, route: dict[str, Any], scope: dict[str, Any], item: Any,
                key: str) -> str:
        if f"route:{key}" in self.memo:
            return self.memo[f"route:{key}"]
        options = route["options"]
        if route["decide"] == "declared":
            chosen = next((name for name, spec in options.items()
                           if "when" in spec and holds(spec["when"], scope)),
                          route.get("otherwise"))
            if chosen is None:
                raise RunFailed(key, {"error": "failed", "detail": "no declared route matched "
                                                                   "and there is no otherwise"})
            self.store.append(self.run_id, {"type": "routed", "key": key, "option": chosen,
                                            "by": "declaration"})
            self.memo[f"route:{key}"] = chosen
            return chosen
        try:
            chosen, reason, model = self.router.choose(
                str(route["question"]),
                {name: str(spec["when_to_choose"]) for name, spec in options.items()},
                item if item is not None else scope.get("steps"))
        except LookupError as exc:
            raise RunPaused(key, {"reason": str(exc), "question": route["question"],
                                  "options": sorted(options),
                                  "item": unframed(item)}) from exc
        self.store.append(self.run_id, {"type": "routed", "key": key, "option": chosen,
                                        "reason": reason, "by": model or "model"})
        self.memo[f"route:{key}"] = chosen
        return chosen

    def _record(self, key: str, action: str, result: dict[str, Any]) -> None:
        summary = _summary(result)
        self.memo[key] = summary
        self.store.append(self.run_id, {"type": "done", "key": key, "action": action,
                                        "result": summary})
