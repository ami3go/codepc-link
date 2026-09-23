"""Linux host-side transport for the CodePC Link vendor HID device."""

from __future__ import annotations

import argparse
import asyncio
import errno
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import DEFAULT_COCKPIT_PORT, collect_status
from .hid_protocol import (
    OP_REQUEST_STATUS,
    OP_SET_PUSH_INTERVAL,
    OP_STATUS_JSON,
    HidProtocolError,
    decode_hidraw_input,
    encode_hidraw_output,
    encode_message,
)
from .protocol import SCHEMA_VERSION

LOGGER = logging.getLogger(__name__)

DEFAULT_SYS_HIDRAW = Path("/sys/class/hidraw")
HID_PRODUCT_NAME = "CodePC Link Transport"
DEFAULT_PUSH_INTERVAL = 5.0
MIN_PUSH_INTERVAL = 1
MAX_PUSH_INTERVAL = 3600
RECONNECT_DELAY_SECONDS = 2.0
POLL_SECONDS = 0.10
WRITE_RETRY_SECONDS = 0.02


class HidTransportError(RuntimeError):
    """Raised for host-side HID transport failures."""


@dataclass(frozen=True)
class HidRawDevice:
    path: Path
    name: str
    address: str
    bus: str


def _normalize_address(address: str | None) -> str | None:
    if address is None:
        return None
    return address.strip().replace("-", ":").upper()


def _read_uevent(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    result: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            result[key] = value
    return result


def list_hidraw_devices(sys_class: Path = DEFAULT_SYS_HIDRAW) -> list[HidRawDevice]:
    """Return hidraw devices whose sysfs metadata is currently visible."""
    devices: list[HidRawDevice] = []
    if not sys_class.exists():
        return devices

    for entry in sorted(sys_class.glob("hidraw*")):
        metadata = _read_uevent(entry / "device" / "uevent")
        devices.append(
            HidRawDevice(
                path=Path("/dev") / entry.name,
                name=metadata.get("HID_NAME", ""),
                address=_normalize_address(metadata.get("HID_UNIQ")) or "",
                bus=metadata.get("HID_ID", ""),
            )
        )
    return devices


def find_codepc_hidraw(
    *,
    explicit_device: Path | None = None,
    address: str | None = None,
    sys_class: Path = DEFAULT_SYS_HIDRAW,
) -> HidRawDevice | None:
    """Find the CodePC Link Android HID transport exposed by the kernel."""
    if explicit_device is not None:
        return HidRawDevice(
            path=explicit_device,
            name=HID_PRODUCT_NAME,
            address=_normalize_address(address) or "",
            bus="",
        )

    normalized_address = _normalize_address(address)
    candidates = list_hidraw_devices(sys_class)
    if normalized_address:
        candidates = [item for item in candidates if item.address == normalized_address]
    else:
        candidates = [
            item
            for item in candidates
            if HID_PRODUCT_NAME.casefold() in item.name.casefold()
        ]

    if not candidates:
        return None
    if len(candidates) > 1:
        paths = ", ".join(str(item.path) for item in candidates)
        raise HidTransportError(
            f"multiple CodePC HID transports match ({paths}); pass --device or --address"
        )
    return candidates[0]


def _compact_json(document: dict[str, Any]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


class HidServer:
    """Read requests from hidraw and push status reports back to Android."""

    def __init__(
        self,
        *,
        device: Path | None,
        address: str | None,
        state_dir: Path | None,
        cockpit_port: int,
        push_interval: float,
        sys_class: Path = DEFAULT_SYS_HIDRAW,
    ) -> None:
        self.device = device
        self.address = address
        self.state_dir = state_dir
        self.cockpit_port = cockpit_port
        self.push_interval = push_interval
        self.sys_class = sys_class
        self._sequence = 0

    def _next_sequence(self) -> int:
        value = self._sequence
        self._sequence = (self._sequence + 1) & 0xFF
        return value

    async def _status_document(self) -> bytes:
        status = await collect_status(
            state_dir=self.state_dir,
            cockpit_port=self.cockpit_port,
        )
        return _compact_json(
            {
                "schema": SCHEMA_VERSION,
                "ok": True,
                "op": "status",
                "transport": "hid",
                "status": status,
            }
        )

    async def _write_report(self, fd: int, report: bytes) -> None:
        while True:
            try:
                written = os.write(fd, report)
            except BlockingIOError:
                await asyncio.sleep(WRITE_RETRY_SECONDS)
                continue
            if written != len(report):
                raise HidTransportError(
                    f"short hidraw write: wrote {written} of {len(report)} bytes"
                )
            return

    async def _send_status(self, fd: int) -> None:
        payload = await self._status_document()
        sequence = self._next_sequence()
        frames = encode_message(payload, opcode=OP_STATUS_JSON, sequence=sequence)
        LOGGER.debug(
            "sending HID status sequence=%d bytes=%d frames=%d",
            sequence,
            len(payload),
            len(frames),
        )
        for frame in frames:
            await self._write_report(fd, encode_hidraw_output(frame))

    def _apply_interval_request(self, payload: bytes) -> None:
        if len(payload) != 2:
            raise HidProtocolError("push interval request must contain uint16 seconds")
        seconds = int.from_bytes(payload, "little")
        if seconds != 0 and not MIN_PUSH_INTERVAL <= seconds <= MAX_PUSH_INTERVAL:
            raise HidProtocolError(
                f"push interval must be 0 or {MIN_PUSH_INTERVAL}..{MAX_PUSH_INTERVAL} seconds"
            )
        self.push_interval = float(seconds)
        LOGGER.info("HID status push interval set to %s seconds", seconds)

    async def _handle_report(self, fd: int, report: bytes) -> None:
        frame = decode_hidraw_input(report)
        if frame.chunk_count != 1 or frame.chunk_index != 0:
            raise HidProtocolError("commands must fit in a single HID report")

        if frame.opcode == OP_REQUEST_STATUS:
            await self._send_status(fd)
            return
        if frame.opcode == OP_SET_PUSH_INTERVAL:
            self._apply_interval_request(frame.payload)
            await self._send_status(fd)
            return
        raise HidProtocolError(f"unsupported HID command opcode: 0x{frame.opcode:02x}")

    async def _serve_device(self, hid: HidRawDevice) -> None:
        flags = os.O_RDWR | os.O_NONBLOCK
        try:
            fd = os.open(hid.path, flags)
        except PermissionError as exc:
            raise HidTransportError(
                f"permission denied opening {hid.path}; run the HID service as root "
                "or grant explicit hidraw access"
            ) from exc
        except OSError as exc:
            raise HidTransportError(f"unable to open {hid.path}: {exc}") from exc

        LOGGER.info(
            "HID transport connected path=%s name=%s address=%s",
            hid.path,
            hid.name or "unknown",
            hid.address or "unknown",
        )
        next_push = asyncio.get_running_loop().time()
        try:
            while True:
                while True:
                    try:
                        report = os.read(fd, 256)
                    except BlockingIOError:
                        break
                    except OSError as exc:
                        if exc.errno in {errno.ENODEV, errno.EIO, errno.EPIPE}:
                            return
                        raise
                    if not report:
                        return
                    try:
                        await self._handle_report(fd, report)
                    except HidProtocolError as exc:
                        LOGGER.warning("ignoring malformed HID report: %s", exc)

                now = asyncio.get_running_loop().time()
                if self.push_interval > 0 and now >= next_push:
                    await self._send_status(fd)
                    next_push = now + self.push_interval

                await asyncio.sleep(POLL_SECONDS)
        finally:
            os.close(fd)
            LOGGER.info("HID transport disconnected path=%s", hid.path)

    async def serve_forever(self) -> None:
        while True:
            try:
                hid = find_codepc_hidraw(
                    explicit_device=self.device,
                    address=self.address,
                    sys_class=self.sys_class,
                )
            except HidTransportError as exc:
                LOGGER.error("%s", exc)
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)
                continue

            if hid is None or not hid.path.exists():
                LOGGER.debug("waiting for Android CodePC HID device")
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)
                continue

            try:
                await self._serve_device(hid)
            except (HidTransportError, OSError) as exc:
                LOGGER.warning("HID transport error: %s", exc)
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)


def _device_json(device: HidRawDevice) -> dict[str, str]:
    return {
        "path": str(device.path),
        "name": device.name,
        "address": device.address,
        "bus": device.bus,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codepc-link-hid",
        description="CodePC Link vendor-defined Bluetooth HID host transport",
    )
    parser.add_argument("--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="action", required=True)

    find_parser = subparsers.add_parser("find", help="List visible hidraw devices")
    find_parser.add_argument("--address")

    serve_parser = subparsers.add_parser("serve", help="Serve CodePC status over hidraw")
    serve_parser.add_argument("--device", type=Path)
    serve_parser.add_argument("--address")
    serve_parser.add_argument("--state-dir", type=Path)
    serve_parser.add_argument("--cockpit-port", type=int, default=DEFAULT_COCKPIT_PORT)
    serve_parser.add_argument("--interval", type=float, default=DEFAULT_PUSH_INTERVAL)

    return parser


async def _run(args: argparse.Namespace) -> int:
    if args.action == "find":
        devices = list_hidraw_devices()
        address = _normalize_address(args.address)
        if address:
            devices = [item for item in devices if item.address == address]
        print(json.dumps({"ok": True, "devices": [_device_json(item) for item in devices]}))
        return 0

    if args.interval < 0 or args.interval > MAX_PUSH_INTERVAL:
        raise HidTransportError(
            f"--interval must be between 0 and {MAX_PUSH_INTERVAL} seconds"
        )
    server = HidServer(
        device=args.device,
        address=args.address,
        state_dir=args.state_dir,
        cockpit_port=args.cockpit_port,
        push_interval=args.interval,
    )
    await server.serve_forever()
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130
    except HidTransportError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
