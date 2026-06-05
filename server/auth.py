"""JWT authentication for the Rudi instructor API.

Credentials are stored in USER_DATA_DIR/credentials.json as a user list.
Old single-user files (pre-2026-06) are migrated automatically on first load.

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib only — no extra deps).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from server.config import DATA_DIR

_CREDENTIALS_FILE = DATA_DIR / "credentials.json"
_SECRET_FILE = DATA_DIR / "jwt_secret.txt"
_DEFAULT_USERNAME = "instructor"
_DEFAULT_PASSWORD = "rudi"
_TOKEN_HOURS = 24

_bearer = HTTPBearer(auto_error=False)

_jwt_secret: str | None = None
_users: list[dict] | None = None


# ── Password hashing ──────────────────────────────────────────────────────────

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


# ── User list ─────────────────────────────────────────────────────────────────

def _get_users() -> list[dict]:
    global _users
    if _users is not None:
        return _users
    if _CREDENTIALS_FILE.exists():
        try:
            data = json.loads(_CREDENTIALS_FILE.read_text())
            if "users" in data:
                _users = data["users"]
                return _users
            # Migrate old single-user format → promote to admin
            if "username" in data and "password_hash" in data:
                _users = [_make_user(
                    data["username"], data["password_hash"],
                    role="admin", active=True,
                )]
                _persist()
                return _users
        except Exception:
            pass
    # First run — create default admin
    _users = [_make_user(
        _DEFAULT_USERNAME, hash_password(_DEFAULT_PASSWORD),
        role="admin", active=True,
    )]
    _CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _persist()
    return _users


def _make_user(username: str, password_hash: str, *, role: str, active: bool) -> dict:
    return {
        "username": username,
        "password_hash": password_hash,
        "role": role,
        "active": active,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _persist() -> None:
    _CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CREDENTIALS_FILE.write_text(json.dumps({"users": _users}, indent=2))


def _find(username: str) -> dict | None:
    return next(
        (u for u in _get_users() if u["username"].lower() == username.lower()), None
    )


def _active_admin_count() -> int:
    return sum(1 for u in _get_users() if u.get("role") == "admin" and u.get("active", True))


# ── Public API ────────────────────────────────────────────────────────────────

def list_users() -> list[dict]:
    return [{k: v for k, v in u.items() if k != "password_hash"} for u in _get_users()]


def add_user(username: str, password: str, role: str = "instructor") -> dict:
    users = _get_users()
    if any(u["username"].lower() == username.lower() for u in users):
        raise ValueError(f"Username '{username}' is already taken")
    user = _make_user(username, hash_password(password), role=role, active=True)
    users.append(user)
    _persist()
    return {k: v for k, v in user.items() if k != "password_hash"}


def update_user(username: str, **kwargs: Any) -> dict:
    """Update active and/or role on a user. Guards against removing the last admin."""
    user = _find(username)
    if user is None:
        raise KeyError(username)
    if user.get("role") == "admin":
        would_demote = "role" in kwargs and kwargs["role"] != "admin"
        would_disable = "active" in kwargs and not kwargs["active"]
        if (would_demote or would_disable) and _active_admin_count() <= 1:
            raise ValueError("Cannot deactivate or demote the last active admin")
    for key, value in kwargs.items():
        if key in ("active", "role"):
            user[key] = value
    _persist()
    return {k: v for k, v in user.items() if k != "password_hash"}


def change_password(username: str, new_password: str) -> None:
    user = _find(username)
    if user is None:
        raise KeyError(username)
    user["password_hash"] = hash_password(new_password)
    _persist()


def delete_user(username: str) -> None:
    global _users
    user = _find(username)
    if user is None:
        raise KeyError(username)
    if user.get("role") == "admin" and _active_admin_count() <= 1:
        raise ValueError("Cannot delete the last active admin")
    _users = [u for u in _get_users() if u["username"].lower() != username.lower()]
    _persist()


# ── Token creation / validation ───────────────────────────────────────────────

def create_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_TOKEN_HOURS),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


def authenticate(username: str, password: str) -> tuple[str, str] | None:
    """Return (token, role) if credentials are valid and the user is active, else None."""
    user = _find(username)
    if user is None or not user.get("active", True):
        return None
    if not verify_password(password, user.get("password_hash", "")):
        return None
    role = user.get("role", "instructor")
    return create_token(user["username"], role), role


def verify_ws_token(token: str | None) -> bool:
    """Validate a raw JWT and confirm the user is still active."""
    if not token:
        return False
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
        user = _find(payload.get("sub", ""))
        return user is not None and user.get("active", True)
    except Exception:
        return False


# ── FastAPI dependencies ───────────────────────────────────────────────────────

def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Validates Bearer JWT and confirms the user is still active. Returns username."""
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
        username = payload["sub"]
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
    user = _find(username)
    if user is None or not user.get("active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username


def require_admin(username: str = Depends(require_auth)) -> str:
    """Layered on require_auth; additionally requires role == admin."""
    user = _find(username)
    if user is None or user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return username
