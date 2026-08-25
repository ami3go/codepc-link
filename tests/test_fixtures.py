import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_schema_fixtures_are_valid_v1_documents() -> None:
    fixtures = sorted(FIXTURE_DIR.glob("*.json"))
    assert fixtures

    for path in fixtures:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema"] == 1, path.name
        assert isinstance(payload.get("errors", []), list), path.name
