"""Persistent CodePC Link device identity."""

from __future__ import annotations

import os
import socket
import uuid
from pathlib import Path

DEFAULT_STATE_DIR = Path("/var/lib/codepc-link")
DEVICE_ID_FILENAME = "device-id"


def resolve_state_dir(state_dir: Path | None = None) -> Path:
    """Resolve the daemon state directory, allowing test/development override."""
    if state_dir is not None:
        return state_dir
    configured = os.environ.get("CODEPC_LINK_STATE_DIR")
    return Path(configured) if configured else DEFAULT_STATE_DIR


def _read_device_id(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    return str(uuid.UUID(value))


def load_or_create_device_id(state_dir: Path | None = None) -> str:
    """Return the persistent device UUID, creating it atomically once."""
    directory = resolve_state_dir(state_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / DEVICE_ID_FILENAME

    try:
        return _read_device_id(path)
    except FileNotFoundError:
        pass

    value = str(uuid.uuid4())
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(path, flags, 0o644)
    except FileExistsError:
        return _read_device_id(path)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise

    return value


def get_hostname() -> str:
    """Return the current host name used for human-readable device identity."""
    return socket.gethostname()


def get_device_name(hostname: str | None = None) -> str:
    """Build the BLE/UI display name without making it the stable identity."""
    host = hostname or get_hostname()
    return f"CodePC Link - {host}"
