"""Create a vault: the starter notes, the layout, and the settings.

`init` never overwrites. Into an empty folder it writes everything; into a
folder that already has files (an existing Obsidian vault, say) it adds only
what is missing and reports what it left alone; into a folder that is already
a vault it refuses, because a second `init` is never what anyone meant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from . import rules
from .rules import Refusal
from .vault import (DEFAULT_CONFIG, NOTE_FOLDERS, SOURCE_KINDS, WORK_FOLDERS, Vault,
                    now_iso, render_config)


@dataclass
class InitReport:
    vault: Path
    created: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    profile: dict | None = None

    def to_dict(self) -> dict:
        return {"vault": str(self.vault), "created": self.created, "kept": self.kept,
                **({"profile": self.profile} if self.profile else {})}


def _starter_files() -> list[tuple[str, str]]:
    """(relative path, text) for every file shipped in `starter/`."""
    root = resources.files("resource_librarian") / "starter"
    out: list[tuple[str, str]] = []

    def walk(node, prefix: str) -> None:
        for child in sorted(node.iterdir(), key=lambda c: c.name):
            rel = f"{prefix}{child.name}"
            if child.is_dir():
                walk(child, rel + "/")
            else:
                out.append((rel, child.read_text(encoding="utf-8")))
    walk(root, "")
    return out


def init(folder: Path | str, name: str = "", profile: str = "") -> InitReport:
    """A new library. `profile` (a standard profile's name, or a profile file)
    specialises it for its domain at creation - see `profiles.py`."""
    root = Path(folder).expanduser().resolve()
    vault = Vault(root)
    if vault.exists():
        raise Refusal("VAULT_EXISTS", f"{root} is already a vault; nothing was changed")
    chosen = None
    if profile:
        from . import profiles
        chosen = profiles.load(profile)          # a bad profile fails before anything is made
    root.mkdir(parents=True, exist_ok=True)
    report = InitReport(root)
    created = now_iso()
    title = name or root.name

    def write(rel: str, text: str) -> None:
        path = root / rel
        if path.exists():
            report.kept.append(rel)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        report.created.append(rel)

    for folder_name in NOTE_FOLDERS:
        (root / folder_name).mkdir(exist_ok=True)
    for kind in SOURCE_KINDS:
        (root / "Sources" / kind).mkdir(parents=True, exist_ok=True)
    for work in WORK_FOLDERS:
        (root / ".librarian" / work).mkdir(parents=True, exist_ok=True)
    (root / ".librarian" / "derived").mkdir(parents=True, exist_ok=True)
    (root / ".evidence").mkdir(exist_ok=True)

    for rel, text in _starter_files():
        if rel == "gitignore.txt":
            write(".gitignore", text)
        else:
            write(rel, text.replace("{name}", title).replace("{created}", created[:10]))
    write("About/Rules.md", "---\ntype: \"about\"\nstatus: \"active\"\ngenerated: true\n---\n\n"
          + rules.render_markdown())

    config = {section: dict(values) for section, values in DEFAULT_CONFIG.items()}
    config["vault"].update(name=title, created=created)
    write(".librarian/config.toml", render_config(config))
    if chosen is not None:
        from . import profiles
        report.profile = profiles.apply_at_creation(vault, chosen)
    return report
