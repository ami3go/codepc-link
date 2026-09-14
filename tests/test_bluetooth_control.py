import asyncio

import pytest
from dbus_next import Variant
from dbus_next.errors import DBusError

from codepc_link import bluetooth_control
from codepc_link.bluetooth_control import (
    AGENT_MANAGER_INTERFACE,
    BLUEZ_REJECTED,
    DEVICE_INTERFACE,
    BluetoothControlError,
    BluezPairingController,
    ServerInitiatedPairingAgent,
    _device_record,
    normalize_address,
)
from codepc_link.protocol import RFCOMM_SERVICE_UUID


def test_normalize_address() -> None:
    assert normalize_address("aa:bb:cc:dd:ee:ff") == "AA:BB:CC:DD:EE:FF"

    with pytest.raises(BluetoothControlError):
        normalize_address("not-a-mac")


def test_device_record_normalizes_bluez_properties() -> None:
    record = _device_record(
        "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
        {
            "Address": Variant("s", "AA:BB:CC:DD:EE:FF"),
            "AddressType": Variant("s", "public"),
            "Alias": Variant("s", "Pixel"),
            "Paired": Variant("b", True),
            "Trusted": Variant("b", True),
            "Connected": Variant("b", False),
            "Blocked": Variant("b", False),
            "RSSI": Variant("n", -42),
            "UUIDs": Variant("as", [RFCOMM_SERVICE_UUID]),
        },
    )

    assert record["address"] == "AA:BB:CC:DD:EE:FF"
    assert record["name"] == "Pixel"
    assert record["paired"] is True
    assert record["bonded"] is False
    assert record["trusted"] is True
    assert record["rssi"] == -42


def test_server_pairing_agent_only_accepts_selected_device() -> None:
    target = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"
    other = "/org/bluez/hci0/dev_11_22_33_44_55_66"
    agent = ServerInitiatedPairingAgent(target)

    assert agent.RequestConfirmation(target, 123456) is None
    assert agent.passkey == 123456
    assert agent.AuthorizeService(target, RFCOMM_SERVICE_UUID) is None

    with pytest.raises(DBusError) as rejected:
        agent.RequestAuthorization(other)
    assert rejected.value.type == BLUEZ_REJECTED


def test_server_pairing_agent_rejects_other_services() -> None:
    target = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"
    agent = ServerInitiatedPairingAgent(target)

    with pytest.raises(DBusError) as rejected:
        agent.AuthorizeService(target, "0000110b-0000-1000-8000-00805f9b34fb")
    assert rejected.value.type == BLUEZ_REJECTED


def test_pair_rejects_a_bond_that_does_not_persist(monkeypatch: pytest.MonkeyPatch) -> None:
    path = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"
    controller = BluezPairingController()

    class FakeBus:
        def export(self, _path: str, _agent: object) -> None:
            pass

    class FakeAgentManager:
        async def call_register_agent(self, _path: str, _capability: str) -> None:
            pass

        async def call_unregister_agent(self, _path: str) -> None:
            pass

    class FakeDevice:
        async def call_pair(self) -> None:
            pass

    controller.bus = FakeBus()  # type: ignore[assignment]
    device_properties = {
        "Address": Variant("s", "AA:BB:CC:DD:EE:FF"),
        "Paired": Variant("b", False),
        "Bonded": Variant("b", False),
        "Trusted": Variant("b", True),
    }
    adapter_updates: list[bool] = []

    async def noop(*_args: object, **_kwargs: object) -> None:
        pass

    async def find_device(_address: str) -> str:
        return path

    async def managed_objects():
        return {path: {DEVICE_INTERFACE: device_properties}}

    async def adapter_properties():
        return {"pairable": False}

    async def set_adapter_property(name: str, value: Variant) -> None:
        assert name == "Pairable"
        adapter_updates.append(bool(value.value))

    async def proxy_interface(_path: str, interface: str):
        if interface == AGENT_MANAGER_INTERFACE:
            return FakeAgentManager()
        if interface == DEVICE_INTERFACE:
            return FakeDevice()
        raise AssertionError(interface)

    monkeypatch.setattr(controller, "_prepare_adapter", noop)
    monkeypatch.setattr(controller, "_adapter_properties", adapter_properties)
    monkeypatch.setattr(controller, "_set_adapter_property", set_adapter_property)
    monkeypatch.setattr(controller, "_find_device_path", find_device)
    monkeypatch.setattr(controller, "_managed_objects", managed_objects)
    monkeypatch.setattr(controller, "_set_device_property", noop)
    monkeypatch.setattr(controller, "_proxy_interface", proxy_interface)
    monkeypatch.setattr(bluetooth_control.asyncio, "sleep", noop)

    with pytest.raises(BluetoothControlError, match="bond did not persist"):
        asyncio.run(controller.pair("AA:BB:CC:DD:EE:FF"))

    assert adapter_updates == [True, False]


def test_pair_keeps_adapter_bondable_after_persistent_bond(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"
    controller = BluezPairingController()

    class FakeBus:
        def export(self, _path: str, _agent: object) -> None:
            pass

    class FakeAgentManager:
        async def call_register_agent(self, _path: str, _capability: str) -> None:
            pass

        async def call_unregister_agent(self, _path: str) -> None:
            pass

    class FakeDevice:
        async def call_pair(self) -> None:
            device_properties["Paired"] = Variant("b", True)
            device_properties["Bonded"] = Variant("b", True)

    controller.bus = FakeBus()  # type: ignore[assignment]
    device_properties = {
        "Address": Variant("s", "AA:BB:CC:DD:EE:FF"),
        "Paired": Variant("b", False),
        "Bonded": Variant("b", False),
        "Trusted": Variant("b", False),
    }
    adapter_updates: list[bool] = []

    async def noop(*_args: object, **_kwargs: object) -> None:
        pass

    async def find_device(_address: str) -> str:
        return path

    async def managed_objects():
        return {path: {DEVICE_INTERFACE: device_properties}}

    async def adapter_properties():
        return {"pairable": False}

    async def set_adapter_property(name: str, value: Variant) -> None:
        assert name == "Pairable"
        adapter_updates.append(bool(value.value))

    async def proxy_interface(_path: str, interface: str):
        if interface == AGENT_MANAGER_INTERFACE:
            return FakeAgentManager()
        if interface == DEVICE_INTERFACE:
            return FakeDevice()
        raise AssertionError(interface)

    monkeypatch.setattr(controller, "_prepare_adapter", noop)
    monkeypatch.setattr(controller, "_adapter_properties", adapter_properties)
    monkeypatch.setattr(controller, "_set_adapter_property", set_adapter_property)
    monkeypatch.setattr(controller, "_find_device_path", find_device)
    monkeypatch.setattr(controller, "_managed_objects", managed_objects)
    monkeypatch.setattr(controller, "_set_device_property", noop)
    monkeypatch.setattr(controller, "_proxy_interface", proxy_interface)
    monkeypatch.setattr(bluetooth_control.asyncio, "sleep", noop)

    result = asyncio.run(controller.pair("AA:BB:CC:DD:EE:FF"))

    assert result["device"]["bonded"] is True
    assert adapter_updates == [True]
