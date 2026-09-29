"""Reading and writing notes: YAML frontmatter, then Markdown sections.

Markdown is truth, so this is the one place that decides what a note *is*.
Everything downstream (the index, the schema checks, the writers) works from
the `Note` objects produced here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import yaml

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
HEADING = re.compile(r"^## +(.+?)\s*$", re.M)


@dataclass
class Note:
    name: str
    path: Path
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    parse_error: str = ""

    @property
    def type(self) -> str:
        return str(self.frontmatter.get("type") or "")

    def sections(self) -> dict[str, str]:
        return split_sections(self.body)

    def text(self) -> str:
        return render(self.frontmatter, self.body)


def parse(text: str) -> tuple[dict[str, Any], str, str]:
    """Split a note into (frontmatter, body, error). Never raises: a note that
    will not parse is reported, not dropped."""
    match = FRONTMATTER.match(text)
    if not match:
        return {}, text, ""
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        return {}, text[match.end():], f"frontmatter is not valid YAML: {exc}"
    if not isinstance(data, dict):
        return {}, text[match.end():], "frontmatter is not a mapping"
    return data, text[match.end():], ""


def render(frontmatter: dict[str, Any], body: str) -> str:
    # Block style, always: PyYAML's default_flow_style=None collapses a
    # mapping of only scalars (no list or dict values) onto one `{...}`
    # line, and the pane's own frontmatter table (a plain one-`key: value`
    # -per-line scan, not a real YAML parser) then reads none of it.
    head = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True,
                          default_flow_style=False, width=100).strip()
    return f"---\n{head}\n---\n\n{body.lstrip()}" if frontmatter else body


FENCE = re.compile(r"^\s*(```|~~~)")


def toggle_fence(open_marker: str, marker: str) -> str:
    """The fence still open after a fence line: a block opened with ``` is
    closed only by ```, so a ~~~ line inside it is code, not a fence."""
    if not open_marker:
        return marker
    return "" if marker == open_marker else open_marker


def _headings(body: str) -> list[tuple[int, int, str]]:
    """(start, end, title) of every `## ` heading line, skipping any inside a
    fenced code block - a `## ` line in a fence is code, not structure."""
    out: list[tuple[int, int, str]] = []
    fence, pos = "", 0
    for line in body.splitlines(keepends=True):
        opened = FENCE.match(line)
        if opened:
            fence = toggle_fence(fence, opened.group(1))
        elif not fence:
            m = HEADING.match(line)
            if m:
                out.append((pos, pos + len(line.rstrip("\r\n")), m.group(1).strip()))
        pos += len(line)
    return out


def split_sections(body: str) -> dict[str, str]:
    """`## Heading` -> its text, in order. Text before the first heading is
    under the empty key. A heading used twice keeps both texts, joined, so a
    reader never silently loses the first one."""
    heads = _headings(body)
    out: dict[str, str] = {"": body[:heads[0][0]].strip() if heads else body.strip()}
    for i, (_start, end, title) in enumerate(heads):
        stop = heads[i + 1][0] if i + 1 < len(heads) else len(body)
        text = body[end:stop].strip()
        out[title] = f"{out[title]}\n\n{text}".strip() if title in out else text
    return out


def compose(title: str, sections: list[tuple[str, str]]) -> str:
    """A note body from a title and ordered sections."""
    parts = [f"# {title}", ""]
    for heading, text in sections:
        parts += [f"## {heading}", text.strip(), ""]
    return "\n".join(parts)


def with_section(body: str, heading: str, text: str) -> str:
    """`body` with `heading`'s section replaced by `text`, spliced in place:
    every other byte of the note - other sections, a second section that
    happens to share the heading, a `## ` line inside a code fence - is left
    exactly as it was. A heading not yet present is added at the end."""
    block = f"## {heading}\n{text.strip()}".rstrip()
    heads = _headings(body)
    for i, (start, _end, title) in enumerate(heads):
        if title == heading:
            stop = heads[i + 1][0] if i + 1 < len(heads) else len(body)
            tail = body[stop:]
            return body[:start] + block + ("\n\n" + tail if tail else "\n")
    head = body.rstrip()
    return (f"{head}\n\n{block}" if head else block) + "\n"


def append_to_section(body: str, heading: str, text: str) -> str:
    """`body` with `text` added at the end of `heading`'s section (the first,
    if a note repeats it), or a new section holding it."""
    heads = _headings(body)
    for i, (_start, end, title) in enumerate(heads):
        if title == heading:
            stop = heads[i + 1][0] if i + 1 < len(heads) else len(body)
            current = body[end:stop].strip()
            return with_section(body, heading, f"{current}\n{text.strip()}" if current
                                else text)
    return with_section(body, heading, text)


def one_line(text: str, what: str = "text") -> str:
    """A field that is written onto a single Markdown line (a task, a title):
    a newline would let it open a section or fake a date of its own."""
    value = " ".join(str(text or "").split())
    if value.startswith("#"):
        raise TypeError(f"{what} cannot start with '#'")
    return value


def load(path: Path) -> Note:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body, error = parse(text)
    return Note(name=path.stem, path=path, frontmatter=frontmatter, body=body,
                parse_error=error)


def iter_paths(root: Path) -> Iterator[Path]:
    """Every note under `root`, skipping dot-directories (`.librarian`,
    `.evidence`, `.obsidian`, `.git`), which hold machinery, not notes."""
    for path in sorted(root.rglob("*.md")):
        parts = path.relative_to(root).parts
        if any(part.startswith(".") for part in parts):
            continue
        yield path


WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def wikilinks(text: str) -> list[str]:
    return [m.group(1).strip() for m in WIKILINK.finditer(text)]


WIKILINK_INNER = re.compile(r"\[\[([^\]]+)\]\]")


def rewrite_wikilinks(text: str, old_name: str, new_name: str) -> tuple[str, bool]:
    """Every `[[link]]` to `old_name` becomes one to `new_name` instead - by
    its bare name, however deep a path prefix the link carries, since that's
    the only part a rename or move actually changes. `#anchor` and `|alias`
    survive untouched. A link naming some other note is left alone."""
    changed = False

    def replace(m: re.Match) -> str:
        nonlocal changed
        inner = m.group(1)
        target = inner.split("#", 1)[0].split("|", 1)[0]
        rest = inner[len(target):]
        parts = target.strip().split("/")
        if parts[-1].lower() != old_name.lower():
            return m.group(0)
        changed = True
        parts[-1] = new_name
        return f"[[{'/'.join(parts)}{rest}]]"

    return WIKILINK_INNER.sub(replace, text), changed


SAFE_NAME = re.compile(r"[^A-Za-z0-9 &_.,()'+-]")


def safe_name(text: str) -> str:
    """A filename every OS and Obsidian accept."""
    return SAFE_NAME.sub("", str(text)).strip(" .")[:150]
