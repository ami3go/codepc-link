"""BlueZ GATT server for the CodePC Link read-only management service."""

# dbus-next uses D-Bus signature strings as annotations.
# ruff: noqa: F821, UP037

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dbus_next import Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType, PropertyAccess
from dbus_next.service import ServiceInterface, dbus_property, method

from .core import (
    DEFAULT_COCKPIT_PORT,
    collect_status,
    network_status_payload,
    system_info_payload,
)
from .protocol import (
    MANAGEMENT_SERVICE_UUID,
    NETWORK_STATUS_CHARACTERISTIC_UUID,
    READ_FLAGS_DEVELOPMENT,
    READ_FLAGS_SECURE,
    SYSTEM_INFO_CHARACTERISTIC_UUID,
    PayloadTooLargeError,
    read_from_offset,
    serialize_payload,
)

APP_PATH = "/org/codepc/link"
SERVICE_PATH = f"{APP_PATH}/service0"
SYSTEM_INFO_PATH = f"{SERVICE_PATH}/char0"
NETWORK_STATUS_PATH = f"{SERVICE_PATH}/char1"
ADVERTISEMENT_PATH = f"{APP_PATH}/advertisement0"
LOCAL_NAME = "CodePC Link"

PayloadBuilder = Callable[[dict[str, Any]], dict[str, Any]]


def _offset_from_options(options: dict[str, Variant]) -> int:
    value = options.get("offset")
    if value is None:
        return 0
    return int(value.value)


def _error_payload(component: str, code: str, message: str) -> bytes:
    return serialize_payload(
        {
            "errors": [
                {
                    "component": component,
                    "code": code,
                    "message": message,
                }
            ]
        }
    )


class GattService(ServiceInterface):
    """CodePC Link primary GATT service."""

    def __init__(self) -> None:
        super().__init__("org.bluez.GattService1")

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return MANAGEMENT_SERVICE_UUID

    @dbus_property(access=PropertyAccess.READ)
    def Primary(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def Includes(self) -> "ao":
        return []

    @staticmethod
    def managed_properties() -> dict[str, Variant]:
        return {
            "UUID": Variant("s", MANAGEMENT_SERVICE_UUID),
            "Primary": Variant("b", True),
            "Includes": Variant("ao", []),
        }


class StatusCharacteristic(ServiceInterface):
    """Read-only JSON characteristic backed by the shared Management Core."""

    def __init__(
        self,
        uuid: str,
        payload_builder: PayloadBuilder,
        *,
        secure_reads: bool,
        state_dir: Path | None,
        cockpit_port: int,
    ) -> None:
        super().__init__("org.bluez.GattCharacteristic1")
        self._uuid = uuid
        self._payload_builder = payload_builder
        self._flags = READ_FLAGS_SECURE if secure_reads else READ_FLAGS_DEVELOPMENT
        self._state_dir = state_dir
        self._cockpit_port = cockpit_port

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return self._uuid

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> "o":
        return SERVICE_PATH

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> "as":
        return list(self._flags)

    @method()
    async def ReadValue(self, options: "a{sv}") -> "ay":
        offset = _offset_from_options(options)
        try:
            status = await collect_status(
                state_dir=self._state_dir,
                cockpit_port=self._cockpit_port,
            )
            payload = serialize_payload(self._payload_builder(status))
        except PayloadTooLargeError as exc:
            payload = _error_payload("ble", "PAYLOAD_TOO_LARGE", str(exc))
        except Exception as exc:
            payload = _error_payload("ble", "STATUS_READ_FAILED", str(exc))
        return read_from_offset(payload, offset)

    def managed_properties(self) -> dict[str, Variant]:
        return {
            "UUID": Variant("s", self._uuid),
            "Service": Variant("o", SERVICE_PATH),
            "Flags": Variant("as", list(self._flags)),
        }


class ObjectManager(ServiceInterface):
    """BlueZ application object manager for service registration."""

    def __init__(
        self,
        system_info: StatusCharacteristic,
        network_status: StatusCharacteristic,
    ) -> None:
        super().__init__("org.freedesktop.DBus.ObjectManager")
        self._system_info = system_info
        self._network_status = network_status

    @method()
    def GetManagedObjects(self) -> "a{oa{sa{sv}}}":
        return {
            SERVICE_PATH: {
                "org.bluez.GattService1": GattService.managed_properties(),
            },
            SYSTEM_INFO_PATH: {
                "org.bluez.GattCharacteristic1": self._system_info.managed_properties(),
            },
            NETWORK_STATUS_PATH: {
                "org.bluez.GattCharacteristic1": self._network_status.managed_properties(),
            },
        }


class Advertisement(ServiceInterface):
    """Advertisement for the CodePC Link management service."""

    def __init__(self, local_name: str = LOCAL_NAME) -> None:
        super().__init__("org.bluez.LEAdvertisement1")
        self._local_name = local_name

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> "s":
        return "peripheral"

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> "as":
        return [MANAGEMENT_SERVICE_UUID]

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> "s":
        return self._local_name

    @method()
    def Release(self):
        """BlueZ callback when the advertisement is released."""


class CodePCLinkGattServer:
    """Own BlueZ registration and cleanup for the read-only GATT service."""

    def __init__(
        self,
        *,
        adapter: str = "hci0",
        local_name: str = LOCAL_NAME,
        secure_reads: bool = True,
        state_dir: Path | None = None,
        cockpit_port: int = DEFAULT_COCKPIT_PORT,
    ) -> None:
        self.adapter = adapter
        self.local_name = local_name
        self.secure_reads = secure_reads
        self.state_dir = state_dir
        self.cockpit_port = cockpit_port
        self._bus: MessageBus | None = None
        self._gatt_manager: Any = None
        self._advertising_manager: Any = None
        self._application_registered = False
        self._advertisement_registered = False

    async def start(self) -> None:
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        self._bus = bus

        system_info = StatusCharacteristic(
            SYSTEM_INFO_CHARACTERISTIC_UUID,
            system_info_payload,
            secure_reads=self.secure_reads,
            state_dir=self.state_dir,
            cockpit_port=self.cockpit_port,
        )
        network_status = StatusCharacteristic(
            NETWORK_STATUS_CHARACTERISTIC_UUID,
            network_status_payload,
            secure_reads=self.secure_reads,
            state_dir=self.state_dir,
            cockpit_port=self.cockpit_port,
        )
        service = GattService()
        object_manager = ObjectManager(system_info, network_status)
        advertisement = Advertisement(self.local_name)

        bus.export(APP_PATH, object_manager)
        bus.export(SERVICE_PATH, service)
        bus.export(SYSTEM_INFO_PATH, system_info)
        bus.export(NETWORK_STATUS_PATH, network_status)
        bus.export(ADVERTISEMENT_PATH, advertisement)

        adapter_path = f"/org/bluez/{self.adapter}"
        introspection = await bus.introspect("org.bluez", adapter_path)
        proxy = bus.get_proxy_object("org.bluez", adapter_path, introspection)
        self._gatt_manager = proxy.get_interface("org.bluez.GattManager1")
        self._advertising_manager = proxy.get_interface(
            "org.bluez.LEAdvertisingManager1"
        )

        try:
            await self._gatt_manager.call_register_application(APP_PATH, {})
            self._application_registered = True
            await self._advertising_manager.call_register_advertisement(
                ADVERTISEMENT_PATH,
                {},
            )
            self._advertisement_registered = True
        except Exception:
            await self.stop()
            raise

    async def stop(self) -> None:
        if self._advertisement_registered and self._advertising_manager is not None:
            try:
                await self._advertising_manager.call_unregister_advertisement(
                    ADVERTISEMENT_PATH
                )
            finally:
                self._advertisement_registered = False

        if self._application_registered and self._gatt_manager is not None:
            try:
                await self._gatt_manager.call_unregister_application(APP_PATH)
            finally:
                self._application_registered = False

        if self._bus is not None:
            self._bus.disconnect()
            self._bus = None

    async def run_forever(self) -> None:
        await self.start()
        try:
            await asyncio.Event().wait()
        finally:
            await self.stop()
