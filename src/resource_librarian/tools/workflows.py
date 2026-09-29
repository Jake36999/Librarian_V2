"""Workflows and pipelines as tools: list, validate, save, accept, run."""
from __future__ import annotations

from .. import clerk, workflows
from ..registry import Card, Context, tool
from ..rules import Refusal


def _library(ctx: Context) -> workflows.Library:
    return workflows.Library(ctx.vault)


def _router(ctx: Context) -> workflows.Router:
    if "router" in ctx.extras:
        return ctx.extras["router"]
    config = ctx.vault.config()
    settings = (config.get("routing") or {}) if (config.get("routing") or {}).get("provider") \
        else (config.get("clerk") or {})
    try:
        endpoint = clerk.from_config(settings)
    except clerk.ClerkUnavailable:
        endpoint = None
    return workflows.Router(endpoint or ctx.extras.get("clerk_fallback"))


@tool("list_workflows", tier="consult", effect="read", returns=("definitions",),
      card=Card("The workflows and pipelines this vault can run: the standard set and its own",
                "choosing automated work to run"))
def list_workflows(ctx: Context) -> dict:
    library = _library(ctx)
    out = []
    for d in library.all().values():
        report = workflows.validate(d, library)
        out.append({"name": d.name, "kind": d.kind, "origin": d.origin,
                    "purpose": d.data.get("purpose", ""), "tier": report["tier"],
                    "valid": report["valid"], "accepted": library.is_accepted(d),
                    "inputs": d.data.get("inputs") or {}})
    return {"definitions": sorted(out, key=lambda r: (r["kind"], r["name"]))}


@tool("show_workflow", tier="consult", effect="read",
      card=Card("One workflow or pipeline: its YAML and its validation", "before running it"))
def show_workflow(ctx: Context, name: str) -> dict:
    library = _library(ctx)
    d = library.get(name)
    return {"name": d.name, "kind": d.kind, "origin": d.origin, "yaml": d.text,
            "accepted": library.is_accepted(d), **workflows.validate(d, library)}


@tool("validate_workflow", tier="consult", effect="read",
      card=Card("Check a workflow or pipeline definition without saving it",
                "drafting a new definition", "Lists every problem at once"))
def validate_workflow(ctx: Context, yaml_text: str) -> dict:
    return workflows.validate(workflows.parse(yaml_text), _library(ctx))


@tool("save_workflow", tier="contribute", effect="write",
      card=Card("Save a workflow or pipeline into this vault",
                "a definition validates and should be kept",
                "Refused unless valid. Saved by an agent it waits for a person's acceptance "
                "before anything but a person may run it"))
def save_workflow(ctx: Context, yaml_text: str) -> dict:
    return _library(ctx).save(yaml_text, accepted_by_person=ctx.tier == "curate")


@tool("accept_workflow", tier="curate", effect="write",
      card=Card("Accept a saved workflow or pipeline so it may run unattended",
                "you have read it",
                "Person-only: an accepted workflow runs without anyone watching each step, so "
                "only a person who has read it may accept it. Tied to its exact text; an edit "
                "revokes it"))
def accept_workflow(ctx: Context, name: str) -> dict:
    return _library(ctx).accept(name)


def _run(ctx: Context, name: str, inputs: dict | None, kind: str) -> dict:
    library = _library(ctx)
    d = library.get(name)
    if d.kind != kind:
        raise TypeError(f"{name!r} is a {d.kind}; use run_{d.kind}")
    runner = workflows.Runner(library, ctx, _router(ctx),
                              require_accepted=ctx.tier != "curate")
    return runner.start(name, inputs or {})


@tool("run_workflow", tier="consult", effect="write", open_world=True,
      returns=("run", "status", "outputs", "steps"),
      card=Card("Run a workflow: a standard set of actions, with no model",
                "a known sequence of actions should happen",
                "Each step runs with the caller's own tier and the session's gates"))
def run_workflow(ctx: Context, name: str, inputs: dict | None = None) -> dict:
    return _run(ctx, name, inputs, "workflow")


@tool("run_pipeline", tier="consult", effect="write", open_world=True,
      returns=("run", "status", "outputs", "steps"),
      card=Card("Run a pipeline: workflows in sequence, routed by declared conditions or by "
                "a model choosing among fixed options",
                "a multi-stage job should run, possibly in the background",
                "Pauses (never guesses) when a routing model is unavailable"))
def run_pipeline(ctx: Context, name: str, inputs: dict | None = None) -> dict:
    return _run(ctx, name, inputs, "pipeline")


@tool("run_status", tier="consult", effect="read",
      card=Card("Where a workflow or pipeline run is: finished, paused, failed or running",
                "checking on a run"))
def run_status(ctx: Context, run_id: str) -> dict:
    return workflows.RunStore(ctx.vault).status(run_id)


@tool("run_resume", tier="consult", effect="write", open_world=True,
      card=Card("Continue a paused run, optionally with a person's route choices",
                "a run paused at a routing step",
                "`choices` maps a paused step key to an option; only a person may give them"))
def run_resume(ctx: Context, run_id: str, choices: dict | None = None) -> dict:
    if choices and ctx.tier != "curate":
        raise Refusal("PERSON_CONFIRMS", "choosing a route by hand is a person's decision")
    runner = workflows.Runner(_library(ctx), ctx, _router(ctx),
                              require_accepted=ctx.tier != "curate")
    return runner.resume(run_id, choices)
