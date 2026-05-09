"""JWT authentication for the Rudi instructor API.

Credentials are stored in USER_DATA_DIR/credentials.json.
Default login: instructor / rudi  (change by editing the file after first run).

Passwords are hashed with PBKDF2-HMAC-SHA256 using stdlib hashlib — no extra
dependencies beyond PyJWT (which is already required for token signing).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from server.config import USER_DATA_DIR

_CREDENTIALS_FILE = USER_DATA_DIR / "credentials.json"
_SECRET_FILE = USER_DATA_DIR / "jwt_secret.txt"
_DEFAULT_USERNAME = "instructor"
_DEFAULT_PASSWORD = "rudi"
_TOKEN_HOURS = 24

_bearer = HTTPBearer(auto_error=False)

# Module-level cache — loaded once on first use.
_jwt_secret: str | None = None
_credentials: dict | None = None


# ── Password hashing (PBKDF2, stdlib only) ────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"pbkdf2:{salt}:{key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash.startswith("pbkdf2:"):
        return False
    parts = stored_hash.split(":", 2)
    if len(parts) != 3:
        return False
    _, salt, stored_key = parts
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return hmac.compare_digest(key.hex(), stored_key)


# ── JWT secret ────────────────────────────────────────────────────────────────

def _get_jwt_secret() -> str:
    global _jwt_secret
    if _jwt_secret is not None:
        return _jwt_secret
    if _SECRET_FILE.exists():
        _jwt_secret = _SECRET_FILE.read_text().strip()
    else:
        _SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        _jwt_secret = secrets.token_hex(32)
        _SECRET_FILE.write_text(_jwt_secret)
    return _jwt_secret


# ── Credentials ───────────────────────────────────────────────────────────────

def _get_credentials() -> dict:
    global _credentials
    if _credentials is not None:
        return _credentials
    if _CREDENTIALS_FILE.exists():
        try:
            _credentials = json.loads(_CREDENTIALS_FILE.read_text())
            return _credentials
        except Exception:
            pass
    # First run: create default credentials file.
    _credentials = {
        "username": _DEFAULT_USERNAME,
        "password_hash": hash_password(_DEFAULT_PASSWORD),
    }
    _CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CREDENTIALS_FILE.write_text(json.dumps(_credentials, indent=2))
    return _credentials


def save_credentials(username: str, password: str) -> None:
    """Persist new credentials and clear the in-memory cache so they take effect."""
    global _credentials
    creds = {"username": username, "password_hash": hash_password(password)}
    _CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CREDENTIALS_FILE.write_text(json.dumps(creds, indent=2))
    _credentials = creds


# ── Token creation / validation ───────────────────────────────────────────────

def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_TOKEN_HOURS),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


def authenticate(username: str, password: str) -> str | None:
    """Return a JWT token if credentials are correct, else None."""
    creds = _get_credentials()
    if username != creds.get("username"):
        return None
    if not verify_password(password, creds.get("password_hash", "")):
        return None
    return create_token(username)


def verify_ws_token(token: str | None) -> bool:
    """Validate a raw JWT string (used for WebSocket query-param auth)."""
    if not token:
        return False
    try:
        jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
        return True
    except Exception:
        return False


# ── FastAPI dependency ────────────────────────────────────────────────────────

def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Dependency that validates a Bearer JWT. Returns the username on success."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials, _get_jwt_secret(), algorithms=["HS256"]
        )
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
