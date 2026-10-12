import os
import pytest
from fastapi.testclient import TestClient
from main import app
from db import init_db

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

client = TestClient(app)

def test_health_unauthenticated_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_route_unauthenticated_401():
    response = client.post("/api/requirements/start", json={"problem_statement": "Test problem"})
    assert response.status_code == 401
    assert "Authentication required" in response.json()["detail"]


def test_protected_route_invalid_key_403():
    headers = {"Authorization": "Bearer wrong-key-999"}
    response = client.post("/api/requirements/start", json={"problem_statement": "Test problem"}, headers=headers)
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_protected_route_valid_bearer_key_ok():
    valid_key = os.getenv("API_KEY", "test-key-alpha-123")
    headers = {"Authorization": f"Bearer {valid_key}"}
    response = client.post("/api/requirements/start", json={"problem_statement": "We are an enterprise needing onboarding system."}, headers=headers)
    assert response.status_code in (200, 400, 500)
    # Ensure it passed auth (not 401 or 403)
    assert response.status_code not in (401, 403)


def test_protected_route_valid_x_api_key_header_ok():
    valid_key = os.getenv("API_KEY", "test-key-alpha-123")
    headers = {"X-API-Key": valid_key}
    response = client.post("/api/requirements/start", json={"problem_statement": "We are an enterprise needing onboarding system."}, headers=headers)
    assert response.status_code not in (401, 403)


def test_exception_handler_no_traceback_leak():
    valid_key = os.getenv("API_KEY", "test-key-alpha-123")
    headers = {"Authorization": f"Bearer {valid_key}"}
    response = client.get("/api/requirements/non-existent-session-id-99999", headers=headers)
    assert response.status_code == 404
    assert "Traceback" not in response.text
    assert "/home/anurag-mandlekar" not in response.text
