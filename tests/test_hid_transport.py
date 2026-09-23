from pathlib import Path

from codepc_link.hid_transport import (
    HID_PRODUCT_NAME,
    find_codepc_hidraw,
    list_hidraw_devices,
)


def _write_uevent(root: Path, name: str, *, product: str, address: str) -> None:
    device = root / name / "device"
    device.mkdir(parents=True)
    (device / "uevent").write_text(
        "\n".join(
            [
                "HID_ID=0005:00000000:00000000",
                f"HID_NAME={product}",
                f"HID_UNIQ={address}",
            ]
        ),
        encoding="utf-8",
    )


def test_list_hidraw_devices_reads_sysfs(tmp_path: Path) -> None:
    _write_uevent(
        tmp_path,
        "hidraw2",
        product=HID_PRODUCT_NAME,
        address="aa:bb:cc:dd:ee:ff",
    )

    devices = list_hidraw_devices(tmp_path)

    assert len(devices) == 1
    assert devices[0].path == Path("/dev/hidraw2")
    assert devices[0].name == HID_PRODUCT_NAME
    assert devices[0].address == "AA:BB:CC:DD:EE:FF"


def test_find_hidraw_filters_vendor_transport(tmp_path: Path) -> None:
    _write_uevent(
        tmp_path,
        "hidraw0",
        product="Ordinary keyboard",
        address="11:22:33:44:55:66",
    )
    _write_uevent(
        tmp_path,
        "hidraw1",
        product=HID_PRODUCT_NAME,
        address="AA:BB:CC:DD:EE:FF",
    )

    selected = find_codepc_hidraw(sys_class=tmp_path)
    assert selected is not None
    assert selected.path == Path("/dev/hidraw1")

    selected = find_codepc_hidraw(
        address="aa:bb:cc:dd:ee:ff",
        sys_class=tmp_path,
    )
    assert selected is not None
    assert selected.path == Path("/dev/hidraw1")
