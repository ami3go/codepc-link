"""NetworkManager-backed network collection and normalization."""

from __future__ import annotations

from typing import Any

from dbus_next import Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType

NM_SERVICE = "org.freedesktop.NetworkManager"
NM_ROOT = "/org/freedesktop/NetworkManager"
NM_IFACE = "org.freedesktop.NetworkManager"
DEVICE_IFACE = "org.freedesktop.NetworkManager.Device"
WIRED_IFACE = "org.freedesktop.NetworkManager.Device.Wired"
WIRELESS_IFACE = "org.freedesktop.NetworkManager.Device.Wireless"
AP_IFACE = "org.freedesktop.NetworkManager.AccessPoint"
IP4_IFACE = "org.freedesktop.NetworkManager.IP4Config"
ACTIVE_IFACE = "org.freedesktop.NetworkManager.Connection.Active"
PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"

NM_CONNECTIVITY_FULL = 4
NM_DEVICE_STATE_ACTIVATED = 100

DEVICE_TYPES = {
    0: "unknown",
    1: "ethernet",
    2: "wifi",
    5: "bluetooth",
    8: "modem",
    9: "infiniband",
    10: "bond",
    11: "vlan",
    13: "bridge",
    14: "generic",
    15: "team",
    16: "tun",
    17: "ip-tunnel",
    18: "macvlan",
    19: "vxlan",
    20: "veth",
    21: "macsec",
    22: "dummy",
    23: "ppp",
    24: "ovs-interface",
    25: "ovs-port",
    26: "ovs-bridge",
    27: "wpan",
    28: "6lowpan",
    29: "wireguard",
    30: "wifi-p2p",
    31: "vrf",
    32: "loopback",
    33: "hsr",
    34: "ipvlan",
    35: "geneve",
}

HIDDEN_NAMES = {"lo", "docker0", "podman0", "virbr0"}
HIDDEN_TYPES = {"loopback", "veth", "tun", "wireguard", "wifi-p2p"}


def _unwrap(value: Any) -> Any:
    if isinstance(value, Variant):
        return _unwrap(value.value)
    if isinstance(value, dict):
        return {key: _unwrap(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_unwrap(item) for item in value]
    return value


def _decode_ssid(value: Any) -> str | None:
    raw = _unwrap(value)
    if raw in (None, [], b""):
        return None
    if isinstance(raw, bytes):
        data = raw
    elif isinstance(raw, list):
        data = bytes(raw)
    else:
        return str(raw)
    return data.decode("utf-8", errors="replace")


def _address_list(ip4_properties: dict[str, Any]) -> list[str]:
    addresses: list[str] = []
    for entry in _unwrap(ip4_properties.get("AddressData", [])):
        if not isinstance(entry, dict):
            continue
        address = entry.get("address")
        prefix = entry.get("prefix")
        if address:
            addresses.append(
                f"{address}/{prefix}" if prefix is not None else str(address)
            )
    return addresses


def _link_state(state: int, carrier: bool | None) -> str:
    if carrier is False:
        return "down"
    if state == NM_DEVICE_STATE_ACTIVATED:
        return "up"
    if 40 <= state < NM_DEVICE_STATE_ACTIVATED:
        return "configuring"
    return "down"


def _should_show(device: dict[str, Any]) -> bool:
    name = str(device.get("name") or "")
    kind = str(device.get("type") or "unknown")
    addresses = device.get("addresses") or []

    if not name or name in HIDDEN_NAMES:
        return False
    if name.startswith("veth"):
        return False
    if kind in HIDDEN_TYPES:
        return False
    if not device.get("managed", True) and not addresses:
        return False
    return True


def normalize_devices(
    raw_devices: list[dict[str, Any]],
    connectivity: int | None,
) -> dict[str, Any]:
    """Normalize NetworkManager snapshots into CodePC Link schema v1."""
    interfaces: list[dict[str, Any]] = []
    internet_available = (
        connectivity == NM_CONNECTIVITY_FULL if connectivity is not None else None
    )

    for raw in raw_devices:
        state = int(raw.get("state") or 0)
        carrier = raw.get("carrier")
        interface = {
            "name": raw.get("name"),
            "type": raw.get("type", "unknown"),
            "managed": bool(raw.get("managed", True)),
            "link": _link_state(
                state,
                carrier if isinstance(carrier, bool) else None,
            ),
            "addresses": list(raw.get("addresses") or []),
            "gateway": raw.get("gateway"),
            "default_route": bool(raw.get("default_route", False)),
            "internet": (
                bool(raw.get("default_route")) and internet_available
                if internet_available is not None
                else None
            ),
        }
        if raw.get("ssid") is not None:
            interface["ssid"] = raw.get("ssid")
        if raw.get("signal") is not None:
            interface["signal"] = raw.get("signal")

        if _should_show(interface):
            interfaces.append(interface)

    priority = {"ethernet": 0, "wifi": 1, "bridge": 2, "bond": 3}
    interfaces.sort(
        key=lambda item: (
            priority.get(str(item["type"]), 9),
            str(item["name"]),
        )
    )
    default_interfaces = [
        item["name"] for item in interfaces if item["default_route"]
    ]

    return {
        "interfaces": interfaces,
        "default_route_interfaces": default_interfaces,
        "internet": internet_available,
    }


async def _get_all(
    bus: MessageBus,
    path: str,
    interface: str,
) -> dict[str, Any]:
    introspection = await bus.introspect(NM_SERVICE, path)
    proxy = bus.get_proxy_object(NM_SERVICE, path, introspection)
    properties = proxy.get_interface(PROPERTIES_IFACE)
    values = await properties.call_get_all(interface)
    return {key: _unwrap(value) for key, value in values.items()}


async def _optional_get_all(
    bus: MessageBus,
    path: str,
    interface: str,
) -> dict[str, Any]:
    try:
        return await _get_all(bus, path, interface)
    except Exception:
        return {}


async def _read_wifi_details(
    bus: MessageBus,
    device_path: str,
) -> tuple[str | None, int | None]:
    wireless = await _optional_get_all(bus, device_path, WIRELESS_IFACE)
    access_point_path = wireless.get("ActiveAccessPoint")
    if not access_point_path or access_point_path == "/":
        return None, None
    access_point = await _optional_get_all(
        bus,
        str(access_point_path),
        AP_IFACE,
    )
    ssid = _decode_ssid(access_point.get("Ssid"))
    signal = access_point.get("Strength")
    return ssid, int(signal) if signal is not None else None


async def _read_device(bus: MessageBus, path: str) -> dict[str, Any]:
    properties = await _get_all(bus, path, DEVICE_IFACE)
    device_type = int(properties.get("DeviceType") or 0)
    kind = DEVICE_TYPES.get(device_type, f"type-{device_type}")
    ip4_path = properties.get("Ip4Config")
    active_path = properties.get("ActiveConnection")

    ip4: dict[str, Any] = {}
    if ip4_path and ip4_path != "/":
        ip4 = await _optional_get_all(bus, str(ip4_path), IP4_IFACE)

    active: dict[str, Any] = {}
    if active_path and active_path != "/":
        active = await _optional_get_all(bus, str(active_path), ACTIVE_IFACE)

    carrier: bool | None = None
    if kind == "ethernet":
        wired = await _optional_get_all(bus, path, WIRED_IFACE)
        if "Carrier" in wired:
            carrier = bool(wired["Carrier"])

    ssid: str | None = None
    signal: int | None = None
    if kind == "wifi":
        ssid, signal = await _read_wifi_details(bus, path)

    return {
        "name": properties.get("Interface"),
        "type": kind,
        "managed": bool(properties.get("Managed", True)),
        "state": int(properties.get("State") or 0),
        "carrier": carrier,
        "addresses": _address_list(ip4),
        "gateway": ip4.get("Gateway") or None,
        "default_route": bool(active.get("Default", False)),
        "ssid": ssid,
        "signal": signal,
    }


async def collect_network_status() -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Collect normalized network status from NetworkManager over D-Bus."""
    errors: list[dict[str, str]] = []
    bus: MessageBus | None = None
    try:
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        introspection = await bus.introspect(NM_SERVICE, NM_ROOT)
        proxy = bus.get_proxy_object(NM_SERVICE, NM_ROOT, introspection)
        manager = proxy.get_interface(NM_IFACE)
        properties = proxy.get_interface(PROPERTIES_IFACE)

        device_paths = await manager.call_get_devices()
        connectivity_variant = await properties.call_get(
            NM_IFACE,
            "Connectivity",
        )
        connectivity = int(_unwrap(connectivity_variant))

        raw_devices: list[dict[str, Any]] = []
        for path in device_paths:
            try:
                raw_devices.append(await _read_device(bus, str(path)))
            except Exception as exc:
                errors.append(
                    {
                        "component": "network",
                        "code": "NM_DEVICE_READ_FAILED",
                        "message": f"{path}: {exc}",
                    }
                )

        return normalize_devices(raw_devices, connectivity), errors
    except Exception as exc:
        errors.append(
            {
                "component": "network",
                "code": "NM_UNAVAILABLE",
                "message": str(exc),
            }
        )
        return normalize_devices([], None), errors
    finally:
        if bus is not None:
            bus.disconnect()
