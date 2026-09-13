import pytest
from dbus_next import Variant
from dbus_next.errors import DBusError

from codepc_link.bluetooth_control import (
    BLUEZ_REJECTED,
    BluetoothControlError,
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
