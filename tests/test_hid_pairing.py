import pytest
from dbus_next.errors import DBusError

from codepc_link.hid_pairing import BLUEZ_REJECTED, HidPairingAgent
from codepc_link.protocol import HID_SERVICE_UUID, RFCOMM_SERVICE_UUID


def test_hid_pairing_agent_only_accepts_selected_phone() -> None:
    target = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"
    other = "/org/bluez/hci0/dev_11_22_33_44_55_66"
    agent = HidPairingAgent(target)

    assert agent.RequestConfirmation(target, 123456) is None
    assert agent.passkey == 123456
    assert agent.AuthorizeService(target, HID_SERVICE_UUID) is None

    with pytest.raises(DBusError) as rejected:
        agent.RequestAuthorization(other)
    assert rejected.value.type == BLUEZ_REJECTED


def test_hid_pairing_agent_rejects_non_hid_services() -> None:
    target = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"
    agent = HidPairingAgent(target)

    with pytest.raises(DBusError) as rejected:
        agent.AuthorizeService(target, RFCOMM_SERVICE_UUID)
    assert rejected.value.type == BLUEZ_REJECTED
