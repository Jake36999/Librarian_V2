"""The batch's stages, declared as data (implementation plan M1b; to-be stage contracts).

`standard/stages.yaml` says, for each stage of the source and folder batches, the tools it may call,
the stages it depends on, its recipe, whether it calls a model, its risk and its role, and what a
source must carry before an agent may accept it. `batch.py` reads its views from here, so the stage
list, the recipes (MF-020) and the tool grant are written once.

A stage's tool use is checked per call: `guard(contract, stage, report)` gives the registry a check
that reports, or in `enforce: refuse` refuses, a tool the running stage did not declare. Report first.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any, Callable

import yaml

RISKS = ("routine", "bounded", "high")
ROLES = ("core", "clerk", "scribe")
ENFORCE = ("report", "refuse")
# Named checks a stage's result must pass before the item moves on. Each reads the stage's result.
GATES: dict[str, Callable[[dict[str, Any]], str]] = {
    "result_status": lambda result: "" if result.get("status") in (
        "complete", "partial", "skipped", "queued", "reused") else
        f"stage ended {result.get('status')!r}",
}


class StageDefinitionError(ValueError):
    """The stage declaration is malformed; the Core does not start on a broken one."""


@dataclass(frozen=True)
class Stage:
    name: str
    tools: frozenset[str]
    after: tuple[str, ...]
    recipe: str
    model: bool
    risk: str
    role: str
    gate: tuple[str, ...]


@dataclass(frozen=True)
class Contract:
    enforce: str
    any_stage: frozenset[str]
    pipelines: dict[str, tuple[Stage, ...]]
    agent_entry: frozenset[str]
    acceptance_enforce: str = "report"

    def stage(self, name: str) -> Stage | None:
        return next((s for stages in self.pipelines.values() for s in stages if s.name == name), None)

    def tools(self) -> frozenset[str]:
        """Every tool any stage may call: the batch's whole grant, now derived from the stages."""
        return frozenset().union(self.any_stage, *(s.tools for st in self.pipelines.values() for s in st))

    def model_stages(self) -> frozenset[str]:
        return frozenset(s.name for st in self.pipelines.values() for s in st if s.model)

    def recipes(self) -> dict[str, str]:
        return {s.name: s.recipe for st in self.pipelines.values() for s in st if s.recipe != "deep_read"}

    def dependencies(self) -> dict[str, set[str]]:
        return {s.name: set(s.after) for st in self.pipelines.values() for s in st if s.after}


def _list(value: Any, where: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise StageDefinitionError(f"{where}: a list")
    return value


def parse(data: Any) -> Contract:
    if not isinstance(data, dict) or data.get("version") != 1:
        raise StageDefinitionError("stages.yaml: version 1")
    enforce = data.get("enforce", "report")
    if enforce not in ENFORCE:
        raise StageDefinitionError(f"enforce is one of {ENFORCE}")
    pipelines: dict[str, tuple[Stage, ...]] = {}
    seen: set[str] = set()
    for kind, rows in (data.get("pipelines") or {}).items():
        stages: list[Stage] = []
        for n, row in enumerate(_list(rows, f"pipelines.{kind}")):
            where = f"pipelines.{kind}[{n}]"
            if not isinstance(row, dict) or not isinstance(row.get("stage"), str):
                raise StageDefinitionError(f"{where}: a mapping with `stage`")
            name = row["stage"]
            if name in seen:
                raise StageDefinitionError(f"{where}: stage {name!r} declared twice")
            after = tuple(_list(row.get("after"), f"{where}.after"))
            earlier = {s.name for s in stages}
            if not set(after) <= earlier:
                raise StageDefinitionError(f"{where}: after names no earlier stage: "
                                           f"{sorted(set(after) - earlier)}")
            if row.get("risk") not in RISKS or row.get("role") not in ROLES:
                raise StageDefinitionError(f"{where}: risk is one of {RISKS}, role one of {ROLES}")
            gate = tuple(_list(row.get("gate"), f"{where}.gate"))
            if not set(gate) <= set(GATES):
                raise StageDefinitionError(f"{where}: unknown gate checks {sorted(set(gate) - set(GATES))}")
            recipe = str(row.get("recipe") or "")
            if not recipe:
                raise StageDefinitionError(f"{where}: a recipe")
            stages.append(Stage(name, frozenset(_list(row.get("tools"), f"{where}.tools")), after,
                                recipe, bool(row.get("model")), row["risk"], row["role"], gate))
            seen.add(name)
        pipelines[str(kind)] = tuple(stages)
    acceptance = data.get("acceptance") or {}
    accept_enforce = acceptance.get("enforce", "report")
    if accept_enforce not in ENFORCE:
        raise StageDefinitionError(f"acceptance.enforce is one of {ENFORCE}")
    return Contract(enforce, frozenset(_list(data.get("any_stage"), "any_stage")), pipelines,
                    frozenset(_list(acceptance.get("agent_entry"), "acceptance.agent_entry")),
                    accept_enforce)


@lru_cache(maxsize=1)
def load() -> Contract:
    text = (resources.files("resource_librarian") / "standard" / "stages.yaml").read_text(encoding="utf-8")
    return parse(yaml.safe_load(text))


def validate_tools(contract: Contract, registered: set[str]) -> None:
    """Every tool a stage declares is registered (checked when the Core starts, as phases are)."""
    unknown = sorted(contract.tools() - registered)
    if unknown:
        raise StageDefinitionError(f"stages.yaml names unregistered tools: {unknown}")


def guard(contract: Contract, stage: str, report: Callable[[str, str], None]) -> Callable[[str], Any]:
    """The registry's per-call check while `stage` runs: None to proceed, or a Refusal."""
    declared = contract.stage(stage)
    allowed = (declared.tools if declared else frozenset()) | contract.any_stage

    def check(tool: str) -> Any:
        if tool in allowed:
            return None
        report(stage, tool)
        if contract.enforce == "refuse":
            from .rules import Refusal
            return Refusal("STAGE_TOOL_REFUSED", f"{tool!r} is not one of stage {stage!r}'s tools "
                                                 f"(standard/stages.yaml)")
        return None
    return check
