"""Shared CodePC Link Management Core used by CLI, BLE, and Cockpit."""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__
from .identity import get_device_name, get_hostname, load_or_create_device_id
from .network import collect_network_status
from .protocol import SCHEMA_VERSION

DEFAULT_COCKPIT_PORT = 9090
COMMAND_TIMEOUT_SECONDS = 3


def _service_active(unit: str) -> bool | None:
    if shutil.which("systemctl") is None:
        return None
    try:
        completed = subprocess.run(
            ["systemctl", "is-active", "--quiet", unit],
            check=False,
            capture_output=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.returncode == 0


async def collect_status(
    state_dir: Path | None = None,
    cockpit_port: int = DEFAULT_COCKPIT_PORT,
) -> dict[str, Any]:
    """Return the authoritative normalized schema-v1 host status."""
    errors: list[dict[str, str]] = []
    hostname = get_hostname()

    try:
        device_id = load_or_create_device_id(state_dir)
    except (OSError, ValueError) as exc:
        device_id = None
        errors.append(
            {
                "component": "identity",
                "code": "DEVICE_ID_UNAVAILABLE",
                "message": str(exc),
            }
        )

    network, network_errors = await collect_network_status()
    errors.extend(network_errors)
    cockpit_active = _service_active("cockpit.socket")

    return {
        "schema": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "device": {
            "id": device_id,
            "name": get_device_name(hostname),
            "hostname": hostname,
            "version": __version__,
        },
        "network": network,
        "cockpit": {
            "port": cockpit_port,
            "available": cockpit_active,
        },
        "errors": errors,
    }


def system_info_payload(status: dict[str, Any]) -> dict[str, Any]:
    """Build the stable SYSTEM_INFO characteristic document."""
    return {
        "schema": SCHEMA_VERSION,
        "device": status.get("device", {}),
        "cockpit": status.get("cockpit", {}),
        "errors": [
            error
            for error in status.get("errors", [])
            if error.get("component") in {"identity", "system"}
        ],
    }


def network_status_payload(status: dict[str, Any]) -> dict[str, Any]:
    """Build the stable NETWORK_STATUS characteristic document."""
    return {
        "schema": SCHEMA_VERSION,
        "network": status.get("network", {}),
        "errors": [
            error
            for error in status.get("errors", [])
            if error.get("component") == "network"
        ],
    }
