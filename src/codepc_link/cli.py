"""Command-line entry point for CodePC Link."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .ble_gatt import LOCAL_NAME, CodePCLinkGattServer
from .ble_probe import DEFAULT_LOCAL_NAME, advertise_for_test
from .core import DEFAULT_COCKPIT_PORT, collect_status
from .diagnostics import collect_diagnostics, render_text_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codepc-link",
        description="CodePC Link management and diagnostics CLI",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    status = subparsers.add_parser("status", help="Show normalized CodePC Link status")
    status.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print the complete schema-v1 JSON status",
    )
    status.add_argument(
        "--output",
        type=Path,
        help="Write the complete schema-v1 JSON status to this file",
    )
    status.add_argument(
        "--state-dir",
        type=Path,
        help="Override the persistent state directory (development/testing)",
    )
    status.add_argument(
        "--cockpit-port",
        type=int,
        default=DEFAULT_COCKPIT_PORT,
        help=f"Cockpit port, default: {DEFAULT_COCKPIT_PORT}",
    )
    status.set_defaults(handler="status")

    serve = subparsers.add_parser(
        "serve",
        help="Run the CodePC Link read-only BLE GATT service",
    )
    serve.add_argument("--adapter", default="hci0", help="BlueZ adapter, default: hci0")
    serve.add_argument("--name", default=LOCAL_NAME, help="BLE local name")
    serve.add_argument("--state-dir", type=Path, help="Override persistent state directory")
    serve.add_argument(
        "--cockpit-port",
        type=int,
        default=DEFAULT_COCKPIT_PORT,
        help=f"Cockpit port, default: {DEFAULT_COCKPIT_PORT}",
    )
    serve.add_argument(
        "--insecure-development",
        action="store_true",
        help="Allow unencrypted BLE reads; development only",
    )
    serve.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help=(
            "Show staged BLE/GATT startup and read diagnostics; repeat as -vv "
            "to also enable dbus-next debug logging"
        ),
    )
    serve.set_defaults(handler="serve")

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


def _write_json(payload: dict[str, Any], output: Path | None) -> str:
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output:
        output.write_text(serialized, encoding="utf-8")
    return serialized


def _render_status(status: dict[str, Any]) -> str:
    device = status.get("device", {})
    network = status.get("network", {})
    cockpit = status.get("cockpit", {})
    lines = [
        f"{device.get('name') or 'CodePC Link'}",
        f"Device ID: {device.get('id') or 'unavailable'}",
        f"Hostname: {device.get('hostname') or 'unknown'}",
        "",
        "Network:",
    ]

    interfaces = network.get("interfaces", [])
    if not interfaces:
        lines.append("  No relevant interfaces available")
    for interface in interfaces:
        flags: list[str] = []
        if interface.get("default_route"):
            flags.append("default")
        if interface.get("internet") is True:
            flags.append("internet")
        suffix = f" ({', '.join(flags)})" if flags else ""
        lines.append(
            f"  {interface.get('name')} [{interface.get('type')}] "
            f"{interface.get('link')}{suffix}"
        )
        if interface.get("ssid"):
            lines.append(f"    SSID: {interface['ssid']}")
        addresses = interface.get("addresses") or []
        lines.append(f"    Addresses: {', '.join(addresses) if addresses else 'none'}")

    cockpit_state = cockpit.get("available")
    if cockpit_state is True:
        available = "running"
    elif cockpit_state is False:
        available = "not running"
    else:
        available = "unknown"
    lines.extend(
        [
            "",
            f"Cockpit: {available} on port {cockpit.get('port', DEFAULT_COCKPIT_PORT)}",
        ]
    )

    errors = status.get("errors") or []
    if errors:
        lines.append("")
        lines.append("Warnings:")
        for error in errors:
            lines.append(f"  {error.get('code')}: {error.get('message')}")
    return "\n".join(lines)


def _valid_port(value: int) -> bool:
    return 1 <= value <= 65535


def _configure_serve_logging(verbose: int) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        stream=sys.stderr,
        force=True,
    )
    logging.getLogger("dbus_next").setLevel(
        logging.DEBUG if verbose >= 2 else logging.WARNING
    )


def _run_status(args: argparse.Namespace) -> int:
    if not _valid_port(args.cockpit_port):
        print("--cockpit-port must be between 1 and 65535", file=sys.stderr)
        return 2

    status = asyncio.run(
        collect_status(
            state_dir=args.state_dir,
            cockpit_port=args.cockpit_port,
        )
    )
    serialized = _write_json(status, args.output)
    if args.json_output:
        print(serialized, end="")
    else:
        print(_render_status(status))
        if args.output:
            print(f"\nFull JSON status: {args.output}")
    return 0


def _run_serve(args: argparse.Namespace) -> int:
    if not _valid_port(args.cockpit_port):
        print("--cockpit-port must be between 1 and 65535", file=sys.stderr)
        return 2

    _configure_serve_logging(args.verbose)

    if args.insecure_development:
        print(
            "WARNING: unencrypted BLE reads enabled for development.",
            file=sys.stderr,
        )

    server = CodePCLinkGattServer(
        adapter=args.adapter,
        local_name=args.name,
        secure_reads=not args.insecure_development,
        state_dir=args.state_dir,
        cockpit_port=args.cockpit_port,
    )
    print(
        f"Starting CodePC Link on {args.adapter} as {args.name!r} "
        f"({'encrypted reads' if not args.insecure_development else 'development reads'})."
    )
    if args.verbose:
        print(
            f"Verbose diagnostics enabled (level {args.verbose}); "
            "watch server.stage=... to see startup progress.",
            file=sys.stderr,
        )
    try:
        asyncio.run(server.run_forever())
    except KeyboardInterrupt:
        print("\nCodePC Link stopped.")
        return 0
    except Exception as exc:
        print(
            f"Unable to start CodePC Link at stage {server.stage}: {exc}",
            file=sys.stderr,
        )
        return 2
    return 0


def _run_doctor(args: argparse.Namespace) -> int:
    report = collect_diagnostics()
    serialized = _write_json(report, args.output)

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
    if handler == "status":
        return _run_status(args)
    if handler == "serve":
        return _run_serve(args)
    if handler == "doctor":
        return _run_doctor(args)
    if handler == "advertise-test":
        return _run_advertise_test(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
