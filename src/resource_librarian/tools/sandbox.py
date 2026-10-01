"""The sandbox's tools (sandbox.py): the agent's run, reading what landed, a person's run."""
from __future__ import annotations

from typing import Literal

from ..registry import Card, Context, tool


@tool("sandbox_run", tier="contribute", effect="write", scope="library",
      returns=("run", "exit_code", "stdout", "stderr", "files"),
      card=Card("Run a Python or shell script you wrote, in an air-gapped container",
                "a question is settled by running code - a calculation, parsing a file, "
                "checking what a snippet does - and the person allows it",
                "No network, no keys, nothing of this machine but the library files you name "
                "in `inputs` (read-only, at /inputs). The only place it can write is its "
                "landing pad (the working folder): read a text file from there with "
                "sandbox_read; nothing that lands is ever run or imported. Asked like any write"))
def sandbox_run(ctx: Context, code: str, language: Literal["python", "shell"] = "python",
                inputs: list[str] | None = None, timeout: int = 60) -> dict:
    from .. import sandbox
    return sandbox.run(ctx.vault, code, language, by="agent", inputs=inputs or [],
                       timeout=max(5, min(int(timeout), 300)))


@tool("sandbox_read", tier="consult", effect="read",
      returns=("run", "name", "text"),
      card=Card("Read a text file a sandbox run left on its landing pad",
                "after sandbox_run, to see what it wrote",
                "Read only: a binary or a large file is a person's to open"))
def sandbox_read(ctx: Context, run: str, name: str) -> dict:
    from .. import sandbox
    return sandbox.read_landed(ctx.vault, run, name)


@tool("sandbox_run_file", tier="curate", effect="write", scope="library",
      returns=("run", "exit_code", "stdout", "stderr", "files"),
      card=Card("Run a script file from the library, in the air-gapped sandbox",
                "a person pressed Run this script in the document pane",
                "A person's action only: a .py or .sh file, never a note or text. The same "
                "container and landing pad as the agent's runs"))
def sandbox_run_file(ctx: Context, path: str) -> dict:
    from .. import sandbox
    from pathlib import Path
    target = ctx.vault.safe_relative(path)
    language = sandbox.SCRIPTS.get(Path(path).suffix.lower())
    if language is None or not target.is_file():
        raise TypeError(f"{path!r} is not a script file (.py or .sh) in the library")
    return sandbox.run(ctx.vault, target.read_text(encoding="utf-8", errors="replace"),
                       language, by="person", label=path)
