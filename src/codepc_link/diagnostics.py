"""Milestone A diagnostics for validating a CodePC Link target host."""

from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COMMAND_TIMEOUT_SECONDS = 5


def _run(args: list[str]) -> tuple[int, str, str]:
    """Run a short local diagnostic command without invoking a shell."""
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def _parse_os_release(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key] = value.strip().strip('"')
    return result


def _read_os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    try:
        return _parse_os_release(path.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _first_version(command: list[str]) -> str | None:
    if shutil.which(command[0]) is None:
        return None
    returncode, stdout, stderr = _run(command)
    if returncode != 0:
        return None
    value = stdout or stderr
    return value.splitlines()[0].strip() if value else None


def _service_state(unit: str) -> str | None:
    if shutil.which("systemctl") is None:
        return None
    returncode, stdout, _ = _run(["systemctl", "is-active", unit])
    if stdout:
        return stdout
    return "unknown" if returncode else "active"


def _extract_hci_names(text: str) -> list[str]:
    return sorted(set(re.findall(r"\bhci\d+\b", text)))


def _discover_adapters() -> list[str]:
    sysfs = Path("/sys/class/bluetooth")
    if sysfs.is_dir():
        adapters = sorted(entry.name for entry in sysfs.iterdir() if entry.name.startswith("hci"))
        if adapters:
            return adapters

    if shutil.which("busctl"):
        _, stdout, _ = _run(["busctl", "--system", "tree", "org.bluez", "--list"])
        adapters = _extract_hci_names(stdout)
        if adapters:
            return adapters

    return []


def _parse_btmgmt_supported_settings(text: str) -> set[str]:
    for raw_line in text.splitlines():
        line = raw_line.strip().lower()
        if line.startswith("supported settings:"):
            _, values = line.split(":", 1)
            return set(values.split())
    return set()


def _btmgmt_info() -> dict[str, Any]:
    if shutil.which("btmgmt") is None:
        return {"available": False, "supported_settings": []}
    returncode, stdout, stderr = _run(["btmgmt", "info"])
    settings = _parse_btmgmt_supported_settings(stdout)
    return {
        "available": True,
        "ok": returncode == 0,
        "supported_settings": sorted(settings),
        "stderr": stderr or None,
    }


def _bluez_interface_available(adapter: str, interface: str) -> bool | None:
    if shutil.which("busctl") is None:
        return None
    path = f"/org/bluez/{adapter}"
    returncode, _, _ = _run(["busctl", "--system", "introspect", "org.bluez", path, interface])
    return returncode == 0


def _rfkill_state() -> dict[str, Any]:
    if shutil.which("rfkill") is None:
        return {"available": False, "blocked": None, "devices": []}

    returncode, stdout, _ = _run(["rfkill", "--json"])
    if returncode != 0 or not stdout:
        return {"available": True, "blocked": None, "devices": []}

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {"available": True, "blocked": None, "devices": []}

    devices = [
        entry
        for entry in payload.get("rfkilldevices", [])
        if str(entry.get("type", "")).lower() == "bluetooth"
    ]
    blocked = any(bool(entry.get("soft")) or bool(entry.get("hard")) for entry in devices)
    return {"available": True, "blocked": blocked, "devices": devices}


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def collect_diagnostics() -> dict[str, Any]:
    """Collect a deterministic Milestone A feasibility report."""
    os_release = _read_os_release()
    adapters = _discover_adapters()
    adapter = adapters[0] if adapters else None
    btmgmt = _btmgmt_info()
    supported_settings = set(btmgmt.get("supported_settings", []))
    rfkill = _rfkill_state()

    advertising_manager = (
        _bluez_interface_available(adapter, "org.bluez.LEAdvertisingManager1") if adapter else False
    )
    gatt_manager = _bluez_interface_available(adapter, "org.bluez.GattManager1") if adapter else False

    checks: list[dict[str, str]] = []
    checks.append(
        _check(
            "linux",
            "pass" if sys.platform.startswith("linux") else "fail",
            platform.platform(),
        )
    )
    checks.append(
        _check(
            "bluez",
            "pass" if _first_version(["bluetoothctl", "--version"]) else "fail",
            _first_version(["bluetoothctl", "--version"]) or "bluetoothctl not found",
        )
    )
    checks.append(
        _check(
            "adapter",
            "pass" if adapter else "fail",
            adapter or "no Bluetooth HCI adapter found",
        )
    )
    checks.append(
        _check(
            "rfkill",
            "fail" if rfkill.get("blocked") is True else "pass",
            "Bluetooth is blocked" if rfkill.get("blocked") is True else "not blocked or unavailable",
        )
    )

    if advertising_manager is None:
        checks.append(_check("advertising_manager", "unknown", "busctl unavailable"))
    else:
        checks.append(
            _check(
                "advertising_manager",
                "pass" if advertising_manager else "fail",
                "LEAdvertisingManager1 available" if advertising_manager else "LEAdvertisingManager1 unavailable",
            )
        )

    if gatt_manager is None:
        checks.append(_check("gatt_manager", "unknown", "busctl unavailable"))
    else:
        checks.append(
            _check(
                "gatt_manager",
                "pass" if gatt_manager else "fail",
                "GattManager1 available" if gatt_manager else "GattManager1 unavailable",
            )
        )

    if supported_settings:
        checks.append(
            _check(
                "le_support",
                "pass" if "le" in supported_settings else "fail",
                "btmgmt reports LE support" if "le" in supported_settings else "btmgmt does not report LE support",
            )
        )
        checks.append(
            _check(
                "advertising_support",
                "pass" if "advertising" in supported_settings else "fail",
                "btmgmt reports advertising support"
                if "advertising" in supported_settings
                else "btmgmt does not report advertising support",
            )
        )

    blockers = [check for check in checks if check["status"] == "fail"]

    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "pass" if not blockers else "fail",
        "system": {
            "os": {
                "id": os_release.get("ID"),
                "version_id": os_release.get("VERSION_ID"),
                "pretty_name": os_release.get("PRETTY_NAME"),
            },
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
        },
        "software": {
            "bluez": _first_version(["bluetoothctl", "--version"]),
            "networkmanager": _first_version(["nmcli", "--version"]),
            "cockpit": _first_version(["cockpit-bridge", "--version"]),
        },
        "services": {
            "bluetooth": _service_state("bluetooth.service"),
            "networkmanager": _service_state("NetworkManager.service"),
            "cockpit_socket": _service_state("cockpit.socket"),
        },
        "bluetooth": {
            "adapters": adapters,
            "selected_adapter": adapter,
            "rfkill": rfkill,
            "btmgmt": btmgmt,
            "le_advertising_manager": advertising_manager,
            "gatt_manager": gatt_manager,
        },
        "checks": checks,
    }


def render_text_report(report: dict[str, Any]) -> str:
    lines = [f"CodePC Link feasibility: {str(report['result']).upper()}"]
    system = report["system"]
    os_info = system["os"]
    lines.append(f"OS: {os_info.get('pretty_name') or 'unknown'}")
    lines.append(f"Kernel: {system.get('kernel')}")
    lines.append(f"Python: {system.get('python')}")
    lines.append("")
    for check in report["checks"]:
        lines.append(f"[{check['status'].upper():7}] {check['name']}: {check['detail']}")
    return "\n".join(lines)
