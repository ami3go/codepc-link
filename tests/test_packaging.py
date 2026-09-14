import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RFCOMM_UNIT = ROOT / "packaging/systemd/codepc-link-rfcomm.service"
RFCOMM_INSTALLER = ROOT / "packaging/install-rfcomm-service.sh"
DEB_BUILDER = ROOT / "packaging/build-deb.sh"


def test_rfcomm_systemd_unit_keeps_server_alive() -> None:
    unit = RFCOMM_UNIT.read_text()

    assert "codepc-link serve-rfcomm" in unit
    assert "ExecStartPre=+/usr/bin/btmgmt --index hci0 connectable on" in unit
    assert "Restart=always" in unit
    assert "RestartSec=3s" in unit
    assert "StartLimitIntervalSec=0" in unit
    assert "WantedBy=multi-user.target" in unit


def test_rfcomm_installer_supports_staged_install(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment["DESTDIR"] = str(tmp_path)

    subprocess.run(["sh", RFCOMM_INSTALLER], check=True, env=environment, capture_output=True)

    installed = tmp_path / "etc/systemd/system/codepc-link-rfcomm.service"
    assert installed.read_text() == RFCOMM_UNIT.read_text()


def test_debug_debian_package_contains_runtime(tmp_path: Path) -> None:
    subprocess.run(
        ["sh", DEB_BUILDER, "0.1.0~test1", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    package = tmp_path / "codepc-link_0.1.0~test1_all.deb"
    listing = subprocess.run(
        ["dpkg-deb", "--contents", package],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert "./usr/bin/codepc-link" in listing
    assert "./usr/bin/codepc-link-bt" in listing
    assert "./usr/share/cockpit/codepc-link/index.html" in listing
    assert "./lib/systemd/system/codepc-link-rfcomm.service" in listing

    archive = subprocess.run(
        ["dpkg-deb", "--fsys-tarfile", package],
        check=True,
        stdout=subprocess.PIPE,
    )
    root_mode = subprocess.run(
        ["tar", "-tvf", "-", "./"],
        input=archive.stdout,
        check=True,
        capture_output=True,
    ).stdout.decode().split()[0]
    assert root_mode == "drwxr-xr-x"

    metadata = subprocess.run(
        ["dpkg-deb", "--field", package, "Installed-Size"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert int(metadata) > 0
