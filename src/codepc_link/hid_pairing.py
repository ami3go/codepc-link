"""Server-initiated BlueZ pairing for the Android vendor HID device."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from dbus_next import Variant
from dbus_next.errors import DBusError
from dbus_next.service import ServiceInterface, method

from .bluetooth_control import (
    AGENT_MANAGER_INTERFACE,
    BLUEZ_REJECTED,
    BLUEZ_ROOT,
    DEFAULT_ADAPTER,
    DEFAULT_SCAN_SECONDS,
    DEVICE_INTERFACE,
    PAIR_AGENT_CAPABILITY,
    PAIR_TIMEOUT_SECONDS,
    PAIR_VERIFY_SECONDS,
    BluetoothControlError,
    BluezPairingController,
    _device_record,
)
from .protocol import HID_SERVICE_UUID

# dbus-next uses D-Bus signature strings as annotations.
# ruff: noqa: F722, F821, UP037

LOGGER = logging.getLogger(__name__)

HID_PAIR_AGENT_PATH = "/org/codepc/link/hid_pairing_agent0"


def _rejected(message: str) -> DBusError:
    return DBusError(BLUEZ_REJECTED, message)


class HidPairingAgent(ServiceInterface):
    """Temporary pairing agent restricted to one administrator-selected phone."""

    def __init__(self, target_device: str) -> None:
        super().__init__("org.bluez.Agent1")
        self.target_device = target_device
        self.passkey: int | None = None

    def _check_target(self, device: str) -> None:
        if device != self.target_device:
            raise _rejected("Pairing was not initiated for this device")

    @method()
    def Release(self):
        LOGGER.info("HID pairing agent released")

    @method()
    def RequestPinCode(self, device: "o") -> "s":
        self._check_target(device)
        raise _rejected("Legacy PIN pairing is not supported")

    @method()
    def DisplayPinCode(self, device: "o", pincode: "s"):
        self._check_target(device)
        LOGGER.info("pairing PIN displayed for device=%s", device)

    @method()
    def RequestPasskey(self, device: "o") -> "u":
        self._check_target(device)
        raise _rejected("Passkey entry on CodePC is not supported")

    @method()
    def DisplayPasskey(self, device: "o", passkey: "u", entered: "q"):
        self._check_target(device)
        self.passkey = int(passkey)
        LOGGER.info(
            "pairing passkey device=%s passkey=%06d entered=%d",
            device,
            passkey,
            entered,
        )

    @method()
    def RequestConfirmation(self, device: "o", passkey: "u"):
        self._check_target(device)
        self.passkey = int(passkey)
        LOGGER.info(
            "pairing confirmation accepted for selected phone=%s passkey=%06d",
            device,
            passkey,
        )

    @method()
    def RequestAuthorization(self, device: "o"):
        self._check_target(device)

    @method()
    def AuthorizeService(self, device: "o", uuid: "s"):
        self._check_target(device)
        if uuid.lower() != HID_SERVICE_UUID.lower():
            raise _rejected("Only the CodePC Link HID service is authorized")

    @method()
    def Cancel(self):
        LOGGER.info("HID pairing request canceled")


class HidPairingController(BluezPairingController):
    """Pair one discoverable Android phone while keeping general pairing closed."""

    async def pair(self, address: str) -> dict[str, object]:
        await self._prepare_adapter()
        path = await self._find_device_path(address)
        objects = await self._managed_objects()
        current = _device_record(path, objects[path][DEVICE_INTERFACE])

        if current["paired"]:
            await self._set_device_property(path, "Trusted", Variant("b", True))
            refreshed = await self._managed_objects()
            return {
                "ok": True,
                "policy": "server-initiated-first-pair",
                "transport": "hid",
                "device": _device_record(path, refreshed[path][DEVICE_INTERFACE]),
                "passkey": None,
            }

        if self.bus is None:
            raise BluetoothControlError("BlueZ controller is not connected")

        agent = HidPairingAgent(path)
        self.bus.export(HID_PAIR_AGENT_PATH, agent)
        agent_manager = await self._proxy_interface(BLUEZ_ROOT, AGENT_MANAGER_INTERFACE)
        await agent_manager.call_register_agent(HID_PAIR_AGENT_PATH, PAIR_AGENT_CAPABILITY)

        adapter = await self._adapter_properties()
        restore_pairable = bool(adapter["pairable"])

        try:
            if not restore_pairable:
                await self._set_adapter_property("Pairable", Variant("b", True))

            device = await self._proxy_interface(path, DEVICE_INTERFACE)
            try:
                await asyncio.wait_for(device.call_pair(), timeout=PAIR_TIMEOUT_SECONDS)
            except TimeoutError as exc:
                raise BluetoothControlError("Bluetooth HID pairing timed out") from exc
            except DBusError as exc:
                raise BluetoothControlError(f"Bluetooth HID pairing failed: {exc}") from exc

            await self._set_device_property(path, "Trusted", Variant("b", True))
            await asyncio.sleep(PAIR_VERIFY_SECONDS)

            refreshed = await self._managed_objects()
            record = _device_record(path, refreshed[path][DEVICE_INTERFACE])
            if not record["paired"] or not record["bonded"]:
                raise BluetoothControlError(
                    "Bluetooth pairing completed but the bond did not persist; "
                    "keep the CodePC Link HID app open and the phone discoverable, then retry"
                )
            return {
                "ok": True,
                "policy": "server-initiated-first-pair",
                "transport": "hid",
                "device": record,
                "passkey": agent.passkey,
            }
        finally:
            try:
                await agent_manager.call_unregister_agent(HID_PAIR_AGENT_PATH)
            except DBusError:
                LOGGER.debug("unable to unregister temporary HID pairing agent", exc_info=True)
            if not restore_pairable:
                try:
                    await self._set_adapter_property("Pairable", Variant("b", False))
                except DBusError:
                    LOGGER.warning("unable to restore non-pairable adapter state", exc_info=True)


async def _run_action(args: argparse.Namespace) -> dict[str, object]:
    controller = HidPairingController(adapter=args.adapter)
    await controller.connect()
    try:
        if args.action == "devices":
            result = await controller.list_devices()
        elif args.action == "scan":
            result = await controller.scan(args.seconds)
        elif args.action == "pair":
            result = await controller.pair(args.address)
        elif args.action == "remove":
            result = await controller.remove(args.address)
        else:
            raise BluetoothControlError(f"unsupported action: {args.action}")
        result["transport"] = "hid"
        return result
    finally:
        controller.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codepc-link-hid-bt",
        description="Server-side Bluetooth pairing for the CodePC Link Android HID device",
    )
    parser.add_argument("--adapter", default=DEFAULT_ADAPTER)
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("devices")

    scan = subparsers.add_parser("scan")
    scan.add_argument("--seconds", type=float, default=DEFAULT_SCAN_SECONDS)

    pair = subparsers.add_parser("pair")
    pair.add_argument("address")

    remove = subparsers.add_parser("remove")
    remove.add_argument("address")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        payload = asyncio.run(_run_action(args))
    except BluetoothControlError as exc:
        payload = {"ok": False, "error": {"message": str(exc)}, "transport": "hid"}
        print(json.dumps(payload, sort_keys=True))
        return 1
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
