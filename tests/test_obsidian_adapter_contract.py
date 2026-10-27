"""Packaged Obsidian discovery follows the Core lifecycle identity contract."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_obsidian_discovery_validates_exact_core_identity_before_using_token() -> None:
    core = (ROOT / "obsidian/src/core.ts").read_text(encoding="utf-8")

    assert "process_start: string" in core
    assert '"host", "status", "--vault", vaultPath' in core
    assert "row.process_start === expected.process_start" in core
    assert "if (!await exactCoreIsRunning" in core
    assert core.index("if (!await exactCoreIsRunning") < core.index(
        "return { url, token: row.token")


def test_obsidian_stop_wait_matches_the_host_shutdown_margin() -> None:
    core = (ROOT / "obsidian/src/core.ts").read_text(encoding="utf-8")
    main = (ROOT / "obsidian/src/main.ts").read_text(encoding="utf-8")

    assert "export const STOP_EXIT_MS = 25_000" in core
    assert "window.setTimeout(() => reject" in main
    assert "STOP_EXIT_MS" in main
    assert "15_000" not in main
