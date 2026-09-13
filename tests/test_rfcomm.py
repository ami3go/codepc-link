import asyncio
import json
import socket

from codepc_link import rfcomm
from codepc_link.protocol import RFCOMM_SERVICE_UUID, SCHEMA_VERSION
from codepc_link.rfcomm import (
    DEFAULT_RFCOMM_CHANNEL,
    MAX_REQUEST_BYTES,
    CodePCLinkRfcommServer,
    decode_request,
    encode_message,
    process_request,
)


def test_rfcomm_uuid_is_vendor_uuid() -> None:
    assert RFCOMM_SERVICE_UUID == "0330ce6c-09db-5189-b7ad-e16bcafac7ee"


def test_decode_status_request() -> None:
    request = decode_request(b'{"schema":1,"op":"status"}')
    assert request == {"schema": 1, "op": "status"}


def test_encode_message_uses_one_json_line() -> None:
    encoded = encode_message({"schema": 1, "ok": True})
    assert encoded.endswith(b"\n")
    assert encoded.count(b"\n") == 1
    assert json.loads(encoded) == {"schema": 1, "ok": True}


def test_invalid_request_returns_structured_error() -> None:
    response = asyncio.run(process_request(b'{"schema":1,"op":"write"}'))
    assert response["schema"] == SCHEMA_VERSION
    assert response["ok"] is False
    assert response["error"]["code"] == "UNSUPPORTED_OPERATION"


def test_status_request_reuses_management_core(monkeypatch) -> None:
    expected = {
        "schema": 1,
        "device": {"hostname": "codepc-test"},
        "network": {"interfaces": []},
        "cockpit": {"port": 9090, "available": True},
        "errors": [],
    }

    async def fake_collect_status(*, state_dir=None, cockpit_port=9090):
        assert state_dir is None
        assert cockpit_port == 9090
        return expected

    monkeypatch.setattr(rfcomm, "collect_status", fake_collect_status)
    response = asyncio.run(process_request(b'{"schema":1,"op":"status"}'))

    assert response == {
        "schema": 1,
        "ok": True,
        "op": "status",
        "status": expected,
    }


def test_profile_options_require_secure_connection_by_default() -> None:
    server = CodePCLinkRfcommServer()
    options = server.profile_options()

    assert options["Service"].value == RFCOMM_SERVICE_UUID
    assert options["Role"].value == "server"
    assert options["Channel"].value == DEFAULT_RFCOMM_CHANNEL
    assert options["RequireAuthentication"].value is True
    assert options["RequireAuthorization"].value is True


async def _read_json_line(loop, connection: socket.socket) -> dict:
    buffer = bytearray()
    while b"\n" not in buffer:
        chunk = await asyncio.wait_for(loop.sock_recv(connection, 65536), timeout=1)
        assert chunk
        buffer.extend(chunk)
    line, _ = bytes(buffer).split(b"\n", 1)
    return json.loads(line)


def test_connection_loop_handles_fragmented_request(monkeypatch) -> None:
    expected = {
        "schema": 1,
        "device": {"hostname": "codepc-fragmented"},
        "network": {"interfaces": []},
        "cockpit": {"port": 9090, "available": True},
        "errors": [],
    }

    async def fake_collect_status(*, state_dir=None, cockpit_port=9090):
        return expected

    monkeypatch.setattr(rfcomm, "collect_status", fake_collect_status)

    async def scenario() -> None:
        server = CodePCLinkRfcommServer()
        server_side, client_side = socket.socketpair()
        server_side.setblocking(False)
        client_side.setblocking(False)
        loop = asyncio.get_running_loop()
        task = asyncio.create_task(server._serve_connection("test-device", server_side))

        try:
            await loop.sock_sendall(client_side, b'{"schema":1,')
            await loop.sock_sendall(client_side, b'"op":"status"}\n')
            response = await _read_json_line(loop, client_side)
            assert response["ok"] is True
            assert response["status"] == expected
        finally:
            client_side.close()
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_connection_loop_rejects_unterminated_oversize_request() -> None:
    async def scenario() -> None:
        server = CodePCLinkRfcommServer()
        server_side, client_side = socket.socketpair()
        server_side.setblocking(False)
        client_side.setblocking(False)
        loop = asyncio.get_running_loop()
        task = asyncio.create_task(server._serve_connection("test-device", server_side))

        try:
            await loop.sock_sendall(client_side, b"x" * (MAX_REQUEST_BYTES + 1))
            response = await _read_json_line(loop, client_side)
            assert response["ok"] is False
            assert response["error"]["code"] == "REQUEST_TOO_LARGE"
            await asyncio.wait_for(task, timeout=1)
        finally:
            client_side.close()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())
