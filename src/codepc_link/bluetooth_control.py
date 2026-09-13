"""Server-initiated BlueZ pairing control for CodePC Link.

This module intentionally keeps first pairing on the CodePC side. The normal
RFCOMM daemon may authorize CodePC Link services, but incoming pairing requests
are rejected by its default agent. Pairing is opened only for the selected
Bluetooth device while an administrator explicitly runs this controller.
"""

# dbus-next uses D-Bus signature strings as annotations.
# ruff: noqa: F722, F821, UP037

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
from typing import Any

from dbus_next import Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType
from dbus_next.errors import DBusError
from dbus_next.service import ServiceInterface, method

from .protocol import RFCOMM_SERVICE_UUID

LOGGER = logging.getLogger(__name__)

BLUEZ_SERVICE = "org.bluez"
BLUEZ_ROOT = "/org/bluez"
OBJECT_MANAGER_PATH = "/"
OBJECT_MANAGER_INTERFACE = "org.freedesktop.DBus.ObjectManager"
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
ADAPTER_INTERFACE = "org.bluez.Adapter1"
DEVICE_INTERFACE = "org.bluez.Device1"
AGENT_MANAGER_INTERFACE = "org.bluez.AgentManager1"
PAIR_AGENT_PATH = "/org/codepc/link/server_pairing_agent0"
PAIR_AGENT_CAPABILITY = "DisplayYesNo"
BLUEZ_REJECTED = "org.bluez.Error.Rejected"
DEFAULT_ADAPTER = "hci0"
DEFAULT_SCAN_SECONDS = 8.0
PAIR_TIMEOUT_SECONDS = 75.0

_ADDRESS_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


class BluetoothControlError(RuntimeError):
    """Raised for user-facing Bluetooth control failures."""


def normalize_address(address: str) -> str:
    value = address.strip().upper()
    if not _ADDRESS_RE.fullmatch(value):
        raise BluetoothControlError(f"invalid Bluetooth address: {address!r}")
    return value


def _value(value: Any) -> Any:
    return value.value if isinstance(value, Variant) else value


def _device_record(path: str, properties: dict[str, Variant]) -> dict[str, Any]:
    uuids = list(_value(properties.get("UUIDs", Variant("as", []))) or [])
    return {
        "path": path,
        "address": str(_value(properties.get("Address", Variant("s", ""))) or ""),
        "address_type": str(
            _value(properties.get("AddressType", Variant("s", "unknown"))) or "unknown"
        ),
        "name": str(
            _value(properties.get("Alias", properties.get("Name", Variant("s", "")))) or ""
        ),
        "paired": bool(_value(properties.get("Paired", Variant("b", False)))),
        "trusted": bool(_value(properties.get("Trusted", Variant("b", False)))),
        "connected": bool(_value(properties.get("Connected", Variant("b", False)))),
        "blocked": bool(_value(properties.get("Blocked", Variant("b", False)))),
        "rssi": _value(properties.get("RSSI")) if "RSSI" in properties else None,
        "uuids": uuids,
    }


def _rejected(message: str) -> DBusError:
    return DBusError(BLUEZ_REJECTED, message)


class ServerInitiatedPairingAgent(ServiceInterface):
    """Temporary agent that authorizes one administrator-selected device only."""

    def __init__(self, target_device: str) -> None:
        super().__init__("org.bluez.Agent1")
        self.target_device = target_device
        self.passkey: int | None = None

    def _check_target(self, device: str) -> None:
        if device != self.target_device:
            LOGGER.warning("pairing rejected for unexpected device=%s", device)
            raise _rejected("Pairing was not initiated for this device")

    @method()
    def Release(self):
        LOGGER.info("server pairing agent released")

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
            "pairing confirmation accepted for server-initiated device=%s passkey=%06d",
            device,
            passkey,
        )

    @method()
    def RequestAuthorization(self, device: "o"):
        self._check_target(device)
        LOGGER.info("pairing authorization accepted device=%s", device)

    @method()
    def AuthorizeService(self, device: "o", uuid: "s"):
        self._check_target(device)
        if uuid.lower() != RFCOMM_SERVICE_UUID.lower():
            raise _rejected("Only the CodePC Link RFCOMM service is authorized")
        LOGGER.info("service authorization accepted device=%s uuid=%s", device, uuid)

    @method()
    def Cancel(self):
        LOGGER.info("server pairing request canceled")


class BluezPairingController:
    """Small BlueZ controller used by the Cockpit pairing page and CLI."""

    def __init__(self, adapter: str = DEFAULT_ADAPTER) -> None:
        self.adapter = adapter
        self.adapter_path = f"/org/bluez/{adapter}"
        self.bus: MessageBus | None = None

    async def connect(self) -> None:
        self.bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    def close(self) -> None:
        if self.bus is not None:
            self.bus.disconnect()
            self.bus = None

    async def _proxy_interface(self, path: str, interface: str):
        if self.bus is None:
            raise BluetoothControlError("BlueZ controller is not connected")
        introspection = await self.bus.introspect(BLUEZ_SERVICE, path)
        proxy = self.bus.get_proxy_object(BLUEZ_SERVICE, path, introspection)
        return proxy.get_interface(interface)

    async def _managed_objects(self) -> dict[str, dict[str, dict[str, Variant]]]:
        manager = await self._proxy_interface(OBJECT_MANAGER_PATH, OBJECT_MANAGER_INTERFACE)
        return await manager.call_get_managed_objects()

    async def _adapter_properties(self) -> dict[str, Any]:
        properties = await self._proxy_interface(self.adapter_path, PROPERTIES_INTERFACE)
        values = await properties.call_get_all(ADAPTER_INTERFACE)
        return {
            "name": self.adapter,
            "path": self.adapter_path,
            "address": str(_value(values.get("Address", Variant("s", ""))) or ""),
            "alias": str(_value(values.get("Alias", Variant("s", ""))) or ""),
            "powered": bool(_value(values.get("Powered", Variant("b", False)))),
            "pairable": bool(_value(values.get("Pairable", Variant("b", False)))),
            "discovering": bool(_value(values.get("Discovering", Variant("b", False)))),
        }

    async def _set_adapter_property(self, name: str, value: Variant) -> None:
        properties = await self._proxy_interface(self.adapter_path, PROPERTIES_INTERFACE)
        await properties.call_set(ADAPTER_INTERFACE, name, value)

    async def _prepare_for_server_pairing(self) -> None:
        adapter = await self._adapter_properties()
        if not adapter["powered"]:
            await self._set_adapter_property("Powered", Variant("b", True))
        # Pairable controls remote-initiated pairing. Keep it disabled because
        # CodePC Link requires the first pair to be initiated from Cockpit.
        if adapter["pairable"]:
            await self._set_adapter_property("Pairable", Variant("b", False))

    async def list_devices(self) -> dict[str, Any]:
        objects = await self._managed_objects()
        devices: list[dict[str, Any]] = []
        prefix = self.adapter_path + "/"
        for path, interfaces in objects.items():
            if not path.startswith(prefix) or DEVICE_INTERFACE not in interfaces:
                continue
            devices.append(_device_record(path, interfaces[DEVICE_INTERFACE]))
        devices.sort(
            key=lambda device: (
                not device["paired"],
                (device["name"] or "").casefold(),
                device["address"],
            )
        )
        return {
            "ok": True,
            "policy": "server-initiated-first-pair",
            "adapter": await self._adapter_properties(),
            "devices": devices,
        }

    async def scan(self, seconds: float = DEFAULT_SCAN_SECONDS) -> dict[str, Any]:
        if seconds <= 0 or seconds > 30:
            raise BluetoothControlError(
                "scan duration must be greater than 0 and at most 30 seconds"
            )
        await self._prepare_for_server_pairing()
        adapter = await self._proxy_interface(self.adapter_path, ADAPTER_INTERFACE)
        try:
            await adapter.call_set_discovery_filter({"Transport": Variant("s", "bredr")})
        except DBusError:
            LOGGER.debug("BlueZ discovery filter unavailable", exc_info=True)

        started = False
        try:
            await adapter.call_start_discovery()
            started = True
        except DBusError as exc:
            if "InProgress" not in str(exc):
                raise BluetoothControlError(f"unable to start Bluetooth scan: {exc}") from exc
        try:
            await asyncio.sleep(seconds)
        finally:
            if started:
                try:
                    await adapter.call_stop_discovery()
                except DBusError:
                    LOGGER.debug("unable to stop BlueZ discovery cleanly", exc_info=True)
        return await self.list_devices()

    async def _find_device_path(self, address: str) -> str:
        target = normalize_address(address)
        objects = await self._managed_objects()
        prefix = self.adapter_path + "/"
        for path, interfaces in objects.items():
            if not path.startswith(prefix) or DEVICE_INTERFACE not in interfaces:
                continue
            candidate = str(_value(interfaces[DEVICE_INTERFACE].get("Address", Variant("s", ""))))
            if candidate.upper() == target:
                return path
        raise BluetoothControlError(
            f"Bluetooth device {target} is not known to BlueZ; "
            "run a scan while the phone is discoverable"
        )

    async def _set_device_property(self, path: str, name: str, value: Variant) -> None:
        properties = await self._proxy_interface(path, PROPERTIES_INTERFACE)
        await properties.call_set(DEVICE_INTERFACE, name, value)

    async def pair(self, address: str) -> dict[str, Any]:
        await self._prepare_for_server_pairing()
        path = await self._find_device_path(address)
        objects = await self._managed_objects()
        current = _device_record(path, objects[path][DEVICE_INTERFACE])
        agent: ServerInitiatedPairingAgent | None = None
        agent_manager = None
        agent_registered = False

        try:
            if not current["paired"]:
                if self.bus is None:
                    raise BluetoothControlError("BlueZ controller is not connected")
                agent = ServerInitiatedPairingAgent(path)
                self.bus.export(PAIR_AGENT_PATH, agent)
                agent_manager = await self._proxy_interface(BLUEZ_ROOT, AGENT_MANAGER_INTERFACE)
                await agent_manager.call_register_agent(PAIR_AGENT_PATH, PAIR_AGENT_CAPABILITY)
                agent_registered = True
                await agent_manager.call_request_default_agent(PAIR_AGENT_PATH)

                device = await self._proxy_interface(path, DEVICE_INTERFACE)
                try:
                    await asyncio.wait_for(device.call_pair(), timeout=PAIR_TIMEOUT_SECONDS)
                except TimeoutError as exc:
                    raise BluetoothControlError("Bluetooth pairing timed out") from exc
                except DBusError as exc:
                    raise BluetoothControlError(f"Bluetooth pairing failed: {exc}") from exc

            await self._set_device_property(path, "Trusted", Variant("b", True))
            refreshed = await self._managed_objects()
            record = _device_record(path, refreshed[path][DEVICE_INTERFACE])
            return {
                "ok": True,
                "policy": "server-initiated-first-pair",
                "device": record,
                "passkey": agent.passkey if agent is not None else None,
            }
        finally:
            if agent_registered and agent_manager is not None:
                try:
                    await agent_manager.call_unregister_agent(PAIR_AGENT_PATH)
                except DBusError:
                    LOGGER.debug("unable to unregister temporary pairing agent", exc_info=True)

    async def remove(self, address: str) -> dict[str, Any]:
        path = await self._find_device_path(address)
        adapter = await self._proxy_interface(self.adapter_path, ADAPTER_INTERFACE)
        try:
            await adapter.call_remove_device(path)
        except DBusError as exc:
            raise BluetoothControlError(f"unable to remove Bluetooth device: {exc}") from exc
        return {
            "ok": True,
            "policy": "server-initiated-first-pair",
            "removed": normalize_address(address),
        }


async def _run_action(args: argparse.Namespace) -> dict[str, Any]:
    controller = BluezPairingController(adapter=args.adapter)
    await controller.connect()
    try:
        if args.action == "devices":
            return await controller.list_devices()
        if args.action == "scan":
            return await controller.scan(args.seconds)
        if args.action == "pair":
            return await controller.pair(args.address)
        if args.action == "remove":
            return await controller.remove(args.address)
        raise BluetoothControlError(f"unsupported action: {args.action}")
    finally:
        controller.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codepc-link-bt",
        description="Server-side Bluetooth pairing control for CodePC Link",
    )
    parser.add_argument("--adapter", default=DEFAULT_ADAPTER, help="BlueZ adapter, default: hci0")
    subparsers = parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("devices", help="List Bluetooth devices known to BlueZ")

    scan = subparsers.add_parser("scan", help="Scan for nearby Bluetooth Classic devices")
    scan.add_argument(
        "--seconds",
        type=float,
        default=DEFAULT_SCAN_SECONDS,
        help=f"Scan duration, default: {DEFAULT_SCAN_SECONDS:g} seconds",
    )

    pair = subparsers.add_parser("pair", help="Pair and trust one device from the CodePC side")
    pair.add_argument("address", help="Bluetooth MAC address")

    remove = subparsers.add_parser("remove", help="Remove one paired/known Bluetooth device")
    remove.add_argument("address", help="Bluetooth MAC address")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        payload = asyncio.run(_run_action(args))
    except (BluetoothControlError, DBusError, OSError) as exc:
        print(
            json.dumps(
                {"ok": False, "error": {"code": "BLUETOOTH_CONTROL_FAILED", "message": str(exc)}},
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
