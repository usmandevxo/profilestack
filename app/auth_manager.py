import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Dict, Optional

from app.config import SESSIONS_FILE, USERS_FILE

COOKIE_NAME = "ps_session"
SESSION_DURATION_SECONDS = 86400 * 30  # 30 days


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    )
    return f"pbkdf2:sha256:100000${salt}${key.hex()}"


def _verify_password(password: str, hashed: str) -> bool:
    try:
        parts = hashed.split("$")
        if len(parts) != 3:
            return False
        algorithm, salt, expected_hash = parts
        calc_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100_000,
        ).hex()
        return hmac.compare_digest(calc_hash, expected_hash)
    except Exception:
        return False


def load_users() -> Dict[str, dict]:
    if USERS_FILE.exists():
        try:
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_users(users: Dict[str, dict]) -> None:
    tmp = str(USERS_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(users, f, indent=2)
    os.replace(tmp, USERS_FILE)


def init_default_user(username: str = "admin", password: str = "admin") -> None:
    users = load_users()
    existing_lower = {u.lower(): u for u in users.keys()}
    if username.lower() not in existing_lower:
        users[username] = {
            "username": username,
            "password_hash": _hash_password(password),
            "role": "admin",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "last_login": None,
        }
        save_users(users)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    users = load_users()
    target_user = None
    target_key = None
    for k, u in users.items():
        if k.lower() == username.strip().lower():
            target_user = u
            target_key = k
            break

    if not target_user:
        return None

    if not _verify_password(password, target_user.get("password_hash", "")):
        return None

    target_user["last_login"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    users[target_key] = target_user
    save_users(users)
    return target_user


# ── Session Management ────────────────────────────────────────────────────────
def load_sessions() -> Dict[str, dict]:
    if SESSIONS_FILE.exists():
        try:
            with open(SESSIONS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_sessions(sessions: Dict[str, dict]) -> None:
    tmp = str(SESSIONS_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(sessions, f, indent=2)
    os.replace(tmp, SESSIONS_FILE)


def purge_expired_sessions() -> None:
    sessions = load_sessions()
    now = time.time()
    valid = {k: v for k, v in sessions.items() if v.get("expires_at", 0) > now}
    if len(valid) != len(sessions):
        save_sessions(valid)


def create_session(username: str, ip_address: str = "", user_agent: str = "") -> str:
    purge_expired_sessions()
    sessions = load_sessions()
    token = secrets.token_urlsafe(32)
    sessions[token] = {
        "username": username,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "expires_at": time.time() + SESSION_DURATION_SECONDS,
    }
    save_sessions(sessions)
    return token


def validate_session(token: str) -> Optional[dict]:
    if not token or not isinstance(token, str):
        return None
    sessions = load_sessions()
    session = sessions.get(token)
    if not session:
        return None
    if session.get("expires_at", 0) < time.time():
        destroy_session(token)
        return None
    return session


def destroy_session(token: str) -> None:
    if not token:
        return
    sessions = load_sessions()
    if token in sessions:
        del sessions[token]
        save_sessions(sessions)

# [ProfileStack v1.27.2] revision checkpoint
