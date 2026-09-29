"""Adding a capability - an outside MCP server - the way the librarian adds
anything: found, read and assessed as a source first, proposed exactly, and
installed only on a person's word (Co-work Roadmap §4 F2, the
`add_capability` session purpose).

- `capability_candidates` reads the curated list (the library's own
  `About/Recommended MCP Servers.md`). Browsing the open MCP Registry stays
  the person's own act, in Settings; a candidate from anywhere else is a
  repository URL the person gives.
- `capability_propose` records one exact definition and refuses what would
  weaken the trust boundary: an unpinned launcher (the acceptance digest pins
  the command, not the code), a literal secret (secrets are `${ENV}` names),
  an unknown launcher, or a server of a kind the library excludes outright
  (filesystem, shell, memory).
- `capability_install` asks the person, and installs only on yes: written
  to the person's mcp.json, accepted, and enabled in *this* library only
  (F1). A no is a finished outcome, recorded like any decision.
"""
from __future__ import annotations

import re
from typing import Any

from ..registry import Card, Context, tool
from ..rules import Refusal
from .sessions import _ask, _event, _session

LAUNCHERS = {"uvx", "npx", "pipx", "bunx", "pnpx", "node", "python", "python3", "py"}
EXCLUDED = re.compile(r"filesystem|file-system|\bshell\b|terminal|\bmemory\b", re.I)
SECRET_ARG = re.compile(r"^--?[\w-]*(token|key|secret|password|passwd|auth)[\w-]*(=.+)?$", re.I)
NAME = re.compile(r"[a-z0-9][a-z0-9\-_]{0,40}")
CURATED_NOTE = ("About", "Recommended MCP Servers.md")


def _curated(ctx: Context) -> list[dict[str, str]]:
    path = ctx.vault.root.joinpath(*CURATED_NOTE)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0] not in ("Server", "---") and not set(cells[0]) <= {"-"}:
            rows.append({"server": cells[0], "for": cells[1],
                         "command": cells[2].strip("`"), "notes": cells[3]})
    return rows


@tool("capability_candidates", tier="consult", effect="read",
      returns=("curated", "installed"),
      card=Card("The curated outside servers a library can add, and which are already "
                "installed", "an add_capability session's candidate phase",
                "Browsing the open MCP Registry is the person's own act, in Settings - not "
                "yours; any other candidate is a repository URL the person gives"))
def capability_candidates(ctx: Context) -> dict:
    mcp = ctx.extras.get("mcp")
    installed = sorted(mcp.servers()) if mcp is not None else []
    return {"curated": _curated(ctx), "installed": installed}


def _problems(name: str, command: str, args: list[str], env: dict[str, str]) -> list[str]:
    from ..mcp_client import _ENV_REF, _SECRET_VALUE, unpinned
    out = []
    if not NAME.fullmatch(name):
        out.append("name: lower-case letters, digits, hyphens")
    launcher = command.replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe")
    if launcher not in LAUNCHERS:
        out.append(f"{command!r} is not a launcher this session installs "
                   f"({', '.join(sorted(LAUNCHERS))}); a server needing its own install step "
                   f"is added by the person, by hand, in Settings")
    if EXCLUDED.search(" ".join([name, *args])):
        out.append("filesystem, shell and memory servers are excluded outright: the vault's "
                   "own tools already reach files through the broker, and the vault is the memory")
    reason = unpinned({"command": command, "args": args})
    if reason:
        out.append(f"not pinned: {reason}")
    for arg in args:
        if SECRET_ARG.match(arg) or _SECRET_VALUE.match(arg):
            out.append(f"argument {arg[:12]!r}… looks like a secret; pass secrets in env as "
                       f"${{NAME}} references")
    for key, value in env.items():
        if not _ENV_REF.match(str(value)):
            out.append(f"env {key}: a literal value - give the variable's name as ${{{key}}}, "
                       f"never the secret itself")
    return out


@tool("capability_propose", tier="contribute", effect="write",
      returns=("proposed",),
      card=Card("Propose one exact, pinned definition for an outside server",
                "an add_capability session's propose phase, after the candidate was assessed",
                "Refused unless pinned, secrets are ${ENV} names only, the launcher is known, "
                "and the server is not a filesystem/shell/memory kind. Installs nothing"))
def capability_propose(ctx: Context, name: str, command: str, why: str,
                       args: list[str] | None = None, env: dict | None = None) -> dict:
    session = _session(ctx)
    args = [str(a) for a in args or []]
    env = {str(k): str(v) for k, v in (env or {}).items()}
    if not why.strip():
        raise TypeError("why: what this library needs it for, in a sentence")
    problems = _problems(name, command, args, env)
    if problems:
        return {"proposed": False, "problems": problems}
    definition = {"command": command, "args": args, "env": env, "enabled": True}
    _event(ctx, {"type": "capability", "name": name, "definition": definition,
                 "why": why.strip(), "status": "proposed",
                 "candidate": str(session.plan.get("candidate", ""))})
    return {"proposed": name, "definition": definition}


@tool("capability_install", tier="contribute", effect="write",
      returns=("installed",),
      card=Card("Install a proposed outside server - only once the person says yes",
                "an add_capability session's install phase",
                "Asks the person first (their answer, never yours); on yes it is installed, "
                "accepted and enabled in this library only"))
def capability_install(ctx: Context, name: str) -> dict:
    session = _session(ctx)
    proposal = session.capabilities.get(name)
    if proposal is None or proposal.get("status") not in ("proposed",):
        raise TypeError(f"no open proposal {name!r} in this session: capability_propose first")
    confirmed = session.answered("install", name)
    if confirmed is None:
        if any(q["kind"] == "install" and q.get("ref") == name for q in session.open_questions()):
            return {"installed": False, "waiting_for": "the person's answer"}
        d = proposal["definition"]
        return {**_ask(ctx, f"Install the outside server {name!r} ({d['command']} "
                            f"{' '.join(d['args'])}) and enable it in this library? "
                            f"Why: {proposal.get('why', '')}", "install", name, ["yes", "no"]),
                "installed": False}
    if str(confirmed["answer"]).strip().lower() not in ("yes", "y", "install"):
        _event(ctx, {"type": "capability", "name": name, "status": "declined"})
        return {"installed": False, "declined_by_person": True}
    mcp = ctx.extras.get("mcp")
    if mcp is None:
        try:
            from ..keys import config_dir
            from ..mcp_client import McpManager
        except ImportError:
            raise Refusal("PERMISSION_DENIED", "outside servers need the `mcp` extra: "
                                               "pip install resource-librarian[mcp]") from None
        mcp = McpManager(config_dir())
        mcp.use_library(ctx.vault.librarian)
    mcp.set_server(name, proposal["definition"])
    mcp.accept(name)
    mcp.set_library_enabled(name, True)
    status: dict[str, Any] = {}
    if ctx.extras.get("mcp") is not None:
        status = mcp.sync().get(name, {})
    _event(ctx, {"type": "capability", "name": name, "status": "installed"})
    return {"installed": name, "enabled_in": ctx.vault.root.name,
            **({"connected": status.get("connected"), "tools": status.get("tools")}
               if status else {})}
