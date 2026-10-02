"""What this install can and cannot do right now.

Every capability that depends on something outside the package reports its
status here, so a session knows what it cannot do before it tries
(`RUN_BEFORE_CLAIM`). Nothing here reads a key's value: a key is reported as
present or absent, never shown.
"""
from __future__ import annotations

import importlib
import importlib.metadata as metadata
import json
import os
import sys
from dataclasses import dataclass
from typing import Any

from . import schema
from .evidence import EvidenceStore
from .vault import Vault

# Confirmed against Obsidian's own community-plugins.json on 2026-09-27 (Co-work
# Roadmap §2, "How delegation works"); id -> display name, as Obsidian's own
# plugin id names each folder under `.obsidian/plugins/`.
RECOMMENDED_PLUGINS = {
    "obsidian-tasks-plugin": "Tasks",
    "calendar": "Calendar",
    "periodic-notes": "Periodic Notes",
    "obsidian-reminder-plugin": "Reminder",
    "obsidian-kanban": "Kanban",
    "dataview": "Dataview",
    "obsidian-spaced-repetition": "Spaced Repetition",
    "obsidian-zotero-desktop-connector": "Zotero Integration",
}

# The key store's name for each (keys.py), so Settings can offer to set one in place.
KEY_PROVIDERS = {"DeepInfra": "deepinfra", "OpenAI": "openai", "Anthropic": "anthropic",
                 "GitHub": "github", "Tavily (web search)": "tavily", "Brave Search": "brave"}

KEY_VARIABLES = {
    "DeepInfra": ("DEEPINFRA_API_KEY", "DEEPINFRA_TOKEN"),
    "OpenAI": ("OPENAI_API_KEY",),
    "Anthropic": ("ANTHROPIC_API_KEY",),
    "GitHub": ("GITHUB_TOKEN",),
    # web_search (websearch.py): either gives the librarian the open web
    "Tavily (web search)": ("TAVILY_API_KEY",),
    "Brave Search": ("BRAVE_API_KEY",),
}


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = False
    key: str = ""                      # a key check: the key store's provider name

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail,
                "required": self.required, **({"key": self.key} if self.key else {})}


def _version(package: str) -> str | None:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def _module(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:                                       # noqa: BLE001
        return False


def _mcp_server_checks(mcp: Any, vault: Vault | None = None) -> list[Check]:
    """One check per configured outside MCP server (Co-work Roadmap §3):
    configured, accepted, and - when a live `McpManager` is passed (a running
    app has one; a bare CLI call doesn't) - actually connected right now.
    Never starts a connection itself: a throwaway manager here only ever
    reads mcp.json/mcp_accepted.json, the same read-only calls the settings
    page's status view makes."""
    try:
        from .keys import config_dir
        from .mcp_client import McpManager, unpinned
    except ImportError:
        return []
    manager = mcp if mcp is not None else McpManager(config_dir())
    if mcp is None and vault is not None:
        manager.use_library(vault.librarian)     # installed for the person, enabled per library
    servers = manager.servers()
    if not servers:
        return []
    live = manager.status() if mcp is not None else {}
    out = []
    for name, definition in servers.items():
        if not definition.get("enabled", True):
            out.append(Check(f"mcp: {name}", True, "disabled"))
        elif not manager.is_accepted(name, definition):
            out.append(Check(f"mcp: {name}", True, "configured, not accepted yet"))
        elif not manager.enabled_here(name):
            out.append(Check(f"mcp: {name}", True, "installed; not enabled in this library"))
        elif mcp is None:
            out.append(Check(f"mcp: {name}", True,
                             "accepted; not running here to confirm it connects"))
        elif live.get(name, {}).get("connected"):
            out.append(Check(f"mcp: {name}", True,
                             f"{live[name].get('tools', 0)} tool(s), connected"))
        else:
            out.append(Check(f"mcp: {name}", False,
                             live.get(name, {}).get("error") or "not connected"))
        if definition.get("enabled", True) and unpinned(definition):
            out.append(Check(f"mcp: {name} version", False, unpinned(definition)))
    return out


def _recommended_plugin_checks(vault: Vault | None) -> list[Check]:
    """Read-only, and vault-scoped (`.obsidian/` lives in the vault, unlike
    mcp.json): which of `About/Recommended Plugins.md`'s plugins Obsidian
    itself has enabled. Absence is the uninteresting default - these are
    always optional - so this reports nothing at all until at least one is
    actually there. Never installs, configures or runs any plugin code."""
    if vault is None:
        return []
    path = vault.root / ".obsidian" / "community-plugins.json"
    if not path.is_file():
        return []
    try:
        enabled = set(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError, TypeError):
        return []
    present = sorted(name for plugin_id, name in RECOMMENDED_PLUGINS.items()
                     if plugin_id in enabled)
    if not present:
        return []
    return [Check("obsidian plugins", True, ", ".join(present))]


def checks(vault: Vault | None = None, mcp: Any = None) -> list[Check]:
    out = [Check("python", sys.version_info >= (3, 11),
                 f"{sys.version.split()[0]} (3.11 or later required)", required=True),
           Check("pyyaml", _module("yaml"), _version("pyyaml") or "not installed", required=True),
           Check("numpy", _module("numpy"), _version("numpy") or "not installed: vector "
                 "search is off")]
    mcp_version = _version("mcp")
    mcp_ok = bool(mcp_version) and mcp_version.split(".")[0] == "2" and _module(
        "mcp.server.mcpserver")
    out.append(Check("mcp server", mcp_ok,
                     f"mcp {mcp_version}" if mcp_ok else
                     f"mcp {mcp_version or 'not installed'}: the MCP surface needs mcp 2.x"))
    out.extend(_mcp_server_checks(mcp, vault))
    out.append(Check("pdf text", _module("pypdf"),
                     f"pypdf {_version('pypdf')}" if _module("pypdf")
                     else "pypdf not installed: PDFs in Inbox/ cannot be read"))
    out.append(Check("embeddings", _module("model2vec"),
                     "model2vec installed" if _module("model2vec")
                     else "model2vec not installed: search is lexical only"))
    for provider, variables in KEY_VARIABLES.items():
        present = next((v for v in variables if os.environ.get(v)), "")
        out.append(Check(f"key: {provider}", bool(present),
                         f"set in {present}" if present else "not set",
                         key=KEY_PROVIDERS.get(provider, "")))
    if vault is None:
        out.append(Check("vault", False, "no vault here: run `init <folder>`"))
        return out
    out.append(Check("vault", vault.exists(), str(vault.root), required=True))
    model = schema.load(vault.root)
    if not model.found:
        out.append(Check("content model", False, "About/Note Content Model.md is missing: "
                         "notes are not checked"))
    else:
        out.append(Check("content model", not model.error, model.error or
                         f"{len(model.shapes)} shapes, {len(model.kinds)} source kinds"))
        # Shapes the app's own tools write: a model from before them indexes what they write
        # with no shape, and no search intent returns it (M0, 2026-10-01: a guide written
        # with write_note was not findable in Librarian-Uni).
        writers = {"note": "write_note", "offering": "promote_offering",
                   "application": "record_application"}
        missing = [s for s in writers if s not in model.shapes]
        if not model.error and model.shapes and missing:
            out.append(Check("content model: shapes", False,
                             f"no {', '.join(missing)} shape: what "
                             f"{', '.join(writers[s] for s in missing)} write is indexed with no "
                             f"shape, so search cannot return it. Copy the rows from the "
                             f"starter Note Content Model's `## Shapes` table"))
        if not model.error and not model.kinds:
            out.append(Check("content model: kinds", False,
                             "no `## Source Kinds` table: nothing can be promoted to Sources/. "
                             "Copy it from the starter Note Content Model"))
        # A deep read files what a text claims under **Claims** and its stated
        # limits under **Evidence & Limits**; a model from before those
        # sections existed silently falls back to Reading Notes.
        headings = {h for h, _ in model.sections_for("source")}
        lacking = [h for h in ("Claims", "Evidence & Limits") if h not in headings]
        if not model.error and model.shapes and lacking:
            out.append(Check("content model: deep-read sections", False,
                             f"source notes have no {' or '.join(lacking)} section, so a deep "
                             f"read files them under Reading Notes. Copy the rows from the "
                             f"starter Note Content Model's `## Sections — source` table"))
        # Repository intake writes code-read access points (§4 D5) into their
        # own section; an older model files them under What Is Inside.
        repo = {h for h, _ in model.sections_for("source", "repository")}
        if not model.error and "repository" in model.kinds and repo \
                and "Access Points" not in repo:
            out.append(Check("content model: access points", False,
                             "repository notes have no Access Points section, so the entry "
                             "points and settings intake reads go under What Is Inside. Copy "
                             "the row from the starter's `## Sections — source/repository`"))
        # A vault made before these tables existed keeps its own model (init
        # never overwrites one), and every check that reads them is then
        # silently skipped - say so, with the fix.
        project_axes = model.axes_for("project")
        missing = [a for a in ("pursuit_kind", "stage") if a not in project_axes]
        if not model.error and missing:
            out.append(Check("content model: pursuits", False,
                             f"no permitted values for {', '.join(missing)}: pursuits are not "
                             f"validated. Copy the `## Axis Values — project` table from the "
                             f"starter Note Content Model"))
    # Clerk routes (roadmap §4 C1): a task sent to another provider waits in
    # the queue if that provider's key is missing - say so before it does.
    from .clerk import PRESETS
    for key, value in (vault.config().get("clerk") or {}).items():
        if not key.startswith("route_") or not str(value).strip():
            continue
        target, _, model = str(value).partition(":")
        preset = PRESETS.get(target)
        needs = (preset or {}).get("key_env", "")
        ok = preset is not None and (not needs or bool(os.environ.get(needs)))
        out.append(Check(f"clerk route: {key[len('route_'):]}", ok,
                         f"{target}{':' + model if model else ''}" if ok else
                         (f"{target!r} is not a clerk provider" if preset is None
                          else f"{target}: {needs} is not set, so these tasks will wait")))
    tampered = EvidenceStore(vault).verify()
    out.append(Check("evidence", not tampered, "every record matches its id" if not tampered
                     else f"{len(tampered)} record(s) were edited after being stored"))
    # Hash-chained records (roadmap §4 B4): a session log or a lens changed
    # after the fact, rather than appended to, shows here.
    from .session import SessionStore
    broken = SessionStore(vault).verify() if SessionStore(vault).folder.exists() else []
    out.append(Check("session records", not broken,
                     "every session log's hash chain holds" if not broken else
                     f"{len(broken)} log(s) edited after being written: " + "; ".join(broken[:3])))
    from .lenses import CONCENTRATION_MIN, LensStore
    record = LensStore(vault).verify()
    lens_ok = not record["chain"] and not record["changed"]
    detail = ("the lens record's chain holds and every lens is as accepted" if lens_ok else
              "; ".join(filter(None, [
                  f"the record's chain breaks at {record['chain']}" if record["chain"] else "",
                  f"changed since acceptance: {', '.join(record['changed'][:5])}"
                  if record["changed"] else ""])))
    if record["unrecorded"]:
        detail += f" ({record['unrecorded']} accepted before the record began)"
    out.append(Check("lens records", lens_ok, detail))
    # Lens concentration (roadmap §4 B3): only said once there are lenses.
    spread = LensStore(vault).concentration()
    if spread["drawn"]:
        top = spread["by_source"][0]
        detail = (f"{spread['drawn']} drawn lens(es) from {spread['sources']} source(s); most "
                  f"from {top['source']} ({top['lenses']}, {spread['top_share']:.0%})")
        if spread["concentrated"]:
            detail += ": more than half from one source - its way of seeing dominates"
        elif spread["drawn"] < CONCENTRATION_MIN:
            detail += f" - too few to judge (under {CONCENTRATION_MIN})"
        out.append(Check("lens concentration", not spread["concentrated"], detail))
    out.extend(_recommended_plugin_checks(vault))
    return out
