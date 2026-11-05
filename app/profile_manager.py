import json
import os
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional
import psutil

from app.config import PROFILES_DIR, REGISTRY_FILE
from app.docker_engine import DockerEngine
from app.validator import (
    force_remove_directory,
    safe_profile_path,
    validate_profile_name,
    validate_proxy_url,
)
import app.folder_manager as fm

_docker = DockerEngine()


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


def _load_registry() -> dict:
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE, "r") as f:
                data = json.load(f)
                changed = False
                for name, item in data.items():
                    if "folder" not in item:
                        item["folder"] = fm.DEFAULT_FOLDER_ID
                        changed = True
                    if "owner" not in item:
                        item["owner"] = _default_owner()
                        changed = True
                if changed:
                    _save_registry(data)
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_registry(data: dict) -> None:
    tmp = str(REGISTRY_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, REGISTRY_FILE)


def _get_dir_size_mb(path: Path) -> float:
    if not path.is_dir():
        return 0.0
    total = 0
    try:
        for dp, _, fnames in os.walk(path):
            for fn in fnames:
                fp = os.path.join(dp, fn)
                if os.path.exists(fp) and not os.path.islink(fp):
                    total += os.path.getsize(fp)
    except Exception:
        pass
    return round(total / (1024 * 1024), 2)


def _read_machine_signature(profile_dir: Path) -> dict:
    sig_path = profile_dir / "hardware-signature.json"
    if not sig_path.is_file():
        return {}
    try:
        with open(sig_path, "r") as f:
            sig = json.load(f)
        m = {}
        m.update(sig.get("hardware", {}))
        m.update(sig.get("system", {}))
        m.update(sig.get("browser", {}))
        return m
    except Exception:
        return {}


def list_profiles(folder_id: Optional[str] = None, owner: Optional[str] = None) -> List[dict]:
    reg = _load_registry()
    statuses = _docker.all_container_telemetry()
    all_folders = {f["id"]: f for f in fm.load_folders()}
    profiles = []

    for name, item in reg.items():
        prof_owner = item.get("owner", "admin")
        if owner and prof_owner.lower() != owner.strip().lower():
            continue

        prof_folder = item.get("folder", fm.DEFAULT_FOLDER_ID)
        if folder_id and folder_id != "all" and prof_folder != folder_id:
            continue

        p_dir = Path(item.get("path", str(PROFILES_DIR / name)))
        container_info = statuses.get(name, {})
        status = container_info.get("status", "stopped")
        vnc_port = container_info.get("vnc_port")
        cdp_port = container_info.get("cdp_port")
        f_info = all_folders.get(prof_folder, fm.DEFAULT_FOLDER)

        profiles.append({
            "name": name,
            "path": str(p_dir),
            "folder": prof_folder,
            "folder_name": f_info.get("name", "General"),
            "folder_color": f_info.get("color", "#64748b"),
            "owner": prof_owner,
            "proxy": item.get("proxy", ""),
            "start_url": item.get("start_url", ""),
            "host_mount": item.get("host_mount", ""),
            "note": item.get("note", ""),
            "created_at": item.get("created_at", ""),
            "status": status,
            "vnc_port": vnc_port,
            "cdp_port": cdp_port,
            "size_mb": _get_dir_size_mb(p_dir),
            "machine": _read_machine_signature(p_dir),
        })

    return sorted(profiles, key=lambda x: x["name"].lower())


def get_profile(name: str, owner: Optional[str] = None) -> Optional[dict]:
    name = validate_profile_name(name)
    reg = _load_registry()
    item = reg.get(name)
    if not item:
        return None

    prof_owner = item.get("owner", "admin")
    if owner and prof_owner.lower() != owner.strip().lower():
        return None

    prof_folder = item.get("folder", fm.DEFAULT_FOLDER_ID)
    f_info = fm.get_folder(prof_folder) or fm.DEFAULT_FOLDER
    p_dir = Path(item.get("path", str(PROFILES_DIR / name)))
    ports = _docker.get_profile_ports(name)
    telemetry = _docker.container_telemetry(name)
    return {
        "name": name,
        "path": str(p_dir),
        "folder": prof_folder,
        "folder_name": f_info.get("name", "General"),
        "folder_color": f_info.get("color", "#64748b"),
        "owner": prof_owner,
        "proxy": item.get("proxy", ""),
        "start_url": item.get("start_url", ""),
        "host_mount": item.get("host_mount", ""),
        "note": item.get("note", ""),
        "created_at": item.get("created_at", ""),
        "status": telemetry.get("status", "stopped"),
        "cpu_percent": telemetry.get("cpu_percent", 0.0),
        "ram_mb": telemetry.get("ram_mb", 0.0),
        "vnc_port": ports.get("vnc_port"),
        "cdp_port": ports.get("cdp_port"),
        "size_mb": _get_dir_size_mb(p_dir),
        "machine": _read_machine_signature(p_dir),
    }


def create_profile(
    name: str,
    proxy: str = "",
    start_url: str = "",
    host_mount: str = "",
    note: str = "",
    folder: str = fm.DEFAULT_FOLDER_ID,
    owner: Optional[str] = None,
) -> dict:
    name = validate_profile_name(name)
    folder = (folder or fm.DEFAULT_FOLDER_ID).strip().lower()
    owner = (owner or _default_owner()).strip()

    # Check user profile quota if applicable
    try:
        from app import auth_manager as auth
        user_data = auth.get_user(owner)
        if user_data:
            max_p = user_data.get("mcp_access", {}).get("max_profiles", 0)
            if max_p > 0:
                current_count = len(list_profiles(owner=owner))
                if current_count >= max_p:
                    raise ValueError(f"Profile creation quota reached for user '{owner}' (maximum {max_p} profiles allowed).")
    except ValueError:
        raise
    except Exception:
        pass

    # Ensure target folder exists and belongs to owner (or admin)
    folder_obj = fm.get_folder(folder)
    if not folder_obj:
        try:
            fm.create_folder(name=folder, folder_id=folder, owner=owner)
        except Exception:
            folder = fm.DEFAULT_FOLDER_ID
    else:
        folder_owner = folder_obj.get("owner", "").lower()
        if folder_owner and owner.lower() != folder_owner:
            from app.auth_manager import is_admin
            if not is_admin(owner):
                user_folders = fm.load_folders(owner=owner)
                folder = user_folders[0]["id"] if user_folders else fm.DEFAULT_FOLDER_ID

    reg = _load_registry()
    if name in reg:
        raise ValueError(f"Profile '{name}' already exists.")

    p_dir = safe_profile_path(name, folder=folder)
    if p_dir.exists():
        force_remove_directory(p_dir)

    p_dir.mkdir(parents=True, exist_ok=True)
    (p_dir / "Downloads").mkdir(exist_ok=True)
    try:
        os.chmod(p_dir, 0o777)
        os.chmod(p_dir / "Downloads", 0o777)
    except Exception:
        pass

    if host_mount:
        host_mount = os.path.realpath(os.path.expanduser(host_mount))
        if not os.path.isdir(host_mount):
            raise ValueError(f"Host folder not found: {host_mount}")

    entry = {
        "name": name,
        "path": str(p_dir),
        "folder": folder,
        "owner": owner,
        "proxy": (proxy or "").strip(),
        "start_url": (start_url or "").strip(),
        "host_mount": host_mount,
        "note": (note or "").strip(),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
    reg[name] = entry
    _save_registry(reg)
    return entry


def update_profile(
    name: str,
    proxy: Optional[str] = None,
    start_url: Optional[str] = None,
    host_mount: Optional[str] = None,
    note: Optional[str] = None,
    folder: Optional[str] = None,
    owner: Optional[str] = None,
) -> dict:
    name = validate_profile_name(name)
    reg = _load_registry()
    if name not in reg:
        raise ValueError(f"Profile '{name}' does not exist.")

    entry = reg[name]
    prof_owner = entry.get("owner", "admin")
    if owner and prof_owner.lower() != owner.strip().lower():
        raise PermissionError(f"Access denied: profile '{name}' belongs to another user.")

    if proxy is not None:
        entry["proxy"] = proxy.strip()
    if start_url is not None:
        entry["start_url"] = start_url.strip()
    if host_mount is not None:
        hm = host_mount.strip()
        if hm:
            hm = os.path.realpath(os.path.expanduser(hm))
            if not os.path.isdir(hm):
                raise ValueError(f"Host mount directory does not exist: {hm}")
        entry["host_mount"] = hm
    if note is not None:
        entry["note"] = note.strip()
    if folder is not None:
        folder = folder.strip().lower()
        folder_obj = fm.get_folder(folder)
        if not folder_obj:
            try:
                fm.create_folder(name=folder, folder_id=folder, owner=prof_owner)
            except Exception:
                folder = fm.DEFAULT_FOLDER_ID
        elif owner and folder_obj.get("owner", "admin").lower() != prof_owner.lower():
            raise PermissionError(f"Access denied: folder '{folder}' belongs to another user.")
        entry["folder"] = folder

    _save_registry(reg)
    return entry


def move_profile_to_folder(name: str, target_folder: str, owner: Optional[str] = None) -> dict:
    name = validate_profile_name(name)
    target_folder = (target_folder or fm.DEFAULT_FOLDER_ID).strip().lower()
    
    target_f_obj = fm.get_folder(target_folder)
    if not target_f_obj:
        raise ValueError(f"Target folder '{target_folder}' does not exist.")

    reg = _load_registry()
    if name not in reg:
        raise ValueError(f"Profile '{name}' does not exist.")

    entry = reg[name]
    prof_owner = entry.get("owner", "admin")
    if owner and prof_owner.lower() != owner.strip().lower():
        raise PermissionError(f"Access denied: profile '{name}' belongs to another user.")

    if owner and target_f_obj.get("owner", "admin").lower() != prof_owner.lower():
        raise PermissionError(f"Access denied: destination folder '{target_folder}' belongs to another user.")

    old_folder = entry.get("folder", fm.DEFAULT_FOLDER_ID)
    if old_folder == target_folder:
        return {"status": "unchanged", "name": name, "folder": target_folder}

    old_path = Path(entry["path"])
    new_path = safe_profile_path(name, folder=target_folder)

    was_running = _docker.is_profile_running(name)
    if was_running:
        _docker.stop_profile(name)

    if old_path.exists() and old_path != new_path and not new_path.exists():
        new_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(old_path), str(new_path))
            entry["path"] = str(new_path)
        except Exception:
            pass

    entry["folder"] = target_folder
    _save_registry(reg)

    if was_running:
        _docker.start_profile(
            profile_name=name,
            profile_dir=entry["path"],
            proxy_val=entry.get("proxy", ""),
            start_url=entry.get("start_url", ""),
            host_mount=entry.get("host_mount", ""),
        )

    return {
        "status": "moved",
        "name": name,
        "old_folder": old_folder,
        "new_folder": target_folder,
        "new_path": entry["path"]
    }


def delete_profile(name: str, owner: Optional[str] = None) -> dict:
    name = validate_profile_name(name)
    reg = _load_registry()
    entry = reg.get(name)
    if not entry:
        raise ValueError(f"Profile '{name}' does not exist.")

    prof_owner = entry.get("owner", "admin")
    if owner and prof_owner.lower() != owner.strip().lower():
        raise PermissionError(f"Access denied: profile '{name}' belongs to another user.")

    _docker.stop_profile(name)
    _docker.remove_profile_container(name)

    reg.pop(name, None)
    _save_registry(reg)

    deleted_paths = set()
    if entry.get("path"):
        target_path = Path(entry["path"]).resolve()
        try:
            if target_path.is_relative_to(PROFILES_DIR.resolve()) and target_path.exists():
                force_remove_directory(target_path)
                deleted_paths.add(str(target_path))
        except (AttributeError, ValueError):
            if str(target_path).startswith(str(PROFILES_DIR.resolve())) and target_path.exists():
                force_remove_directory(target_path)
                deleted_paths.add(str(target_path))

    candidates = [PROFILES_DIR / name]
    try:
        candidates.extend(list(PROFILES_DIR.glob(f"*/{name}")))
    except Exception:
        pass

    for candidate in candidates:
        try:
            c_res = candidate.resolve()
            if str(c_res) not in deleted_paths:
                is_rel = False
                try:
                    is_rel = c_res.is_relative_to(PROFILES_DIR.resolve())
                except (AttributeError, ValueError):
                    is_rel = str(c_res).startswith(str(PROFILES_DIR.resolve()))
                if is_rel and c_res.exists():
                    force_remove_directory(c_res)
                    deleted_paths.add(str(c_res))
        except Exception:
            pass

    return {"status": "deleted", "name": name}


def start_profile(name: str, owner: Optional[str] = None) -> dict:
    name = validate_profile_name(name)
    reg = _load_registry()
    if name not in reg:
        raise ValueError(f"Profile '{name}' not found.")

    entry = reg[name]
    prof_owner = entry.get("owner", "admin")
    if owner and prof_owner.lower() != owner.strip().lower():
        raise PermissionError(f"Access denied: profile '{name}' belongs to another user.")

    return _docker.start_profile(
        profile_name=name,
        profile_dir=entry.get("path", str(PROFILES_DIR / name)),
        proxy_val=entry.get("proxy", ""),
        start_url=entry.get("start_url", ""),
        host_mount=entry.get("host_mount", ""),
    )


def stop_profile(name: str, owner: Optional[str] = None) -> dict:
    name = validate_profile_name(name)
    reg = _load_registry()
    if name not in reg:
        raise ValueError(f"Profile '{name}' not found.")

    entry = reg[name]
    prof_owner = entry.get("owner", "admin")
    if owner and prof_owner.lower() != owner.strip().lower():
        raise PermissionError(f"Access denied: profile '{name}' belongs to another user.")

    p_dir = entry.get("path", "")
    return _docker.stop_profile(name, profile_dir=p_dir)


def restart_profile(name: str, owner: Optional[str] = None) -> dict:
    name = validate_profile_name(name)
    stop_profile(name, owner=owner)
    time.sleep(0.5)
    return start_profile(name, owner=owner)


def reassign_profiles(old_owner: Optional[str], new_owner: str) -> int:
    registry = _load_registry()
    count = 0
    old_lower = old_owner.strip().lower() if old_owner else None
    for name, p in registry.items():
        curr_owner = str(p.get("owner", "admin")).lower()
        if old_lower is None or curr_owner == old_lower:
            p["owner"] = new_owner
            count += 1
    if count > 0:
        _save_registry(registry)
    return count


def system_telemetry(owner: Optional[str] = None) -> dict:
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    profiles = list_profiles(owner=owner)
    running_count = sum(1 for p in profiles if p["status"] == "running")
    total_storage_mb = sum(p["size_mb"] for p in profiles)

    return {
        "cpu_percent": round(cpu_percent, 1),
        "ram_total_gb": round(mem.total / (1024**3), 1),
        "ram_used_gb": round(mem.used / (1024**3), 1),
        "ram_percent": mem.percent,
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "disk_used_gb": round(disk.used / (1024**3), 1),
        "disk_percent": disk.percent,
        "total_profiles": len(profiles),
        "running_profiles": running_count,
        "storage_profiles_mb": round(total_storage_mb, 1),
    }
