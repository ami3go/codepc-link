from codepc_link.core import network_status_payload, system_info_payload


def _status_fixture() -> dict:
    return {
        "schema": 1,
        "device": {
            "id": "5e8e2ba4-2a08-42bf-b68a-7e256812240d",
            "name": "CodePC Link - mini",
            "hostname": "mini",
            "version": "0.0.0.dev0",
        },
        "cockpit": {"port": 9090, "available": True},
        "network": {"interfaces": [], "internet": None},
        "errors": [
            {
                "component": "network",
                "code": "NM_UNAVAILABLE",
                "message": "test",
            },
            {
                "component": "identity",
                "code": "DEVICE_ID_UNAVAILABLE",
                "message": "test identity",
            },
        ],
    }


def test_system_info_excludes_network_errors() -> None:
    payload = system_info_payload(_status_fixture())
    assert payload["schema"] == 1
    assert payload["device"]["hostname"] == "mini"
    assert [error["component"] for error in payload["errors"]] == ["identity"]


def test_network_status_excludes_identity_errors() -> None:
    payload = network_status_payload(_status_fixture())
    assert payload["schema"] == 1
    assert [error["component"] for error in payload["errors"]] == ["network"]
