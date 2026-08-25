"""Command-line entry point for the early CodePC Link scaffold."""

from __future__ import annotations

import argparse

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codepc-link",
        description="CodePC Link development CLI",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["status"],
        help="Development placeholder; BLE status is not implemented yet.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "status":
        parser.error("status is not implemented yet; see docs/ROADMAP.md")
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
