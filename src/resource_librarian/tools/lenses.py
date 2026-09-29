"""Using accepted lenses: suggest, adopt into a thread, and install lens packs.

The model may *suggest* a lens (`lens_suggest`, read-only) and ask the person
whether to take it up; only a person *adopts* one (`lens_adopt`, curate),
which puts that lens's instruction into this thread's system prompt
(`loop.Loop.system_prompt`). Dropping a lens only removes an instruction, so
anyone in the thread may do it. Installing a pack is a person's acceptance of
its exact text (`lens_packs.py`).
"""
from __future__ import annotations

from ..lens_packs import PackError, PackLibrary
from ..lenses import LensStore
from ..registry import Card, Context, tool
from ..rules import Refusal
from .sessions import _event, _session

MAX_ADOPTED = 3        # each is an instruction in every later step's prompt; keep it few


@tool("lens_suggest", tier="consult", effect="read",
      returns=("lenses",),
      card=Card("Accepted lenses worth taking up for this material and task, each with why",
                "before assessing a source, designing, debugging or learning something, when "
                "a way of looking at it that a source teaches could help; then ask_user "
                "whether to adopt one",
                "Tags are free-form (material: paper, repository, document...; task: assess, "
                "design, learn...). Read each lens's not_when before suggesting it"))
def lens_suggest(ctx: Context, material: str = "", task: str = "", query: str = "",
                 limit: int = 5) -> dict:
    return {"lenses": LensStore(ctx.vault).suggest(material, task, query, limit)}


@tool("lens_adopt", tier="curate", effect="write",
      returns=("adopted", "lenses"),
      card=Card("Adopt an accepted lens for this thread: its instruction joins the "
                "model's system prompt until dropped",
                "the person has chosen a lens to reason with",
                "Person-only: a lens's instruction was drawn from source text, and becomes an "
                "instruction to the model only by a person's choice"))
def lens_adopt(ctx: Context, lens_id: str) -> dict:
    session = _session(ctx)
    lens = LensStore(ctx.vault).get(lens_id)
    if lens is None:
        raise TypeError(f"no accepted lens {lens_id!r}; lens_list shows them")
    if not lens.get("prompt_fragment"):
        raise TypeError(f"{lens_id!r} has no instruction to adopt")
    if lens_id not in session.lenses and len(session.lenses) >= MAX_ADOPTED:
        raise Refusal("LENS_LIMIT", f"this thread already has {MAX_ADOPTED} lenses adopted "
                                    f"({', '.join(session.lenses)}); lens_drop one first")
    _event(ctx, {"type": "lens", "id": lens_id, "on": True, "by": ctx.tier})
    return {"adopted": lens_id, "lenses": _session(ctx).lenses}


@tool("lens_drop", tier="consult", effect="write",
      returns=("dropped", "lenses"),
      card=Card("Stop using an adopted lens in this thread",
                "a lens no longer fits the work, or the person asks"))
def lens_drop(ctx: Context, lens_id: str) -> dict:
    session = _session(ctx)
    if lens_id not in session.lenses:
        return {"dropped": False, "lenses": session.lenses}
    _event(ctx, {"type": "lens", "id": lens_id, "on": False, "by": ctx.tier})
    return {"dropped": lens_id, "lenses": _session(ctx).lenses}


@tool("library_profile", tier="consult", effect="read",
      returns=("profile",),
      card=Card("The domain profile this library was created with, and where each thing it "
                "suggests stands here: lens packs, outside servers, workflows",
                "setting a library up, or asked what it was set up for",
                "Suggestions only - each is accepted, installed or enabled by a person through "
                "its own gate"))
def library_profile(ctx: Context) -> dict:
    from .. import profiles
    return profiles.checklist(ctx.vault, ctx.extras.get("mcp"))


@tool("lens_packs", tier="consult", effect="read",
      returns=("packs",),
      card=Card("Lens packs - a plugin's or domain pack's hand-written lenses - and whether "
                "each is accepted, changed since, or invalid",
                "setting a vault up for a discipline, or after a plugin added a pack"))
def lens_packs(ctx: Context) -> dict:
    return {"packs": PackLibrary(ctx.vault).status()}


@tool("lens_pack_accept", tier="curate", effect="write",
      returns=("pack", "lenses"),
      card=Card("Accept a lens pack's exact text: its lenses join the lens store",
                "the person has read a pack and wants its lenses available",
                "Person-only, tied to the text's digest: a changed pack needs accepting again, "
                "which replaces its lenses rather than adding duplicates"))
def lens_pack_accept(ctx: Context, name: str) -> dict:
    try:
        return PackLibrary(ctx.vault).accept(name, accepted_by="person")
    except PackError as exc:
        raise TypeError(str(exc)) from None
