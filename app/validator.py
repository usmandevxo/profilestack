import os
import re
from pathlib import Path
from typing import Union
from app.config import PROFILES_DIR

_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_FOLDER_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_PROXY_RE = re.compile(
    r"^(socks5|socks5h|http|https)://(?:([^:@/]+)(?::([^:@/]+))?@)?([a-zA-Z0-9._-]+):(\d{1,5})$"
)


def validate_profile_name(name: str) -> str:
    if not name or not isinstance(name, str):
        raise ValueError("Profile name must be a non-empty string.")
    name = name.strip()
    if not _NAME_RE.match(name):
        raise ValueError(
            "Invalid profile name. Allowed: letters, numbers, dash (-) and underscore (_), max 64 chars."
        )
    return name


def validate_folder_id(folder_id: str) -> str:
    if not folder_id or not isinstance(folder_id, str):
        raise ValueError("Folder ID must be a non-empty string.")
    folder_id = folder_id.strip().lower()
    if not _FOLDER_RE.match(folder_id):
        raise ValueError(
            "Invalid folder ID. Allowed: letters, numbers, dash (-) and underscore (_), max 64 chars."
        )
    return folder_id


def validate_folder_name(name: str) -> str:
    if not name or not isinstance(name, str):
        raise ValueError("Folder name must be a non-empty string.")
    name = name.strip()
    if len(name) < 1 or len(name) > 64:
        raise ValueError("Folder name must be between 1 and 64 characters.")
    return name


def safe_profile_path(name: str, folder: str = "", base_dir: Path = PROFILES_DIR) -> Path:
    name = validate_profile_name(name)
    base_resolved = base_dir.resolve()
    if folder:
        f_clean = validate_folder_id(folder)
        candidate = (base_dir / f_clean / name).resolve()
    else:
        candidate = (base_dir / name).resolve()

    try:
        if not candidate.is_relative_to(base_resolved):
            raise ValueError(f"Profile path escapes managed directory: {candidate}")
    except AttributeError:
        if not str(candidate).startswith(str(base_resolved) + os.sep) and candidate != base_resolved:
            raise ValueError(f"Profile path escapes managed directory: {candidate}")
    return candidate


def fix_profile_permissions(profile_path: Union[str, Path]) -> None:
    path = Path(profile_path)
    if not path.is_dir():
        return
    try:
        os.chmod(path, 0o777)
    except Exception:
        pass
    for root, dirs, files in os.walk(path):
        for d in dirs:
            try:
                os.chmod(os.path.join(root, d), 0o777)
            except Exception:
                pass
        for f in files:
            try:
                os.chmod(os.path.join(root, f), 0o666)
            except Exception:
                pass


def clean_stale_locks(profile_path: Union[str, Path]) -> None:
    p = Path(profile_path)
    if not p.is_dir():
        return
    for lock_name in ["SingletonLock", "SingletonCookie", "SingletonSocket", "LOCK"]:
        for target in [p / lock_name, p / "Default" / lock_name]:
            try:
                if target.is_symlink() or target.exists():
                    target.unlink(missing_ok=True)
            except Exception:
                pass


def validate_proxy_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not _PROXY_RE.match(url):
        raise ValueError(
            "Invalid proxy format. Use e.g. socks5://127.0.0.1:1080 or http://user:pass@host:port"
        )
    return url


def parse_proxy(proxy_url: str):
    url = (proxy_url or "").strip()
    if not url:
        return None
    m = _PROXY_RE.match(url)
    if not m:
        return None
    scheme, user, pwd, host, port = m.groups()
    return {
        "scheme": scheme,
        "user": user or "",
        "pass": pwd or "",
        "host": host,
        "port": int(port),
    }

# [ProfileStack v1.6.74] revision checkpoint
