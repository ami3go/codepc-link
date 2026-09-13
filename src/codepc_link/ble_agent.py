"""BlueZ pairing agent for CodePC Link Bluetooth transports."""

# dbus-next uses D-Bus signature strings as annotations.
# ruff: noqa: F722, F821, UP037

from __future__ import annotations

import logging

from dbus_next.errors import DBusError
from dbus_next.service import ServiceInterface, method

from .protocol import MANAGEMENT_SERVICE_UUID, RFCOMM_SERVICE_UUID

LOGGER = logging.getLogger(__name__)

AGENT_PATH = "/org/codepc/link/agent0"
AGENT_CAPABILITY = "NoInputNoOutput"
BLUEZ_REJECTED = "org.bluez.Error.Rejected"
AUTHORIZED_SERVICE_UUIDS = {
    MANAGEMENT_SERVICE_UUID.lower(),
    RFCOMM_SERVICE_UUID.lower(),
}


def _rejected(message: str) -> DBusError:
    return DBusError(BLUEZ_REJECTED, message)


class PairingAgent(ServiceInterface):
    """Headless Just Works agent for CodePC Link Bluetooth services.

    CodePC Link currently exposes read-only status. The agent therefore uses
    BlueZ's NoInputNoOutput capability: incoming Just Works pairing requests are
    accepted so BlueZ can establish an authenticated/encrypted transport. Requests
    that require entering a PIN/passkey are rejected because this agent
    intentionally has no input capability.
    """

    def __init__(self) -> None:
        super().__init__("org.bluez.Agent1")

    @method()
    def Release(self):
        """BlueZ callback after the agent has been unregistered."""
        LOGGER.info("bluetooth.pairing agent released by BlueZ")

    @method()
    def RequestPinCode(self, device: "o") -> "s":
        LOGGER.warning("bluetooth.pairing PIN requested device=%s; rejecting", device)
        raise _rejected("CodePC Link has no PIN input capability")

    @method()
    def DisplayPinCode(self, device: "o", pincode: "s"):
        LOGGER.info("bluetooth.pairing PIN display requested device=%s", device)

    @method()
    def RequestPasskey(self, device: "o") -> "u":
        LOGGER.warning("bluetooth.pairing passkey requested device=%s; rejecting", device)
        raise _rejected("CodePC Link has no passkey input capability")

    @method()
    def DisplayPasskey(self, device: "o", passkey: "u", entered: "q"):
        LOGGER.info(
            "bluetooth.pairing passkey display requested device=%s entered=%d",
            device,
            entered,
        )

    @method()
    def RequestConfirmation(self, device: "o", passkey: "u"):
        LOGGER.info("bluetooth.pairing confirmation accepted device=%s", device)

    @method()
    def RequestAuthorization(self, device: "o"):
        LOGGER.info("bluetooth.pairing Just Works authorization accepted device=%s", device)

    @method()
    def AuthorizeService(self, device: "o", uuid: "s"):
        normalized_uuid = uuid.lower()
        if normalized_uuid not in AUTHORIZED_SERVICE_UUIDS:
            LOGGER.warning(
                "bluetooth.pairing service authorization rejected device=%s uuid=%s",
                device,
                uuid,
            )
            raise _rejected("Only CodePC Link services are authorized")

        LOGGER.info(
            "bluetooth.pairing service authorization accepted device=%s uuid=%s",
            device,
            uuid,
        )

    @method()
    def Cancel(self):
        LOGGER.info("bluetooth.pairing request canceled by BlueZ")
