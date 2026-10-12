#api_client.py
import time
from typing import Any
from urllib.parse import urljoin

import os
from dotenv import load_dotenv
import requests

from config import API_BASE_URL, GENERATION_TIMEOUT_SECONDS, MAX_RETRIES, REQUEST_TIMEOUT_SECONDS


class ApiClientError(RuntimeError):
    pass

from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

def _client_api_key() -> str:
    raw = os.getenv("API_KEY", "")
    key = raw.split(",")[0].strip()
    if not key:
        raise ApiClientError("API_KEY is not set. Add it to .env before starting the UI.")
    return key

def _request(method: str, path: str, *, timeout: int, **kwargs) -> requests.Response:
    url = urljoin(API_BASE_URL, path)
    headers = kwargs.pop("headers", {})
    if "Authorization" not in headers and "X-API-Key" not in headers:
        headers["Authorization"] = f"Bearer {_client_api_key()}"
    last_error: Exception | None = None 
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
            if response.status_code >= 400:
                raise ApiClientError(_error_message(response))
            return response
        except (requests.RequestException, ApiClientError) as exc:
            last_error = exc
            if attempt == MAX_RETRIES - 1 or isinstance(exc, ApiClientError):
                break
            time.sleep(2**attempt)
    raise ApiClientError(str(last_error) if last_error else "Unable to reach API.")


def _error_message(response: requests.Response) -> str:
    if response.status_code in (401, 403):
        return "Authentication failed: check that API_KEY in .env matches on server and UI."
    try:
        payload = response.json()
        detail = payload.get("detail")
        if isinstance(detail, list):
            return "; ".join(str(item) for item in detail)
        return str(detail or payload)
    except ValueError:
        return response.text or f"API returned HTTP {response.status_code}."


def start_requirements(problem_statement: str) -> dict[str, Any]:
    response = _request(
        "POST",
        "/api/requirements/start",
        json={"problem_statement": problem_statement},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    return response.json()


def answer_questions(session_id: str, round_num: int, answers: list[dict[str, str]]) -> dict[str, Any]:
    response = _request(
        "POST",
        f"/api/requirements/{session_id}/answer-questions",
        json={"round": round_num, "answers": answers},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    return response.json()


def generate_documents(session_id: str) -> dict[str, Any]:
    response = _request(
        "POST",
        f"/api/requirements/{session_id}/generate",
        json={"approval_type": "both"},
        timeout=GENERATION_TIMEOUT_SECONDS,
    )
    return response.json()


def download_docx(session_id: str, doc_type: str) -> bytes:
    response = _request(
        "GET",
        f"/api/requirements/{session_id}/download/{doc_type}",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    return response.content


def get_session_state(session_id: str) -> dict[str, Any]:
    response = _request(
        "GET",
        f"/api/requirements/{session_id}",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    return response.json()


def generate_prototype(session_id: str) -> dict[str, Any]:
    """POST /api/requirements/{session_id}/prototype"""
    response = _request(
        "POST",
        f"/api/requirements/{session_id}/prototype",
        timeout=GENERATION_TIMEOUT_SECONDS,
    )
    return response.json()


def download_estimation(session_id: str) -> bytes:
    """GET /api/requirements/{session_id}/download/estimation"""
    response = _request(
        "GET",
        f"/api/requirements/{session_id}/download/estimation",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    return response.content


def download_prototype_html(session_id: str) -> bytes:
    """GET /api/requirements/{session_id}/download/prototype"""
    response = _request(
        "GET",
        f"/api/requirements/{session_id}/download/prototype",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    return response.content


def download_epics_stories(session_id: str) -> bytes:
    """GET /api/requirements/{session_id}/download/epics-stories"""
    response = _request(
        "GET",
        f"/api/requirements/{session_id}/download/epics-stories",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    return response.content
