"""Persistent MCP credentials: high-entropy secrets, only SHA-256 digests at rest."""
import hashlib
import json
from app.key_policy import ALL_PERMISSIONS, validate_policy
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
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


def _public(row):
    item = dict(row)
    item.pop("digest", None)
    item['permissions'] = json.loads(item['permissions'])
    item['profiles'] = json.loads(item['profiles'])
    item['folders'] = json.loads(item['folders']) if 'folders' in item and item['folders'] else []
    item["status"] = "revoked" if item["revoked_at"] else "expired" if item["expires_at"] and item["expires_at"] <= time.time() else "active"
    return item


def create_key(name, expires_in_days, permissions=None, profile_access='all', profiles=None, folders=None):
    policy = validate_policy(ALL_PERMISSIONS if permissions is None else permissions, profile_access, profiles or [], folders or [])
    raw = "psk_" + secrets.token_urlsafe(36)
    now = time.time()
    item = (secrets.token_hex(12), name, raw[:12], hashlib.sha256(raw.encode()).hexdigest(), now, now + expires_in_days * 86400 if expires_in_days else None)
    with _db() as con:
        con.execute("INSERT INTO api_keys (id,name,prefix,digest,created_at,expires_at) VALUES (?,?,?,?,?,?)", item)
        con.execute(
            "UPDATE api_keys SET permissions=?,profile_access=?,profiles=?,folders=? WHERE id=?",
            (json.dumps(policy['permissions']), policy['profile_access'], json.dumps(policy['profiles']), json.dumps(policy['folders']), item[0]),
        )
        row = con.execute("SELECT * FROM api_keys WHERE id=?", (item[0],)).fetchone()
    return {"key": _public(row), "secret": raw}


def list_keys():
    with _db() as con:
        rows = con.execute("SELECT * FROM api_keys ORDER BY created_at DESC").fetchall()
    return [_public(row) for row in rows]


def rename_key(key_id, name):
    with _db() as con:
        cur = con.execute("UPDATE api_keys SET name=? WHERE id=?", (name, key_id))
        if not cur.rowcount:
            return None
        row = con.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
    return _public(row)


def revoke_key(key_id):
    with _db() as con:
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
        row = con.execute("SELECT id FROM api_keys WHERE digest=? AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>?)", (digest, now)).fetchone()
        if not row:
            return False
        con.execute("UPDATE api_keys SET last_used_at=? WHERE id=? AND (last_used_at IS NULL OR last_used_at<?)", (now, row["id"], now - 30))
    return True


def get_principal(raw):
    if not validate_key(raw):
        return None
    with _db() as con:
        row = con.execute("SELECT * FROM api_keys WHERE digest=?", (hashlib.sha256(raw.encode()).hexdigest(),)).fetchone()
    return _public(row) if row else None


def get_active_principal(key_id):
    with _db() as con:
        row = con.execute("SELECT * FROM api_keys WHERE id=? AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>?)", (key_id, time.time())).fetchone()
    return _public(row) if row else None


def update_policy(key_id, permissions, profile_access, profiles, folders=None):
    policy = validate_policy(permissions, profile_access, profiles, folders or [])
    with _db() as con:
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
