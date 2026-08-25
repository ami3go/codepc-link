from codepc_link.ble_probe import DEFAULT_LOCAL_NAME, FeasibilityAdvertisement
from codepc_link.protocol import MANAGEMENT_SERVICE_UUID


def test_feasibility_advertisement_matches_production_discovery_contract() -> None:
    advertisement = FeasibilityAdvertisement(DEFAULT_LOCAL_NAME)

    assert advertisement.Type == "peripheral"
    assert advertisement.LocalName == "CodePC Link"
    assert advertisement.ServiceUUIDs == [MANAGEMENT_SERVICE_UUID]
    assert advertisement.Discoverable is True
