"""Lens packs: how a plugin or a domain pack ships reasoning lenses.

A lens pack is one YAML file - a name, default material/task tags, and a list
of hand-written lenses in the same shape the extraction chain drafts (stance,
probes, the failure caught, when it applies and doesn't, an instruction).
It is the third way a vault is specialised without code, beside a domain
pack (what a note holds, `About/Domain Packs.md`) and a stance (how the model
talks, Answer/Coach): *how the model reasons about a kind of material*.

Where packs live, and who trusts them - the same rule as workflows
(`workflows.py`):

- **standard** packs ship with the package (`standard/lens_packs/`);
- **vault** packs are files a person or a plugin put in the vault
  (`.librarian/lens_packs/`), never trusted by being there.

Nothing in a pack reaches the lens store until a person accepts that pack's
exact text (`accept`, a curate action): its lenses are then imported, tagged
with the pack and the digest they came from. If the file changes afterwards,
the pack shows as `changed` and its lenses stay the accepted snapshot until a
person accepts again - which replaces them rather than adding duplicates. A
lens's instruction is text someone else wrote that will be put in front of a
model, so every text field is screened for embedded instructions and links
before a pack can be accepted, and a pack that fails is refused whole.
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

from .clerk import INJECTION_MARKERS
from .lenses import LensStore, tags
from .vault import Vault, now_iso

NAME = re.compile(r"[a-z0-9][a-z0-9\-]{1,60}")
MAX_LENSES = 40
FIELD_CHARS = 800
REQUIRED = ("name", "source", "perspective", "probes", "catches", "prompt_fragment")
TEXT_FIELDS = ("name", "source", "source_quote", "perspective", "catches", "applies_when",
               "not_when", "prompt_fragment")
LIST_FIELDS = ("probes", "attends_to", "deprioritizes")


class PackError(ValueError):
    pass


@dataclass
class Pack:
    name: str
    origin: str                      # standard | vault
    text: str
    data: dict[str, Any] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]

    @property
    def lenses(self) -> list[dict[str, Any]]:
        return list(self.data.get("lenses") or [])


def parse(text: str, origin: str) -> Pack:
    """A pack, with every problem found listed (a pack with problems can be
    shown but never accepted)."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PackError(f"not valid YAML: {exc}") from None
    if not isinstance(data, dict) or "lens_pack" not in data:
        raise PackError("a lens pack is a mapping with `lens_pack: <name>`")
    name = str(data.get("lens_pack") or "")
    if not NAME.fullmatch(name):
        raise PackError(f"pack name {name!r}: lower-case letters, digits and hyphens")
    pack = Pack(name, origin, text, data)
    lenses = data.get("lenses")
    if not isinstance(lenses, list) or not lenses:
        pack.problems.append("`lenses` is a non-empty list")
        return pack
    if len(lenses) > MAX_LENSES:
        pack.problems.append(f"at most {MAX_LENSES} lenses per pack")
    seen: set[str] = set()
    for i, lens in enumerate(lenses):
        where = f"lens {i + 1}"
        if not isinstance(lens, dict):
            pack.problems.append(f"{where} is not a mapping")
            continue
        where = f"lens {i + 1} ({lens.get('name', '?')})"
        for key in REQUIRED:
            if not lens.get(key):
                pack.problems.append(f"{where}: `{key}` is required")
        for key in TEXT_FIELDS:
            value = lens.get(key)
            if value is None:
                continue
            if not isinstance(value, str):
                pack.problems.append(f"{where}: `{key}` is text")
            elif len(value) > FIELD_CHARS:
                pack.problems.append(f"{where}: `{key}` is longer than {FIELD_CHARS} characters")
        for key in LIST_FIELDS:
            value = lens.get(key)
            if value is not None and not (isinstance(value, list) and
                                          all(isinstance(v, str) for v in value)):
                pack.problems.append(f"{where}: `{key}` is a list of text")
        for key in TEXT_FIELDS + LIST_FIELDS:
            value = lens.get(key)
            for text_value in ([value] if isinstance(value, str) else
                               value if isinstance(value, list) else []):
                if isinstance(text_value, str) and INJECTION_MARKERS.search(text_value):
                    pack.problems.append(f"{where}: `{key}` reads as an embedded instruction "
                                         f"or link")
        key_name = str(lens.get("name", "")).strip().lower()
        if key_name in seen:
            pack.problems.append(f"{where}: a second lens with this name")
        seen.add(key_name)
    return pack


class PackLibrary:
    def __init__(self, vault: Vault):
        self.vault = vault

    def folder(self) -> Path:
        return self.vault.librarian / "lens_packs"

    def _accepted_path(self) -> Path:
        return self.vault.librarian / "lens_packs_accepted.json"

    def _standard(self) -> list[Pack]:
        node = resources.files("resource_librarian") / "standard" / "lens_packs"
        if not node.is_dir():
            return []
        return [self._load(child.read_text(encoding="utf-8"), "standard", child.name)
                for child in sorted(node.iterdir(), key=lambda c: c.name)
                if child.name.endswith((".yaml", ".yml"))]

    def _vault(self) -> list[Pack]:
        folder = self.folder()
        return [self._load(path.read_text(encoding="utf-8"), "vault", path.name)
                for path in sorted(folder.glob("*.y*ml"))] if folder.is_dir() else []

    @staticmethod
    def _load(text: str, origin: str, filename: str) -> Pack:
        try:
            return parse(text, origin)
        except PackError as exc:
            stem = re.sub(r"[^a-z0-9-]+", "-", Path(filename).stem.lower()).strip("-") or "pack"
            return Pack(stem, origin, text, {}, [f"{filename}: {exc}"])

    def all(self) -> dict[str, Pack]:
        out: dict[str, Pack] = {}
        for pack in self._standard() + self._vault():
            out.setdefault(pack.name, pack)   # a vault pack can never shadow a standard one
        return out

    def accepted(self) -> dict[str, dict[str, Any]]:
        path = self._accepted_path()
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def status(self) -> list[dict[str, Any]]:
        accepted = self.accepted()
        out = []
        for name, pack in sorted(self.all().items()):
            record = accepted.get(name)
            state = ("invalid" if pack.problems else
                     "not accepted" if record is None else
                     "accepted" if record.get("digest") == pack.digest else "changed")
            out.append({"name": name, "origin": pack.origin, "state": state,
                        "description": str(pack.data.get("description") or ""),
                        "lenses": [str(lens.get("name", "")) for lens in pack.lenses
                                   if isinstance(lens, dict)],
                        "problems": pack.problems, "digest": pack.digest,
                        **({"accepted_at": record.get("at")} if record else {})})
        return out

    def accept(self, name: str, accepted_by: str) -> dict[str, Any]:
        pack = self.all().get(name)
        if pack is None:
            raise PackError(f"no lens pack named {name!r}; lens_packs lists them")
        if pack.problems:
            raise PackError(f"{name!r} cannot be accepted: " + "; ".join(pack.problems[:5]))
        store = LensStore(self.vault)
        accepted = self.accepted()
        previous = accepted.get(name)
        replaced = store.remove_origin(previous["origin"]) if previous else 0
        origin = f"pack:{name}@{pack.digest}"
        defaults_m = tags(pack.data.get("materials"))
        defaults_t = tags(pack.data.get("tasks"))
        ids = []
        for lens in pack.lenses:
            proposal = {**lens,
                        "probes": [{"question": q} for q in lens.get("probes") or []],
                        "attends_to": [{"what": w} for w in lens.get("attends_to") or []],
                        "materials": tags(lens.get("materials")) or defaults_m,
                        "tasks": tags(lens.get("tasks")) or defaults_t,
                        "proposal_id": f"{name}#{lens.get('name', '')}"}
            ids.append(store.accept(proposal, accepted_by, origin=origin))
        accepted[name] = {"digest": pack.digest, "origin": origin, "at": now_iso(),
                          "by": accepted_by, "lenses": ids}
        path = self._accepted_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(accepted, indent=1), encoding="utf-8")
        return {"pack": name, "accepted": True, "digest": pack.digest, "lenses": ids,
                "replaced": replaced}
