"""Temporary BLE advertiser used only for Milestone A hardware validation."""

# dbus-next intentionally uses D-Bus signatures in return annotations.
# ruff: noqa: F821, UP037

from __future__ import annotations

import asyncio

from dbus_next.aio import MessageBus
from dbus_next.constants import BusType, PropertyAccess
from dbus_next.service import ServiceInterface, dbus_property, method

from .protocol import MANAGEMENT_SERVICE_UUID

ADVERTISEMENT_PATH = "/org/codepc/link/feasibility_advertisement"
DEFAULT_LOCAL_NAME = "CodePC Link"


class FeasibilityAdvertisement(ServiceInterface):
    """Minimal BlueZ LEAdvertisement1 object for real-device discovery tests."""

    def __init__(self, local_name: str) -> None:
        super().__init__("org.bluez.LEAdvertisement1")
        self._local_name = local_name

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> "s":
        return "peripheral"

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> "as":
        # Match the production/Web Bluetooth discovery contract so Android tools
        # can identify the same service that the PWA filters for.
        return [MANAGEMENT_SERVICE_UUID]

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> "s":
        return self._local_name

    @dbus_property(access=PropertyAccess.READ)
    def Discoverable(self) -> "b":
        # Explicitly request general discoverability for the feasibility probe.
        # This is valid for Type="peripheral" and avoids relying on the adapter's
        # global Discoverable setting.
        return True

    @method()
    def Release(self):
        """BlueZ callback when the advertisement is released."""


async def advertise_for_test(
    adapter: str = "hci0",
    local_name: str = DEFAULT_LOCAL_NAME,
    seconds: float = 0,
) -> None:
    """Register a CodePC Link discovery advertisement until timeout or Ctrl-C."""
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    advertisement = FeasibilityAdvertisement(local_name)
    bus.export(ADVERTISEMENT_PATH, advertisement)

    adapter_path = f"/org/bluez/{adapter}"
    introspection = await bus.introspect("org.bluez", adapter_path)
    proxy = bus.get_proxy_object("org.bluez", adapter_path, introspection)
    manager = proxy.get_interface("org.bluez.LEAdvertisingManager1")

    registered = False
    try:
        await manager.call_register_advertisement(ADVERTISEMENT_PATH, {})
        registered = True
        if seconds > 0:
            await asyncio.sleep(seconds)
        else:
            await asyncio.Event().wait()
    finally:
        if registered:
            await manager.call_unregister_advertisement(ADVERTISEMENT_PATH)
        bus.disconnect()
