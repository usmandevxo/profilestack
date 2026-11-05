import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Dict, List, Optional

from app.config import SESSIONS_FILE, USERS_FILE

COOKIE_NAME = "ps_session"
SESSION_DURATION_SECONDS = 86400 * 30  # 30 days

DEFAULT_MCP_PRESETS = {
    "standard": [
        "profiles.read", "profiles.create", "profiles.update", "profiles.delete",
        "lifecycle.start", "lifecycle.stop", "lifecycle.restart",
        "browser.read", "browser.control",
        "folders.read", "folders.manage"
    ],
    "full": [
        "profiles.read", "profiles.create", "profiles.update", "profiles.delete",
        "lifecycle.start", "lifecycle.stop", "lifecycle.restart",
        "browser.read", "browser.control",
        "folders.read", "folders.manage",
        "proxies.read", "proxies.manage", "system.read"
    ],
    "readonly": [
        "profiles.read", "browser.read", "folders.read"
    ]
}


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


def _normalize_mcp_access(role: str, mcp_access: Optional[dict] = None) -> dict:
    if not isinstance(mcp_access, dict):
        preset = "full" if role == "admin" else "standard"
        return {
            "profile_preset": preset,
            "allowed_permissions": list(DEFAULT_MCP_PRESETS.get(preset, DEFAULT_MCP_PRESETS["standard"])),
            "max_profiles": 0
        }
    preset = mcp_access.get("profile_preset", "custom")
    allowed = mcp_access.get("allowed_permissions")
    if allowed is None:
        if preset in DEFAULT_MCP_PRESETS:
            allowed = list(DEFAULT_MCP_PRESETS[preset])
        else:
            allowed = list(DEFAULT_MCP_PRESETS["full"] if role == "admin" else DEFAULT_MCP_PRESETS["standard"])
    return {
        "profile_preset": preset,
        "allowed_permissions": list(allowed),
        "max_profiles": max(0, int(mcp_access.get("max_profiles", 0) or 0))
    }


def _sanitize_user(user: dict) -> dict:
    sanitized = dict(user)
    sanitized.pop("password_hash", None)
    sanitized.setdefault("status", "active")
    sanitized.setdefault("role", "user")
    sanitized["mcp_access"] = _normalize_mcp_access(sanitized["role"], sanitized.get("mcp_access"))
    return sanitized


def load_users() -> Dict[str, dict]:
    users: Dict[str, dict] = {}
    if USERS_FILE.exists():
        try:
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
        except (json.JSONDecodeError, OSError):
            users = {}

    modified = False
    for k, u in list(users.items()):
        if not isinstance(u, dict):
            continue
        if "status" not in u:
            u["status"] = "active"
            modified = True
        if "role" not in u:
            u["role"] = "admin" if k.lower() == "admin" else "user"
            modified = True
        if "mcp_access" not in u:
            u["mcp_access"] = _normalize_mcp_access(u["role"], None)
            modified = True
    if modified:
        try:
            save_users(users)
        except Exception:
            pass
    return users


def save_users(users: Dict[str, dict]) -> None:
    tmp = str(USERS_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(users, f, indent=2)
    os.replace(tmp, USERS_FILE)


def init_default_user(username: str = "admin", password: str = "admin") -> None:
    users = load_users()
    if not users:
        users[username] = {
            "username": username,
            "password_hash": _hash_password(password),
            "role": "admin",
            "status": "active",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "last_login": None,
            "mcp_access": _normalize_mcp_access("admin", {"profile_preset": "full"})
        }
        save_users(users)


def list_users() -> List[dict]:
    users = load_users()
    return [_sanitize_user(u) for u in users.values() if isinstance(u, dict)]


def get_user(username: str) -> Optional[dict]:
    if not username:
        return None
    users = load_users()
    for k, u in users.items():
        if k.lower() == username.strip().lower() and isinstance(u, dict):
            return _sanitize_user(u)
    return None


def get_user_internal(username: str) -> Optional[dict]:
    if not username:
        return None
    users = load_users()
    for k, u in users.items():
        if k.lower() == username.strip().lower() and isinstance(u, dict):
            u_copy = dict(u)
            u_copy.setdefault("status", "active")
            u_copy.setdefault("role", "user")
            u_copy["mcp_access"] = _normalize_mcp_access(u_copy["role"], u_copy.get("mcp_access"))
            return u_copy
    return None


def is_admin(user_or_username) -> bool:
    if isinstance(user_or_username, dict):
        return user_or_username.get("role") == "admin"
    if isinstance(user_or_username, str):
        u = get_user(user_or_username)
        return bool(u and u.get("role") == "admin")
    return False


def create_user(
    username: str,
    password: str,
    role: str = "user",
    status: str = "active",
    mcp_profile: Optional[str] = "standard",
    mcp_access: Optional[dict] = None,
    notes: str = ""
) -> dict:
    username = (username or "").strip()
    if not re.match(r"^[a-zA-Z0-9_\-\.]{3,32}$", username):
        raise ValueError("Username must be 3-32 characters (letters, numbers, underscore, hyphen, dot).")

    if not password or len(password) < 5:
        raise ValueError("Password must be at least 5 characters.")

    role = role.lower().strip()
    if role not in ("admin", "user"):
        raise ValueError("Role must be 'admin' or 'user'.")

    status = status.lower().strip()
    if status not in ("active", "disabled"):
        raise ValueError("Status must be 'active' or 'disabled'.")

    users = load_users()
    for existing in users.keys():
        if existing.lower() == username.lower():
            raise ValueError(f"User '{username}' already exists.")

    access_dict = dict(mcp_access or {})
    if mcp_profile:
        access_dict.setdefault("profile_preset", mcp_profile)
    normalized_mcp = _normalize_mcp_access(role, access_dict)
    preset_name = normalized_mcp.get("profile_preset", mcp_profile or "standard")

    now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    user_record = {
        "username": username,
        "password_hash": _hash_password(password),
        "role": role,
        "status": status,
        "mcp_profile": preset_name,
        "notes": notes or "",
        "created_at": now_str,
        "last_login": None,
        "mcp_access": normalized_mcp
    }
    users[username] = user_record
    save_users(users)

    # Initialize user default category/folder
    try:
        from app import folder_manager as fm
        folders = fm.load_folders(owner=username)
        if not folders:
            fm.create_folder(
                name="General",
                description=f"Default category for {username}",
                color="#64748b",
                folder_id=f"general-{username.lower()}",
                owner=username
            )
    except Exception:
        pass

    return _sanitize_user(user_record)


def update_user(
    username: str,
    role: Optional[str] = None,
    status: Optional[str] = None,
    mcp_profile: Optional[str] = None,
    mcp_access: Optional[dict] = None,
    password: Optional[str] = None,
    notes: Optional[str] = None
) -> dict:
    users = load_users()
    target_key = None
    target_user = None
    for k, u in users.items():
        if k.lower() == username.strip().lower():
            target_key = k
            target_user = u
            break

    if not target_user or not target_key:
        raise ValueError(f"User '{username}' not found.")

    # Guard: prevent removing the last active admin
    if (role and role != "admin") or (status and status == "disabled"):
        if target_user.get("role") == "admin":
            active_admins = [
                u for u in users.values()
                if u.get("role") == "admin" and u.get("status", "active") == "active"
                and u.get("username", "").lower() != username.lower()
            ]
            if not active_admins:
                raise ValueError("Cannot disable or demote the last remaining active administrator.")

    if role:
        role = role.lower().strip()
        if role not in ("admin", "user"):
            raise ValueError("Role must be 'admin' or 'user'.")
        target_user["role"] = role

    if status:
        status = status.lower().strip()
        if status not in ("active", "disabled"):
            raise ValueError("Status must be 'active' or 'disabled'.")
        target_user["status"] = status
        if status == "disabled":
            destroy_all_user_sessions(username)

    if notes is not None:
        target_user["notes"] = notes

    if mcp_profile or mcp_access is not None:
        access_dict = dict(mcp_access or target_user.get("mcp_access", {}))
        if mcp_profile:
            access_dict["profile_preset"] = mcp_profile
        target_user["mcp_access"] = _normalize_mcp_access(target_user.get("role", "user"), access_dict)
        target_user["mcp_profile"] = target_user["mcp_access"].get("profile_preset", mcp_profile or "standard")

    if password:
        if len(password) < 5:
            raise ValueError("Password must be at least 5 characters.")
        target_user["password_hash"] = _hash_password(password)

    users[target_key] = target_user
    save_users(users)
    return _sanitize_user(target_user)


def admin_reset_password(username: str, new_password: str, preserve_token: Optional[str] = None) -> None:
    users = load_users()
    target_key = None
    target_user = None
    for k, u in users.items():
        if k.lower() == username.strip().lower():
            target_key = k
            target_user = u
            break

    if not target_user or not target_key:
        raise ValueError("User not found.")

    if not new_password or len(new_password) < 5:
        raise ValueError("New password must be at least 5 characters.")

    target_user["password_hash"] = _hash_password(new_password)
    users[target_key] = target_user
    save_users(users)
    destroy_all_user_sessions(username, except_token=preserve_token)


def delete_user(username: str, current_username: Optional[str] = None, reassign_to: Optional[str] = None) -> bool:
    username = username.strip()
    if current_username and username.lower() == current_username.strip().lower():
        raise ValueError("You cannot delete your own active administrator account.")

    users = load_users()
    target_key = None
    target_user = None
    for k, u in users.items():
        if k.lower() == username.lower():
            target_key = k
            target_user = u
            break

    if not target_user or not target_key:
        raise ValueError(f"User '{username}' not found.")

    if target_user.get("role") == "admin":
        active_admins = [
            u for u in users.values()
            if u.get("role") == "admin" and u.get("username", "").lower() != username.lower() and u.get("status", "active") == "active"
        ]
        if not active_admins:
            raise ValueError("Cannot delete the only administrator account.")

    # 1. Terminate all active sessions immediately
    destroy_all_user_sessions(username)

    if reassign_to:
        target_reassign_user = get_user(reassign_to)
        if not target_reassign_user:
            raise ValueError(f"Target reassign user '{reassign_to}' does not exist.")
        reassign_name = target_reassign_user["username"]

        try:
            from app import api_key_store as store
            store.reassign_keys(old_owner=username, new_owner=reassign_name)
        except Exception:
            pass

        try:
            from app import profile_manager as pm
            pm.reassign_profiles(old_owner=username, new_owner=reassign_name)
        except Exception:
            pass

        try:
            from app import folder_manager as fm
            fm.reassign_folders(old_owner=username, new_owner=reassign_name)
        except Exception:
            pass
    else:
        # 2. Revoke all user API keys
        try:
            from app import api_key_store as store
            user_keys = store.list_keys(owner=username)
            for k in user_keys:
                store.revoke_key(k["id"])
        except Exception:
            pass

        # 3. Clean up user's profiles and folders
        try:
            from app import profile_manager as pm
            user_profiles = pm.list_profiles(owner=username)
            for p in user_profiles:
                try:
                    pm.delete_profile(p["name"])
                except Exception:
                    pass
        except Exception:
            pass

        try:
            from app import folder_manager as fm
            folders = fm.load_folders(owner=username)
            for f in folders:
                try:
                    fm.delete_folder(f["id"])
                except Exception:
                    pass
        except Exception:
            pass

    # 4. Remove from users store
    del users[target_key]
    save_users(users)
    return True


def change_user_password(username: str, current_password: str, new_password: str) -> None:
    users = load_users()
    target_key = None
    target_user = None
    for k, u in users.items():
        if k.lower() == username.strip().lower():
            target_key = k
            target_user = u
            break

    if not target_user or not target_key:
        raise ValueError("User not found.")

    if not _verify_password(current_password, target_user.get("password_hash", "")):
        raise ValueError("Incorrect current password.")

    if not new_password or len(new_password) < 5:
        raise ValueError("New password must be at least 5 characters.")

    target_user["password_hash"] = _hash_password(new_password)
    users[target_key] = target_user
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

    if target_user.get("status") == "disabled":
        return None

    if not _verify_password(password, target_user.get("password_hash", "")):
        return None

    target_user["last_login"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    users[target_key] = target_user
    save_users(users)
    return _sanitize_user(target_user)


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


def destroy_all_user_sessions(username: str, except_token: Optional[str] = None) -> None:
    if not username:
        return
    sessions = load_sessions()
    filtered = {
        token: s for token, s in sessions.items()
        if (s.get("username", "").lower() != username.strip().lower()) or (except_token and token == except_token)
    }
    if len(filtered) != len(sessions):
        save_sessions(filtered)


def create_session(username: str, ip_address: str = "", user_agent: str = "") -> str:
    purge_expired_sessions()
    sessions = load_sessions()
    token = secrets.token_urlsafe(32)
    user = get_user(username)
    role = user.get("role", "user") if user else "user"
    sessions[token] = {
        "username": username,
        "role": role,
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

    # Verify user existence and active status
    username = session.get("username", "")
    user = get_user(username)
    if not user or user.get("status") == "disabled":
        destroy_session(token)
        return None

    session["role"] = user.get("role", "user")
    session["mcp_access"] = user.get("mcp_access", {})
    return session


def destroy_session(token: str) -> None:
    if not token:
        return
    sessions = load_sessions()
    if token in sessions:
        del sessions[token]
        save_sessions(sessions)


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage:")
        print("  python3 -m app.auth_manager list")
        print("  python3 -m app.auth_manager reset <username> <new_password>")
        print("  python3 -m app.auth_manager add <username> <password> [role]")
        print("  python3 -m app.auth_manager delete <username> [--reassign <target>]")
        sys.exit(0)

    cmd = args[0]
    if cmd == "list":
        for u in list_users():
            print(f"- {u['username']} (role={u['role']}, status={u['status']}, mcp={u.get('mcp_profile')})")
    elif cmd == "reset":
        if len(args) < 3:
            print("Error: Missing arguments. Usage: python3 -m app.auth_manager reset <username> <new_password>")
            sys.exit(1)
        target = args[1]
        pwd = args[2]
        admin_reset_password(target, pwd)
        print(f"Password reset successfully for user '{target}'.")
    elif cmd == "add":
        if len(args) < 3:
            print("Error: Missing arguments. Usage: python3 -m app.auth_manager add <username> <password> [role]")
            sys.exit(1)
        target = args[1]
        pwd = args[2]
        user_role = args[3] if len(args) > 3 else "user"
        create_user(target, pwd, role=user_role)
        print(f"User '{target}' created with role '{user_role}'.")
    elif cmd == "delete":
        if len(args) < 2:
            print("Error: Missing argument. Usage: python3 -m app.auth_manager delete <username> [--reassign <target>]")
            sys.exit(1)
        target = args[1]
        reassign = None
        if len(args) >= 4 and args[2] in ("--reassign", "--reassign-to"):
            reassign = args[3]
        delete_user(target, reassign_to=reassign)
        msg = f"User '{target}' deleted successfully."
        if reassign:
            msg += f" Profiles and resources reassigned to '{reassign}'."
        print(msg)
    else:
        print(f"Unknown command '{cmd}'. Run with --help for usage.")
        sys.exit(1)

