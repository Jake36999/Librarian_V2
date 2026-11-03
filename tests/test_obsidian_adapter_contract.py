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


def test_shared_popovers_do_not_collide_with_obsidian_host_css() -> None:
    panels = (ROOT / "ui/src/panels.ts").read_text(encoding="utf-8")
    css = (ROOT / "ui/src/style.css").read_text(encoding="utf-8")

    assert 'class: "lib-popover"' in panels
    assert 'class: "popover"' not in panels
    assert 'class: "model-grid"' in panels
    assert 'class: "grid"' not in panels
    assert 'class: `model-card${' in panels
    assert 'class: `card${' not in panels
    assert ".lib-app .lib-popover { display: block;" in css
    assert ".lib-app .model-card { display: block;" in css
    assert "height: auto" in css and "white-space: normal" in css
    assert ".lib-app .popover" not in css


def test_obsidian_opens_full_librarian_in_main_workspace_tab() -> None:
    main = (ROOT / "obsidian/src/main.ts").read_text(encoding="utf-8")

    assert 'getLeaf("tab")' in main
    assert "getRightLeaf" not in main
    assert "leaf.getRoot() === this.app.workspace.rootSplit" in main


def test_write_conflict_ui_says_review_does_not_retry() -> None:
    main = (ROOT / "ui/src/main.ts").read_text(encoding="utf-8")

    assert "Resolving this card records your decision only; it does not retry the blocked write" in main
    assert "Mark reviewed; retry manually" in main
    assert "The blocked write was not retried" in main


def test_obsidian_retry_uses_takeover_only_for_a_typed_stale_lease() -> None:
    core = (ROOT / "obsidian/src/core.ts").read_text(encoding="utf-8")
    main = (ROOT / "obsidian/src/main.ts").read_text(encoding="utf-8")

    assert "export class StaleCoreLease" in core
    assert 'row?.error === "stale_vault_lease"' in core
    stale_parse = core.index('row?.error === "stale_vault_lease"')
    assert core.rfind('child.on("close", (code)', 0, stale_parse) > core.rfind(
        'child.on("exit", (code)', 0, stale_parse
    )
    assert 'if (options.takeover) args.push("--takeover")' in core
    assert "e instanceof StaleCoreLease" in main
    assert "this.render(staleLease)" in main
    assert "ensureCore(takeover = false)" in main
