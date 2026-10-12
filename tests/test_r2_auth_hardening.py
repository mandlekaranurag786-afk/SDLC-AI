import os
import pytest
from fastapi.testclient import TestClient
from main import app
from db import init_db, create_requirement_session, get_db
from auth import get_api_key, get_owner_id_from_token

@pytest.fixture(autouse=True)
def setup_db_and_env():
    os.environ["API_KEY"] = "test-key-alpha-123"
    init_db()
    yield
    if "API_KEY" in os.environ:
        del os.environ["API_KEY"]

def test_missing_api_key_raises_runtime_error(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc_info:
        get_api_key()
    assert "API_KEY environment variable is required" in str(exc_info.value)


def test_cross_owner_access_returns_404():
    os.environ["API_KEY"] = "token-user-a"
    client_a = TestClient(app)
    
    # User A creates a session
    headers_a = {"Authorization": "Bearer token-user-a"}
    resp_a = client_a.post(
        "/api/requirements/start",
        json={"problem_statement": "We are a mid-size enterprise experiencing significant pain in our employee onboarding process. A new hire sits idle for 3 to 5 days waiting for IT provisioning and document sign-offs."},
        headers=headers_a
    )
    assert resp_a.status_code == 200
    session_id = resp_a.json()["session_id"]

    # User B attempts to access User A's session using token-user-b
    os.environ["API_KEY"] = "token-user-b"
    client_b = TestClient(app)
    headers_b = {"Authorization": "Bearer token-user-b"}
    
    resp_b = client_b.get(f"/api/requirements/{session_id}", headers=headers_b)
    assert resp_b.status_code == 404
    assert resp_b.json()["detail"] == "Requirement session not found."


def test_same_owner_access_succeeds():
    os.environ["API_KEY"] = "token-user-a"
    client_a = TestClient(app)
    headers_a = {"Authorization": "Bearer token-user-a"}
    
    resp_a = client_a.post(
        "/api/requirements/start",
        json={"problem_statement": "We are a mid-size enterprise experiencing significant pain in our employee onboarding process. A new hire sits idle for 3 to 5 days waiting for IT provisioning and document sign-offs."},
        headers=headers_a
    )
    session_id = resp_a.json()["session_id"]

    # Same user accesses session
    resp_read = client_a.get(f"/api/requirements/{session_id}", headers=headers_a)
    assert resp_read.status_code == 200
    assert resp_read.json()["session_id"] == session_id


def test_cors_origins_header(monkeypatch):
    os.environ["API_KEY"] = "test-key-alpha-123"
    client = TestClient(app)
    headers = {
        "Origin": "http://localhost:8501",
        "Access-Control-Request-Method": "GET"
    }
    resp = client.options("/health", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:8501"
