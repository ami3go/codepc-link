"""BlueZ GATT server for the CodePC Link read-only management service."""

# dbus-next uses D-Bus signature strings as annotations.
# ruff: noqa: F722, F821, UP037

from __future__ import annotations

import asyncio
import logging
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

LOGGER = logging.getLogger(__name__)

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
        LOGGER.debug("gatt.read start uuid=%s offset=%d", self._uuid, offset)
        try:
            status = await collect_status(
                state_dir=self._state_dir,
                cockpit_port=self._cockpit_port,
            )
            payload = serialize_payload(self._payload_builder(status))
            LOGGER.debug(
                "gatt.read payload uuid=%s total_bytes=%d status_errors=%d",
                self._uuid,
                len(payload),
                len(status.get("errors") or []),
            )
        except PayloadTooLargeError as exc:
            LOGGER.warning("gatt.read payload-too-large uuid=%s: %s", self._uuid, exc)
            payload = _error_payload("ble", "PAYLOAD_TOO_LARGE", str(exc))
        except Exception as exc:
            LOGGER.exception("gatt.read failed uuid=%s", self._uuid)
            payload = _error_payload("ble", "STATUS_READ_FAILED", str(exc))

        response = read_from_offset(payload, offset)
        LOGGER.debug(
            "gatt.read complete uuid=%s offset=%d returned_bytes=%d",
            self._uuid,
            offset,
            len(response),
        )
        return response

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
        LOGGER.debug("gatt.object-manager GetManagedObjects requested by BlueZ")
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
        LOGGER.info("ble.advertisement released by BlueZ")


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
        self.stage = "initialized"
        self._bus: MessageBus | None = None
        self._gatt_manager: Any = None
        self._advertising_manager: Any = None
        self._application_registered = False
        self._advertisement_registered = False

    def _set_stage(self, stage: str) -> None:
        self.stage = stage
        LOGGER.debug("server.stage=%s", stage)

    async def start(self) -> None:
        LOGGER.info(
            "ble.server starting adapter=%s name=%r security=%s state_dir=%s cockpit_port=%d",
            self.adapter,
            self.local_name,
            "encrypted-read" if self.secure_reads else "development-read",
            self.state_dir or "default",
            self.cockpit_port,
        )

        try:
            self._set_stage("dbus-connect")
            LOGGER.debug("connecting to system D-Bus")
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            self._bus = bus
            LOGGER.debug("system D-Bus connected")

            self._set_stage("build-gatt-objects")
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
            LOGGER.debug(
                "GATT objects built service_uuid=%s system_info_uuid=%s network_status_uuid=%s",
                MANAGEMENT_SERVICE_UUID,
                SYSTEM_INFO_CHARACTERISTIC_UUID,
                NETWORK_STATUS_CHARACTERISTIC_UUID,
            )

            self._set_stage("export-dbus-objects")
            exports = (
                (APP_PATH, object_manager),
                (SERVICE_PATH, service),
                (SYSTEM_INFO_PATH, system_info),
                (NETWORK_STATUS_PATH, network_status),
                (ADVERTISEMENT_PATH, advertisement),
            )
            for path, interface in exports:
                LOGGER.debug("exporting D-Bus object path=%s", path)
                bus.export(path, interface)
            LOGGER.debug("all D-Bus objects exported")

            adapter_path = f"/org/bluez/{self.adapter}"
            self._set_stage("introspect-adapter")
            LOGGER.debug("introspecting BlueZ adapter path=%s", adapter_path)
            introspection = await bus.introspect("org.bluez", adapter_path)
            proxy = bus.get_proxy_object("org.bluez", adapter_path, introspection)
            LOGGER.debug("BlueZ adapter introspection complete")

            self._set_stage("resolve-managers")
            self._gatt_manager = proxy.get_interface("org.bluez.GattManager1")
            self._advertising_manager = proxy.get_interface(
                "org.bluez.LEAdvertisingManager1"
            )
            LOGGER.debug("GattManager1 and LEAdvertisingManager1 resolved")

            self._set_stage("register-gatt-application")
            LOGGER.debug("registering GATT application path=%s", APP_PATH)
            await self._gatt_manager.call_register_application(APP_PATH, {})
            self._application_registered = True
            LOGGER.info("ble.gatt application registered path=%s", APP_PATH)

            self._set_stage("register-advertisement")
            LOGGER.debug(
                "registering advertisement path=%s name=%r service_uuid=%s",
                ADVERTISEMENT_PATH,
                self.local_name,
                MANAGEMENT_SERVICE_UUID,
            )
            await self._advertising_manager.call_register_advertisement(
                ADVERTISEMENT_PATH,
                {},
            )
            self._advertisement_registered = True
            LOGGER.info("ble.advertisement registered path=%s", ADVERTISEMENT_PATH)

            self._set_stage("ready")
            LOGGER.info(
                "ble.server ready adapter=%s service_uuid=%s",
                self.adapter,
                MANAGEMENT_SERVICE_UUID,
            )
        except Exception:
            failed_stage = self.stage
            LOGGER.exception("ble.server startup failed stage=%s", failed_stage)
            await self.stop(reason="startup-failure")
            self.stage = f"failed:{failed_stage}"
            raise

    async def stop(self, *, reason: str = "shutdown") -> None:
        LOGGER.info("ble.server stopping reason=%s stage=%s", reason, self.stage)

        if self._advertisement_registered and self._advertising_manager is not None:
            self._set_stage("unregister-advertisement")
            LOGGER.debug("unregistering advertisement path=%s", ADVERTISEMENT_PATH)
            try:
                await self._advertising_manager.call_unregister_advertisement(
                    ADVERTISEMENT_PATH
                )
                LOGGER.debug("advertisement unregistered")
            except Exception:
                LOGGER.exception("failed to unregister advertisement")
            finally:
                self._advertisement_registered = False

        if self._application_registered and self._gatt_manager is not None:
            self._set_stage("unregister-gatt-application")
            LOGGER.debug("unregistering GATT application path=%s", APP_PATH)
            try:
                await self._gatt_manager.call_unregister_application(APP_PATH)
                LOGGER.debug("GATT application unregistered")
            except Exception:
                LOGGER.exception("failed to unregister GATT application")
            finally:
                self._application_registered = False

        if self._bus is not None:
            self._set_stage("dbus-disconnect")
            LOGGER.debug("disconnecting system D-Bus")
            self._bus.disconnect()
            self._bus = None

        self._set_stage("stopped")
        LOGGER.info("ble.server stopped")

    async def run_forever(self) -> None:
        await self.start()
        try:
            LOGGER.debug("server event loop waiting for shutdown")
            await asyncio.Event().wait()
        finally:
            await self.stop()
