#!/usr/bin/env python
"""Pre-landing diff-scope guard for delegated patches (DELEG-03).

Given a work package and a candidate change, report every way the change
leaves the package's admitted scope: files outside the write targets,
forbidden or protected files, deletions, renames, binaries, and test edits
that weaken an admitted check. A finding means the change is refused, not
repaired. The test heuristics are deliberately strict: a lead may still land
a refused change by hand, but the delegated path may not.

Usage:
    check_diff_scope.py PACKAGE.json (--patch FILE | --git RANGE | --worktree BASE)
                        [--repository DIR] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from check_work_package import matches, schema_errors  # noqa: E402


KINDS = ("out_of_scope", "forbidden", "protected", "deleted", "renamed", "binary",
         "test_removed", "assertions_reduced", "skip_added")


@dataclass(frozen=True)
class FileChange:
    old_path: str | None      # None for an added file
    new_path: str | None      # None for a deleted file
    status: str               # "modified" | "added" | "deleted" | "renamed" | "copied"
    binary: bool
    added: tuple[str, ...]    # '+' lines inside hunks, without the '+'
    removed: tuple[str, ...]  # '-' lines inside hunks, without the '-'


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str
    detail: str


# --- parsing ----------------------------------------------------------------------

_ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}
_HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")


def unquote(raw: str) -> str:
    """Decode git's C-style quoting; octal escapes are UTF-8 bytes."""
    if not (len(raw) >= 2 and raw.startswith('"') and raw.endswith('"')):
        return raw
    out = bytearray()
    body, i = raw[1:-1], 0
    while i < len(body):
        ch = body[i]
        if ch != "\\":
            out += ch.encode("utf-8")
            i += 1
        elif body[i + 1:i + 4].isdigit() and len(body[i + 1:i + 4]) == 3:
            out.append(int(body[i + 1:i + 4], 8))
            i += 4
        else:
            out.append(_ESCAPES.get(body[i + 1:i + 2], ord(body[i + 1:i + 2] or "\\")))
            i += 2
    return out.decode("utf-8", errors="replace")


def _side(raw: str) -> str | None:
    """A '---'/'+++' path: unquoted, without its a/ or b/ prefix; None for /dev/null."""
    path = unquote(raw.rstrip("\t"))
    if path == "/dev/null":
        return None
    return path[2:] if path[:2] in ("a/", "b/") else path


def _header_paths(rest: str) -> tuple[str, str]:
    """Paths from 'diff --git a/X b/Y', used only when no other line names them."""
    if rest.startswith('"'):
        tokens = re.findall(r'"(?:[^"\\]|\\.)*"|\S+', rest)
        if len(tokens) == 2:
            return _side(tokens[0]) or "", _side(tokens[1]) or ""
    half = (len(rest) - 1) // 2  # unchanged path: "a/P b/P"
    if rest[half] == " " and rest[2:half] == rest[half + 3:]:
        return rest[2:half], rest[half + 3:]
    old, _, new = rest.partition(" b/")
    return old[2:], new


def parse_diff(text: str) -> list[FileChange]:
    """Parse `git diff -M --no-color --no-ext-diff` output (or a patch file of it)."""
    changes: list[FileChange] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].startswith("diff --git "):
            i += 1
            continue
        header_old, header_new = _header_paths(lines[i][len("diff --git "):])
        old: str | None = header_old
        new: str | None = header_new
        status, binary = "modified", False
        added: list[str] = []
        removed: list[str] = []
        i += 1
        while i < len(lines) and not lines[i].startswith("diff --git "):
            line = lines[i]
            hunk = _HUNK.match(line)
            if hunk:
                # Count the hunk's lines exactly, so a removed "-- x" is content.
                old_left = int(hunk.group(1) if hunk.group(1) is not None else 1)
                new_left = int(hunk.group(2) if hunk.group(2) is not None else 1)
                i += 1
                while i < len(lines) and (old_left > 0 or new_left > 0):
                    body = lines[i]
                    if body.startswith("+"):
                        added.append(body[1:])
                        new_left -= 1
                    elif body.startswith("-"):
                        removed.append(body[1:])
                        old_left -= 1
                    elif body.startswith("\\"):
                        pass  # "\ No newline at end of file"
                    else:
                        old_left -= 1
                        new_left -= 1
                    i += 1
                continue
            if line.startswith("new file mode"):
                status = "added"
            elif line.startswith("deleted file mode"):
                status = "deleted"
            elif line.startswith("rename from "):
                status, old = "renamed", unquote(line[len("rename from "):])
            elif line.startswith("rename to "):
                new = unquote(line[len("rename to "):])
            elif line.startswith("copy from "):
                status, old = "copied", unquote(line[len("copy from "):])
            elif line.startswith("copy to "):
                new = unquote(line[len("copy to "):])
            elif line.startswith(("Binary files ", "GIT binary patch")):
                binary = True
            elif line.startswith("--- "):
                old = _side(line[4:])
            elif line.startswith("+++ "):
                new = _side(line[4:])
            i += 1
        changes.append(FileChange(
            old_path=None if status == "added" else (old or None),
            new_path=None if status == "deleted" else (new or None),
            status=status, binary=binary, added=tuple(added), removed=tuple(removed)))
    return changes


# --- scope rules ------------------------------------------------------------------

_TEST_FUNC = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)\s*\(")
_ASSERTION = re.compile(r"\bassert\b|pytest\.raises|self\.assert\w*\(")
_SKIP = re.compile(r"pytest\.mark\.(?:skip|skipif|xfail)\b|pytest\.(?:skip|xfail)\("
                   r"|unittest\.skip|@skip\b")


def is_test_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (path.startswith("tests/") or name.endswith("_test.py")
            or (name.startswith("test_") and name.endswith(".py")))


def _test_findings(path: str, change: FileChange) -> list[Finding]:
    found = []
    removed = {m.group(1) for m in map(_TEST_FUNC.match, change.removed) if m}
    kept = {m.group(1) for m in map(_TEST_FUNC.match, change.added) if m}
    for name in sorted(removed - kept):
        found.append(Finding("test_removed", path, f"test function {name} removed"))
    lost = sum(1 for line in change.removed if _ASSERTION.search(line))
    gained = sum(1 for line in change.added if _ASSERTION.search(line))
    if lost > gained:
        found.append(Finding("assertions_reduced", path,
                             f"{lost} assertion lines removed, {gained} added"))
    for line in change.added:
        if _SKIP.search(line):
            found.append(Finding("skip_added", path, line.strip()))
    return found


def scope_findings(package: dict[str, Any], changes: list[FileChange]) -> list[Finding]:
    """Every way the changes leave the package's admitted scope, in a stable order."""
    admission = package["admission"]
    protected = {t["path"] for t in admission["protected_targets"]}
    found: list[Finding] = []
    for change in changes:
        # A copy leaves its source untouched; only the new file is a change.
        touched = [p for p in ((None if change.status == "copied" else change.old_path),
                               change.new_path) if p is not None]
        primary = change.new_path or change.old_path or ""
        for path in dict.fromkeys(touched):
            if not matches(path, admission["write_targets"]):
                found.append(Finding("out_of_scope", path, "not in write_targets"))
            if matches(path, admission["forbidden_targets"]):
                found.append(Finding("forbidden", path, "matches forbidden_targets"))
            if path in protected:
                found.append(Finding("protected", path, "protected acceptance target"))
        if change.status == "deleted":
            found.append(Finding("deleted", primary, "file deleted"))
        if change.status == "renamed":
            found.append(Finding("renamed", primary,
                                 f"renamed from {change.old_path} to {change.new_path}"))
        if change.binary:
            found.append(Finding("binary", primary, "binary file"))
        if is_test_file(primary):
            found += _test_findings(primary, change)
    order = {kind: n for n, kind in enumerate(KINDS)}
    return sorted(found, key=lambda f: (f.path, order[f.kind]))


# --- git --------------------------------------------------------------------------

def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repository), *args], capture_output=True,
                            check=False)
    if result.returncode != 0:
        raise SystemExit(f"git {args[0]} failed: "
                         f"{result.stderr.decode('utf-8', errors='replace').strip()}")
    return result.stdout.decode("utf-8", errors="replace")


def diff_text_from_git(rev_range: str, repository: Path) -> str:
    return _git(repository, "diff", "-M", "--no-color", "--no-ext-diff", rev_range)


def added_file_diff(path: str, data: bytes) -> str:
    """A git-format diff that adds one file.

    Written here rather than by `git diff --no-index /dev/null PATH`: native
    Windows git cannot open /dev/null, and that error exits 1 just like a
    successful diff, so a failure would pass silently as "no change".
    """
    head = f"diff --git a/{path} b/{path}\nnew file mode 100644\n"
    if b"\0" in data:
        return head + f"Binary files /dev/null and b/{path} differ\n"
    lines = data.decode("utf-8", errors="replace").splitlines()
    if not lines:
        return head
    body = "".join(f"+{line}\n" for line in lines)
    return head + f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n" + body


def worktree_diff_text(base: str, repository: Path) -> str:
    """The working tree against base, including untracked (new) files."""
    text = _git(repository, "diff", "-M", "--no-color", "--no-ext-diff", base)
    untracked = _git(repository, "ls-files", "--others", "--exclude-standard", "-z")
    for path in filter(None, untracked.split("\0")):
        text += added_file_diff(path, (repository / path).read_bytes())
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("package", type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--patch", type=Path)
    source.add_argument("--git", dest="git_range")
    source.add_argument("--worktree", dest="worktree_base")
    parser.add_argument("--repository", type=Path, default=_SCRIPTS.parent)
    parser.add_argument("--json", dest="json_output", action="store_true")
    args = parser.parse_args(argv)

    try:
        package = json.loads(args.package.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read work package: {exc}") from exc
    errors = schema_errors(package)
    if errors:
        raise SystemExit("work package is not schema-valid:\n  " + "\n  ".join(errors))

    if args.patch:
        try:
            text = args.patch.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise SystemExit(f"cannot read patch file: {exc}") from exc
    elif args.git_range:
        text = diff_text_from_git(args.git_range, args.repository)
    else:
        text = worktree_diff_text(args.worktree_base, args.repository)

    findings = scope_findings(package, parse_diff(text))
    if args.json_output:
        print(json.dumps([vars(f) for f in findings], indent=2))
    else:
        for f in findings:
            print(f"{f.kind}  {f.path}  {f.detail}")
        if not findings:
            print("ok")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
