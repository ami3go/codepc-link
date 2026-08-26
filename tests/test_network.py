from codepc_link.network import NM_CONNECTIVITY_FULL, normalize_devices


def test_wifi_internet_and_isolated_ethernet_are_distinct() -> None:
    normalized = normalize_devices(
        [
            {
                "name": "wlan0",
                "type": "wifi",
                "managed": True,
                "state": 100,
                "addresses": ["192.168.1.73/24"],
                "gateway": "192.168.1.1",
                "default_route": True,
                "ssid": "HomeNetwork",
                "signal": 78,
            },
            {
                "name": "enp2s0",
                "type": "ethernet",
                "managed": True,
                "state": 100,
                "carrier": True,
                "addresses": ["10.10.10.1/24"],
                "default_route": False,
            },
        ],
        NM_CONNECTIVITY_FULL,
    )

    by_name = {item["name"]: item for item in normalized["interfaces"]}
    assert by_name["wlan0"]["internet"] is True
    assert by_name["wlan0"]["default_route"] is True
    assert by_name["enp2s0"]["internet"] is False
    assert by_name["enp2s0"]["link"] == "up"
    assert normalized["default_route_interfaces"] == ["wlan0"]


def test_bridge_with_useful_address_is_not_hidden() -> None:
    normalized = normalize_devices(
        [
            {
                "name": "br-lan",
                "type": "bridge",
                "managed": True,
                "state": 100,
                "addresses": ["10.0.0.1/24"],
                "default_route": False,
            }
        ],
        None,
    )
    assert [item["name"] for item in normalized["interfaces"]] == ["br-lan"]


def test_container_and_veth_interfaces_are_hidden() -> None:
    normalized = normalize_devices(
        [
            {
                "name": "docker0",
                "type": "bridge",
                "managed": True,
                "state": 100,
                "addresses": ["172.17.0.1/16"],
            },
            {
                "name": "veth1234",
                "type": "veth",
                "managed": True,
                "state": 100,
                "addresses": ["169.254.1.1/16"],
            },
        ],
        None,
    )
    assert normalized["interfaces"] == []


def test_wifi_p2p_pseudo_device_is_hidden() -> None:
    normalized = normalize_devices(
        [
            {
                "name": "wlp1s0",
                "type": "wifi",
                "managed": True,
                "state": 30,
                "addresses": [],
            },
            {
                "name": "p2p-dev-wlp1s0",
                "type": "wifi-p2p",
                "managed": True,
                "state": 30,
                "addresses": [],
            },
        ],
        None,
    )

    assert [item["name"] for item in normalized["interfaces"]] == ["wlp1s0"]


def test_route_presence_does_not_imply_internet() -> None:
    normalized = normalize_devices(
        [
            {
                "name": "enp1s0",
                "type": "ethernet",
                "managed": True,
                "state": 100,
                "carrier": True,
                "addresses": ["192.168.50.2/24"],
                "default_route": True,
            }
        ],
        3,
    )
    interface = normalized["interfaces"][0]
    assert interface["default_route"] is True
    assert interface["internet"] is False
    assert normalized["internet"] is False
