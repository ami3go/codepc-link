import json

import pytest

from codepc_link.protocol import (
    MAX_CHARACTERISTIC_BYTES,
    PayloadTooLargeError,
    read_from_offset,
    serialize_payload,
)


def test_serialize_payload_adds_schema() -> None:
    encoded = serialize_payload({"hello": "world"})
    payload = json.loads(encoded.decode("utf-8"))
    assert payload == {"hello": "world", "schema": 1}


def test_serialize_payload_rejects_oversize_document() -> None:
    with pytest.raises(PayloadTooLargeError):
        serialize_payload({"data": "x" * MAX_CHARACTERISTIC_BYTES})


def test_read_from_offset_supports_gatt_long_reads() -> None:
    payload = b"abcdefgh"
    assert read_from_offset(payload, 0) == b"abcdefgh"
    assert read_from_offset(payload, 3) == b"defgh"
    assert read_from_offset(payload, len(payload)) == b""


def test_read_from_offset_rejects_negative_offset() -> None:
    with pytest.raises(ValueError):
        read_from_offset(b"abc", -1)
