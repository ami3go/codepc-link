import pytest
from dbus_next.errors import DBusError

from codepc_link.ble_agent import AGENT_CAPABILITY, BLUEZ_REJECTED, PairingAgent
from codepc_link.protocol import MANAGEMENT_SERVICE_UUID, RFCOMM_SERVICE_UUID


def test_pairing_agent_uses_headless_capability() -> None:
    assert AGENT_CAPABILITY == "NoInputNoOutput"


def test_pairing_agent_rejects_incoming_first_pair() -> None:
    agent = PairingAgent()
    device = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"

    with pytest.raises(DBusError) as authorization:
        agent.RequestAuthorization(device)
    assert authorization.value.type == BLUEZ_REJECTED

    with pytest.raises(DBusError) as confirmation:
        agent.RequestConfirmation(device, 123456)
    assert confirmation.value.type == BLUEZ_REJECTED


def test_pairing_agent_rejects_input_requests() -> None:
    agent = PairingAgent()

    with pytest.raises(DBusError) as pin_error:
        agent.RequestPinCode("/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF")
    assert pin_error.value.type == BLUEZ_REJECTED

    with pytest.raises(DBusError) as passkey_error:
        agent.RequestPasskey("/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF")
    assert passkey_error.value.type == BLUEZ_REJECTED


def test_pairing_agent_only_authorizes_codepc_services() -> None:
    agent = PairingAgent()
    device = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"

    assert agent.AuthorizeService(device, MANAGEMENT_SERVICE_UUID) is None
    assert agent.AuthorizeService(device, RFCOMM_SERVICE_UUID) is None

    with pytest.raises(DBusError) as rejected:
        agent.AuthorizeService(device, "0000110b-0000-1000-8000-00805f9b34fb")
    assert rejected.value.type == BLUEZ_REJECTED
