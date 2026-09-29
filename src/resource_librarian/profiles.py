"""Domain profiles: how a new library is specialised for its domain, in one step.

One library per domain (Co-work Roadmap §4 F). A profile bundles the four
things that specialise a library without code - its Content Model rows (what
a note holds), the lens packs it would reason with, the outside servers it
would use, and the workflows it runs - as one YAML file, applied once when
the library is created (`init --profile`, `new-vault.ps1 -Profile`).

What "applied" means, part by part, since nothing here may bypass a person:

- **Content Model rows** are written into the new library's own
  `About/Note Content Model.md`. Choosing the profile *at creation* is the
  person's decision to have them - the same act as pasting a domain pack's
  rows in by hand (`About/Domain Packs.md`), made at the one moment the file
  is new. Nothing is ever rewritten in an existing library.
- **Lens packs, MCP servers and workflows are only suggested.** They are
  recorded in `.librarian/profile.json` and shown as a checklist (Settings ->
  Library, and `library_profile`), each still accepted, installed or enabled
  by a person through its own usual gate - a profile never accepts a lens
  pack, installs a server or turns one on.

Profiles ship in `standard/profiles/`; a person may also point `init` at a
profile file of their own. Both are parsed strictly: table rows only, under
headings a Content Model already knows how to read.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from .vault import Vault, now_iso

NAME = re.compile(r"[a-z0-9][a-z0-9\-]{1,40}")
TABLE_HEADING = re.compile(r"^## (Frontmatter|Sections|Axis Values) — [a-z0-9_/\-]+$")
ROW = re.compile(r"^\|.*\|$")
FILE = "profile.json"


class ProfileError(ValueError):
    pass


@dataclass
class Profile:
    name: str
    text: str
    description: str = ""
    source_kinds: list[str] = field(default_factory=list)
    tables: list[tuple[str, list[str]]] = field(default_factory=list)
    lens_packs: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    workflows: list[str] = field(default_factory=list)
    pursuit_kind: str = ""

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]


def _names(value: Any, what: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) and NAME.fullmatch(v)
                                               for v in value):
        raise ProfileError(f"`{what}` is a list of names (lower-case letters, digits, hyphens)")
    return list(value)


def parse(text: str) -> Profile:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ProfileError(f"not valid YAML: {exc}") from None
    if not isinstance(data, dict) or not NAME.fullmatch(str(data.get("profile") or "")):
        raise ProfileError("a profile is a mapping with `profile: <name>` (lower-case, hyphens)")
    known = {"profile", "description", "content_model", "lens_packs", "mcp_servers",
             "workflows", "pursuit_kind"}
    if set(data) - known:
        raise ProfileError(f"unknown key(s) {sorted(set(data) - known)}")
    model = data.get("content_model") or {}
    if not isinstance(model, dict) or set(model) - {"source_kinds", "tables"}:
        raise ProfileError("`content_model` has `source_kinds` and/or `tables`")
    kinds = model.get("source_kinds") or []
    if not isinstance(kinds, list) or not all(isinstance(r, str) and ROW.match(r.strip())
                                              for r in kinds):
        raise ProfileError("`content_model.source_kinds` is a list of `| kind | folder | "
                           "description |` rows")
    tables = []
    for table in model.get("tables") or []:
        heading = str((table or {}).get("heading") or "").strip()
        rows = (table or {}).get("rows") or []
        if not TABLE_HEADING.match(heading):
            raise ProfileError(f"table heading {heading!r} is not one a Content Model reads "
                               f"(## Frontmatter / Sections / Axis Values — <scope>)")
        if not isinstance(rows, list) or len(rows) < 3 or not all(
                isinstance(r, str) and ROW.match(r.strip()) for r in rows):
            raise ProfileError(f"{heading}: `rows` is a Markdown table - header, separator, rows")
        tables.append((heading, [r.strip() for r in rows]))
    return Profile(name=str(data["profile"]), text=text,
                   description=str(data.get("description") or ""),
                   source_kinds=[r.strip() for r in kinds], tables=tables,
                   lens_packs=_names(data.get("lens_packs"), "lens_packs"),
                   mcp_servers=_names(data.get("mcp_servers"), "mcp_servers"),
                   workflows=_names(data.get("workflows"), "workflows"),
                   pursuit_kind=str(data.get("pursuit_kind") or ""))


def standard() -> dict[str, Profile]:
    node = resources.files("resource_librarian") / "standard" / "profiles"
    if not node.is_dir():
        return {}
    out = {}
    for child in sorted(node.iterdir(), key=lambda c: c.name):
        if child.name.endswith((".yaml", ".yml")):
            profile = parse(child.read_text(encoding="utf-8"))
            out[profile.name] = profile
    return out


def load(name_or_path: str) -> Profile:
    """A standard profile by name, else a profile file the person points at."""
    found = standard().get(name_or_path)
    if found is not None:
        return found
    path = Path(name_or_path).expanduser()
    if path.is_file():
        return parse(path.read_text(encoding="utf-8"))
    raise ProfileError(f"no profile {name_or_path!r}: the standard ones are "
                       f"{sorted(standard())}, or give a path to a profile file")


def apply_at_creation(vault: Vault, profile: Profile) -> dict[str, Any]:
    """Write the profile's Content Model rows into a *new* library and record
    what it suggests. Called by `init` only - never on an existing library."""
    model = vault.root / "About" / "Note Content Model.md"
    text = model.read_text(encoding="utf-8")
    added: list[str] = []
    if profile.source_kinds:
        start = text.index("## Source Kinds")
        nxt = text.find("\n## ", start + 5)
        block_end = len(text) if nxt == -1 else nxt
        block = text[start:block_end].rstrip("\n")
        present = set(re.findall(r"^\| ([a-z0-9_\-]+) \|", block, re.M))
        new_rows = [r for r in profile.source_kinds
                    if re.match(r"^\| ([a-z0-9_\-]+) \|", r) and
                    re.match(r"^\| ([a-z0-9_\-]+) \|", r).group(1) not in present]
        if new_rows:
            text = text[:start] + block + "\n" + "\n".join(new_rows) + "\n" + text[block_end:]
            added += [f"source kind {re.match(r'^[|] ([a-z0-9_-]+)', r).group(1)}"
                      for r in new_rows]
    for heading, rows in profile.tables:
        if re.search(rf"^{re.escape(heading)}\s*$", text, re.M):
            continue                                     # never overwrite a table
        text = text.rstrip("\n") + f"\n\n{heading}\n\n" + "\n".join(rows) + "\n"
        added.append(heading.removeprefix("## "))
    model.write_text(text, encoding="utf-8")
    record = {"name": profile.name, "digest": profile.digest, "applied_at": now_iso(),
              "content_model_added": added,
              "suggests": {"lens_packs": profile.lens_packs, "mcp_servers": profile.mcp_servers,
                           "workflows": profile.workflows},
              "pursuit_kind": profile.pursuit_kind}
    (vault.librarian / FILE).write_text(json.dumps(record, indent=1), encoding="utf-8")
    return record


def recorded(vault: Vault) -> dict[str, Any] | None:
    path = vault.librarian / FILE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def checklist(vault: Vault, mcp: Any = None) -> dict[str, Any]:
    """The profile's suggestions and where each stands in this library - the
    person's setup checklist. Every item is completed through its own gate."""
    record = recorded(vault)
    if record is None:
        return {"profile": None}
    from .lens_packs import PackLibrary
    packs = {p["name"]: p["state"] for p in PackLibrary(vault).status()}
    here: dict[str, bool] = {}
    installed: set[str] = set()
    if mcp is not None:
        status = mcp.status()
        installed = set(status)
        here = {n: bool(s.get("library_enabled")) for n, s in status.items()}
    from .workflows import Library
    workflows = Library(vault).all()
    suggests = record.get("suggests") or {}
    return {"profile": record["name"], "applied_at": record.get("applied_at"),
            "content_model_added": record.get("content_model_added", []),
            "lens_packs": [{"name": n, "state": packs.get(n, "not available")}
                           for n in suggests.get("lens_packs", [])],
            "mcp_servers": [{"name": n, "state": ("enabled here" if here.get(n) else
                                                  "installed, not enabled here" if n in installed
                                                  else "not installed")}
                            for n in suggests.get("mcp_servers", [])],
            "workflows": [{"name": n, "state": "available" if n in workflows else "not available"}
                          for n in suggests.get("workflows", [])]}
