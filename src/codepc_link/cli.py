"""Command-line entry point for CodePC Link."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import __version__
from .ble_probe import DEFAULT_LOCAL_NAME, advertise_for_test
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

    advertise = subparsers.add_parser(
        "advertise-test",
        help="Advertise a temporary CodePC Link BLE name for Android discovery testing",
    )
    advertise.add_argument("--adapter", default="hci0", help="BlueZ adapter, default: hci0")
    advertise.add_argument(
        "--name",
        default=DEFAULT_LOCAL_NAME,
        help=f"Temporary BLE local name, default: {DEFAULT_LOCAL_NAME!r}",
    )
    advertise.add_argument(
        "--seconds",
        type=float,
        default=0,
        help="Stop automatically after N seconds; 0 means run until Ctrl-C",
    )
    advertise.set_defaults(handler="advertise-test")

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


def _run_advertise_test(args: argparse.Namespace) -> int:
    if args.seconds < 0:
        print("--seconds must be zero or greater", file=sys.stderr)
        return 2

    print(
        f"Advertising {args.name!r} on {args.adapter}. "
        "Scan from Android; press Ctrl-C to stop."
    )
    try:
        asyncio.run(
            advertise_for_test(
                adapter=args.adapter,
                local_name=args.name,
                seconds=args.seconds,
            )
        )
    except KeyboardInterrupt:
        print("\nAdvertisement stopped.")
        return 0
    except Exception as exc:  # BlueZ/D-Bus failures must be visible during feasibility.
        print(f"Unable to advertise: {exc}", file=sys.stderr)
        return 2
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    handler = getattr(args, "handler", None)
    if handler == "doctor":
        return _run_doctor(args)
    if handler == "advertise-test":
        return _run_advertise_test(args)
    if handler == "status":
        parser.error("status is not implemented yet; see docs/ROADMAP.md")

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
