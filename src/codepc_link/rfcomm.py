"""BlueZ RFCOMM transport for CodePC Link status requests."""

# dbus-next uses D-Bus signature strings as annotations.
# ruff: noqa: F722, F821, UP037

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from pathlib import Path
from typing import Any

from dbus_next import Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType
from dbus_next.service import ServiceInterface, method

from .ble_agent import AGENT_CAPABILITY, PairingAgent
from .core import DEFAULT_COCKPIT_PORT, collect_status
from .protocol import RFCOMM_SERVICE_UUID, SCHEMA_VERSION

LOGGER = logging.getLogger(__name__)

BLUEZ_ROOT = "/org/bluez"
PROFILE_PATH = "/org/codepc/link/rfcomm/profile0"
AGENT_PATH = "/org/codepc/link/rfcomm/agent0"
PROFILE_NAME = "CodePC Link"
DEFAULT_RFCOMM_CHANNEL = 22
MAX_REQUEST_BYTES = 4096
READ_CHUNK_BYTES = 1024


class RfcommProtocolError(ValueError):
    """A malformed or unsupported RFCOMM request."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def decode_request(line: bytes) -> dict[str, Any]:
    """Decode and validate one newline-delimited RFCOMM JSON request."""
    if len(line) > MAX_REQUEST_BYTES:
        raise RfcommProtocolError(
            "REQUEST_TOO_LARGE",
            f"request is {len(line)} bytes; maximum is {MAX_REQUEST_BYTES}",
        )

    try:
        request = json.loads(line.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise RfcommProtocolError("INVALID_UTF8", "request must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise RfcommProtocolError("INVALID_JSON", "request must be valid JSON") from exc

    if not isinstance(request, dict):
        raise RfcommProtocolError("INVALID_REQUEST", "request must be a JSON object")
    if request.get("schema") != SCHEMA_VERSION:
        raise RfcommProtocolError(
            "UNSUPPORTED_SCHEMA",
            f"request schema must be {SCHEMA_VERSION}",
        )
    if request.get("op") != "status":
        raise RfcommProtocolError("UNSUPPORTED_OPERATION", "supported operation: status")
    return request


def encode_message(payload: dict[str, Any]) -> bytes:
    """Encode one compact newline-delimited RFCOMM JSON message."""
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def error_response(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "ok": False,
        "error": {
            "code": code,
            "message": message,
        },
    }


async def process_request(
    line: bytes,
    *,
    state_dir: Path | None = None,
    cockpit_port: int = DEFAULT_COCKPIT_PORT,
) -> dict[str, Any]:
    """Process one request line using the shared Management Core."""
    try:
        request = decode_request(line)
    except RfcommProtocolError as exc:
        return error_response(exc.code, str(exc))

    if request["op"] == "status":
        try:
            status = await collect_status(
                state_dir=state_dir,
                cockpit_port=cockpit_port,
            )
        except Exception as exc:
            LOGGER.exception("rfcomm.status collection failed")
            return error_response("STATUS_READ_FAILED", str(exc))
        return {
            "schema": SCHEMA_VERSION,
            "ok": True,
            "op": "status",
            "status": status,
        }

    # decode_request keeps this unreachable; retain a defensive transport error.
    return error_response("UNSUPPORTED_OPERATION", "supported operation: status")


class RfcommProfile(ServiceInterface):
    """BlueZ Profile1 object forwarding RFCOMM lifecycle callbacks to the server."""

    def __init__(self, server: "CodePCLinkRfcommServer") -> None:
        super().__init__("org.bluez.Profile1")
        self._server = server

    @method()
    def Release(self):
        LOGGER.warning("rfcomm.profile released by BlueZ")
        self._server.profile_released()

    @method()
    def NewConnection(self, device: "o", fd: "h", fd_properties: "a{sv}"):
        self._server.accept_connection(device, fd, fd_properties)

    @method()
    def RequestDisconnection(self, device: "o"):
        self._server.disconnect_device(device, reason="bluez-request")


class CodePCLinkRfcommServer:
    """Register a secured RFCOMM profile and serve CodePC Link JSON requests."""

    def __init__(
        self,
        *,
        channel: int = DEFAULT_RFCOMM_CHANNEL,
        profile_name: str = PROFILE_NAME,
        require_authentication: bool = True,
        require_authorization: bool = True,
        state_dir: Path | None = None,
        cockpit_port: int = DEFAULT_COCKPIT_PORT,
    ) -> None:
        self.channel = channel
        self.profile_name = profile_name
        self.require_authentication = require_authentication
        self.require_authorization = require_authorization
        self.state_dir = state_dir
        self.cockpit_port = cockpit_port
        self.stage = "initialized"
        self._bus: MessageBus | None = None
        self._profile_manager: Any = None
        self._agent_manager: Any = None
        self._profile_registered = False
        self._agent_registered = False
        self._release_event = asyncio.Event()
        self._connections: dict[str, tuple[socket.socket, asyncio.Task[None]]] = {}

    def _set_stage(self, stage: str) -> None:
        self.stage = stage
        LOGGER.debug("rfcomm.server.stage=%s", stage)

    def profile_options(self) -> dict[str, Variant]:
        """Return the BlueZ RegisterProfile options for the custom RFCOMM service."""
        return {
            "Name": Variant("s", self.profile_name),
            "Service": Variant("s", RFCOMM_SERVICE_UUID),
            "Role": Variant("s", "server"),
            "Channel": Variant("q", self.channel),
            "RequireAuthentication": Variant("b", self.require_authentication),
            "RequireAuthorization": Variant("b", self.require_authorization),
            "AutoConnect": Variant("b", False),
        }

    async def start(self) -> None:
        LOGGER.info(
            "rfcomm.server starting name=%r uuid=%s channel=%d authentication=%s "
            "authorization=%s state_dir=%s cockpit_port=%d",
            self.profile_name,
            RFCOMM_SERVICE_UUID,
            self.channel,
            self.require_authentication,
            self.require_authorization,
            self.state_dir or "default",
            self.cockpit_port,
        )
        try:
            self._set_stage("dbus-connect")
            self._bus = await MessageBus(
                bus_type=BusType.SYSTEM,
                negotiate_unix_fd=True,
            ).connect()

            self._set_stage("build-profile")
            profile = RfcommProfile(self)
            pairing_agent = (
                PairingAgent()
                if self.require_authentication or self.require_authorization
                else None
            )

            self._set_stage("export-dbus-objects")
            self._bus.export(PROFILE_PATH, profile)
            if pairing_agent is not None:
                self._bus.export(AGENT_PATH, pairing_agent)

            self._set_stage("resolve-managers")
            root_introspection = await self._bus.introspect("org.bluez", BLUEZ_ROOT)
            root_proxy = self._bus.get_proxy_object(
                "org.bluez",
                BLUEZ_ROOT,
                root_introspection,
            )
            self._profile_manager = root_proxy.get_interface("org.bluez.ProfileManager1")
            if pairing_agent is not None:
                self._agent_manager = root_proxy.get_interface("org.bluez.AgentManager1")

            if pairing_agent is not None:
                self._set_stage("register-pairing-agent")
                await self._agent_manager.call_register_agent(
                    AGENT_PATH,
                    AGENT_CAPABILITY,
                )
                self._agent_registered = True
                await self._agent_manager.call_request_default_agent(AGENT_PATH)
                LOGGER.info(
                    "rfcomm.pairing agent registered path=%s capability=%s default=true",
                    AGENT_PATH,
                    AGENT_CAPABILITY,
                )

            self._set_stage("register-profile")
            await self._profile_manager.call_register_profile(
                PROFILE_PATH,
                RFCOMM_SERVICE_UUID,
                self.profile_options(),
            )
            self._profile_registered = True

            self._set_stage("ready")
            LOGGER.info(
                "rfcomm.server ready uuid=%s channel=%d",
                RFCOMM_SERVICE_UUID,
                self.channel,
            )
        except Exception:
            failed_stage = self.stage
            LOGGER.exception("rfcomm.server startup failed stage=%s", failed_stage)
            await self.stop(reason="startup-failure")
            self.stage = f"failed:{failed_stage}"
            raise

    def accept_connection(
        self,
        device: str,
        fd: int,
        fd_properties: dict[str, Variant],
    ) -> None:
        """Take ownership of a BlueZ RFCOMM fd and start a request loop."""
        LOGGER.info(
            "rfcomm.connection accepted device=%s properties=%s",
            device,
            sorted(fd_properties),
        )
        self.disconnect_device(device, reason="replace-existing")
        try:
            connection = socket.socket(fileno=fd)
            connection.setblocking(False)
        except Exception:
            os.close(fd)
            raise

        task = asyncio.create_task(
            self._serve_connection(device, connection),
            name=f"codepc-link-rfcomm:{device}",
        )
        self._connections[device] = (connection, task)
        task.add_done_callback(lambda completed, dev=device: self._connection_done(dev, completed))

    def _connection_done(self, device: str, task: asyncio.Task[None]) -> None:
        entry = self._connections.get(device)
        if entry is not None and entry[1] is task:
            self._connections.pop(device, None)
        if task.cancelled():
            return
        try:
            task.result()
        except Exception:
            LOGGER.exception("rfcomm.connection task failed device=%s", device)

    async def _serve_connection(self, device: str, connection: socket.socket) -> None:
        loop = asyncio.get_running_loop()
        buffer = bytearray()
        try:
            while True:
                chunk = await loop.sock_recv(connection, READ_CHUNK_BYTES)
                if not chunk:
                    LOGGER.info("rfcomm.connection eof device=%s", device)
                    return
                buffer.extend(chunk)

                if len(buffer) > MAX_REQUEST_BYTES and b"\n" not in buffer:
                    response = error_response(
                        "REQUEST_TOO_LARGE",
                        f"request exceeds {MAX_REQUEST_BYTES} bytes",
                    )
                    await loop.sock_sendall(connection, encode_message(response))
                    return

                while b"\n" in buffer:
                    line, remainder = bytes(buffer).split(b"\n", 1)
                    buffer = bytearray(remainder)
                    if not line.strip():
                        continue
                    LOGGER.debug(
                        "rfcomm.request device=%s bytes=%d",
                        device,
                        len(line),
                    )
                    response = await process_request(
                        line,
                        state_dir=self.state_dir,
                        cockpit_port=self.cockpit_port,
                    )
                    await loop.sock_sendall(connection, encode_message(response))
                    LOGGER.debug(
                        "rfcomm.response device=%s ok=%s",
                        device,
                        response.get("ok"),
                    )
        except asyncio.CancelledError:
            raise
        except (ConnectionError, OSError):
            LOGGER.info("rfcomm.connection lost device=%s", device, exc_info=True)
        finally:
            connection.close()

    def disconnect_device(self, device: str, *, reason: str) -> None:
        entry = self._connections.pop(device, None)
        if entry is None:
            return
        connection, task = entry
        LOGGER.info("rfcomm.connection closing device=%s reason=%s", device, reason)
        connection.close()
        task.cancel()

    def profile_released(self) -> None:
        """Handle BlueZ releasing the profile, typically during daemon shutdown/restart."""
        self._profile_registered = False
        self._release_event.set()

    async def stop(self, *, reason: str = "shutdown") -> None:
        LOGGER.info("rfcomm.server stopping reason=%s stage=%s", reason, self.stage)

        for device in list(self._connections):
            self.disconnect_device(device, reason=reason)

        if self._profile_registered and self._profile_manager is not None:
            self._set_stage("unregister-profile")
            try:
                await self._profile_manager.call_unregister_profile(PROFILE_PATH)
            except Exception:
                LOGGER.exception("failed to unregister RFCOMM profile")
            finally:
                self._profile_registered = False

        if self._agent_registered and self._agent_manager is not None:
            self._set_stage("unregister-pairing-agent")
            try:
                await self._agent_manager.call_unregister_agent(AGENT_PATH)
            except Exception:
                LOGGER.exception("failed to unregister RFCOMM pairing agent")
            finally:
                self._agent_registered = False

        if self._bus is not None:
            self._set_stage("dbus-disconnect")
            self._bus.disconnect()
            self._bus = None

        self._set_stage("stopped")
        LOGGER.info("rfcomm.server stopped")

    async def run_forever(self) -> None:
        await self.start()
        try:
            await self._release_event.wait()
        finally:
            await self.stop()
