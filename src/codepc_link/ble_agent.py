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
PAIRING_POLICY_MESSAGE = "Initial pairing must be initiated from the CodePC Cockpit page"


def _rejected(message: str) -> DBusError:
    return DBusError(BLUEZ_REJECTED, message)


class PairingAgent(ServiceInterface):
    """Service-authorization agent that rejects unsolicited first pairing.

    The always-on CodePC Link transport is intentionally not allowed to accept
    a phone's initial pairing request. An administrator must start the first pair
    from the server-side Cockpit page, which uses a short-lived targeted pairing
    agent. Once the device is paired/trusted, this agent may authorize only the
    CodePC Link service UUIDs.
    """

    def __init__(self) -> None:
        super().__init__("org.bluez.Agent1")

    @method()
    def Release(self):
        LOGGER.info("bluetooth.pairing agent released by BlueZ")

    @method()
    def RequestPinCode(self, device: "o") -> "s":
        LOGGER.warning("incoming pairing PIN requested device=%s; rejecting", device)
        raise _rejected(PAIRING_POLICY_MESSAGE)

    @method()
    def DisplayPinCode(self, device: "o", pincode: "s"):
        LOGGER.info("bluetooth.pairing PIN display requested device=%s", device)

    @method()
    def RequestPasskey(self, device: "o") -> "u":
        LOGGER.warning("incoming pairing passkey requested device=%s; rejecting", device)
        raise _rejected(PAIRING_POLICY_MESSAGE)

    @method()
    def DisplayPasskey(self, device: "o", passkey: "u", entered: "q"):
        LOGGER.info(
            "bluetooth.pairing passkey display requested device=%s entered=%d",
            device,
            entered,
        )

    @method()
    def RequestConfirmation(self, device: "o", passkey: "u"):
        LOGGER.warning("incoming pairing confirmation requested device=%s; rejecting", device)
        raise _rejected(PAIRING_POLICY_MESSAGE)

    @method()
    def RequestAuthorization(self, device: "o"):
        LOGGER.warning("incoming pairing authorization requested device=%s; rejecting", device)
        raise _rejected(PAIRING_POLICY_MESSAGE)

    @method()
    def AuthorizeService(self, device: "o", uuid: "s"):
        normalized_uuid = uuid.lower()
        if normalized_uuid not in AUTHORIZED_SERVICE_UUIDS:
            LOGGER.warning(
                "bluetooth service authorization rejected device=%s uuid=%s",
                device,
                uuid,
            )
            raise _rejected("Only CodePC Link services are authorized")

        LOGGER.info(
            "bluetooth service authorization accepted device=%s uuid=%s",
            device,
            uuid,
        )

    @method()
    def Cancel(self):
        LOGGER.info("bluetooth.pairing request canceled by BlueZ")
