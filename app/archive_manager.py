import os
import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from app.config import ARCHIVES_DIR, PROFILES_DIR
from app.profile_manager import _load_registry, _save_registry, _get_dir_size_mb
from app.validator import clean_stale_locks, fix_profile_permissions, validate_profile_name

_EXCLUDE_DIRS = {
    "Cache",
    "Code Cache",
    "GPUCache",
    "ShaderCache",
    "GrShaderCache",
    "GraphiteDawnCache",
    "DawnWebGPUCache",
    "DawnGraphiteCache",
    "component_crx_cache",
    "OnDeviceHeadSuggestModel",
    "hyphen-data",
    "ZxcvbnData",
    "Crashpad",
    "Crash Reports",
}
_EXCLUDE_FILES = {"SingletonLock", "SingletonCookie", "SingletonSocket", "Lock", "LOCK"}


def _safe_member_path(member_path: str) -> str:
    if os.path.isabs(member_path):
        raise ValueError(f"Absolute path in archive: {member_path}")
    parts = PurePosixPath(member_path).parts
    if any(p == ".." for p in parts):
        raise ValueError(f"Path traversal detected: {member_path}")
    return member_path


def export_profile_zip(profile_name: str) -> Path:
    profile_name = validate_profile_name(profile_name)
    reg = _load_registry()
    if profile_name not in reg:
        raise ValueError(f"Profile '{profile_name}' not found.")

    p_dir = Path(reg[profile_name]["path"])
    if not p_dir.is_dir():
        raise FileNotFoundError(f"Directory not found: {p_dir}")

    ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
    out_zip = ARCHIVES_DIR / f"{profile_name}.zip"

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(p_dir):
            dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
            for fname in files:
                if fname in _EXCLUDE_FILES:
                    continue
                fpath = os.path.join(root, fname)
                if os.path.islink(fpath):
                    continue
                if not os.path.isfile(fpath):
                    continue
                try:
                    rel_path = os.path.relpath(fpath, p_dir)
                    zf.write(fpath, rel_path)
                except (OSError, PermissionError):
                    continue

    return out_zip


def import_profile_zip(archive_path: Path) -> dict:
    if not archive_path.is_file():
        raise FileNotFoundError(f"Archive file not found: {archive_path}")

    tmp_dir = tempfile.mkdtemp(prefix="profilestack-import-")
    try:
        if not zipfile.is_zipfile(archive_path):
            raise ValueError("Unsupported archive. Only standard .zip is supported.")

        with zipfile.ZipFile(archive_path, "r") as zf:
            members = zf.infolist()
            if not members:
                raise ValueError("Zip archive is empty.")
            for info in members:
                _safe_member_path(info.filename)
                unix_mode = (info.external_attr >> 16) & 0xFFFF
                if unix_mode and (unix_mode & 0xA000) == 0xA000:
                    raise ValueError(f"Symlinks not permitted in profile archive: {info.filename}")
            zf.extractall(tmp_dir)

        entries = os.listdir(tmp_dir)
        dirs = [e for e in entries if os.path.isdir(os.path.join(tmp_dir, e))]

        # Detect archive packaging shape (nested single folder vs flat root contents)
        if len(dirs) == 1 and dirs[0].lower() not in {"default", "crash reports"}:
            profile_name = validate_profile_name(dirs[0])
            source_content_dir = os.path.join(tmp_dir, dirs[0])
        else:
            stem = archive_path.stem
            clean_stem = re.sub(r"[^a-zA-Z0-9_-]", "-", stem)[:64].strip("-") or "imported-profile"
            profile_name = validate_profile_name(clean_stem)
            source_content_dir = tmp_dir

        dest_dir = PROFILES_DIR / profile_name
        if dest_dir.exists():
            # If already exists, provide unique suffix
            profile_name = validate_profile_name(f"{profile_name}-{int(time.time()) % 10000}")
            dest_dir = PROFILES_DIR / profile_name

        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / "Downloads").mkdir(exist_ok=True)

        # Move extracted data into target profile directory
        for item in os.listdir(source_content_dir):
            if item == "Downloads" and (dest_dir / "Downloads").exists():
                continue
            s = os.path.join(source_content_dir, item)
            d = os.path.join(str(dest_dir), item)
            if not os.path.exists(d):
                shutil.move(s, d)

        # Clean stale Singleton locks from previous host runs
        clean_stale_locks(dest_dir)

        # Enforce full read/write permissions for container UID 1001 and host
        fix_profile_permissions(dest_dir)

        # Compute accurate size in MB
        size_mb = _get_dir_size_mb(dest_dir)

        reg = _load_registry()
        reg[profile_name] = {
            "name": profile_name,
            "path": str(dest_dir),
            "folder": "default",
            "proxy": "",
            "start_url": "https://www.google.com",
            "host_mount": "",
            "note": "Imported from archive",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        }
        _save_registry(reg)

        result_entry = dict(reg[profile_name])
        result_entry["size_mb"] = size_mb
        return result_entry

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def sync_back_profile_zip(profile_name: str, archive_path: Path) -> dict:
    """Updates an existing profile with session state uploaded from the local launcher."""
    profile_name = validate_profile_name(profile_name)
    reg = _load_registry()
    if profile_name not in reg:
        raise ValueError(f"Profile '{profile_name}' not found.")

    p_dir = Path(reg[profile_name]["path"])
    p_dir.mkdir(parents=True, exist_ok=True)

    if not archive_path.is_file():
        raise FileNotFoundError(f"Archive file not found: {archive_path}")

    tmp_dir = tempfile.mkdtemp(prefix="profilestack-sync-")
    try:
        if not zipfile.is_zipfile(archive_path):
            raise ValueError("Unsupported archive. Only standard .zip is supported.")

        with zipfile.ZipFile(archive_path, "r") as zf:
            members = zf.infolist()
            for info in members:
                _safe_member_path(info.filename)
                unix_mode = (info.external_attr >> 16) & 0xFFFF
                if unix_mode and (unix_mode & 0xA000) == 0xA000:
                    continue  # skip symlinks safely
            zf.extractall(tmp_dir)

        entries = os.listdir(tmp_dir)
        dirs = [e for e in entries if os.path.isdir(os.path.join(tmp_dir, e))]

        if len(dirs) == 1 and dirs[0].lower() not in {"default", "crash reports"}:
            source_dir = Path(tmp_dir) / dirs[0]
        else:
            source_dir = Path(tmp_dir)

        # Merge updated files into existing profile directory
        for root, _, files in os.walk(source_dir):
            rel = os.path.relpath(root, source_dir)
            target_sub = p_dir / rel if rel != "." else p_dir
            target_sub.mkdir(parents=True, exist_ok=True)
            for f in files:
                if f in _EXCLUDE_FILES:
                    continue
                src_f = Path(root) / f
                dst_f = target_sub / f
                try:
                    shutil.copy2(src_f, dst_f)
                except Exception:
                    pass

        clean_stale_locks(p_dir)
        fix_profile_permissions(p_dir)
        size_mb = _get_dir_size_mb(p_dir)
        reg[profile_name]["size_mb"] = size_mb
        _save_registry(reg)

        return {"status": "synced", "profile": profile_name, "size_mb": size_mb}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

