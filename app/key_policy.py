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


def validate_policy(permissions, profile_access, profiles):
    if not isinstance(permissions, list) or any(p not in PERMISSIONS for p in permissions):
        raise ValueError('Unknown API key permission.')
    if profile_access not in ('all', 'selected'):
        raise ValueError('Choose all or selected profile access.')
    if not isinstance(profiles, list) or any(not isinstance(p, str) or not p or len(p) > 128 for p in profiles):
        raise ValueError('Invalid profile selection.')
    if profile_access == 'selected' and GLOBAL_PERMISSIONS.intersection(permissions):
        raise ValueError('Global folder, proxy and telemetry permissions require all-profile access.')
    return {'permissions': sorted(set(permissions)), 'profile_access': profile_access, 'profiles': sorted(set(profiles)) if profile_access == 'selected' else []}


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
    if principal['profile_access'] == 'selected':
        if permission in GLOBAL_PERMISSIONS:
            raise PermissionError(DENIED)
        name = arguments.get('profile_name')
        if name and tool != 'create_profile' and name not in principal['profiles']:
            raise PermissionError(DENIED)


def visible_profile(name):
    p = current_principal.get()
    return p is None or p['profile_access'] == 'all' or name in p['profiles']


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
