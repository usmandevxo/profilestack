"""Bind every SSE session to its opening API key before SDK dispatch."""
import re
from urllib.parse import parse_qs
from starlette.responses import Response


class KeyBoundSSE:
    def __init__(self, app):
        self.app = app
        self.owners = {}

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        principal = scope.get('state', {}).get('mcp_principal')
        if principal is None:
            return await Response('Unauthorized', status_code=401, headers={'Cache-Control':'no-store'})(scope, receive, send)
        owner = principal['id']
        if scope['method'] == 'POST':
            sessions = parse_qs(scope.get('query_string', b'').decode('ascii',errors='ignore')).get('session_id', [])
            if len(sessions) != 1 or self.owners.get(sessions[0]) != owner:
                return await Response('Could not find session', status_code=404, headers={'Cache-Control':'no-store'})(scope, receive, send)
            return await self.app(scope, receive, send)
        registered = []
        pending = b''
        async def bound_send(message):
            nonlocal pending
            if message['type'] == 'http.response.body' and len(pending) < 4096:
                pending += message.get('body', b'')
                match = re.search(rb'session_id=([a-fA-F0-9]{32})', pending)
                if match and not registered:
                    session = match[1].decode('ascii')
                    self.owners[session] = owner
                    registered.append(session)
            await send(message)
        try:
            await self.app(scope, receive, bound_send)
        finally:
            for session in registered:
                self.owners.pop(session, None)
