from __future__ import annotations

from pathlib import Path

import pytest

from resource_librarian.init import init
from resource_librarian.vault import Vault


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
