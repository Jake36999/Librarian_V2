"""The permission envelope, asked once (implementation plan M2; plan-forward W1b item 5).

Owner, 21 November: "if we map out the permissions required for actions, no matter what workflows,
pipelines, or sprints are constructed from them, it means we can predict the permissions needed, then
flatten them to a single permissions gate". A process's manifest (manifests.py) names every write it
can make, so an agent asks once, before the run, for all of them; the person answers once, and the
Broker grants each tool for the session, exactly as "allow for this session" grants one. On 20
November every Geo-Grapher tool was asked once per session and an always-ask macro waited 600 s each
time.

What is never inside an envelope, because the Broker checks it first: a tool set to Deny or Ask, Plan
mode, the always-ask tools (project_edit, sandbox_output), and every decision reserved for a person
(promotion, sensitivity, spending), which are refusals of their own, not permission prompts. A call
outside the envelope is asked as before. The envelope is recorded in the session's log.
"""
from __future__ import annotations

from typing import Any

from ..registry import REGISTRY, Card, Context, tool


@tool("request_envelope", tier="consult", effect="read",
      returns=("outcome", "tools", "excluded", "reason", "next"),
      card=Card("Ask the person once for every write a process will make, so its run is not "
                "stopped by a permission prompt at each step",
                "before running a workflow or pipeline (or a known set of tools) in Ask mode",
                "Name a process (its manifest gives the writes) and/or tools. One answer grants each "
                "for this session. Tools set to Deny or Ask, Plan mode and always-ask tools stay "
                "outside; reserved decisions are refusals, never permissions. Needs a session"))
def request_envelope(ctx: Context, process: str = "", tools: list[str] | None = None) -> dict:
    if not ctx.session:
        raise TypeError("an envelope is for a session: open_session first")
    wanted: dict[str, str] = {}
    preview: dict[str, Any] = {}
    if process:
        from .. import manifests
        from .workflows import _library
        manifest = manifests.compile_process(process, _library(ctx))
        wanted.update({a["action"]: a["effect"] for a in manifest["actions"]
                       if a.get("declared") and a["effect"] != "read"})
        preview.update(process=process, manifest_digest=manifest["digest"],
                       changes=manifest["rollup"]["changes"],
                       open_world=manifest["rollup"]["open_world"])
    for name in tools or []:
        if name not in REGISTRY:
            raise TypeError(f"{name!r} is not a registered action")
        spec = REGISTRY.get(name)
        if spec.effect != "read":
            wanted[name] = spec.effect
    if not wanted:
        return {"outcome": "not needed", "tools": [], "excluded": {},
                "reason": "nothing named writes, and reads are never asked"}
    broker = ctx.extras.get("broker")
    if broker is None:
        return {"outcome": "not needed", "tools": sorted(wanted), "excluded": {},
                "reason": "this surface's calls are the person's own and are not asked"}
    label = f"the {process} run" if process else "these tools"
    out = broker.envelope(ctx.session, wanted, label, ctx, preview={**preview, "tools": sorted(wanted)})
    if ctx.vault is not None:
        from ..session import SessionStore
        SessionStore(ctx.vault).append(ctx.session, {
            "type": "envelope", "process": process, "tools": out["tools"],
            "excluded": out["excluded"], "outcome": out["outcome"],
            **({"manifest_digest": preview["manifest_digest"]} if "manifest_digest" in preview else {})})
    return {**out, "next": "run the process: its granted writes are not asked again in this session; "
                           "a call outside the envelope is asked as before"}
