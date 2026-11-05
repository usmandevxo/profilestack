"""Canonical permission vocabulary and per-call MCP authorization."""
from contextvars import ContextVar

PERMISSIONS = {
    'profiles.read': ('View profiles', 'Profiles'),
    'profiles.create': ('Create profiles', 'Profiles'),
    'profiles.update': ('Edit profiles', 'Profiles'),
    'profiles.delete': ('Delete profiles', 'Profiles'),
    'lifecycle.start': ('Start profiles', 'Lifecycle'),
    'lifecycle.stop': ('Stop profiles', 'Lifecycle'),
    'lifecycle.restart': ('Restart profiles', 'Lifecycle'),
    'browser.read': ('Read pages and screenshots', 'Browser'),
    'browser.control': ('Navigate, click, type and run JavaScript', 'Browser'),
    'folders.read': ('View accessible folders', 'Folders'),
    'folders.manage': ('Create, edit and delete folders', 'Folders'),
    'proxies.read': ('View proxy catalog', 'Global resources'),
    'proxies.manage': ('Manage and test proxies', 'Global resources'),
    'system.read': ('View host telemetry', 'Global resources'),
}
ALL_PERMISSIONS = list(PERMISSIONS)
DEFAULT_PERMISSIONS = ['profiles.read', 'folders.read', 'browser.read']
GLOBAL_PERMISSIONS = {'folders.manage', 'proxies.read', 'proxies.manage', 'system.read'}
TOOL_PERMISSIONS = {
    'list_profiles': 'profiles.read', 'get_profile_details': 'profiles.read',
    'create_profile': 'profiles.create', 'update_profile': 'profiles.update',
    'delete_profile': 'profiles.delete', 'move_profile_to_folder': 'profiles.update',
    'start_profile': 'lifecycle.start', 'stop_profile': 'lifecycle.stop', 'restart_profile': 'lifecycle.restart',
    'get_active_page_details': 'browser.read', 'take_screenshot': 'browser.read',
    'navigate_browser': 'browser.control', 'evaluate_javascript': 'browser.control',
    'click_element': 'browser.control', 'type_into_element': 'browser.control',
    'list_folders': 'folders.read', 'create_folder': 'folders.manage', 'update_folder': 'folders.manage', 'delete_folder': 'folders.manage',
    'list_proxies': 'proxies.read', 'add_proxy': 'proxies.manage', 'delete_proxy': 'proxies.manage', 'test_proxy': 'proxies.manage',
    'get_system_telemetry': 'system.read',
}
# None is reserved for trusted OS-local stdio, never an unauthenticated HTTP request.
current_principal: ContextVar[dict | None] = ContextVar('mcp_key_principal', default=None)
DENIED = 'Permission denied for this API key.'


def validate_policy(permissions, profile_access, profiles, folders=None):
    if not isinstance(permissions, list) or any(p not in PERMISSIONS for p in permissions):
        raise ValueError('Unknown API key permission.')
    if profile_access not in ('all', 'selected', 'group'):
        raise ValueError('Choose all, group, or selected profile access.')
    if not isinstance(profiles, list) or any(not isinstance(p, str) or not p or len(p) > 128 for p in profiles):
        raise ValueError('Invalid profile selection.')
    if folders is None:
        folders = []
    if not isinstance(folders, list) or any(not isinstance(f, str) or not f or len(f) > 64 for f in folders):
        raise ValueError('Invalid folder/group selection.')
    if profile_access in ('selected', 'group') and GLOBAL_PERMISSIONS.intersection(permissions):
        raise ValueError('Global folder, proxy and telemetry permissions require all-profile access.')
    if profile_access == 'group' and not folders:
        raise ValueError('Select at least one group/folder for group-scoped access.')
    return {
        'permissions': sorted(set(permissions)),
        'profile_access': profile_access,
        'profiles': sorted(set(profiles)) if profile_access == 'selected' else [],
        'folders': sorted(set(f.strip().lower() for f in folders)) if profile_access == 'group' else [],
    }


def authorize(tool, arguments):
    principal = current_principal.get()
    if principal is None:
        return
    name = arguments.get('profile_name')
    if name is not None:
        import re
        if not isinstance(name, str) or re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', name) is None:
            raise PermissionError(DENIED)
    permission = TOOL_PERMISSIONS.get(tool)
    if not permission or permission not in principal['permissions']:
        raise PermissionError(DENIED)
    if principal['profile_access'] in ('selected', 'group'):
        if permission in GLOBAL_PERMISSIONS:
            raise PermissionError(DENIED)

    # Multi-tenant tenant boundary checks for non-admin accounts
    if principal.get('role') != 'admin' and 'owner' in principal:
        owner = principal.get('owner', 'admin').lower()
        if permission in ('proxies.manage', 'system.read'):
            raise PermissionError(DENIED)
        if name:
            from app import profile_manager as pm
            prof = pm.get_profile(name)
            if not prof or prof.get('owner', 'admin').lower() != owner:
                raise PermissionError(DENIED)
        if tool == 'create_profile':
            from app import folder_manager as fm
            from app import profile_manager as pm
            target_folder = (arguments.get('folder') or 'default').strip().lower()
            f_obj = fm.get_folder(target_folder)
            if f_obj and f_obj.get('owner', 'admin').lower() != owner:
                raise PermissionError(DENIED)
            max_p = principal.get('max_profiles', 0)
            if max_p > 0:
                current_p = pm.list_profiles(owner=owner)
                if len(current_p) >= max_p:
                    raise PermissionError(DENIED)
        elif tool in ('update_folder', 'delete_folder'):
            from app import folder_manager as fm
            fid = arguments.get('folder_id')
            f_obj = fm.get_folder(fid)
            if not f_obj or f_obj.get('owner', 'admin').lower() != owner:
                raise PermissionError(DENIED)
        elif tool == 'move_profile_to_folder':
            from app import folder_manager as fm
            target_folder = arguments.get('target_folder_id')
            if target_folder:
                f_obj = fm.get_folder(target_folder)
                if not f_obj or f_obj.get('owner', 'admin').lower() != owner:
                    raise PermissionError(DENIED)

    if principal['profile_access'] == 'selected':
        name = arguments.get('profile_name')
        if name and tool != 'create_profile' and name not in principal['profiles']:
            raise PermissionError(DENIED)
    elif principal['profile_access'] == 'group':
        allowed_folders = set(principal.get('folders', []))
        if tool == 'create_profile':
            target_folder = (arguments.get('folder') or 'default').strip().lower()
            if target_folder not in allowed_folders:
                raise PermissionError(DENIED)
        else:
            if name:
                from app import profile_manager as pm
                prof = pm.get_profile(name)
                if not prof or (prof.get('folder') or 'default').strip().lower() not in allowed_folders:
                    raise PermissionError(DENIED)
            if tool == 'update_profile':
                target_folder = arguments.get('folder')
                if target_folder is not None and target_folder.strip().lower() not in allowed_folders:
                    raise PermissionError(DENIED)
            elif tool == 'move_profile_to_folder':
                target_folder = arguments.get('target_folder_id')
                if target_folder is not None and target_folder.strip().lower() not in allowed_folders:
                    raise PermissionError(DENIED)


def visible_profile(profile_or_name):
    p = current_principal.get()
    if p is None:
        return True

    name = profile_or_name if isinstance(profile_or_name, str) else profile_or_name.get('name')
    if p.get('role') != 'admin' and 'owner' in p:
        owner = p.get('owner', 'admin').lower()
        if isinstance(profile_or_name, dict) and 'owner' in profile_or_name:
            prof_owner = profile_or_name.get('owner', 'admin').lower()
        else:
            from app import profile_manager as pm
            prof = pm.get_profile(name)
            prof_owner = prof.get('owner', 'admin').lower() if prof else None
        if prof_owner != owner:
            return False

    if p['profile_access'] == 'all':
        return True
    if p['profile_access'] == 'selected':
        return name in p['profiles']
    if p['profile_access'] == 'group':
        if isinstance(profile_or_name, dict) and 'folder' in profile_or_name:
            folder = (profile_or_name.get('folder') or 'default').strip().lower()
        else:
            from app import profile_manager as pm
            prof = pm.get_profile(name)
            folder = (prof.get('folder') or 'default').strip().lower() if prof else None
        return folder in p.get('folders', [])
    return False


def sanitize_scoped_result(value):
    p = current_principal.get()
    if p is None:
        return value
    # Do not hand scoped clients raw transport endpoints that bypass tool authorization.
    blocked = {'cdp_port', 'vnc_port', 'ws_debug_url', 'webSocketDebuggerUrl', 'host_mount', 'profile_dir', 'path', 'file_path', 'proxy'}
    if isinstance(value, dict):
        return {k: sanitize_scoped_result(v) for k, v in value.items() if k not in blocked}
    if isinstance(value, list):
        return [sanitize_scoped_result(v) for v in value]
    return value
