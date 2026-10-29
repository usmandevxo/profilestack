"""MCP transport identity binding and per-message policy refresh."""
from app.mcp_auth import http_principal, refresh_principal, resolve_mcp_principal
from app.key_policy import current_principal, authorize, TOOL_PERMISSIONS, GLOBAL_PERMISSIONS, DENIED


async def enforce_key_policy(ctx, call_next):
    connection = http_principal.get()
    request = getattr(ctx, 'request', None)
    if request is not None:
        posted = resolve_mcp_principal(request.headers)
        if posted is None or connection is None or posted['id'] != connection['id']:
            raise PermissionError(DENIED)
    # HTTP-bound connections retain identity but refresh policy/revocation each message.
    principal = refresh_principal(connection) if connection is not None else None
    if connection is not None and principal is None:
        raise PermissionError(DENIED)
    token = current_principal.set(principal)
    try:
        if ctx.method == 'tools/call':
            params = ctx.params or {}
            try:
                authorize(params.get('name'), params.get('arguments') or {})
            except PermissionError:
                from mcp.types import CallToolResult, TextContent
                return CallToolResult(content=[TextContent(type='text', text=DENIED)], is_error=True)
        result = await call_next(ctx)
        if ctx.method == 'tools/list' and principal is not None:
            allowed = {tool for tool, permission in TOOL_PERMISSIONS.items() if permission in principal['permissions'] and (principal['profile_access'] == 'all' or permission not in GLOBAL_PERMISSIONS)}
            if isinstance(result, dict):
                result['tools'] = [tool for tool in result.get('tools', []) if (tool.get('name') if isinstance(tool, dict) else tool.name) in allowed]
            else:
                result.tools = [tool for tool in result.tools if tool.name in allowed]
        return result
    finally:
        current_principal.reset(token)
