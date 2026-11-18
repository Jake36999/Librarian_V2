"""The tool reference note: every registered tool, by tier, generated from the registry so it
cannot drift from the code (like `rules.render_markdown`, which does the same for the rules)."""
from __future__ import annotations

from .registry import REGISTRY, TIERS

_TIER_MEANING = {
    "consult": "reads: what a Reader (an agent working elsewhere) may call",
    "contribute": "writes inside the library's rules: what the librarian's own work calls",
    "curate": "the person's own controls: never a model's call",
}


def render_markdown() -> str:
    lines = ["# Tool Reference", "",
             "Generated from the tool registry. Edit the code, not this page.", "",
             "Every action in the Librarian, from this page or an agent, is one of these tools. "
             "A tool is granted at a *tier*; a caller below that tier is refused by name.", ""]
    for tier in TIERS:
        specs = [REGISTRY.get(name) for name in REGISTRY.names() if REGISTRY.get(name).tier == tier]
        if not specs:
            continue
        lines += [f"## {tier.capitalize()}", "", f"_{_TIER_MEANING.get(tier, '')}_", "",
                  "| Tool | Effect | What it is for | Use it when |", "| --- | --- | --- | --- |"]
        for spec in specs:
            # a card that mentions [[link]] in prose must not become a link the checker finds
            cell = lambda text: " ".join(str(text or "").split()).replace("|", "\\|") \
                .replace("[[", "\\[\\[").replace("]]", "\\]\\]")
            lines.append(f"| `{spec.name}` | {spec.effect} | {cell(spec.card.purpose)} | "
                         f"{cell(spec.card.use_when)} |")
        lines.append("")
    return "\n".join(lines)
