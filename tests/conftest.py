from __future__ import annotations

from pathlib import Path

import pytest

from resource_librarian.init import init
from resource_librarian.vault import Vault


@pytest.fixture(autouse=True)
def own_config_dir(tmp_path_factory, monkeypatch):
    """Every test has a config directory of its own: the app keeps the person's model
    choices and shared model profiles there, and a test must neither read nor change
    the owner's real ones. A test that sets its own still wins (it sets it later)."""
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path_factory.mktemp("config")))


@pytest.fixture(autouse=True)
def no_live_search(monkeypatch):
    """Tests never reach a live search engine: a real key in the owner's environment
    (TAVILY_API_KEY was set 2026-09-30) made research rounds call Tavily, so every
    round found something new and the stopping rule could never fire. Nor a paid model:
    the batch's PDF cleanup (P3b) calls DeepInfra whenever its key is in the environment."""
    for name in ("TAVILY_API_KEY", "BRAVE_API_KEY", "APIFY_TOKEN", "DEEPINFRA_API_KEY",
                 "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    """A fresh starter vault."""
    init(tmp_path / "vault", name="Test Vault")
    return Vault(tmp_path / "vault")


def write_note(root: Path, rel: str, frontmatter: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter.strip()}\n---\n\n{body}", encoding="utf-8")
    return path


REPO_FM = """type: source
kind: repository
title: {title}
canonical_url: https://example.org/{slug}
status: active
primary_topic: {topic}
captured_at: 2026-09-25
repo_key: example/{slug}
license_class: {license}
ecosystem: Python
domain_primary: ""
maturity_stage: Active
deployment_target: Local_Only
interface_protocol: CLI
data_locality: Local_First
hardware_footprint: CPU_Only
security_compliance: Uncertified
agent_surface: None"""


def add_source(root: Path, name: str, bottom: str, solves: str = "", *,
               license: str = "Permissive", topic: str = "Unfiled", reading: str = "",
               related: str = "", extra_fm: str = "", kind_folder: str = "repository") -> Path:
    from resource_librarian import notes
    sections = [("Bottom Line", bottom), ("What It Solves", solves or bottom)]
    if reading:
        sections.append(("Reading Notes", reading))
    if related:
        sections.append(("Related", related))
    sections.append(("Evidence", "- fetched"))
    fm = REPO_FM.format(title=name, slug=notes.safe_name(name).replace(" ", "-").lower(),
                        topic=topic, license=license)
    if extra_fm:
        fm += "\n" + extra_fm.strip()
    return write_note(root, f"Sources/{kind_folder}/{name}.md", fm, notes.compose(name, sections))


def blind_answer(payload: dict, teaches: str, quote: str) -> dict:
    """A scripted answer to the blind challenge (`lens_discriminate`): the
    option whose stance is named `teaches` is taught (with `quote`), every
    other option is not. `teaches=""` finds nothing taught."""
    import re
    options = re.findall(r"^([ABCD])\. (.+?) - ", payload["user"], re.M)
    return {"judgements": [{"option": letter, "teaches": bool(teaches) and name == teaches,
                            "quote": quote if teaches and name == teaches else ""}
                           for letter, name in options]}


def pdf_bytes(pages: list[list[str]]) -> bytes:
    """A small text PDF, one list of lines per page (an empty list: a page with no text
    layer, as a scan reads) - so PDF tests need only pypdf, not a PDF-writing library."""
    def text(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    objects = ["<< /Type /Catalog /Pages 2 0 R >>", "",
               "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        ops = "".join(f"({text(line)}) Tj T* " for line in lines)
        stream = f"BT /F1 12 Tf 14 TL 72 760 Td {ops}ET" if lines else ""
        objects.append(f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\n"
                       f"endstream")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources "
                       f"<< /Font << /F1 3 0 R >> >> /Contents {len(objects)} 0 R >>")
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = b"%PDF-1.4\n", []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n" \
        .encode()
    return out
