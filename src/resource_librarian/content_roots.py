"""Content roots: which documents a library reads and watches (DEPLOY-02).

A library's documents are named in a versioned manifest,
`.librarian/content-roots.json`:

    {"version": 1, "mode": "adopt",
     "roots": [{"path": ".", "access": "read_write"},
               {"path": "D:/Team/Docs", "access": "read_only", "attached": true,
                "survey_fingerprint": "..."}],
     "excludes": ["node_modules", ".git"],
     "survey_fingerprint": "...", "applied": "..."}

A vault created by `init` has no manifest and keeps today's behaviour: the
whole vault, hidden folders excluded.

**Adopt** turns a folder that already holds documents into a library. It
writes operational state under `.librarian/` only (the config, the work
folders, this manifest). It never adds, moves or rewrites a document, and no
document is placed under `.librarian/`.

**Attach** names a folder outside the vault as a read-only root. Nothing is
written into it: every vault write resolves inside the vault's own root.

Both are compare-and-apply. The person reviews a plan made from a survey
(`deploy_survey.py`), and the plan applies only while the folder's survey
fingerprint is still the one the plan was made from.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .deploy_survey import survey
from .rules import Refusal
from .vault import DEFAULT_CONFIG, WORK_FOLDERS, Vault, now_iso, render_config

MANIFEST = "content-roots.json"
MANIFEST_VERSION = 1


def manifest_path(root: Path) -> Path:
    return Path(root) / ".librarian" / MANIFEST


def load(root: Path) -> dict[str, Any] | None:
    """The manifest, or None for a vault without one (whole vault, today's rules)."""
    path = manifest_path(root)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != MANIFEST_VERSION:
        raise Refusal("VAULT_REQUIRED", f"{path} is content-roots version "
                                        f"{data.get('version')!r}; this build reads "
                                        f"{MANIFEST_VERSION}")
    return data


def watch_scope(root: Path) -> tuple[list[str], set[str]]:
    """The vault-relative folders to watch and the relative paths to skip.

    Attached read-only roots lie outside the vault and are not watched here:
    nothing the Core writes can land in them.
    """
    data = load(root)
    if data is None:
        return ["."], set()
    roots = [r["path"] for r in data.get("roots") or []
             if r.get("access") == "read_write" and not r.get("attached")]
    return roots or ["."], {str(e).strip("/") for e in data.get("excludes") or []}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    from .coordination import atomic_write_text
    atomic_write_text(path, json.dumps(data, indent=1, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------- adopt

def plan_adopt(folder: Path | str, *, name: str = "",
               excludes: list[str] | None = None) -> dict[str, Any]:
    """What adopting `folder` would do, from a survey made now. Changes nothing."""
    found = survey(folder)
    if found.stops:
        raise Refusal("ADOPTION_STOPPED", "; ".join(found.stops))
    if not found.modes["adopt"]["possible"]:
        raise Refusal("ADOPTION_STOPPED", f"{found.canonical_root} cannot be adopted: "
                                      f"{found.modes['adopt']['why']}")
    chosen = sorted({e["path"] for e in found.exclusion_candidates} | set(excludes or []))
    root = Path(found.canonical_root)
    creates = [".librarian/config.toml", f".librarian/{MANIFEST}", ".librarian/.gitignore",
               ".librarian/derived/"] + [f".librarian/{w}/" for w in WORK_FOLDERS]
    return {"mode": "adopt", "root": str(root), "name": name or root.name,
            "survey_fingerprint": found.fingerprint,
            "markdown_files": found.markdown_files, "git": found.git,
            "obsidian": found.obsidian,
            "roots": [{"path": ".", "access": "read_write"}], "excludes": chosen,
            "creates": creates,
            "leaves": "every existing file byte-identical; nothing is added outside "
                      ".librarian/ and no document is moved under it"}


def apply_adopt(folder: Path | str, fingerprint: str, *, name: str = "",
                excludes: list[str] | None = None) -> dict[str, Any]:
    """Adopt `folder` if its survey fingerprint is still `fingerprint`."""
    plan = plan_adopt(folder, name=name, excludes=excludes)
    if plan["survey_fingerprint"] != fingerprint:
        raise Refusal("ADOPTION_PLAN_STALE",
                      "the folder changed since the plan was made (survey fingerprint "
                      f"{plan['survey_fingerprint']}, plan {fingerprint}): survey it again")
    root = Path(plan["root"])
    before = survey(root).entries
    state = root / ".librarian"
    for work in (*WORK_FOLDERS, "derived"):
        (state / work).mkdir(parents=True, exist_ok=True)
    (state / ".gitignore").write_text("# rebuilt on demand; never commit it\nderived/\n",
                                      encoding="utf-8")
    config = {section: dict(values) for section, values in DEFAULT_CONFIG.items()}
    config["vault"].update(name=plan["name"], created=now_iso(), origin="adopted")
    (state / "config.toml").write_text(render_config(config), encoding="utf-8")
    _write_json(state / MANIFEST, {"version": MANIFEST_VERSION, "mode": "adopt",
                                   "roots": plan["roots"], "excludes": plan["excludes"],
                                   "survey_fingerprint": fingerprint, "applied": now_iso()})
    # The documents must be exactly as they were: only .librarian/ may differ.
    after = [row for row in survey(root).entries if row[0] != ".librarian/"]
    if after != before:
        changed = sorted(set(map(str, after)) ^ set(map(str, before)))[:5]
        raise Refusal("ADOPTION_PLAN_STALE", "the documents changed while the library was "
                                              f"being adopted: {changed}; review them")
    return {**plan, "applied": True, "vault": str(root)}


# ------------------------------------------------------------------ attach

def plan_attach(vault: Vault, folder: Path | str) -> dict[str, Any]:
    """What attaching `folder` read-only to `vault` would do. Changes nothing."""
    if not vault.exists():
        raise Refusal("VAULT_REQUIRED", f"{vault.root} is not a library to attach to")
    found = survey(folder)
    if found.stops:
        raise Refusal("ADOPTION_STOPPED", "; ".join(found.stops))
    if not found.modes["attach"]["possible"]:
        raise Refusal("ADOPTION_STOPPED", f"{found.canonical_root} cannot be attached: "
                                      f"{found.modes['attach']['why']}")
    root, home = Path(found.canonical_root), vault.root.resolve()
    if root == home or home in root.parents or root in home.parents:
        raise Refusal("ADOPTION_STOPPED", f"{root} overlaps the library at {home}; an attached "
                                      "root lies wholly outside it")
    return {"mode": "attach", "vault": str(home), "root": str(root),
            "survey_fingerprint": found.fingerprint, "markdown_files": found.markdown_files,
            "access": "read_only", "excludes": sorted(e["path"] for e in
                                                      found.exclusion_candidates),
            "creates": [f".librarian/{MANIFEST} (in the library, not the attached folder)"],
            "leaves": "the attached folder untouched; the library never writes into it"}


def apply_attach(vault: Vault, folder: Path | str, fingerprint: str) -> dict[str, Any]:
    plan = plan_attach(vault, folder)
    if plan["survey_fingerprint"] != fingerprint:
        raise Refusal("ADOPTION_PLAN_STALE",
                      "the folder changed since the plan was made: survey it again")
    data = load(vault.root) or {"version": MANIFEST_VERSION, "mode": "create",
                                "roots": [{"path": ".", "access": "read_write"}],
                                "excludes": []}
    data["roots"] = [r for r in data["roots"] if r.get("path") != plan["root"]] + [
        {"path": plan["root"], "access": "read_only", "attached": True,
         "excludes": plan["excludes"], "survey_fingerprint": fingerprint,
         "applied": now_iso()}]
    _write_json(manifest_path(vault.root), data)
    return {**plan, "applied": True}



# ------------------------------------------------- documents in the roots (DEPLOY-03)

WORKSPACE_DOCUMENT = "workspace_document"


def iter_documents(root: Path) -> list[Path]:
    """Every visible Markdown file under the manifest's read-write roots, sorted,
    without entering hidden folders, excluded paths or links."""
    import os
    import sys
    root = Path(root)
    roots, excludes = watch_scope(root)
    fold = sys.platform == "win32"      # rglob's '*.md' matches '.MD' there too
    out: set[Path] = set()
    for start in roots:
        top = root if start in (".", "") else root / start
        for dirpath, dirnames, filenames in os.walk(top):
            here = Path(dirpath)
            rel = here.relative_to(root).as_posix()
            dirnames[:] = [d for d in dirnames if not d.startswith(".")
                           and not (here / d).is_symlink()
                           and (f"{rel}/{d}" if rel != "." else d) not in excludes]
            for name in filenames:
                if (name.lower() if fold else name).endswith(".md"):
                    out.add(here / name)
    return sorted(out)


def adopted(root: Path) -> bool:
    """Whether this library was made by adopting an existing documents folder."""
    data = load(root)
    return bool(data and data.get("mode") == "adopt")


def manifest_bytes(root: Path) -> bytes:
    path = manifest_path(root)
    return path.read_bytes() if path.is_file() else b""
