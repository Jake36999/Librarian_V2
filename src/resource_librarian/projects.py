"""Project access (Research Pipeline §6; plan P6): the librarian reads a project's own files
only where a person allowed it.

- **Off by default.** `enabled` is a person's switch (Settings -> Projects); off, every
  project tool is refused at the core and taken out of the model's tool set - a session
  that was already open loses it on its next call.
- **Allowlisted roots.** A person adds each project folder; the model never names a path. A
  Project note's `repository:` is honoured only when it is one of these roots.
- **Reading is not editing.** Reading and scanning never change a project file. Edits
  (`edit`, the `project_edit` tool) are a separate per-folder permission, off by default:
  one exact snippet replaced or one new file created, confined to the folder, shown as a
  diff, asked through the broker every time, logged with digests and backed up in
  `logs/backups/` so it can be undone.
- **The sidecar.** Adding a root creates `<root>/librarian-app/` - manifest, README, data/,
  information/, sessions/, applications/, index/, logs/ - never overwriting a file already
  there. It holds paths, revisions and derived maps, never copies of the project's files;
  every read, scan and edit is logged in `logs/access.jsonl`.

State: `.librarian/projects.json` in the library (paths are this machine's own).
"""
from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from typing import Any

from .rules import Refusal
from .vault import Vault, now_iso

SCAFFOLD_VERSION = 1
FOLDERS = ("data", "information", "sessions", "applications", "index", "logs")
README = """# librarian-app

This folder belongs to the Resource Librarian library named in `manifest.json`. It is a
sidecar: it holds what the librarian learned about this project - the paths it read, the
revision it read them at, maps of the components and how they relate, and a log of every
read - never a copy of the project's own files.

- **Ownership.** Deleting this folder removes only the librarian's notes about the project;
  your source code and the library's own notes are untouched. `logs/backups/` exists only
  where you allowed edits: it keeps the previous text of each file the librarian changed,
  so any edit can be undone, and its own `.gitignore` keeps it out of version control. It is rebuilt by adding the
  project again in the library's Settings -> Projects.
- **Rebuildable.** `index/` and anything under `data/` and `information/` can be regenerated
  by a scan. `logs/` is the audit trail: keep it if you want the history.
- **Privacy.** Nothing here leaves this machine unless you commit it. The local
  `.gitignore` keeps the generated index and cache out of version control; this folder does
  not touch your project's own `.gitignore`.
"""
LOCAL_IGNORE = "index/\n*.tmp\n"


def _path(vault: Vault) -> Path:
    return vault.librarian / "projects.json"


def state(vault: Vault) -> dict[str, Any]:
    path = _path(vault)
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return {"enabled": bool(data.get("enabled")), "roots": list(data.get("roots") or [])}


def _save(vault: Vault, data: dict[str, Any]) -> None:
    _path(vault).parent.mkdir(parents=True, exist_ok=True)
    _path(vault).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def set_enabled(vault: Vault, on: bool) -> dict[str, Any]:
    data = state(vault)
    data["enabled"] = bool(on)
    _save(vault, data)
    return data


def add_root(vault: Vault, folder: str, project: str = "") -> dict[str, Any]:
    """A person's choice of a project folder: canonical, a real folder, not the library, not a
    whole drive. Creates (or validates) its scaffold."""
    root = Path(folder).expanduser()
    if not root.is_absolute():
        raise TypeError("give the project folder's full path")
    root = root.resolve()
    if not root.is_dir():
        raise TypeError(f"{root} is not a folder")
    if root == Path(root.anchor) or root == Path.home().resolve():
        raise TypeError(f"{root} is a whole drive or home folder: choose the project's own folder")
    vault_root = vault.root.resolve()
    if root == vault_root or vault_root in root.parents or root in vault_root.parents:
        raise TypeError("a project folder cannot contain, or be inside, the library itself")
    data = state(vault)
    existing = next((r for r in data["roots"] if r["path"] == str(root)), None)
    scaffold_state = scaffold(vault, root)
    if existing:
        existing.update(project=project or existing.get("project", ""), scaffold=scaffold_state)
        entry = existing
    else:
        entry = {"id": secrets.token_hex(4), "path": str(root), "project": project,
                 "added_at": now_iso(), "scaffold": scaffold_state}
        data["roots"].append(entry)
    _save(vault, data)
    log(root, {"event": "root added", "project": project})
    return entry


def set_writes(vault: Vault, root_id: str, allowed: bool) -> dict[str, Any]:
    """A person's separate permission for edits in one folder (reading is not editing)."""
    data = state(vault)
    entry = next((r for r in data["roots"] if r["id"] == root_id), None)
    if entry is None:
        raise TypeError(f"no project folder {root_id!r}")
    entry["writes"] = bool(allowed)
    _save(vault, data)
    log(Path(entry["path"]), {"event": "edits " + ("allowed" if allowed else "withdrawn")})
    return data


def writes_allowed(vault: Vault, root: Path) -> bool:
    return any(r["path"] == str(root) and r.get("writes") for r in state(vault)["roots"])


EDIT_MAX_BYTES = 400_000


def edit(vault: Vault, root: Path, rel: str, mode: str, new_text: str, old_text: str = "",
         dry_run: bool = False, session: str = "") -> dict[str, Any]:
    """One scoped change to a text file in an allowed project folder: replace one exact,
    unique snippet, or create a new file. Never inside librarian-app/, .git or a dot-folder;
    never a binary or a symlink; nothing is run. Returns the diff; applied, it is logged with
    the file's digest before and after, the project's revision and a backup of the old text."""
    import difflib
    if not writes_allowed(vault, root):
        raise Refusal("PROJECT_WRITES_OFF", f"edits in {root} are not allowed: a person allows "
                                            f"them per folder in Settings -> Projects")
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    if not parts or any(p in (".", "..") or p.startswith(".") or ":" in p for p in parts) or \
            parts[0].lower() == "librarian-app":
        raise TypeError(f"{rel!r}: a path inside the project, outside librarian-app/ and "
                        f"dot-folders")
    target = root.joinpath(*parts)
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise TypeError(f"{rel!r} is not an ordinary file")
    resolved = target.resolve() if target.exists() else target.parent.resolve() / target.name
    if root.resolve() not in resolved.parents:
        raise TypeError(f"{rel!r} is outside the project folder")
    if mode == "create":
        if target.exists():
            raise TypeError(f"{rel!r} exists: replace a snippet in it instead")
        before = ""
        after = new_text
    elif mode == "replace":
        if not target.is_file():
            raise TypeError(f"{rel!r} does not exist: create it instead")
        raw = target.read_bytes()
        if len(raw) > EDIT_MAX_BYTES or b"\x00" in raw[:4096]:
            raise TypeError(f"{rel!r} is binary or too large to edit here")
        try:
            before = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise TypeError(f"{rel!r} is not UTF-8 text: not edited here") from None
        if not old_text:
            raise TypeError("replace needs old_text: the exact snippet being changed")
        if "\r\n" in before and "\r\n" not in old_text:
            # The file keeps its own line endings; a model writes "\n".
            old_text = old_text.replace("\n", "\r\n")
            new_text = new_text.replace("\r\n", "\n").replace("\n", "\r\n")
        count = before.count(old_text)
        if count != 1:
            raise TypeError(f"old_text occurs {count} times in {rel!r}; it must occur exactly "
                            f"once - include more of the surrounding lines")
        after = before.replace(old_text, new_text, 1)
    else:
        raise TypeError("mode is replace or create")
    clean = "/".join(parts)
    diff = "\n".join(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                           f"a/{clean}", f"b/{clean}", lineterm=""))
    if dry_run:
        return {"path": clean, "applied": False, "diff": diff}
    digest = lambda text: hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]   # noqa: E731
    backups = root / "librarian-app" / "logs" / "backups"
    backup = ""
    if before:
        backups.mkdir(parents=True, exist_ok=True)
        if not (backups / ".gitignore").exists():
            (backups / ".gitignore").write_text("*\n", encoding="utf-8")
        stamp = now_iso().replace(":", "").replace("-", "")[:15]
        name = f"{stamp}-{secrets.token_hex(2)}-{clean.replace('/', '__')}"
        (backups / name).write_bytes(before.encode("utf-8"))
        backup = f"librarian-app/logs/backups/{name}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(after.encode("utf-8"))   # bytes: the file's own line endings stay
    entry = {"event": "edit", "path": clean, "mode": mode, "session": session,
             "revision": revision(root), "before": digest(before) if before else "",
             "after": digest(after), "backup": backup, "diff": diff[:20_000]}
    log(root, entry)
    return {"path": clean, "applied": True, "diff": diff, "backup": backup,
            "revision": entry["revision"]}


def remove_root(vault: Vault, root_id: str) -> dict[str, Any]:
    data = state(vault)
    data["roots"] = [r for r in data["roots"] if r["id"] != root_id]
    _save(vault, data)
    return data


def scaffold(vault: Vault, root: Path) -> dict[str, Any]:
    """Create what is missing of `librarian-app/`; never overwrite a file that exists. An
    existing manifest is read and its version reported."""
    app = root / "librarian-app"
    created: list[str] = []
    for folder in FOLDERS:
        (app / folder).mkdir(parents=True, exist_ok=True)
    manifest = app / "manifest.json"
    if manifest.is_file():
        try:
            found = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"state": "manifest unreadable: left as it is", "version": None}
        version = found.get("schema_version")
        status = "present" if version == SCAFFOLD_VERSION else \
            f"present, version {version} (this app writes {SCAFFOLD_VERSION})"
    else:
        manifest.write_text(json.dumps({
            "schema_version": SCAFFOLD_VERSION, "project_id": secrets.token_hex(8),
            "root": str(root), "library": vault.root.name,
            "library_id": hashlib.sha256(str(vault.root.resolve()).encode()).hexdigest()[:16],
            "created_at": now_iso()}, indent=1), encoding="utf-8")
        created.append("manifest.json")
        status = "created"
    for name, text in (("README.md", README), (".gitignore", LOCAL_IGNORE)):
        if not (app / name).exists():
            (app / name).write_text(text, encoding="utf-8")
            created.append(name)
    return {"state": status, "version": SCAFFOLD_VERSION, **({"created": created} if created else {})}


def log(root: Path, event: dict[str, Any]) -> None:
    path = root / "librarian-app" / "logs" / "access.jsonl"
    if path.parent.is_dir():
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"t": now_iso(), **event}, ensure_ascii=False) + "\n")


def root_for(vault: Vault, project: str, repository: str = "") -> Path:
    """The allowlisted root a project may be read from - or a refusal saying why not."""
    data = state(vault)
    if not data["enabled"]:
        raise Refusal("PROJECT_ACCESS_OFF", "project access is off for this library: a person "
                                            "turns it on in Settings -> Projects")
    wanted = str(Path(repository).expanduser().resolve()) if repository else ""
    for r in data["roots"]:
        if (project and r.get("project") == project) or (wanted and r["path"] == wanted):
            path = Path(r["path"])
            if not path.is_dir():
                raise Refusal("PROJECT_ACCESS_OFF", f"{path} has moved or gone: reselect it in "
                                                    f"Settings -> Projects")
            return path
    raise Refusal("PROJECT_ACCESS_OFF", f"no project folder is allowed for {project!r}: a person "
                                        f"adds it in Settings -> Projects")


def allowed(vault: Vault | None) -> bool:
    return vault is not None and state(vault)["enabled"]


def revision(root: Path) -> str:
    """The project's git commit if it has one, else a digest of its file listing."""
    head = root / ".git" / "HEAD"
    try:
        ref = head.read_text(encoding="utf-8").strip()
        if ref.startswith("ref:"):
            target = root / ".git" / ref.split(" ", 1)[1]
            if target.is_file():
                return target.read_text(encoding="utf-8").strip()[:40]
            packed = root / ".git" / "packed-refs"
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line.endswith(ref.split(" ", 1)[1]):
                    return line.split(" ", 1)[0][:40]
        return ref[:40]
    except OSError:
        listing = sorted(p.relative_to(root).as_posix() for p in root.rglob("*")
                         if p.is_file() and "librarian-app" not in p.parts
                         and not any(part.startswith(".") for part in p.parts))[:5000]
        return "listing-" + hashlib.sha256("\n".join(listing).encode()).hexdigest()[:16]


def scan(vault: Vault, root: Path, project: str) -> dict[str, Any]:
    """Read the project's structure (never its files' contents into the sidecar) and write its
    Data and Information maps into `librarian-app/`."""
    from . import dik, structure
    survey = structure.survey(root)
    rev = revision(root)
    record = dik.from_survey(project, survey, rev, method="static structure (project scan)",
                             files=structure._files(root)[:2000])
    app = root / "librarian-app"
    (app / "data" / "components.json").write_text(json.dumps(
        {"project": project, "revision": rev, "scanned_at": now_iso(), "data": record["data"]},
        indent=1, ensure_ascii=False), encoding="utf-8")
    (app / "information" / "map.json").write_text(json.dumps(
        {"project": project, "revision": rev, "information": record["information"]},
        indent=1, ensure_ascii=False), encoding="utf-8")
    data = state(vault)
    for r in data["roots"]:
        if r["path"] == str(root):
            r["last_scan"] = {"at": now_iso(), "revision": rev, "components": len(record["data"])}
    _save(vault, data)
    log(root, {"event": "scan", "project": project, "revision": rev,
               "components": len(record["data"]), "relations": len(record["information"])})
    return {"project": project, "revision": rev, "components": len(record["data"]),
            "relations": len(record["information"]),
            "written": ["librarian-app/data/components.json", "librarian-app/information/map.json"]}
