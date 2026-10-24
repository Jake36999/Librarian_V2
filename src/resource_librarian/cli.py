"""The command line: `init`, `mcp` and `app`, plus one subcommand per registered tool.

Tool subcommands are generated from the registry, so the CLI can never offer
less than the MCP server or the chat (V1's research pass left the MCP surface
because the CLI reached further). Output is JSON by default, because the CLI is
as much an agent's surface as a person's; `--text` gives a readable summary for
the commands that have one.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import tools  # noqa: F401  (registers the tools)
from .coordination import LeaseHeldError, VaultCoordinator, VaultWriter
from .index import IndexService
from . import connection, process_identity
from .checkpoints import CheckpointStore
from .init import init
from .registry import REGISTRY, TIERS, Context, _json_type
from .rules import Refusal
from .vault import Vault


def _vault_or_none(path: str | None) -> Vault | None:
    try:
        return Vault.find(path)
    except Refusal:
        return None


def _call_active_core(vault: Vault, tool: str, arguments: dict[str, Any],
                      session: str | None = None) -> tuple[bool, dict[str, Any]]:
    """Route a CLI action through the active Core when it published one.

    The vault lease contains diagnostic information only, so it cannot safely
    be used as a connection channel.  The per-user connection record is
    owner-protected and still gets the normal loopback/token checks here.  A
    record that exists but cannot be contacted is deliberately *not* a reason
    to fall back to a direct writer: doing that would reintroduce the exact
    two-writer race the coordinator prevents.
    """
    record = connection.load(vault.root)
    if record is None:
        return False, {}
    pid = int(record.get("pid") or 0)
    if not process_identity.is_alive(pid, record.get("process_start")):
        # Only remove the exact record we just found; a new Core cannot lose
        # its discovery data in the tiny race between this check and cleanup.
        connection.remove(vault.root, pid=pid, token=str(record.get("token") or ""))
        return False, {}
    url = str(record.get("url") or "").rstrip("/")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "::1", "localhost"):
        return True, {"error": "active_core_unavailable",
                      "detail": "the protected active-Core record is not a loopback URL; refusing to proxy"}
    endpoint = url + "/api/tool/" + urllib.parse.quote(tool, safe="")
    payload = json.dumps({"arguments": arguments, "session": session or ""}).encode("utf-8")
    request = urllib.request.Request(endpoint, data=payload, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "X-Librarian-Token": str(record.get("token") or ""),
                                              "Origin": url})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            data = {"error": "active_core_error", "detail": str(exc)}
    except (OSError, ValueError) as exc:
        data = {"error": "active_core_unavailable",
                "detail": f"could not reach the recorded active Core: {exc}"}
    return True, data if isinstance(data, dict) else {"result": data}


def _add_tool_parsers(sub: argparse._SubParsersAction) -> None:
    for spec in sorted(REGISTRY.for_tier("curate"), key=lambda s: s.name):
        p = sub.add_parser(spec.name, help=spec.card.purpose,
                           description=spec.description())
        hints = spec.hints()
        for param in spec.parameters():
            schema = _json_type(hints.get(param.name, str))
            required = param.default is param.empty
            flag = f"--{param.name.replace('_', '-')}"
            if schema["type"] == "boolean":
                p.add_argument(flag, dest=param.name, action="store_true")
            elif schema["type"] == "array":
                p.add_argument(flag, dest=param.name, nargs="*", required=required)
            elif schema["type"] == "object":
                p.add_argument(flag, dest=param.name, type=json.loads, required=required,
                               help="JSON object")
            else:
                p.add_argument(flag, dest=param.name, required=required,
                               choices=schema.get("enum"))
        p.set_defaults(tool=spec.name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resource-librarian",
        description="Librarian V2: a research library for a vault of sources someone "
                    "has actually read.")
    parser.add_argument("--vault", help="the vault to use (default: the one containing "
                                        "the current directory)")
    parser.add_argument("--session", help="run the tool inside this session (its phase "
                                          "gates writes and its envelope comes back)")
    parser.add_argument("--tier", default="curate", choices=TIERS,
                        help="the tier to run tools at (default: curate, a person at "
                             "their own terminal)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create a vault in a folder")
    p.add_argument("folder")
    p.add_argument("--name", default="")
    p.add_argument("--profile", default="",
                   help="specialise the new library for its domain: a standard profile "
                        "(software-systems, course, history) or a profile file")

    p = sub.add_parser("mcp", help="serve the tools over MCP on stdio (needs the `mcp` extra)")
    p.add_argument("--tier", dest="mcp_tier", default="consult", choices=TIERS,
                   help="the tier every client of this server runs at (default: consult, "
                        "a Reader; the Cowork plugin launches at contribute)")

    p = sub.add_parser("app", help="serve the interface and its local API on 127.0.0.1")
    p.add_argument("--port", type=int, default=8323, help="0 picks a free port")
    p.add_argument("--open", action="store_true", help="open it in the browser")
    p.add_argument("--pick", action="store_true",
                   help="start at the library picker, whatever library is near (the "
                        "desktop shortcut's way in)")
    p.add_argument("--takeover", action="store_true",
                   help="explicitly replace stale diagnostic lease metadata after verifying its Core stopped")

    p = sub.add_parser("host", help="explicitly manage the per-user Librarian Host Core")
    p.add_argument("action", choices=("start", "status", "doctor", "restart", "stop", "quit"))
    p.add_argument("--vault", dest="host_vault", default="", help="vault for start/restart")
    p.add_argument("--open", action="store_true", help="open the Core after starting it")
    p.add_argument("--force", action="store_true",
                   help="explicitly Quit despite active Core work (never implied by closing a client)")

    _add_tool_parsers(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            try:
                report = init(args.folder, args.name, args.profile)
            except ValueError as exc:                    # a profile that won't parse or load
                _emit({"error": "profile", "detail": str(exc)})
                return 1
            _emit(report.to_dict())
            return 0
        if args.command == "mcp":
            try:
                from .mcp_server import serve
            except ImportError as exc:
                print(f"the MCP server needs the `mcp` extra: pip install "
                      f"'resource-librarian[mcp]' ({exc})", file=sys.stderr)
                return 1
            return serve(args.vault, args.mcp_tier)
        if args.command == "app":
            from .app import serve as serve_app
            if args.pick:
                from .library_picker import serve_picker
                return serve_picker(args.port, args.open)
            return serve_app(args.vault, args.port, open_browser=args.open, takeover=args.takeover)
        if args.command == "host":
            from .host import HostManager
            manager = HostManager()
            try:
                if args.action == "status":
                    _emit(manager.status())
                elif args.action == "doctor":
                    from . import doctor
                    state = manager.status()
                    _emit({"host": state, "doctor": [check.to_dict() for check in doctor.checks()]})
                elif args.action == "start":
                    _emit(manager.start(args.host_vault or args.vault or str(Path.cwd()), open_browser=args.open))
                elif args.action == "restart":
                    _emit(manager.restart(args.host_vault or args.vault, open_browser=args.open))
                else:  # stop/quit are both explicit lifecycle actions for this small companion
                    _emit(manager.stop(args.host_vault or args.vault or "", force=bool(args.force)))
                return 0
            except (RuntimeError, ValueError) as exc:
                _emit({"error": "host", "detail": str(exc)})
                return 1
    except Refusal as refusal:
        _emit({"error": "refused", **refusal.to_dict()})
        return 2

    spec = REGISTRY.get(args.tool)
    arguments = {p.name: getattr(args, p.name) for p in spec.parameters()
                 if getattr(args, p.name, None) is not None}
    vault = _vault_or_none(args.vault)
    # A terminal command is an explicit person action.  This matters for the
    # deliberately person-only controls such as selecting a ranking policy or
    # starting a source workbench engagement; an agent/MCP call cannot claim
    # that authority merely by requesting the curate tier.
    ctx = Context(tier=args.tier, vault=vault, session=args.session,
                  extras={"caller": "cli", "caller_kind": "person"})
    if vault is not None:
        proxied, result = _call_active_core(vault, spec.name, arguments, args.session)
        if proxied:
            _emit(result)
            return 2 if result.get("error") == "refused" else (1 if "error" in result else 0)
    coordinator = None
    writer = None
    index_service = None
    if vault is not None:
        # A direct CLI invocation is a short-lived Core authority.  It takes
        # the same lease even for index-backed reads, so it never opens the
        # vault SQLite file beside an undiscoverable mutable Core.  If an
        # active Core published its protected connection record, the earlier
        # proxy path is used instead.
        coordinator = VaultCoordinator(vault)
        try:
            coordinator.acquire()
            index_service = IndexService(vault)
            ctx.extras["index_service"] = index_service
            ctx.extras["checkpoints"] = CheckpointStore(vault)
            if spec.effect != "read":
                writer = VaultWriter(vault)
                ctx.extras["vault_writer"] = writer
        except LeaseHeldError as exc:
            # A Core can exist while its discovery record is unavailable (for
            # example because a user profile ACL could not be protected).
            # Refuse rather than writing beside it.
            _emit({"error": "vault_in_use", "detail": str(exc),
                   "next": "use the active Core or stop it before a direct write"})
            return 2
        except Exception:
            # Setup failed before the normal call/finally below was entered.
            # Do not leave a diagnostic lease behind merely because SQLite or
            # a local config path could not initialise.
            coordinator.release()
            raise
    try:
        result = REGISTRY.call(spec.name, arguments, ctx)
    finally:
        if writer is not None:
            writer.close()
        if index_service is not None:
            index_service.close()
        if coordinator is not None:
            coordinator.release()
    _emit(result)
    return 2 if result.get("error") == "refused" else (1 if "error" in result else 0)


def _emit(payload: Any) -> None:
    json.dump(payload, sys.stdout, indent=1, ensure_ascii=False, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(main())
