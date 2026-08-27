"""BlueZ pairing agent for the CodePC Link encrypted GATT service."""

# dbus-next uses D-Bus signature strings as annotations.
# ruff: noqa: F722, F821, UP037

from __future__ import annotations

import logging

from dbus_next.errors import DBusError
from dbus_next.service import ServiceInterface, method

from .protocol import MANAGEMENT_SERVICE_UUID

LOGGER = logging.getLogger(__name__)

AGENT_PATH = "/org/codepc/link/agent0"
AGENT_CAPABILITY = "NoInputNoOutput"
BLUEZ_REJECTED = "org.bluez.Error.Rejected"


def _rejected(message: str) -> DBusError:
    return DBusError(BLUEZ_REJECTED, message)


class PairingAgent(ServiceInterface):
    """Headless Just Works agent for the read-only encrypted BLE service.

    CodePC Link v0.1 exposes read-only status. The agent therefore uses BlueZ's
    NoInputNoOutput capability: incoming Just Works pairing requests are accepted
    so BlueZ can establish an encrypted link for ``encrypt-read`` characteristics.
    Requests that require entering a PIN/passkey are rejected because this agent
    intentionally has no input capability.
    """

    def __init__(self) -> None:
        super().__init__("org.bluez.Agent1")

    @method()
    def Release(self):
        """BlueZ callback after the agent has been unregistered."""
        LOGGER.info("ble.pairing agent released by BlueZ")

    @method()
    def RequestPinCode(self, device: "o") -> "s":
        LOGGER.warning("ble.pairing PIN requested device=%s; rejecting", device)
        raise _rejected("CodePC Link has no PIN input capability")

    @method()
    def DisplayPinCode(self, device: "o", pincode: "s"):
        LOGGER.info("ble.pairing PIN display requested device=%s", device)

    @method()
    def RequestPasskey(self, device: "o") -> "u":
        LOGGER.warning("ble.pairing passkey requested device=%s; rejecting", device)
        raise _rejected("CodePC Link has no passkey input capability")

    @method()
    def DisplayPasskey(self, device: "o", passkey: "u", entered: "q"):
        LOGGER.info(
            "ble.pairing passkey display requested device=%s entered=%d",
            device,
            entered,
        )

    @method()
    def RequestConfirmation(self, device: "o", passkey: "u"):
        LOGGER.info("ble.pairing confirmation accepted device=%s", device)

    @method()
    def RequestAuthorization(self, device: "o"):
        LOGGER.info("ble.pairing Just Works authorization accepted device=%s", device)

    @method()
    def AuthorizeService(self, device: "o", uuid: "s"):
        normalized_uuid = uuid.lower()
        if normalized_uuid != MANAGEMENT_SERVICE_UUID.lower():
            LOGGER.warning(
                "ble.pairing service authorization rejected device=%s uuid=%s",
                device,
                uuid,
            )
            raise _rejected("Only the CodePC Link management service is authorized")

        LOGGER.info(
            "ble.pairing service authorization accepted device=%s uuid=%s",
            device,
            uuid,
        )

    @method()
    def Cancel(self):
        LOGGER.info("ble.pairing request canceled by BlueZ")
