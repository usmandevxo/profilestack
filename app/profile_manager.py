import json
import os
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional
import psutil

from app.config import PROFILES_DIR, REGISTRY_FILE
from app.docker_engine import DockerEngine
from app.validator import safe_profile_path, validate_profile_name, validate_proxy_url
import app.folder_manager as fm

_docker = DockerEngine()


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


def list_profiles(folder_id: Optional[str] = None) -> List[dict]:
    reg = _load_registry()
    statuses = _docker.all_container_telemetry()
    all_folders = {f["id"]: f for f in fm.load_folders()}
    profiles = []

    for name, item in reg.items():
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


def get_profile(name: str) -> Optional[dict]:
    name = validate_profile_name(name)
    reg = _load_registry()
    item = reg.get(name)
    if not item:
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
) -> dict:
    name = validate_profile_name(name)
    folder = (folder or fm.DEFAULT_FOLDER_ID).strip().lower()
    
    # Ensure target folder exists
    if not fm.get_folder(folder):
        try:
            fm.create_folder(name=folder, folder_id=folder)
        except Exception:
            folder = fm.DEFAULT_FOLDER_ID

    reg = _load_registry()
    if name in reg:
        raise ValueError(f"Profile '{name}' already exists.")

    p_dir = safe_profile_path(name, folder=folder)
    if p_dir.exists():
        raise ValueError(f"Directory already exists: {p_dir}")

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
) -> dict:
    name = validate_profile_name(name)
    reg = _load_registry()
    if name not in reg:
        raise ValueError(f"Profile '{name}' does not exist.")

    entry = reg[name]
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
        if not fm.get_folder(folder):
            try:
                fm.create_folder(name=folder, folder_id=folder)
            except Exception:
                folder = fm.DEFAULT_FOLDER_ID
        entry["folder"] = folder

    _save_registry(reg)
    return entry


def move_profile_to_folder(name: str, target_folder: str) -> dict:
    name = validate_profile_name(name)
    target_folder = (target_folder or fm.DEFAULT_FOLDER_ID).strip().lower()
    if not fm.get_folder(target_folder):
        raise ValueError(f"Target folder '{target_folder}' does not exist.")

    reg = _load_registry()
    if name not in reg:
        raise ValueError(f"Profile '{name}' does not exist.")

    entry = reg[name]
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


def delete_profile(name: str) -> dict:
    name = validate_profile_name(name)
    _docker.stop_profile(name)
    _docker.remove_profile_container(name)

    reg = _load_registry()
    entry = reg.pop(name, None)
    _save_registry(reg)

    if entry and entry.get("path"):
        target_path = Path(entry["path"])
        if target_path.is_dir() and str(target_path).startswith(str(PROFILES_DIR)):
            shutil.rmtree(target_path, ignore_errors=True)

    return {"status": "deleted", "name": name}


def start_profile(name: str) -> dict:
    name = validate_profile_name(name)
    reg = _load_registry()
    if name not in reg:
        raise ValueError(f"Profile '{name}' not found.")

    entry = reg[name]
    return _docker.start_profile(
        profile_name=name,
        profile_dir=entry.get("path", str(PROFILES_DIR / name)),
        proxy_val=entry.get("proxy", ""),
        start_url=entry.get("start_url", ""),
        host_mount=entry.get("host_mount", ""),
    )


def stop_profile(name: str) -> dict:
    name = validate_profile_name(name)
    reg = _load_registry()
    p_dir = reg.get(name, {}).get("path", "")
    return _docker.stop_profile(name, profile_dir=p_dir)


def restart_profile(name: str) -> dict:
    name = validate_profile_name(name)
    stop_profile(name)
    time.sleep(0.5)
    return start_profile(name)


def system_telemetry() -> dict:
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    profiles = list_profiles()
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

# [ProfileStack v1.21.28] revision checkpoint
