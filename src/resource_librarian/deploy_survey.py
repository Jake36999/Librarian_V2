"""A read-only survey of a folder before it becomes a library (DEPLOY-01).

Three ways a folder can become a library:
- **Create:** the folder is missing or empty, and a new vault is made there.
- **Adopt:** the folder already holds documents (a Git repository, an Obsidian
  vault, a docs tree). The Librarian adds its operational state beside them and
  leaves every document byte-identical (DEPLOY-02 applies it).
- **Attach:** the folder stays read-only: a vault elsewhere reads it as a
  document root and never writes into it.

The survey decides none of this and changes nothing. It reports what an
adoption plan needs:
- the canonical root and its file identity;
- the file system's case rule, and names that differ only by case;
- any existing `.librarian`: a Librarian vault (open it instead), or an
  unrelated folder of that name, which is a hard stop and never reused;
- Git and Obsidian presence;
- content candidates and exclusion candidates;
- symlinks and junctions, which are reported and never followed;
- the Markdown file count, which budgets the watcher;
- a fingerprint of everything it saw, so DEPLOY-02 can refuse to apply a plan
  to a tree that changed since.

It never constructs a `Vault` (which could create state) and opens no file
for writing. Only `.librarian/config.toml` is read, to classify a collision.
"""
from __future__ import annotations

import hashlib
import os
import stat
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SURVEY_VERSION = 1
MAX_ENTRIES = 200_000            # past this the survey stops and says it is partial
# Folders that are never documents. Hidden folders are excluded as well.
EXCLUDE_NAMES = frozenset({
    "node_modules", "__pycache__", ".venv", "venv", "env", "dist", "build", "target",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache", "site-packages", ".next",
    ".cache", "bower_components", ".gradle", ".idea", ".vs", "coverage", "htmlcov"})
DOCUMENT_SUFFIXES = (".md", ".markdown")
WATCHER_POLL_SECONDS = 0.35      # VaultWatcher's current whole-vault poll


@dataclass
class Survey:
    folder: str
    canonical_root: str = ""
    exists: bool = False
    root_identity: dict[str, Any] = field(default_factory=dict)
    root_is_link: bool = False
    case_insensitive: bool | None = None
    case_collisions: list[list[str]] = field(default_factory=list)
    librarian: dict[str, Any] = field(default_factory=dict)
    git: bool = False
    obsidian: bool = False
    content_candidates: list[dict[str, Any]] = field(default_factory=list)
    exclusion_candidates: list[dict[str, Any]] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    markdown_files: int = 0
    files: int = 0
    folders: int = 0
    unreadable: list[str] = field(default_factory=list)
    partial: bool = False
    watcher: dict[str, Any] = field(default_factory=dict)
    modes: dict[str, dict[str, Any]] = field(default_factory=dict)
    stops: list[str] = field(default_factory=list)
    fingerprint: str = ""
    version: int = SURVEY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_link(entry: os.DirEntry | Path) -> bool:
    """A symlink, or on Windows any reparse point (a junction, a mount point)."""
    try:
        info = entry.stat(follow_symlinks=False) if isinstance(entry, os.DirEntry) \
            else os.lstat(entry)
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _case_insensitive(root: Path) -> bool | None:
    """Whether the file system folds case, probed read-only on the root's own name."""
    name = root.name
    flipped = name.swapcase()
    if not name or flipped == name:
        return None
    try:
        return os.path.samefile(root, root.parent / flipped)
    except OSError:
        return False


def _librarian(root: Path) -> dict[str, Any]:
    folder = root / ".librarian"
    if not os.path.lexists(folder):
        return {"state": "absent"}
    if _is_link(folder) or not folder.is_dir():
        return {"state": "unrelated", "why": ".librarian is not a plain folder"}
    config = folder / "config.toml"
    if not config.is_file():
        return {"state": "unrelated", "why": ".librarian has no config.toml"}
    try:
        with config.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return {"state": "unrelated", "why": f"config.toml does not parse: {exc}"[:200]}
    vault = data.get("vault")
    if not isinstance(vault, dict) or "format" not in vault:
        return {"state": "unrelated", "why": "config.toml has no [vault] format: another "
                                             "tool's folder"}
    return {"state": "librarian_vault", "name": str(vault.get("name", "")),
            "format": vault.get("format"), "created": str(vault.get("created", ""))}


def _excluded(name: str) -> str:
    if name in EXCLUDE_NAMES:
        return "build, cache or dependency folder"
    if name.startswith("."):
        return "hidden folder"
    return ""


def survey(folder: Path | str) -> Survey:
    """Survey `folder` without changing anything in it."""
    given = Path(folder).expanduser()
    out = Survey(folder=str(given))
    out.root_is_link = os.path.lexists(given) and _is_link(given)
    root = given.resolve()
    out.canonical_root = str(root)
    out.exists = root.is_dir()
    if os.path.lexists(given) and not out.exists:
        out.stops.append(f"{given} exists and is not a folder")
    if not out.exists:
        _modes(out, empty=True)
        out.fingerprint = _digest(out, [])
        return out
    info = os.stat(root)
    out.root_identity = {"device": info.st_dev, "file_id": info.st_ino}
    out.case_insensitive = _case_insensitive(root)
    out.librarian = _librarian(root)
    out.git = os.path.lexists(root / ".git")
    out.obsidian = (root / ".obsidian").is_dir()

    seen: list[tuple[str, int, int]] = []
    by_folded: dict[str, list[str]] = {}
    top: dict[str, dict[str, int]] = {}
    excluded: dict[str, str] = {}
    stack = [root]
    while stack and not out.partial:
        here = stack.pop()
        try:
            entries = sorted(os.scandir(here), key=lambda e: e.name)
        except OSError as exc:
            out.unreadable.append(f"{here.relative_to(root).as_posix() or '.'}: "
                                  f"{exc.strerror or exc}")
            continue
        for entry in entries:
            rel = Path(entry.path).relative_to(root).as_posix()
            by_folded.setdefault(rel.lower(), []).append(rel)
            if len(seen) >= MAX_ENTRIES:
                out.partial = True
                break
            if _is_link(entry):
                try:
                    target = os.readlink(entry.path)
                except OSError:
                    target = ""
                out.links.append({"path": rel, "target": target})
                seen.append((rel, -1, 0))
                continue
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError as exc:
                out.unreadable.append(f"{rel}: {exc.strerror or exc}")
                continue
            head = rel.split("/", 1)[0]
            if entry.is_dir(follow_symlinks=False):
                why = _excluded(entry.name)
                if why:
                    excluded[rel] = why
                    seen.append((rel + "/", -2, 0))
                    continue
                out.folders += 1
                seen.append((rel + "/", 0, 0))
                stack.append(Path(entry.path))
                continue
            out.files += 1
            seen.append((rel, info.st_size, info.st_mtime_ns))
            if entry.name.lower().endswith(DOCUMENT_SUFFIXES):
                out.markdown_files += 1
                bucket = top.setdefault(head if "/" in rel else ".", {"markdown": 0})
                bucket["markdown"] += 1
    out.case_collisions = sorted(sorted(names) for names in by_folded.values()
                                 if len(names) > 1)
    out.content_candidates = [{"path": k, "markdown_files": v["markdown"]}
                              for k, v in sorted(top.items())]
    out.exclusion_candidates = [{"path": k, "why": v} for k, v in sorted(excluded.items())]
    out.watcher = {"markdown_files": out.markdown_files,
                   "stats_per_second_now": round(out.markdown_files / WATCHER_POLL_SECONDS),
                   "note": "VaultWatcher stats every visible Markdown file each poll today; "
                           "DEPLOY-02 scopes it to the approved roots"}
    _modes(out, empty=not seen)
    out.fingerprint = _digest(out, seen)
    return out


def _modes(out: Survey, *, empty: bool) -> None:
    state = out.librarian.get("state", "absent")
    if state == "unrelated":
        out.stops.append(f"an unrelated .librarian is already here ({out.librarian['why']}); "
                         "it is never reused or replaced: move it, or choose another folder")
    if out.case_collisions and out.case_insensitive is False:
        out.stops.append("names differ only by case on a case-sensitive file system: they "
                         "would collide when opened on Windows or macOS")
    stopped = bool(out.stops)
    vault = state == "librarian_vault"
    out.modes = {
        "create": {"possible": empty and not stopped and not vault,
                   "why": "the folder is missing or empty" if empty else
                          "the folder already has content: adopt or attach it"},
        "adopt": {"possible": not empty and not stopped and not vault and out.exists,
                  "why": "operational state is added beside the documents, which stay "
                         "byte-identical"},
        "attach": {"possible": out.exists and not stopped,
                   "why": "read-only: another library reads it and never writes into it"},
    }
    if vault:
        for mode in ("create", "adopt"):
            out.modes[mode]["why"] = "this folder is already a Librarian vault: open it"
    if out.partial:
        out.modes["adopt"]["possible"] = False
        out.modes["adopt"]["why"] = f"the survey stopped at {MAX_ENTRIES} entries; narrow " \
                                    "the root before adopting it"


def _digest(out: Survey, seen: list[tuple[str, int, int]]) -> str:
    """What DEPLOY-02 compares before it applies: the root's identity and every
    entry's path, size and modification time."""
    digest = hashlib.sha256()
    digest.update(repr((SURVEY_VERSION, out.canonical_root, out.root_identity,
                        out.librarian.get("state"))).encode("utf-8"))
    for row in sorted(seen):
        digest.update(repr(row).encode("utf-8"))
    return digest.hexdigest()[:32]
