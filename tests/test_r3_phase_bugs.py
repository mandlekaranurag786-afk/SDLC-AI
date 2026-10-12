import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app
import os
from db import get_db, create_requirement_session, add_pending_questions, RequirementSession

client = TestClient(app)

def test_start_idempotency_duplicate_calls(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    headers = {"Authorization": "Bearer test-key"}
    
    payload = {"problem_statement": "We are a mid-size enterprise and our employee onboarding is manual across HR, IT and reporting managers, with no real-time visibility, delayed asset provisioning and scattered meeting scheduling."}
    with patch("main.run_decision_and_maybe_questions") as m_run:
        m_run.return_value = {"pending_questions": {"round": 1, "questions": [{"id": "q1", "question": "test?", "category": "scope", "field": "f"}]}}
        res1 = client.post("/api/requirements/start", json=payload, headers=headers)
        assert res1.status_code == 200
        sess1 = res1.json()["session_id"]
        
        # Immediate second request
        res2 = client.post("/api/requirements/start", json=payload, headers=headers)
        assert res2.status_code == 200
        sess2 = res2.json()["session_id"]
        
        # session id should be exactly the same
        assert sess1 == sess2

def test_wrong_round_answer_error(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    headers = {"Authorization": "Bearer test-key"}
    
    with get_db() as db_session:
        s = create_requirement_session(db_session, "Another unique string")
        add_pending_questions(db_session, s, 3, {"round": 3, "questions": [{"id": "q1", "question": "test?", "category": "scope", "field": "f"}]})
        db_session.commit()
        sid = s.id
        
    res = client.post(f"/api/requirements/{sid}/answer-questions", json={"round": 1, "answers": []}, headers=headers)
    assert res.status_code == 400
    assert "Expected answers for round 3" in res.json()["detail"]

def test_answer_questions_empty_pending_conflict_409(monkeypatch):
    # If the user tries to answer questions but none are pending
    monkeypatch.setenv("API_KEY", "test-key")
    headers = {"Authorization": "Bearer test-key"}
    
    with get_db() as db_session:
        s = create_requirement_session(db_session, "Yet another unique string")
        s.pending_questions = None
        db_session.commit()
        sid = s.id
        
    res = client.post(f"/api/requirements/{sid}/answer-questions", json={"round": 1, "answers": []}, headers=headers)
    assert res.status_code == 409
    assert "not currently waiting" in res.json()["detail"]

def test_mocked_p2_07_happy_path(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    headers = {"Authorization": "Bearer test-key"}
    
    payload = {"problem_statement": "We are a mid-size enterprise and our employee onboarding is manual across HR, IT and reporting managers, with no real-time visibility, delayed asset provisioning and scattered meeting scheduling."}
    with patch("main.run_decision_and_maybe_questions") as m_run:
        # First round /start
        m_run.return_value = {"pending_questions": {"round": 1, "questions": [{"id": "q1", "question": "test?", "category": "scope", "field": "f"}]}}
        res1 = client.post("/api/requirements/start", json=payload, headers=headers)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "asking_questions"
        sid = data1["session_id"]
        assert len(data1["questions"]) == 1
        
        # Second round /answer-questions resolving it (mocking to return ready_for_generation)
        m_run.return_value = {"current_phase": "ready_for_generation", "pending_questions": None}
        ans = client.post(f"/api/requirements/{sid}/answer-questions", json={"round": 1, "answers": [{"q_id": "q1", "answer": "resolved"}]}, headers=headers)
        assert ans.status_code == 200
        data2 = ans.json()
        assert data2["status"] == "ready_for_generation"
