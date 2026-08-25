from codepc_link.diagnostics import (
    _extract_hci_names,
    _parse_btmgmt_supported_settings,
    _parse_os_release,
    render_text_report,
)


def test_parse_os_release() -> None:
    parsed = _parse_os_release('ID=debian\nVERSION_ID="13"\nPRETTY_NAME="Debian GNU/Linux 13"\n')
    assert parsed["ID"] == "debian"
    assert parsed["VERSION_ID"] == "13"
    assert parsed["PRETTY_NAME"] == "Debian GNU/Linux 13"


def test_extract_hci_names() -> None:
    text = "/org/bluez/hci1\n/org/bluez/hci0\n/org/bluez/hci0/dev_00_11_22_33_44_55"
    assert _extract_hci_names(text) == ["hci0", "hci1"]


def test_parse_btmgmt_supported_settings() -> None:
    text = "supported settings: powered connectable le advertising secure-conn\n"
    assert _parse_btmgmt_supported_settings(text) == {
        "powered",
        "connectable",
        "le",
        "advertising",
        "secure-conn",
    }


def test_render_text_report() -> None:
    report = {
        "result": "pass",
        "system": {
            "os": {"pretty_name": "Test Linux"},
            "kernel": "6.1.0",
            "python": "3.13.0",
        },
        "checks": [
            {"name": "adapter", "status": "pass", "detail": "hci0"},
        ],
    }
    rendered = render_text_report(report)
    assert "CodePC Link feasibility: PASS" in rendered
    assert "[PASS" in rendered
    assert "adapter: hci0" in rendered
