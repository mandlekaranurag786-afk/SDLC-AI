import pytest
from fastapi.testclient import TestClient
import os
from pathlib import Path
from main import app
from auth import get_valid_api_keys
from streamlit_app.api_client import _client_api_key

client = TestClient(app)

def test_no_hardcoded_keys():
    # Verify api_client.py doesn't have dev-secret-key-123
    client_path = Path(__file__).resolve().parent.parent / "streamlit_app" / "api_client.py"
    content = client_path.read_text()
    assert "dev-secret-key-123" not in content

def test_missing_header_returns_401():
    # Start route expects auth
    os.environ["API_KEY"] = "test-key"
    response = client.post("/api/requirements/start", json={"problem_statement": "t"})
    assert response.status_code == 401

def test_wrong_key_returns_401_with_detail():
    os.environ["API_KEY"] = "test-key"
    response = client.post("/api/requirements/start", headers={"Authorization": "Bearer wrong-key"}, json={"problem_statement": "t"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"

def test_correct_key_passes_auth():
    os.environ["API_KEY"] = "test-key"
    # It will pass auth and hit the next validation step or route logic
    response = client.post("/api/requirements/start", headers={"Authorization": "Bearer test-key"}, json={"problem_statement": "t"})
    assert response.status_code == 400  # 400 Bad Request because length < 50

def test_client_helper_raises_error_if_unset(monkeypatch):
    monkeypatch.setenv("API_KEY", "")
    with pytest.raises(RuntimeError, match="API_KEY is not set"):
        _client_api_key()
