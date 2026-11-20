"""Session purposes and phases, declared as data (W1, owner 2026-11-20).

`standard/phases.yaml` is the one place that says, for each purpose, its phases; and for each
phase, its question, budget, tool bundle, exit gate (named checks) and the tools those checks tell
a model to use. This module loads and validates it and gives the rest of the code its views:
`PURPOSES`, `MODE`, `ASKS`, `DEFAULT_BUDGETS`, `ASSUMPTION_PHASES`, the bundle table and the tail.

The gate checks themselves are code - each reads a session's state - and live in session.py's
closed `GATES` registry; `validate_checks` confirms every name declared here is registered there.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from typing import Any

import yaml


class PhaseDefinitionError(ValueError):
    """The phase declaration is malformed; the Core does not start on a broken one."""


@dataclass(frozen=True)
class Remedy:
    tool: str
    purposes: frozenset[str] = frozenset()        # empty: every purpose using the phase
    alternative_in: frozenset[str] = frozenset()  # purposes where it is one of two ways out

    def applies_to(self, purpose: str) -> bool:
        return not self.purposes or purpose in self.purposes


@dataclass(frozen=True)
class GateCheck:
    check: str
    remedies: tuple[Remedy, ...] = ()


@dataclass(frozen=True)
class Phase:
    id: str
    ask: str
    budget: int | None
    assumptions: bool
    bundle_purpose: str
    tools: tuple[str, ...]
    gate: tuple[GateCheck, ...]
    extras: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def bundle_id(self) -> str:
        return self.id.replace("_", "-")

    def remedies(self, purpose: str) -> tuple[Remedy, ...]:
        return tuple(r for g in self.gate for r in g.remedies if r.applies_to(purpose))


@dataclass(frozen=True)
class Declaration:
    version: int
    tool_groups: dict[str, tuple[str, ...]]
    tail: tuple[str, ...]
    refusal_remedies: tuple[str, ...]
    bootstrap_purposes: frozenset[str]
    bootstrap_tools: tuple[str, ...]
    purposes: dict[str, tuple[str, ...]]
    modes: dict[str, str]
    phases: dict[str, Phase]
    bundles: dict[str, tuple[str, tuple[str, ...]]]    # non-phase: id -> (purpose, tools)


def _strings(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise PhaseDefinitionError(f"{where}: a list of names")
    return tuple(value)


def _expand(tools: tuple[str, ...], groups: dict[str, tuple[str, ...]], where: str) -> tuple[str, ...]:
    out: list[str] = []
    for name in tools:
        if name.startswith("@"):
            if name[1:] not in groups:
                raise PhaseDefinitionError(f"{where}: no tool group {name!r}")
            out.extend(groups[name[1:]])
        else:
            out.append(name)
    return tuple(out)


def _remedy(raw: Any, where: str) -> Remedy:
    if isinstance(raw, str):
        return Remedy(raw)
    if not isinstance(raw, dict) or not isinstance(raw.get("tool"), str):
        raise PhaseDefinitionError(f"{where}: a remedy is a tool name or {{tool, purposes, alternative_in}}")
    unknown = set(raw) - {"tool", "purposes", "alternative_in"}
    if unknown:
        raise PhaseDefinitionError(f"{where}: unknown remedy key(s) {sorted(unknown)}")
    return Remedy(raw["tool"], frozenset(_strings(raw.get("purposes", []), where)),
                  frozenset(_strings(raw.get("alternative_in", []), where)))


def parse(text: str) -> Declaration:
    data = yaml.safe_load(text) or {}
    if data.get("version") != 1:
        raise PhaseDefinitionError("phases.yaml: version 1 expected")
    groups = {k: _strings(v, f"tool_groups.{k}") for k, v in (data.get("tool_groups") or {}).items()}
    purposes, modes = {}, {}
    for name, spec in (data.get("purposes") or {}).items():
        if not isinstance(spec, dict) or spec.get("mode") not in ("librarian", "reader"):
            raise PhaseDefinitionError(f"purposes.{name}: needs mode librarian|reader and phases")
        purposes[name] = _strings(spec.get("phases"), f"purposes.{name}.phases")
        modes[name] = spec["mode"]
    phases = {}
    for name, spec in (data.get("phases") or {}).items():
        where = f"phases.{name}"
        if not isinstance(spec, dict) or not isinstance(spec.get("ask"), str):
            raise PhaseDefinitionError(f"{where}: needs ask, bundle and gate")
        bundle = spec.get("bundle") or {}
        gate = []
        for i, g in enumerate(spec.get("gate") or []):
            if not isinstance(g, dict) or not isinstance(g.get("check"), str):
                raise PhaseDefinitionError(f"{where}.gate[{i}]: needs a check name")
            gate.append(GateCheck(g["check"], tuple(_remedy(r, f"{where}.gate[{i}]")
                                                    for r in g.get("remedies") or [])))
        if not gate:
            raise PhaseDefinitionError(f"{where}: a phase declares its gate (at least one check)")
        budget = spec.get("budget")
        if budget is not None and (not isinstance(budget, int) or budget < 1):
            raise PhaseDefinitionError(f"{where}.budget: a positive whole number")
        phases[name] = Phase(
            id=name, ask=spec["ask"], budget=budget, assumptions=bool(spec.get("assumptions")),
            bundle_purpose=str(bundle.get("purpose") or ""),
            tools=_expand(_strings(bundle.get("tools") or [], f"{where}.bundle.tools") if bundle.get("tools")
                          else (), groups, where),
            gate=tuple(gate),
            extras={p: _strings(v, f"{where}.extras.{p}") for p, v in (spec.get("extras") or {}).items()})
    for purpose, sequence in purposes.items():
        missing = [p for p in sequence if p not in phases]
        if missing:
            raise PhaseDefinitionError(f"purposes.{purpose}: undeclared phase(s) {missing}")
    bundles = {}
    for name, spec in (data.get("bundles") or {}).items():
        if name in {p.bundle_id for p in phases.values()}:
            raise PhaseDefinitionError(f"bundles.{name}: a phase's own bundle is declared on the phase")
        tools = _strings(spec.get("tools"), f"bundles.{name}.tools") if spec.get("tools") else ()
        bundles[name] = (str(spec.get("purpose") or ""), _expand(tools, groups, f"bundles.{name}"))
    boot = data.get("bootstrap") or {}
    return Declaration(
        version=1, tool_groups=groups, tail=_strings(data.get("tail") or [], "tail"),
        refusal_remedies=_strings(data.get("refusal_remedies") or [], "refusal_remedies"),
        bootstrap_purposes=frozenset(_strings(boot.get("purposes") or [], "bootstrap.purposes")),
        bootstrap_tools=_strings(boot.get("tools") or [], "bootstrap.tools"),
        purposes=purposes, modes=modes, phases=phases, bundles=bundles)


def load() -> Declaration:
    text = (resources.files("resource_librarian") / "standard" / "phases.yaml").read_text(
        encoding="utf-8")
    return parse(text)


DECLARATION = load()

# The views the rest of the code has always used.
PURPOSES: dict[str, tuple[str, ...]] = dict(DECLARATION.purposes)
MODE: dict[str, str] = dict(DECLARATION.modes)
ASKS: dict[str, str] = {name: p.ask for name, p in DECLARATION.phases.items()}
DEFAULT_BUDGETS: dict[str, int] = {name: p.budget for name, p in DECLARATION.phases.items()
                                   if p.budget is not None}
ASSUMPTION_PHASES: frozenset[str] = frozenset(
    name for name, p in DECLARATION.phases.items() if p.assumptions)
TAIL: tuple[str, ...] = DECLARATION.tail


def phase(name: str) -> Phase:
    return DECLARATION.phases[name]


def validate_checks(registered: set[str]) -> None:
    """Every gate check the declaration names is a registered check function."""
    unknown = sorted({g.check for p in DECLARATION.phases.values() for g in p.gate} - registered)
    if unknown:
        raise PhaseDefinitionError(f"phases.yaml names unregistered gate check(s): {unknown}")
