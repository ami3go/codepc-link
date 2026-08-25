from dbus_next import Variant

from codepc_link.ble_gatt import (
    NETWORK_STATUS_PATH,
    SYSTEM_INFO_PATH,
    GattService,
    ObjectManager,
    StatusCharacteristic,
    _offset_from_options,
)
from codepc_link.core import network_status_payload, system_info_payload
from codepc_link.protocol import (
    NETWORK_STATUS_CHARACTERISTIC_UUID,
    SYSTEM_INFO_CHARACTERISTIC_UUID,
)


def _characteristic(uuid: str, builder, secure: bool) -> StatusCharacteristic:
    return StatusCharacteristic(
        uuid,
        builder,
        secure_reads=secure,
        state_dir=None,
        cockpit_port=9090,
    )


def test_secure_characteristics_use_encrypt_read() -> None:
    characteristic = _characteristic(
        SYSTEM_INFO_CHARACTERISTIC_UUID,
        system_info_payload,
        True,
    )
    assert characteristic.Flags == ["encrypt-read"]


def test_development_characteristics_use_plain_read() -> None:
    characteristic = _characteristic(
        NETWORK_STATUS_CHARACTERISTIC_UUID,
        network_status_payload,
        False,
    )
    assert characteristic.Flags == ["read"]


def test_object_manager_wires_service_and_both_characteristics() -> None:
    system_info = _characteristic(
        SYSTEM_INFO_CHARACTERISTIC_UUID,
        system_info_payload,
        True,
    )
    network_status = _characteristic(
        NETWORK_STATUS_CHARACTERISTIC_UUID,
        network_status_payload,
        True,
    )
    manager = ObjectManager(system_info, network_status)

    assert GattService.managed_properties()["Primary"].value is True
    assert manager._system_info is system_info
    assert manager._network_status is network_status
    assert system_info.managed_properties()["UUID"].value == SYSTEM_INFO_CHARACTERISTIC_UUID
    assert (
        network_status.managed_properties()["UUID"].value
        == NETWORK_STATUS_CHARACTERISTIC_UUID
    )
    assert SYSTEM_INFO_PATH != NETWORK_STATUS_PATH


def test_offset_option_defaults_to_zero() -> None:
    assert _offset_from_options({}) == 0
    assert _offset_from_options({"offset": Variant("q", 7)}) == 7
