"""Vendor-defined Bluetooth HID framing for CodePC Link.

The Android phone is a Bluetooth HID *device*. It deliberately exposes only a
vendor-defined usage page, not Keyboard or Mouse usages. Linux therefore gets
a hidraw transport without synthetic key events.
"""

from __future__ import annotations

from dataclasses import dataclass

PROTOCOL_VERSION = 1

REPORT_ID_COMMAND = 1
REPORT_ID_STATUS = 2
REPORT_DATA_BYTES = 63

# Report data layout (the HID report ID is outside this structure):
#   0      protocol version
#   1      opcode
#   2      sequence
#   3..4   chunk index, little-endian
#   5..6   chunk count, little-endian
#   7      payload length
#   8..62  payload
HEADER_BYTES = 8
MAX_CHUNK_PAYLOAD = REPORT_DATA_BYTES - HEADER_BYTES
MAX_CHUNKS = 0xFFFF
MAX_MESSAGE_BYTES = MAX_CHUNK_PAYLOAD * MAX_CHUNKS

OP_REQUEST_STATUS = 0x01
OP_SET_PUSH_INTERVAL = 0x02
OP_STATUS_JSON = 0x10


class HidProtocolError(ValueError):
    """Raised for malformed CodePC Link HID reports."""


@dataclass(frozen=True)
class HidFrame:
    """One decoded vendor-defined HID frame."""

    opcode: int
    sequence: int
    chunk_index: int
    chunk_count: int
    payload: bytes


def _u16_le(value: int) -> bytes:
    if not 0 <= value <= 0xFFFF:
        raise HidProtocolError(f"value is outside uint16 range: {value}")
    return value.to_bytes(2, "little")


def encode_frame(
    *,
    opcode: int,
    sequence: int,
    payload: bytes = b"",
    chunk_index: int = 0,
    chunk_count: int = 1,
) -> bytes:
    """Encode exactly 63 bytes of HID report data (without report ID)."""
    if not 0 <= opcode <= 0xFF:
        raise HidProtocolError("opcode must fit in one byte")
    if not 0 <= sequence <= 0xFF:
        raise HidProtocolError("sequence must fit in one byte")
    if not 1 <= chunk_count <= MAX_CHUNKS:
        raise HidProtocolError("chunk_count must be between 1 and 65535")
    if not 0 <= chunk_index < chunk_count:
        raise HidProtocolError("chunk_index must refer to an existing chunk")
    if len(payload) > MAX_CHUNK_PAYLOAD:
        raise HidProtocolError(
            f"payload is {len(payload)} bytes; maximum frame payload is {MAX_CHUNK_PAYLOAD}"
        )

    report = bytearray(REPORT_DATA_BYTES)
    report[0] = PROTOCOL_VERSION
    report[1] = opcode
    report[2] = sequence
    report[3:5] = _u16_le(chunk_index)
    report[5:7] = _u16_le(chunk_count)
    report[7] = len(payload)
    report[8 : 8 + len(payload)] = payload
    return bytes(report)


def decode_frame(data: bytes) -> HidFrame:
    """Decode report data, tolerating omitted trailing zero padding."""
    if len(data) < HEADER_BYTES:
        raise HidProtocolError(f"report data is too short: {len(data)} bytes")
    if data[0] != PROTOCOL_VERSION:
        raise HidProtocolError(f"unsupported HID protocol version: {data[0]}")

    chunk_index = int.from_bytes(data[3:5], "little")
    chunk_count = int.from_bytes(data[5:7], "little")
    payload_length = data[7]

    if chunk_count == 0:
        raise HidProtocolError("chunk_count must not be zero")
    if chunk_index >= chunk_count:
        raise HidProtocolError("chunk_index is outside chunk_count")
    if payload_length > MAX_CHUNK_PAYLOAD:
        raise HidProtocolError("payload length exceeds the report capacity")
    if len(data) < HEADER_BYTES + payload_length:
        raise HidProtocolError("report ended before its declared payload length")

    return HidFrame(
        opcode=data[1],
        sequence=data[2],
        chunk_index=chunk_index,
        chunk_count=chunk_count,
        payload=bytes(data[8 : 8 + payload_length]),
    )


def encode_message(payload: bytes, *, opcode: int, sequence: int) -> list[bytes]:
    """Split an arbitrary message into fixed-size HID report-data frames."""
    if len(payload) > MAX_MESSAGE_BYTES:
        raise HidProtocolError(
            f"message is {len(payload)} bytes; maximum is {MAX_MESSAGE_BYTES}"
        )

    if not payload:
        return [encode_frame(opcode=opcode, sequence=sequence)]

    chunks = [
        payload[offset : offset + MAX_CHUNK_PAYLOAD]
        for offset in range(0, len(payload), MAX_CHUNK_PAYLOAD)
    ]
    count = len(chunks)
    return [
        encode_frame(
            opcode=opcode,
            sequence=sequence,
            payload=chunk,
            chunk_index=index,
            chunk_count=count,
        )
        for index, chunk in enumerate(chunks)
    ]


def decode_hidraw_input(report: bytes) -> HidFrame:
    """Decode a Linux hidraw input report from the Android HID device."""
    if not report:
        raise HidProtocolError("empty hidraw report")
    if report[0] != REPORT_ID_COMMAND:
        raise HidProtocolError(f"unexpected HID input report id: {report[0]}")
    return decode_frame(report[1:])


def encode_hidraw_output(frame_data: bytes) -> bytes:
    """Prefix one status frame with the report ID expected by hidraw."""
    if len(frame_data) != REPORT_DATA_BYTES:
        raise HidProtocolError(
            f"status frame must be exactly {REPORT_DATA_BYTES} bytes of report data"
        )
    return bytes([REPORT_ID_STATUS]) + frame_data
