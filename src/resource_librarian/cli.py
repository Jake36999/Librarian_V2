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
from pathlib import Path
from typing import Any

from . import tools  # noqa: F401  (registers the tools)
from .init import init
from .registry import REGISTRY, TIERS, Context, _json_type
from .rules import Refusal
from .vault import Vault


def _vault_or_none(path: str | None) -> Vault | None:
    try:
        return Vault.find(path)
    except Refusal:
        return None


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
            return serve_app(args.vault, args.port, open_browser=args.open)
    except Refusal as refusal:
        _emit({"error": "refused", **refusal.to_dict()})
        return 2

    spec = REGISTRY.get(args.tool)
    arguments = {p.name: getattr(args, p.name) for p in spec.parameters()
                 if getattr(args, p.name, None) is not None}
    ctx = Context(tier=args.tier, vault=_vault_or_none(args.vault), session=args.session)
    result = REGISTRY.call(spec.name, arguments, ctx)
    _emit(result)
    return 2 if result.get("error") == "refused" else (1 if "error" in result else 0)


def _emit(payload: Any) -> None:
    json.dump(payload, sys.stdout, indent=1, ensure_ascii=False, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(main())
