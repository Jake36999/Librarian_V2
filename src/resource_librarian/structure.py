"""A repository's code structure and access points, read from a shallow clone
(Co-work Roadmap §1 item 6, §4 D5).

Nothing in the clone is run, installed or imported: Python is parsed with
`ast`, other languages are read with patterns, manifests as text. What comes
back is data - which files define what, how the project is started, which
routes and environment variables it exposes - recorded as evidence and
written into the note by code, never by a model. Each item names the file it
was read from, so a person can check it.

The code-intelligence MCP server answers only for the repositories it has
already indexed, and Topos would be a third-party install; this reader needs
only `git`, and can be swapped for either once they read an arbitrary
checkout.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import tomllib
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

MAX_FILES = 600               # source files read, most shallow first
MAX_FILE_BYTES = 300_000
MAX_REPO_KB = 200_000         # GitHub's `size`; larger repositories are not cloned
CLONE_TIMEOUT = 120
SKIP_DIRS = frozenset({".git", "node_modules", "vendor", "third_party", "dist", "build",
                       ".venv", "venv", "__pycache__", "site-packages", ".tox", "target"})
LANGUAGES = {".py": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
             ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript", ".go": "go",
             ".rs": "rust", ".java": "java", ".kt": "kotlin", ".rb": "ruby", ".cs": "csharp",
             ".cpp": "cpp", ".cc": "cpp", ".c": "c", ".h": "c", ".hpp": "cpp", ".php": "php",
             ".swift": "swift"}
# Examples, docs and scripts show how a project is used; they are read after
# its own code, and their routes, mains and settings are kept apart.
EXAMPLE = re.compile(r"(^|/)(examples?|samples?|docs?|docs_src|demos?|scripts|benchmarks?|"
                     r"tutorials?|playground)/", re.I)
TEST_FILE = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]+\.py$|_test\.(py|go)$|"
                       r"\.(test|spec)\.[jt]sx?$")

# Patterns for languages without a parser here. Each captures a name.
SYMBOLS = {
    "javascript": re.compile(r"^export\s+(?:default\s+)?(?:async\s+)?(?:function\*?|class|const|"
                             r"let)\s+([A-Za-z_$][\w$]*)"
                             r"|^(?:module\.)?exports\.([A-Za-z_$][\w$]*)\s*="
                             r"|^[A-Za-z_$][\w$]*\.([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?"
                             r"function\b", re.M),
    "go": re.compile(r"^func\s+(?:\([^)]*\)\s*)?([A-Z]\w*)\s*\(|^type\s+([A-Z]\w*)\s", re.M),
    "rust": re.compile(r"^\s*pub\s+(?:async\s+)?(?:fn|struct|enum|trait)\s+([A-Za-z_]\w*)",
                       re.M),
    "java": re.compile(r"^\s*public\s+(?:final\s+|abstract\s+)?(?:class|interface|record|enum)"
                       r"\s+([A-Z]\w*)", re.M),
}
SYMBOLS["typescript"] = re.compile(SYMBOLS["javascript"].pattern.replace(
    r"class|const|", r"class|const|interface|type|enum|"), re.M)
ROUTE = re.compile(
    r"""@(?:\w+\.)?(?:route|get|post|put|patch|delete|websocket|api_route)\(\s*['"]([^'"]+)['"]"""
    r"""(?:[^)]*methods\s*=\s*\[([^\]]*)\])?"""
    r"""|\b(?:app|router|server)\.(get|post|put|patch|delete|use|all)\(\s*['"`](/[^'"`]*)['"`]"""
    r"""|\bHandleFunc\(\s*"([^"]+)\"""")
ENV = re.compile(r"""os\.environ(?:\.get)?[\[(]\s*['"]([A-Z][A-Z0-9_]{2,})['"]"""
                 r"""|os\.getenv\(\s*['"]([A-Z][A-Z0-9_]{2,})['"]"""
                 r"""|process\.env\.([A-Z][A-Z0-9_]{2,})"""
                 r"""|process\.env\[\s*['"]([A-Z][A-Z0-9_]{2,})['"]"""
                 r"""|os\.Getenv\(\s*"([A-Z][A-Z0-9_]{2,})"\)"""
                 r"""|std::env::var\(\s*"([A-Z][A-Z0-9_]{2,})"\)""")
SECRET = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH", re.I)
MCP_TOOL = re.compile(r"""@(?:\w+\.)?tool\(|\.tool\(\s*['"]([\w-]+)['"]|server\.tool\(""")


class CloneError(Exception):
    pass


# ------------------------------------------------------------------ checkout

def _unlock(func, path, _exc):                                  # pragma: no cover - Windows
    os.chmod(path, stat.S_IWRITE)
    func(path)


@contextmanager
def shallow_clone(url: str, timeout: int = CLONE_TIMEOUT) -> Iterator[Path]:
    """The default branch at depth 1, blobs over 1 MB left out, no submodules,
    no LFS, no hooks, no prompt for credentials; removed afterwards."""
    if shutil.which("git") is None:
        raise CloneError("git is not installed")
    tmp = Path(tempfile.mkdtemp(prefix="librarian-clone-"))
    dest = tmp / "repo"
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1",
           "GIT_ASKPASS": "", "SSH_ASKPASS": ""}
    try:
        try:
            done = subprocess.run(
                ["git", "-c", "core.hooksPath=" + os.devnull, "-c", "protocol.file.allow=never",
                 "-c", "core.symlinks=false", "clone", "--quiet", "--depth", "1",
                 "--single-branch", "--no-tags", "--filter=blob:limit=1m", "--", url, str(dest)],
                env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise CloneError(f"clone took longer than {timeout}s") from exc
        if done.returncode != 0:
            raise CloneError((done.stderr or "clone failed").strip().splitlines()[-1][:300])
        yield dest
    finally:
        shutil.rmtree(tmp, onerror=_unlock)


# ------------------------------------------------------------------ reading

def _files(root: Path) -> list[str]:
    out: list[str] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        rel = Path(current).relative_to(root)
        out += [(rel / n).as_posix() for n in sorted(names)]
    return sorted(out, key=lambda p: (bool(EXAMPLE.search(p)), p.count("/"), p))


def _read(root: Path, rel: str) -> str:
    path = root / rel
    try:
        if path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _python(source: str) -> tuple[list[str], bool]:
    """Public top-level classes and functions, and whether it has a
    `__main__` block."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return [], False
    names, main = [], False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                and not node.name.startswith("_"):
            names.append(("class " if isinstance(node, ast.ClassDef) else "def ") + node.name)
        elif isinstance(node, ast.If) and "__main__" in ast.unparse(node.test):
            main = True
    return names, main


def _manifest_entries(root: Path, files: set[str]) -> list[dict[str, str]]:
    """How a project says it is started: console scripts, npm bins and
    scripts, container entry points, binaries."""
    out: list[dict[str, str]] = []
    if "pyproject.toml" in files:
        try:
            data = tomllib.loads(_read(root, "pyproject.toml"))
        except tomllib.TOMLDecodeError:
            data = {}
        project = data.get("project") or {}
        for kind in ("scripts", "gui-scripts"):
            for name, target in (project.get(kind) or {}).items():
                out.append({"kind": "console script", "name": name, "target": str(target),
                            "file": "pyproject.toml"})
        poetry = ((data.get("tool") or {}).get("poetry") or {}).get("scripts") or {}
        for name, target in poetry.items():
            out.append({"kind": "console script", "name": name, "target": str(target),
                        "file": "pyproject.toml"})
    if "setup.py" in files:
        for name, target in re.findall(r"['\"]([\w.-]+)\s*=\s*([\w.]+:[\w.]+)['\"]",
                                       _read(root, "setup.py")):
            out.append({"kind": "console script", "name": name, "target": target,
                        "file": "setup.py"})
    if "package.json" in files:
        try:
            pkg = json.loads(_read(root, "package.json") or "{}")
        except json.JSONDecodeError:
            pkg = {}
        bins = pkg.get("bin") or {}
        if isinstance(bins, str):
            bins = {pkg.get("name", "bin"): bins}
        for name, target in bins.items():
            out.append({"kind": "npm bin", "name": name, "target": str(target),
                        "file": "package.json"})
        if isinstance(pkg.get("main"), str):
            out.append({"kind": "npm main", "name": pkg.get("name", ""), "target": pkg["main"],
                        "file": "package.json"})
        for name in ("start", "serve", "dev", "cli"):
            if name in (pkg.get("scripts") or {}):
                out.append({"kind": "npm script", "name": name,
                            "target": str(pkg["scripts"][name])[:120], "file": "package.json"})
    if "Cargo.toml" in files:
        try:
            cargo = tomllib.loads(_read(root, "Cargo.toml"))
        except tomllib.TOMLDecodeError:
            cargo = {}
        for b in cargo.get("bin") or []:
            out.append({"kind": "binary", "name": b.get("name", ""),
                        "target": b.get("path", ""), "file": "Cargo.toml"})
    for rel in sorted(files):
        if Path(rel).name == "Dockerfile" or Path(rel).name.startswith("Dockerfile."):
            for kind, value in re.findall(r"^(ENTRYPOINT|CMD)\s+(.+)$", _read(root, rel), re.M):
                out.append({"kind": f"container {kind.lower()}", "name": rel,
                            "target": value.strip()[:120], "file": rel})
    if "src/main.rs" in files and not any(e["kind"] == "binary" for e in out):
        out.append({"kind": "binary", "name": "main", "target": "src/main.rs",
                    "file": "src/main.rs"})
    return out


def survey(root: Path) -> dict[str, Any]:
    """Structure and access points of a checkout. Bounded: at most MAX_FILES
    source files, each at most MAX_FILE_BYTES, shallowest first."""
    files = _files(root)
    fileset = set(files)
    languages: dict[str, int] = {}
    for rel in files:
        lang = LANGUAGES.get(Path(rel).suffix.lower())
        if lang:
            languages[lang] = languages.get(lang, 0) + 1
    tests = [f for f in files if TEST_FILE.search(f)]
    modules: list[dict[str, Any]] = []
    entry = _manifest_entries(root, fileset)
    routes: list[dict[str, str]] = []
    example_routes: list[dict[str, str]] = []
    env: dict[str, str] = {}
    mcp_files: list[str] = []
    read = 0
    for rel in files:
        lang = LANGUAGES.get(Path(rel).suffix.lower())
        if not lang or rel in tests:
            continue
        if read >= MAX_FILES:
            break
        source = _read(root, rel)
        if not source:
            continue
        read += 1
        example = bool(EXAMPLE.search(rel))
        if lang == "python":
            names, main = _python(source)
            if main and not example:
                entry.append({"kind": "__main__ block", "name": rel, "target": rel, "file": rel})
        else:
            pattern = SYMBOLS.get(lang)
            names = [next(g for g in m.groups() if g) for m in pattern.finditer(source)] \
                if pattern else []
            if not example and lang == "go" and re.search(r"^package main\b", source, re.M) \
                    and re.search(r"^func main\(\)", source, re.M):
                entry.append({"kind": "go main", "name": rel, "target": rel, "file": rel})
        if names:
            modules.append({"file": rel, "symbols": list(dict.fromkeys(names))[:25]})
        for m in ROUTE.finditer(source):
            g = m.groups()
            if g[0]:
                methods = ",".join(re.findall(r"[A-Z]+", g[1] or "")) or "-"
                route = {"path": g[0], "method": methods, "file": rel}
            elif g[3]:
                route = {"path": g[3], "method": g[2].upper(), "file": rel}
            else:
                route = {"path": g[4], "method": "-", "file": rel}
            (example_routes if example else routes).append(route)
        if example:
            continue
        for m in ENV.finditer(source):
            env.setdefault(next(g for g in m.groups() if g), rel)
        if MCP_TOOL.search(source) and re.search(r"\bmcp\b|modelcontextprotocol|FastMCP",
                                                 source, re.I):
            mcp_files.append(rel)
    for rel in files:                           # documented settings, e.g. `.env.example`
        if Path(rel).name in (".env.example", ".env.sample", "env.example", ".env.template"):
            for name in re.findall(r"^\s*([A-Z][A-Z0-9_]{2,})\s*=", _read(root, rel), re.M):
                env.setdefault(name, rel)
    unique_routes = list({(r["method"], r["path"]): r for r in routes}.values())
    return {
        "files": len(files), "source_files_read": read,
        "languages": dict(sorted(languages.items(), key=lambda kv: -kv[1])),
        "test_files": len(tests),
        "modules": modules[:80],
        "entry_points": entry[:40],
        "routes": unique_routes[:60],
        "example_routes": len({(r["method"], r["path"]) for r in example_routes}),
        "environment": [{"name": n, "file": f, "credential": bool(SECRET.search(n))}
                        for n, f in sorted(env.items())][:60],
        "mcp_server_files": mcp_files[:10],
        "limited": read >= MAX_FILES,
    }


# ------------------------------------------------------------------ writing

def structure_text(s: dict[str, Any]) -> str:
    """The part a clerk may read for What Is Inside: modules and their names."""
    if not s:
        return ""
    lines = [f"source files read: {s['source_files_read']}, test files: {s['test_files']}",
             "languages: " + ", ".join(f"{k} ({v})" for k, v in s["languages"].items())]
    for m in s["modules"][:40]:
        lines.append(f"{m['file']}: {', '.join(m['symbols'][:10])}")
    return "\n".join(lines)


def access_points_section(s: dict[str, Any]) -> str:
    """Written by code: each bullet names the file it was read from."""
    lines: list[str] = []
    declared = [e for e in s.get("entry_points", []) if e["kind"] not in ("__main__ block",
                                                                         "go main")]
    for e in declared[:10]:
        target = f" → `{e['target']}`" if e["target"] and e["target"] != e["name"] else ""
        where = f" ({e['file']})" if e["file"] != e["name"] else ""
        lines.append(f"- **{e['kind']}** `{e['name']}`{target}{where}")
    mains = [e["file"] for e in s.get("entry_points", []) if e not in declared]
    if mains:
        more = f" and {len(mains) - 6} more" if len(mains) > 6 else ""
        lines.append(f"- **Runnable files** ({len(mains)}): " +
                     ", ".join(f"`{f}`" for f in mains[:6]) + more)
    if s.get("mcp_server_files"):
        lines.append("- **MCP server** defined in " +
                     ", ".join(f"`{f}`" for f in s["mcp_server_files"][:3]))
    routes = s.get("routes", [])
    if routes:
        shown = ", ".join(f"`{r['method']} {r['path']}`".replace("`- ", "`")
                          for r in routes[:10])
        more = f" and {len(routes) - 10} more" if len(routes) > 10 else ""
        lines.append(f"- **HTTP routes** ({len(routes)}): {shown}{more} "
                     f"(first in {routes[0]['file']})")
    if s.get("example_routes"):
        lines.append(f"- {s['example_routes']} HTTP routes in its examples and docs, "
                     f"not listed")
    creds = [e for e in s.get("environment", []) if e["credential"]]
    other = [e for e in s.get("environment", []) if not e["credential"]]
    if creds:
        lines.append("- **Credentials it reads**: " +
                     ", ".join(f"`{e['name']}`" for e in creds[:10]))
    if other:
        lines.append("- **Settings it reads**: " +
                     ", ".join(f"`{e['name']}`" for e in other[:12]) +
                     (f" and {len(other) - 12} more" if len(other) > 12 else ""))
    if lines:
        lines.append("- *Read from a shallow clone by code, nothing run; "
                     + ("the first " if s.get("limited") else "") +
                     f"{s['source_files_read']} source files.*")
    return "\n".join(lines)
