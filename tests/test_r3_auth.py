import os
import pytest
from auth import get_valid_api_keys, get_owner_id_from_token

def test_multi_key_parsing(monkeypatch):
    monkeypatch.setenv("API_KEY", " key1 , key2,key3 ")
    keys = get_valid_api_keys()
    assert keys == {"key1", "key2", "key3"}


def test_empty_api_key_raises(monkeypatch):
    monkeypatch.setenv("API_KEY", "")
    with pytest.raises(RuntimeError) as exc_info:
        get_valid_api_keys()
    assert "API_KEY environment variable is required" in str(exc_info.value)


def test_different_keys_produce_different_owner_ids():
    owner1 = get_owner_id_from_token("key-alpha-123")
    owner2 = get_owner_id_from_token("key-beta-456")
    assert owner1 != owner2
    assert owner1.startswith("owner_")
    assert owner2.startswith("owner_")
