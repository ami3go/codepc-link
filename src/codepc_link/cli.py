"""Command-line entry point for CodePC Link."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .diagnostics import collect_diagnostics, render_text_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codepc-link",
        description="CodePC Link management and diagnostics CLI",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    status = subparsers.add_parser("status", help="Show normalized CodePC Link status")
    status.set_defaults(handler="status")

    doctor = subparsers.add_parser(
        "doctor",
        help="Run Milestone A platform and Bluetooth feasibility checks",
    )
    doctor.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print the complete machine-readable report",
    )
    doctor.add_argument(
        "--output",
        type=Path,
        help="Write the complete JSON report to this file",
    )
    doctor.set_defaults(handler="doctor")

    return parser


def _run_doctor(args: argparse.Namespace) -> int:
    report = collect_diagnostics()
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"

    if args.output:
        args.output.write_text(serialized, encoding="utf-8")

    if args.json_output:
        print(serialized, end="")
    else:
        print(render_text_report(report))
        if args.output:
            print(f"\nFull JSON report: {args.output}")

    return 0 if report["result"] == "pass" else 2


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, "handler", None) == "doctor":
        return _run_doctor(args)
    if getattr(args, "handler", None) == "status":
        parser.error("status is not implemented yet; see docs/ROADMAP.md")

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
