import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from app.config import FOLDERS_FILE, PROFILES_DIR, REGISTRY_FILE
from app.validator import validate_folder_id, validate_folder_name

DEFAULT_FOLDER_ID = "default"
DEFAULT_FOLDER = {
    "id": DEFAULT_FOLDER_ID,
    "name": "General",
    "description": "Default workspace for general profiles",
    "color": "#64748b",
    "created_at": "2026-10-03 00:00:00",
}

PRESET_COLORS = [
    "#2563eb",  # Blue
    "#059669",  # Emerald
    "#d97706",  # Amber
    "#7c3aed",  # Purple
    "#db2777",  # Pink
    "#dc2626",  # Red
    "#0891b2",  # Cyan
    "#64748b",  # Slate
]


def _ensure_physical_dir(folder_id: str) -> Path:
    f_dir = PROFILES_DIR / folder_id
    f_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(f_dir, 0o777)
    except Exception:
        pass
    return f_dir


def load_folders() -> List[dict]:
    folders = []
    if FOLDERS_FILE.exists():
        try:
            with open(FOLDERS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    folders = data
        except (json.JSONDecodeError, OSError):
            folders = []

    # Ensure default folder is present
    has_default = any(f.get("id") == DEFAULT_FOLDER_ID for f in folders)
    if not has_default:
        folders.insert(0, dict(DEFAULT_FOLDER))
        save_folders(folders)

    # Ensure physical folder directories exist on disk
    for f in folders:
        fid = f.get("id")
        if fid:
            _ensure_physical_dir(fid)

    return folders


def save_folders(folders: List[dict]) -> None:
    tmp = str(FOLDERS_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(folders, f, indent=2)
    os.replace(tmp, FOLDERS_FILE)


def get_folder(folder_id: str) -> Optional[dict]:
    folder_id = (folder_id or "").strip().lower()
    folders = load_folders()
    for f in folders:
        if f.get("id") == folder_id:
            return dict(f)
    return None


def generate_folder_id(name: str, existing_ids: List[str]) -> str:
    base = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower()).strip("-")
    base = re.sub(r"-+", "-", base)
    if not base:
        base = "folder"
    base = base[:50]

    candidate = base
    counter = 1
    while candidate in existing_ids:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def create_folder(
    name: str,
    description: str = "",
    color: str = "#2563eb",
    folder_id: Optional[str] = None,
) -> dict:
    name = validate_folder_name(name)
    folders = load_folders()
    existing_ids = [f.get("id") for f in folders]

    if folder_id:
        fid = validate_folder_id(folder_id)
        if fid in existing_ids:
            raise ValueError(f"Folder with ID '{fid}' already exists.")
    else:
        fid = generate_folder_id(name, existing_ids)

    color = (color or "#2563eb").strip()
    if not re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", color):
        color = "#2563eb"

    new_folder = {
        "id": fid,
        "name": name,
        "description": (description or "").strip(),
        "color": color,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }

    folders.append(new_folder)
    save_folders(folders)
    _ensure_physical_dir(fid)
    return new_folder


def update_folder(
    folder_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[str] = None,
) -> dict:
    folder_id = validate_folder_id(folder_id)
    folders = load_folders()
    target = None
    for f in folders:
        if f.get("id") == folder_id:
            target = f
            break

    if not target:
        raise ValueError(f"Folder '{folder_id}' not found.")

    if name is not None:
        target["name"] = validate_folder_name(name)
    if description is not None:
        target["description"] = description.strip()
    if color is not None:
        c = color.strip()
        if re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", c):
            target["color"] = c

    save_folders(folders)
    return target


def delete_folder(folder_id: str, move_to: str = DEFAULT_FOLDER_ID) -> dict:
    folder_id = validate_folder_id(folder_id)
    if folder_id == DEFAULT_FOLDER_ID:
        raise ValueError("Cannot delete the default General folder.")

    folders = load_folders()
    existing_ids = [f.get("id") for f in folders]
    if folder_id not in existing_ids:
        raise ValueError(f"Folder '{folder_id}' does not exist.")

    if move_to not in existing_ids:
        move_to = DEFAULT_FOLDER_ID

    # Reassign profiles in registry
    reassigned_count = 0
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE, "r") as f:
                reg = json.load(f)
            changed = False
            for p_name, p_entry in reg.items():
                if p_entry.get("folder") == folder_id:
                    p_entry["folder"] = move_to
                    reassigned_count += 1
                    changed = True
            if changed:
                tmp = str(REGISTRY_FILE) + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(reg, f, indent=2)
                os.replace(tmp, REGISTRY_FILE)
        except Exception:
            pass

    folders = [f for f in folders if f.get("id") != folder_id]
    save_folders(folders)

    return {
        "status": "deleted",
        "deleted_folder_id": folder_id,
        "moved_to_folder": move_to,
        "reassigned_profiles": reassigned_count,
    }


def list_folders_with_stats() -> List[dict]:
    folders = load_folders()
    
    # Load profile registry and statuses
    profiles_data = {}
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE, "r") as f:
                profiles_data = json.load(f)
        except Exception:
            pass

    # Tally counts
    counts = {f["id"]: {"total": 0, "size_mb": 0.0} for f in folders}
    for p_name, p in profiles_data.items():
        fid = p.get("folder", DEFAULT_FOLDER_ID)
        if fid not in counts:
            counts[fid] = {"total": 0, "size_mb": 0.0}
        counts[fid]["total"] += 1

    result = []
    for f in folders:
        fid = f["id"]
        c = counts.get(fid, {"total": 0, "size_mb": 0.0})
        item = dict(f)
        item["total_profiles"] = c["total"]
        result.append(item)

    return result

# [ProfileStack v1.24.68] revision checkpoint
