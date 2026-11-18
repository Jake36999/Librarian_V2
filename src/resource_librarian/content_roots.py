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
    excludes = {str(e).strip('/') for e in data.get('excludes') or []}
    excludes.update(r['path'] for r in data.get('roots', [])
                    if r.get('access') == 'read_only' and not r.get('attached'))
    all_readonly = any(r.get('path') == '.' and r.get('access') == 'read_only'
                       for r in data.get('roots', []))
    return roots or ([] if all_readonly else ['.']), excludes


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

def plan_attach(vault: Vault, folder: Path | str, *, _survey=None) -> dict[str, Any]:
    """What attaching `folder` read-only to `vault` would do. Changes nothing."""
    if not vault.exists():
        raise Refusal("VAULT_REQUIRED", f"{vault.root} is not a library to attach to")
    from .folder_review import configuration
    config = configuration(vault)
    found = _survey or (survey(folder, geographer=config) if config.get('enabled') else survey(folder))
    if found.stops:
        raise Refusal("ADOPTION_STOPPED", "; ".join(found.stops))
    if not found.modes["attach"]["possible"]:
        raise Refusal("ADOPTION_STOPPED", f"{found.canonical_root} cannot be attached: "
                                      f"{found.modes['attach']['why']}")
    root, home = Path(found.canonical_root), vault.root.resolve()
    if root == home or home in root.parents or root in home.parents:
        raise Refusal("ADOPTION_STOPPED", f"{root} overlaps the library at {home}; an attached "
                                      "root lies wholly outside it")
    result = {"mode": "attach", "vault": str(home), "root": str(root),
            "survey_fingerprint": found.fingerprint, "markdown_files": found.markdown_files,
            "access": "read_only", "excludes": sorted(e["path"] for e in
                                                      found.exclusion_candidates),
            "creates": [f".librarian/{MANIFEST} (in the library, not the attached folder)"],
            "leaves": "the attached folder untouched; the library never writes into it"}
    if config.get('enabled'): result['geo_grapher'] = found.geo_grapher['plan']
    return result


def apply_attach(vault: Vault, folder: Path | str, fingerprint: str) -> dict[str, Any]:
    from .folder_review import configuration, FolderReview
    config = configuration(vault)
    found = survey(folder, geographer=config) if config.get('enabled') else survey(folder)
    plan = plan_attach(vault, folder, _survey=found)
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
    result = {**plan, "applied": True}
    if config.get('enabled'): result['folders'] = FolderReview(vault).survey(folder, surveyed=found)
    return result



# ------------------------------------------------- documents in the roots (DEPLOY-03)

WORKSPACE_DOCUMENT = "workspace_document"


def folder_overrides(root):
    """In-vault folders with an accepted decision -> its purpose, as acceptance recorded them in
    the manifest (a root row with its `folder_decision`, or an `exclude`). Reading the manifest,
    not every folder card, keeps Core startup flat: Parallax's 15,543 cards (233 MB) made it take
    longer than the Host's 20-second start window (2026-11-17)."""
    data = load(Path(root)) or {}
    result = {}
    for row in data.get('roots') or []:
        path = str(row.get('path') or '')
        if row.get('folder_decision') and not row.get('attached') and not Path(path).is_absolute() and row.get('purpose'):
            result[path.strip('/') or '.'] = row['purpose']
    for path in data.get('excludes') or []:
        if not Path(str(path)).is_absolute():
            result[str(path).strip('/') or '.'] = 'exclude'
    return result


def outside_scope(rel: str, excludes: set[str], path: Path | None = None, *, overrides=None, hidden: bool = True) -> bool:
    """One visibility rule for indexing and watching an adopted library: a hidden
    name, an excluded path (file or folder) or anything under one, and any
    link or Windows reparse point (a junction is not a symlink to Python 3.11)
    are outside it. The Codex review (2026-10-30) found the walker and the
    watcher each applied only part of this."""
    from .deploy_survey import is_link
    from .credentials import credential_path
    if credential_path(rel):
        return True
    parts = rel.split("/")
    # Indexing and watching skip hidden names; READING a connected project does not (hidden=False):
    # .github, .gitignore and root dotfiles are ordinary project files an agent must be able to open.
    if hidden and any(part.startswith(".") for part in parts):
        return True
    blocked = [e for e in excludes if e == '.' or rel == e or rel.startswith(e + '/')]
    if blocked:
        choices = [(len(p.split('/')), purpose) for p, purpose in (overrides or {}).items()
                   if rel == p or rel.startswith(p + '/')]
        depth, purpose = max(choices, default=(-1, 'exclude'))
        if purpose == 'exclude' or depth <= max(len(e.split('/')) for e in blocked): return True
    return path is not None and is_link(path)


def is_managed(note: Any, model: Any) -> bool:
    """Whether a note is one the Librarian manages: it declares, in its own
    frontmatter, a type the content model knows (`type: source`, `type: concept`).

    This is the one classification for an adopted library, shared by the index
    and validation (REMED-01). Neither the folder a file sits in nor the mere
    presence of frontmatter decides it: a docs tree's `title:`-only README is
    the folder's own documentation, not a managed note."""
    declared = str(getattr(note, "type", "") or "")
    return bool(declared) and any(spec.get("type") == declared
                                  for spec in (getattr(model, "shapes", None) or {}).values())


def iter_files(root: Path) -> list[Path]:
    """Every visible file of any kind under the read-write roots: what a link in
    an adopted library may name (attachments included), by the same rule."""
    return _walk(root, markdown_only=False)


def iter_documents(root: Path) -> list[Path]:
    """Every visible Markdown file under the manifest's read-write roots, sorted:
    `outside_scope` decides what is visible, for folders and files alike."""
    return _walk(root, markdown_only=True)


def _walk(root: Path, *, markdown_only: bool) -> list[Path]:
    from .credentials import generated_path
    import os
    import sys
    root = Path(root)
    roots, excludes = watch_scope(root)
    overrides = folder_overrides(root)
    fold = sys.platform == "win32"      # rglob's '*.md' matches '.MD' there too
    out: set[Path] = set()

    def rel_of(path: Path) -> str:
        return path.relative_to(root).as_posix()

    for start in roots:
        top = root if start in (".", "") else root / start
        if top != root and outside_scope(rel_of(top), excludes, top, overrides=overrides):
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            here = Path(dirpath)
            dirnames[:] = [d for d in dirnames
                           if not outside_scope(rel_of(here / d), excludes, here / d, overrides=overrides)]
            for name in filenames:
                path = here / name
                wanted = not markdown_only or (name.lower() if fold else name).endswith(".md")
                if wanted and not generated_path(rel_of(path)) and not outside_scope(rel_of(path), excludes, path, overrides=overrides):
                    out.add(path)
    return sorted(out)


def adopted(root: Path) -> bool:
    """Whether this library was made by adopting an existing documents folder."""
    data = load(root)
    return bool(data and data.get("mode") == "adopt")


def manifest_bytes(root: Path) -> bytes:
    path = manifest_path(root)
    return path.read_bytes() if path.is_file() else b""


_RESOLVED_SCOPES: dict[tuple[str, bytes], tuple[Path, list, list]] = {}


def _resolved_scope(vault) -> tuple[Path, list[tuple[Path, dict]], list[Path]]:
    """The vault's resolved home, attached roots and manifest exclusions, computed once per
    manifest content. Resolving every root and exclusion on every read cost ~0.7 s per path
    on a manifest with many exclusions, and `sync_documents` reads every in-place Source's
    original on each index refresh (2026-11-18: 143 Sources made one refresh take 95 s)."""
    key = (str(vault.root), manifest_bytes(vault.root))
    hit = _RESOLVED_SCOPES.get(key)
    if hit is None:
        data = load(vault.root) or {}
        home = vault.root.resolve()
        attached = [((home / entry['path']).resolve(), entry)
                    for entry in data.get('roots', []) if entry.get('attached')]
        excludes = []
        for excluded in data.get('excludes', []):
            folder = Path(excluded)
            excludes.append((folder if folder.is_absolute() else home / folder).resolve())
        if len(_RESOLVED_SCOPES) >= 16:
            _RESOLVED_SCOPES.clear()
        hit = _RESOLVED_SCOPES[key] = (home, attached, excludes)
    return hit


def resolve_read_path(vault, value):
    """Resolve a library/attached read under the owner's current manifest.

    Attachment grants reading without requiring a later folder classification.
    An explicit deeper exclusion and configured exclusions still narrow that grant.
    This is path authority only; registry actor/grant and publication checks remain.
    """
    from .credentials import refuse_credentials
    path = (vault.root / value).resolve()
    refuse_credentials(value)
    refuse_credentials(path)
    home, attached, excludes = _resolved_scope(vault)
    if path == home or path.is_relative_to(home):
        return path
    candidates = []
    for base, entry in attached:
        if path.is_relative_to(base):
            candidates.append((len(base.parts), base, entry))
    if not candidates:
        from . import projects
        configured = projects.state(vault)
        if configured['enabled']:
            for entry in configured['roots']:
                base = Path(entry['path']).resolve()
                if path.is_relative_to(base):
                    projects.root_for(vault, '', repository=str(base))
                    candidates.append((len(base.parts), base,
                                       {**entry, 'access': 'read_only'}))
        if not candidates:
            raise TypeError(f"{value!r} is outside the library and configured connected roots")
    _, base, entry = max(candidates, key=lambda item: item[0])
    if entry.get('purpose') == 'exclude' or entry.get('access') not in ('read_only', 'read_write'):
        raise TypeError(f"{value!r} is excluded by the connected-root configuration")
    # An `exclude` decision is written to the manifest's own excludes, not to the root entry
    # (2026-11-17): honour those too, as absolute folders under this root.
    for folder in excludes:
        if folder != home and folder.is_relative_to(base) and (path == folder or path.is_relative_to(folder)):
            raise TypeError(f"{value!r} is excluded by the connected-root configuration")
    rel = path.relative_to(base).as_posix()
    if outside_scope(rel, set(entry.get('excludes', [])), path, hidden=False):
        raise TypeError(f"{value!r} is excluded by the connected-root configuration")
    return path
