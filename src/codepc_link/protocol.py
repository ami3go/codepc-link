"""Stable CodePC Link BLE protocol constants and payload helpers."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = 1
MAX_CHARACTERISTIC_BYTES = 16 * 1024

MANAGEMENT_SERVICE_UUID = "78561c99-7412-45b5-84b6-4ef7062fe7d0"
SYSTEM_INFO_CHARACTERISTIC_UUID = "83cf19fa-bf46-4fc9-8366-321b545c4bf4"
NETWORK_STATUS_CHARACTERISTIC_UUID = "6ef6c725-99f8-4533-bd85-874453f28af3"
EVENT_CHARACTERISTIC_UUID = "5b45ee1f-060f-48db-9fa4-b0096115967d"

READ_FLAGS_SECURE = ["encrypt-read"]
READ_FLAGS_DEVELOPMENT = ["read"]


class PayloadTooLargeError(ValueError):
    """Raised when a serialized characteristic exceeds the protocol limit."""


def serialize_payload(payload: dict[str, Any]) -> bytes:
    """Serialize one schema-v1 payload as compact UTF-8 JSON."""
    document = dict(payload)
    document.setdefault("schema", SCHEMA_VERSION)
    encoded = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > MAX_CHARACTERISTIC_BYTES:
        raise PayloadTooLargeError(
            f"payload is {len(encoded)} bytes; maximum is {MAX_CHARACTERISTIC_BYTES}"
        )
    return encoded


def read_from_offset(payload: bytes, offset: int) -> bytes:
    """Implement BlueZ ReadValue offset semantics for GATT long reads."""
    if offset < 0:
        raise ValueError("offset must be zero or greater")
    if offset >= len(payload):
        return b""
    return payload[offset:]
