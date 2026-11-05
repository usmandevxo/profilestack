"""Persistent MCP credentials: high-entropy secrets, only SHA-256 digests at rest."""
import hashlib
import json
from app.key_policy import ALL_PERMISSIONS, validate_policy
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from typing import Optional
from app.config import DATA_DIR

DB_PATH = DATA_DIR / "api-keys.sqlite3"


@contextmanager
def _db():
    # Create privately before sqlite opens it; never expose a new DB with umask defaults.
    fd = os.open(DB_PATH, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)
    os.chmod(DB_PATH, 0o600)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        con.execute("CREATE TABLE IF NOT EXISTS api_keys (id TEXT PRIMARY KEY, name TEXT NOT NULL, prefix TEXT NOT NULL, digest TEXT NOT NULL UNIQUE, created_at REAL NOT NULL, expires_at REAL, last_used_at REAL, revoked_at REAL)")
        columns = {r[1] for r in con.execute("PRAGMA table_info(api_keys)")}
        for column, definition in [
            ('permissions', "TEXT NOT NULL DEFAULT '[" + ','.join(json.dumps(p) for p in ALL_PERMISSIONS) + "]'"),
            ('profile_access', "TEXT NOT NULL DEFAULT 'all'"),
            ('profiles', "TEXT NOT NULL DEFAULT '[]'"),
            ('folders', "TEXT NOT NULL DEFAULT '[]'"),
            ('owner', "TEXT NOT NULL DEFAULT 'admin'"),
        ]:
            if column not in columns:
                con.execute(f"ALTER TABLE api_keys ADD COLUMN {column} {definition}")
        con.execute("CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _default_owner() -> str:
    try:
        from app.auth_manager import load_users
        users = load_users()
        for u in users.values():
            if u.get("role") == "admin" and u.get("status") == "active":
                return u.get("username", "Usmandevx")
    except Exception:
        pass
    return "Usmandevx"


def _public(row):
    item = dict(row)
    item.pop("digest", None)
    item['permissions'] = json.loads(item['permissions'])
    item['profiles'] = json.loads(item['profiles'])
    item['folders'] = json.loads(item['folders']) if 'folders' in item and item['folders'] else []
    item['owner'] = item.get('owner') or _default_owner()
    item["status"] = "revoked" if item["revoked_at"] else "expired" if item["expires_at"] and item["expires_at"] <= time.time() else "active"
    return item


def create_key(name, expires_in_days, permissions=None, profile_access='all', profiles=None, folders=None, owner=None):
    policy = validate_policy(ALL_PERMISSIONS if permissions is None else permissions, profile_access, profiles or [], folders or [])
    raw = "psk_" + secrets.token_urlsafe(36)
    now = time.time()
    owner = (owner or _default_owner()).strip()
    if owner.lower() == 'admin':
        owner = _default_owner()
    item = (secrets.token_hex(12), name, raw[:12], hashlib.sha256(raw.encode()).hexdigest(), now, now + expires_in_days * 86400 if expires_in_days else None, owner)
    with _db() as con:
        con.execute("INSERT INTO api_keys (id,name,prefix,digest,created_at,expires_at,owner) VALUES (?,?,?,?,?,?,?)", item)
        con.execute(
            "UPDATE api_keys SET permissions=?,profile_access=?,profiles=?,folders=? WHERE id=?",
            (json.dumps(policy['permissions']), policy['profile_access'], json.dumps(policy['profiles']), json.dumps(policy['folders']), item[0]),
        )
        row = con.execute("SELECT * FROM api_keys WHERE id=?", (item[0],)).fetchone()
    return {"key": _public(row), "secret": raw}


def list_keys(owner: Optional[str] = None):
    with _db() as con:
        if owner:
            rows = con.execute("SELECT * FROM api_keys WHERE owner=? ORDER BY created_at DESC", (owner.strip(),)).fetchall()
        else:
            rows = con.execute("SELECT * FROM api_keys ORDER BY created_at DESC").fetchall()
    return [_public(row) for row in rows]


def get_key(key_id: str, owner: Optional[str] = None):
    with _db() as con:
        if owner:
            row = con.execute("SELECT * FROM api_keys WHERE id=? AND owner=?", (key_id, owner.strip())).fetchone()
        else:
            row = con.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
    return _public(row) if row else None


def rename_key(key_id, name, owner: Optional[str] = None):
    with _db() as con:
        if owner:
            cur = con.execute("UPDATE api_keys SET name=? WHERE id=? AND owner=?", (name, key_id, owner.strip()))
        else:
            cur = con.execute("UPDATE api_keys SET name=? WHERE id=?", (name, key_id))
        if not cur.rowcount:
            return None
        row = con.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
    return _public(row)


def revoke_key(key_id, owner: Optional[str] = None):
    with _db() as con:
        if owner:
            cur = con.execute("UPDATE api_keys SET revoked_at=COALESCE(revoked_at,?) WHERE id=? AND owner=?", (time.time(), key_id, owner.strip()))
        else:
            cur = con.execute("UPDATE api_keys SET revoked_at=COALESCE(revoked_at,?) WHERE id=?", (time.time(), key_id))
    return bool(cur.rowcount)


def legacy_enabled():
    with _db() as con:
        row = con.execute("SELECT value FROM settings WHERE name='legacy_disabled'").fetchone()
    return not row or row["value"] != "1"


def revoke_legacy():
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO settings (name,value) VALUES ('legacy_disabled','1')")


def validate_key(raw):
    if not raw or not raw.isascii() or len(raw) > 512:
        return False
    digest = hashlib.sha256(raw.encode()).hexdigest()
    now = time.time()
    with _db() as con:
        row = con.execute("SELECT id, owner FROM api_keys WHERE digest=? AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>?)", (digest, now)).fetchone()
        if not row:
            return False
        
        # Verify owner account status
        key_owner = row["owner"] if "owner" in row.keys() and row["owner"] else _default_owner()
        if key_owner.lower() == 'admin':
            key_owner = _default_owner()
        try:
            from app import auth_manager as auth
            user = auth.get_user(key_owner)
            if user and user.get("status") == "disabled":
                return False
        except Exception:
            pass

        con.execute("UPDATE api_keys SET last_used_at=? WHERE id=? AND (last_used_at IS NULL OR last_used_at<?)", (now, row["id"], now - 30))
    return True


def get_principal(raw):
    if not validate_key(raw):
        return None
    with _db() as con:
        row = con.execute("SELECT * FROM api_keys WHERE digest=?", (hashlib.sha256(raw.encode()).hexdigest(),)).fetchone()
    if not row:
        return None
    principal = _public(row)
    owner = principal.get("owner") or _default_owner()
    if owner.lower() == 'admin':
        owner = _default_owner()
    try:
        from app import auth_manager as auth
        user = auth.get_user(owner)
        if user:
            if user.get("status") == "disabled":
                return None
            principal["role"] = user.get("role", "user")
            if principal["role"] != "admin":
                user_mcp = user.get("mcp_access", {})
                allowed = user_mcp.get("allowed_permissions")
                if allowed is not None:
                    principal["permissions"] = [p for p in principal["permissions"] if p in allowed]
                principal["max_profiles"] = user_mcp.get("max_profiles", 0)
        else:
            principal["role"] = "admin" if owner.lower() in ("admin", "usmandevx") else "user"
    except Exception:
        pass
    return principal


def get_active_principal(key_id):
    with _db() as con:
        row = con.execute("SELECT * FROM api_keys WHERE id=? AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>?)", (key_id, time.time())).fetchone()
    if not row:
        return None
    principal = _public(row)
    owner = principal.get("owner", "admin")
    try:
        from app import auth_manager as auth
        user = auth.get_user(owner)
        if not user or user.get("status") == "disabled":
            return None
        principal["role"] = user.get("role", "user")
        if principal["role"] != "admin":
            user_mcp = user.get("mcp_access", {})
            allowed = user_mcp.get("allowed_permissions")
            if allowed is not None:
                principal["permissions"] = [p for p in principal["permissions"] if p in allowed]
            principal["max_profiles"] = user_mcp.get("max_profiles", 0)
    except Exception:
        pass
    return principal


def update_policy(key_id, permissions, profile_access, profiles, folders=None, owner: Optional[str] = None):
    policy = validate_policy(permissions, profile_access, profiles, folders or [])
    with _db() as con:
        if owner:
            cur = con.execute(
                "UPDATE api_keys SET permissions=?,profile_access=?,profiles=?,folders=? WHERE id=? AND owner=?",
                (json.dumps(policy['permissions']), policy['profile_access'], json.dumps(policy['profiles']), json.dumps(policy['folders']), key_id, owner.strip()),
            )
        else:
            cur = con.execute(
                "UPDATE api_keys SET permissions=?,profile_access=?,profiles=?,folders=? WHERE id=?",
                (json.dumps(policy['permissions']), policy['profile_access'], json.dumps(policy['profiles']), json.dumps(policy['folders']), key_id),
            )
        row = con.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
    return _public(row) if cur.rowcount else None


def assign_created_profile(key_id, profile_name):
    with _db() as con:
        row = con.execute("SELECT profiles,profile_access FROM api_keys WHERE id=?", (key_id,)).fetchone()
        if row and row['profile_access'] == 'selected':
            profiles = sorted(set(json.loads(row['profiles']) + [profile_name]))
            con.execute("UPDATE api_keys SET profiles=? WHERE id=?", (json.dumps(profiles), key_id))


def reassign_keys(old_owner: Optional[str], new_owner: str) -> int:
    with _db() as con:
        if old_owner:
            cur = con.execute("UPDATE api_keys SET owner = ? WHERE LOWER(owner) = LOWER(?)", (new_owner, old_owner.strip()))
        else:
            cur = con.execute("UPDATE api_keys SET owner = ?", (new_owner,))
        return cur.rowcount
