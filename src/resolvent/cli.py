"""Argparse entry point for GUI, HTTP, direct calculations, and MCP."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from resolvent import __version__
from resolvent.catalog import OPERATIONS, catalog
from resolvent.models import MathError, MathRequest
from resolvent.service import MathService


def json_value(value):
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"Invalid JSON: {exc.msg}") from exc


def parser():
    p = argparse.ArgumentParser(prog="resolvent", description="Local symbolic mathematics workbench")
    p.add_argument("--version", action="version", version=f"Resolvent {__version__}")
    sub = p.add_subparsers(dest="command")
    gui = sub.add_parser("gui", help="Open the native pywebview desktop app (default)")
    gui.add_argument("--gui", choices=["qt", "gtk", "edgechromium", "cocoa"])
    gui.add_argument("--debug", action="store_true", help="Enable webview developer tools")
    gui.add_argument("--timeout", type=float, default=15)
    web = sub.add_parser("serve", help="Run the Quart app on loopback")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--open", action="store_true", help="Open the app in the default browser")
    web.add_argument("--timeout", type=float, default=15)
    calc = sub.add_parser("calc", help="Calculate a mathematical expression")
    calc.add_argument("operation", choices=list(OPERATIONS))
    calc.add_argument("expression", help="Quote the expression to protect it from your shell")
    calc.add_argument("--syntax", choices=["auto", "python", "latex"], default="auto")
    calc.add_argument("--variable", "-v", default="x")
    calc.add_argument("--variables", nargs="+", default=[])
    calc.add_argument(
        "--param",
        "-p",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Repeatable operation parameter. VALUE is JSON when valid, otherwise maths text.",
    )
    calc.add_argument("--assumptions", type=json_value, default={})
    calc.add_argument("--precision", type=int, default=16)
    calc.add_argument("--format", choices=["text", "json", "latex"], default="text")
    calc.add_argument("--timeout", type=float, default=15)
    ops = sub.add_parser("operations", help="List available operations or inspect one")
    ops.add_argument("operation", nargs="?", choices=list(OPERATIONS))
    ops.add_argument("--json", action="store_true")
    ops.add_argument("--category")
    batch = sub.add_parser("batch", help="Calculate a JSON file containing an array of requests")
    batch.add_argument("file", type=Path)
    batch.add_argument("--timeout", type=float, default=15)
    mcp = sub.add_parser("mcp", help="Run an MCP server over stdio")
    mcp.add_argument("--timeout", type=float, default=15)
    return p


def main(argv=None) -> int:
    p = parser()
    args = p.parse_args(argv)
    if hasattr(args, "timeout") and not 0.05 <= args.timeout <= 300:
        p.error("--timeout must be between 0.05 and 300 seconds")
    try:
        if args.command in {None, "gui"}:
            from resolvent.desktop import launch

            launch(
                gui=getattr(args, "gui", None),
                debug=getattr(args, "debug", False),
                timeout=getattr(args, "timeout", 15),
            )
        elif args.command == "serve":
            if not 1 <= args.port <= 65535:
                p.error("--port must be between 1 and 65535")
            from resolvent.desktop import serve_browser

            serve_browser(args.port, timeout=args.timeout, open_browser=args.open)
        elif args.command == "mcp":
            from resolvent.mcp_server import run_mcp

            run_mcp(args.timeout)
        elif args.command == "operations":
            values = [OPERATIONS[args.operation]] if args.operation else catalog()
            if args.category:
                values = [op for op in values if op["category"].casefold() == args.category.casefold()]
            if args.json or args.operation:
                print(json.dumps(values[0] if args.operation else values, indent=2))
            else:
                for op in values:
                    print(f"{op['id']:<22} {op['category']:<16} {op['label']}")
        elif args.command == "calc":
            params = {}
            for arg in args.param:
                if "=" not in arg:
                    p.error("Each --param must be KEY=VALUE")
                key, value = arg.split("=", 1)
                try:
                    params[key] = json.loads(value)
                except json.JSONDecodeError:
                    params[key] = value
            req = MathRequest(
                operation=args.operation,
                expression=args.expression,
                syntax=args.syntax,
                variable=args.variable,
                variables=args.variables,
                parameters=params,
                assumptions=args.assumptions,
                precision=args.precision,
            )
            result = MathService(args.timeout).calculate(req)
            if args.format == "json":
                print(result.model_dump_json(indent=2))
            elif args.format == "latex":
                print(result.latex)
            else:
                print(result.result)
                if result.numeric and result.numeric != result.result:
                    print(f"≈ {result.numeric}")
                for warning in result.warnings:
                    print(f"Note: {warning}", file=sys.stderr)
        elif args.command == "batch":
            payload = json.loads(args.file.read_text())
            if not isinstance(payload, list) or not 1 <= len(payload) <= 100:
                raise MathError("A batch file must contain an array of 1–100 requests.")
            service = MathService(args.timeout)
            results, failed = [], False
            for req in payload:
                try:
                    results.append({"ok": True, "result": service.calculate(req).model_dump()})
                except (MathError, ValidationError) as exc:
                    failed = True
                    results.append(
                        {
                            "ok": False,
                            "error": {"code": getattr(exc, "code", "invalid_request"), "message": str(exc)},
                        }
                    )
            print(json.dumps(results, indent=2))
            return 1 if failed else 0
        return 0
    except KeyboardInterrupt:
        return 130
    except (MathError, ValidationError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        if getattr(args, "format", None) == "json":
            print(json.dumps({"error": {"code": getattr(exc, "code", "error"), "message": str(exc)}}))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
