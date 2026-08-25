import uuid

from codepc_link.identity import DEVICE_ID_FILENAME, get_device_name, load_or_create_device_id


def test_device_id_is_persistent(tmp_path) -> None:
    first = load_or_create_device_id(tmp_path)
    second = load_or_create_device_id(tmp_path)

    assert first == second
    assert str(uuid.UUID(first)) == first
    assert (tmp_path / DEVICE_ID_FILENAME).read_text(encoding="utf-8").strip() == first


def test_device_name_uses_hostname_without_becoming_identity() -> None:
    assert get_device_name("mini-01") == "CodePC Link - mini-01"
