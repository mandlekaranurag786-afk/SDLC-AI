import hashlib
import hmac
import os
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

PUBLIC_PATHS = {"/health", "/api/health", "/docs", "/openapi.json", "/redoc"}
security_bearer = HTTPBearer(auto_error=False)


def _ordered_api_keys() -> list[str]:
    """API_KEY may hold several comma-separated keys. Order is preserved."""
    raw = os.getenv("API_KEY", "")
    if not raw or not raw.strip():
        raise RuntimeError("API_KEY environment variable is required. App cannot process requests without API_KEY set.")
    keys: list[str] = []
    for k in raw.split(","):
        k = k.strip()
        if k and k not in keys:
            keys.append(k)
    if not keys:
        raise RuntimeError("API_KEY environment variable is empty. At least one valid API key must be defined.")
    return keys


def get_valid_api_keys() -> set[str]:
    # kept for existing callers (startup check in main.py, tests)
    return set(_ordered_api_keys())


def get_api_key() -> str:
    """First configured key, deterministic across processes."""
    return _ordered_api_keys()[0]


def _is_valid_key(token: str, keys: list[str]) -> bool:
    ok = False
    for k in keys:  # check every key, no early exit
        if hmac.compare_digest(token.encode("utf-8"), k.encode("utf-8")):
            ok = True
    return ok


def get_owner_id_from_token(token: str) -> str:
    """
    Interface for deriving owner_id from the auth token.
    Replace with the Entra ID user object id / JWT claim later.
    OWNER_ID_SALT (optional env var) makes the hash depend on a server secret.
    """
    if not token:
        return "anonymous"
    salt = os.getenv("OWNER_ID_SALT", "")
    hashed = hashlib.sha256((salt + token).encode("utf-8")).hexdigest()[:16]
    return f"owner_{hashed}"


def verify_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> str:
    """
    Verifies a Bearer token or X-API-Key header against the API_KEY env var.
    Public health/docs paths are exempt.
    Returns 401 for both a missing and an invalid credential.
    """
    if request.url.path in PUBLIC_PATHS:
        return "public"

    keys = _ordered_api_keys()

    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials.strip()
    elif x_api_key:
        token = x_api_key.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not _is_valid_key(token, keys):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    owner_id = get_owner_id_from_token(token)
    request.state.owner_id = owner_id
    return owner_id