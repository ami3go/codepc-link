import pytest
from dbus_next.errors import DBusError

from codepc_link.ble_agent import AGENT_CAPABILITY, BLUEZ_REJECTED, PairingAgent
from codepc_link.protocol import MANAGEMENT_SERVICE_UUID


def test_pairing_agent_uses_headless_capability() -> None:
    assert AGENT_CAPABILITY == "NoInputNoOutput"


def test_pairing_agent_accepts_just_works_authorization() -> None:
    agent = PairingAgent()
    assert agent.RequestAuthorization("/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF") is None
    assert agent.RequestConfirmation(
        "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
        123456,
    ) is None


def test_pairing_agent_rejects_input_requests() -> None:
    agent = PairingAgent()

    with pytest.raises(DBusError) as pin_error:
        agent.RequestPinCode("/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF")
    assert pin_error.value.type == BLUEZ_REJECTED

    with pytest.raises(DBusError) as passkey_error:
        agent.RequestPasskey("/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF")
    assert passkey_error.value.type == BLUEZ_REJECTED


def test_pairing_agent_only_authorizes_management_service() -> None:
    agent = PairingAgent()
    device = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"

    assert agent.AuthorizeService(device, MANAGEMENT_SERVICE_UUID) is None

    with pytest.raises(DBusError) as rejected:
        agent.AuthorizeService(device, "0000110b-0000-1000-8000-00805f9b34fb")
    assert rejected.value.type == BLUEZ_REJECTED
