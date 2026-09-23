import pytest

from codepc_link.hid_protocol import (
    MAX_CHUNK_PAYLOAD,
    OP_REQUEST_STATUS,
    OP_STATUS_JSON,
    REPORT_DATA_BYTES,
    REPORT_ID_COMMAND,
    REPORT_ID_STATUS,
    HidProtocolError,
    decode_frame,
    decode_hidraw_input,
    encode_frame,
    encode_hidraw_output,
    encode_message,
)


def test_hid_frame_round_trip() -> None:
    encoded = encode_frame(
        opcode=OP_STATUS_JSON,
        sequence=7,
        payload=b"hello",
        chunk_index=2,
        chunk_count=4,
    )

    assert len(encoded) == REPORT_DATA_BYTES
    decoded = decode_frame(encoded)
    assert decoded.opcode == OP_STATUS_JSON
    assert decoded.sequence == 7
    assert decoded.chunk_index == 2
    assert decoded.chunk_count == 4
    assert decoded.payload == b"hello"


def test_hid_message_chunking() -> None:
    payload = bytes(range(200))
    frames = encode_message(payload, opcode=OP_STATUS_JSON, sequence=9)

    assert len(frames) == 4
    decoded = [decode_frame(frame) for frame in frames]
    assert all(frame.sequence == 9 for frame in decoded)
    assert all(frame.chunk_count == 4 for frame in decoded)
    assert b"".join(frame.payload for frame in decoded) == payload
    assert max(len(frame.payload) for frame in decoded) <= MAX_CHUNK_PAYLOAD


def test_hidraw_report_ids_are_directional() -> None:
    command = encode_frame(opcode=OP_REQUEST_STATUS, sequence=3)
    decoded = decode_hidraw_input(bytes([REPORT_ID_COMMAND]) + command)
    assert decoded.opcode == OP_REQUEST_STATUS

    status = encode_hidraw_output(
        encode_frame(opcode=OP_STATUS_JSON, sequence=3, payload=b"{}")
    )
    assert status[0] == REPORT_ID_STATUS
    assert len(status) == REPORT_DATA_BYTES + 1


def test_hid_protocol_rejects_invalid_chunk() -> None:
    with pytest.raises(HidProtocolError):
        encode_frame(
            opcode=OP_STATUS_JSON,
            sequence=1,
            chunk_index=2,
            chunk_count=2,
        )
