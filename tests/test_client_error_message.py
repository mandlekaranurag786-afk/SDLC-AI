from streamlit_app.api_client import _error_message


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_auth_failure_shows_ui_hint():
    msg = _error_message(FakeResponse(401, {"detail": "Invalid API key"}))
    assert "matches on server and UI" in msg


def test_forbidden_also_shows_ui_hint():
    msg = _error_message(FakeResponse(403, {"detail": "Forbidden"}))
    assert "matches on server and UI" in msg


def test_other_errors_keep_server_detail():
    msg = _error_message(FakeResponse(400, {"detail": "Expected answers for round 2"}))
    assert msg == "Expected answers for round 2"
