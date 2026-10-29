"""Per-key policy survives storage and is enforced at MCP dispatch."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import api_key_store as store


class PermissionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.patch = patch.object(store, 'DB_PATH', Path(self.temp.name)/'keys.sqlite3')
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_policy_is_stored_without_secret(self):
        result = store.create_key('Read only', 30, permissions=['profiles.read'], profile_access='selected', profiles=['alpha'])
        item = store.list_keys()[0]
        self.assertEqual(item['permissions'], ['profiles.read'])
        self.assertEqual(item['profiles'], ['alpha'])
        self.assertEqual(item['profile_access'], 'selected')
        self.assertNotIn('digest', item)

    def test_read_only_key_denies_create_and_other_profiles(self):
        from app.key_policy import current_principal, authorize
        result = store.create_key('Read only', 30, permissions=['profiles.read'], profile_access='selected', profiles=['alpha'])
        token = current_principal.set(store.get_principal(result['secret']))
        try:
            authorize('get_profile_details', {'profile_name': 'alpha'})
            with self.assertRaises(PermissionError):
                authorize('get_profile_details', {'profile_name': 'beta'})
            with self.assertRaises(PermissionError):
                authorize('create_profile', {'profile_name': 'new'})
        finally:
            current_principal.reset(token)

    def test_existing_database_migrates_to_compatibility_access(self):
        import sqlite3
        from app.key_policy import ALL_PERMISSIONS
        con = sqlite3.connect(store.DB_PATH)
        con.execute('CREATE TABLE api_keys (id TEXT PRIMARY KEY,name TEXT,prefix TEXT,digest TEXT UNIQUE,created_at REAL,expires_at REAL,last_used_at REAL,revoked_at REAL)')
        con.execute("INSERT INTO api_keys VALUES ('old','Existing','prefix','digest',1,NULL,NULL,NULL)")
        con.commit()
        con.close()
        key = store.list_keys()[0]
        self.assertEqual(set(key['permissions']), set(ALL_PERMISSIONS))
        self.assertEqual(key['profile_access'], 'all')

    def test_all_profile_actions_reject_unassigned_target(self):
        from app.key_policy import current_principal, authorize, ALL_PERMISSIONS, GLOBAL_PERMISSIONS
        permissions = [p for p in ALL_PERMISSIONS if p not in GLOBAL_PERMISSIONS]
        result = store.create_key('Scoped operator', 30, permissions=permissions, profile_access='selected', profiles=['alpha'])
        token = current_principal.set(store.get_principal(result['secret']))
        try:
            tools = ['get_profile_details','update_profile','delete_profile','move_profile_to_folder','start_profile','stop_profile','restart_profile','get_active_page_details','take_screenshot','navigate_browser','evaluate_javascript','click_element','type_into_element']
            for tool in tools:
                with self.subTest(tool=tool):
                    authorize(tool, {'profile_name':'alpha'})
                    with self.assertRaises(PermissionError):
                        authorize(tool, {'profile_name':'beta'})
            with self.assertRaises(PermissionError):
                authorize('unregistered_tool', {})
        finally:
            current_principal.reset(token)

    def test_selected_global_permissions_rejected(self):

        with self.assertRaises(ValueError):
            store.create_key('Bad', 30, permissions=['folders.manage'], profile_access='selected')

    def test_every_registered_tool_has_permission_mapping(self):
        import asyncio
        from app.mcp_server import mcp
        from app.key_policy import TOOL_PERMISSIONS
        tools = asyncio.run(mcp.list_tools())
        self.assertEqual({t.name for t in tools}, set(TOOL_PERMISSIONS))

    def test_filtered_profiles_and_no_transport_or_proxy_leak(self):
        import json
        from app import mcp_server as ms
        from app.key_policy import current_principal
        result = store.create_key('Scoped', 30, permissions=['profiles.read','folders.read'], profile_access='selected', profiles=['alpha'])
        token = current_principal.set(store.get_principal(result['secret']))
        try:
            with patch.object(ms.pm, 'list_profiles', return_value=[{'name':'alpha','folder':'a','cdp_port':123,'proxy':'sensitive'}, {'name':'beta','folder':'b'}]):
                listed = json.loads(ms.list_profiles())
                self.assertEqual(listed, [{'name':'alpha','folder':'a'}])
                with patch.object(ms.fm, 'list_folders_with_stats', return_value=[{'id':'a','total_profiles':99},{'id':'b','total_profiles':5}]):
                    self.assertEqual(json.loads(ms.list_folders()), [{'id':'a','total_profiles':1}])
            with patch.object(ms.pm, 'delete_profile') as delete:
                self.assertIn('error', json.loads(ms.delete_profile('alpha')))
                delete.assert_not_called()
        finally:
            current_principal.reset(token)

    def test_profile_creation_cannot_implicitly_create_global_folder(self):
        import json
        from app import mcp_server as ms
        from app.key_policy import current_principal
        result = store.create_key('Creator', 30, permissions=['profiles.create'], profile_access='selected')
        token = current_principal.set(store.get_principal(result['secret']))
        try:
            with patch.object(ms.fm, 'get_folder', return_value=None), patch.object(ms.pm, 'create_profile') as create:
                self.assertIn('Permission denied', json.loads(ms.create_profile('new', folder='new-folder'))['error'])
                create.assert_not_called()
        finally:
            current_principal.reset(token)

    def test_remote_profile_identifiers_are_not_silently_normalized(self):
        import json
        from app import mcp_server as ms
        from app.key_policy import current_principal
        result = store.create_key('Creator', 30, permissions=['profiles.create'], profile_access='selected')
        token = current_principal.set(store.get_principal(result['secret']))
        try:
            with patch.object(ms.pm, 'create_profile', return_value={'name':'new'}) as create:
                self.assertIn('error', json.loads(ms.create_profile(' new ')))
                create.assert_not_called()
        finally:
            current_principal.reset(token)

    def test_selected_creator_is_assigned_new_profile(self):
        import json
        from app import mcp_server as ms
        from app.key_policy import current_principal
        result = store.create_key('Creator', 30, permissions=['profiles.create'], profile_access='selected')
        token = current_principal.set(store.get_principal(result['secret']))
        try:
            with patch.object(ms.pm, 'create_profile', return_value={'name':'new'}):
                self.assertEqual(json.loads(ms.create_profile('new'))['status'], 'success')
            self.assertEqual(store.get_principal(result['secret'])['profiles'], ['new'])
        finally:
            current_principal.reset(token)


class TransportPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.patch = patch.object(store, 'DB_PATH', Path(self.temp.name)/'keys.sqlite3')
        self.patch.start()

    async def asyncTearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    async def test_transport_binds_session_before_initialization(self):
        from app.mcp_transport import KeyBoundSSE
        import asyncio
        opened = asyncio.Event()
        close = asyncio.Event()
        calls = []
        async def downstream(scope, receive, send):
            calls.append(scope['method'])
            if scope['method'] == 'GET':
                await send({'type':'http.response.start','status':200,'headers':[]})
                await send({'type':'http.response.body','body':b'data: /mcp/messages/?session_id=' + b'a'*32 + b'\n\n','more_body':True})
                opened.set()
                await close.wait()
            else:
                await send({'type':'http.response.start','status':202,'headers':[]})
        wrapper = KeyBoundSSE(downstream)
        async def receive():
            return {'type':'http.request','body':b''}
        async def discard(message):
            pass
        get = {'type':'http','method':'GET','state':{'mcp_principal':{'id':'owner'}}}
        task = asyncio.create_task(wrapper(get, receive, discard))
        await opened.wait()
        try:
            for key, expected in [('other',404),('owner',202)]:
                sent = []
                async def capture(message):
                    sent.append(message)
                scope = {'type':'http','method':'POST','query_string':b'session_id='+b'a'*32,'state':{'mcp_principal':{'id':key}}}
                await wrapper(scope,receive,capture)
                self.assertEqual(sent[0]['status'],expected)
            self.assertEqual(calls,['GET','POST'])
        finally:
            close.set()
            await task
        self.assertEqual(wrapper.owners,{})

    async def test_tool_discovery_filters_dictionary_result(self):
        from app.mcp_policy import enforce_key_policy
        from app.mcp_auth import http_principal
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        key = store.create_key('Reader',30,permissions=['profiles.read'],profile_access='selected')
        token = http_principal.set(store.get_principal(key['secret']))
        try:
            result = await enforce_key_policy(SimpleNamespace(request=None,method='tools/list'), AsyncMock(return_value={'tools':[{'name':'list_profiles'},{'name':'create_profile'}]}))
            self.assertEqual(result,{'tools':[{'name':'list_profiles'}]})
        finally:
            http_principal.reset(token)

    async def test_policy_refresh_and_cross_key_connection_rejection(self):
        from app.mcp_policy import enforce_key_policy
        from app.mcp_auth import http_principal
        from starlette.requests import Request
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        a = store.create_key('A',30, permissions=['profiles.read'])
        b = store.create_key('B',30)
        token = http_principal.set(store.get_principal(a['secret']))
        request = Request({'type':'http','headers':[(b'x-api-key', a['secret'].encode())]})
        ctx = SimpleNamespace(request=request, method='tools/call', params={'name':'delete_profile','arguments':{'profile_name':'alpha'}})
        next_call = AsyncMock()
        try:
            self.assertTrue((await enforce_key_policy(ctx, next_call)).is_error)
            next_call.assert_not_called()
            store.update_policy(a['key']['id'], ['profiles.delete'], 'all', [])
            await enforce_key_policy(ctx, next_call)
            next_call.assert_awaited_once()
            ctx.request = Request({'type':'http','headers':[(b'x-api-key', b['secret'].encode())]})
            with self.assertRaises(PermissionError):
                await enforce_key_policy(ctx, next_call)
            request.scope['headers'] = [(b'x-api-key', a['secret'].encode())]
            # Request caches its headers, so construct a fresh one.
            ctx.request = Request({'type':'http','headers':[(b'x-api-key', a['secret'].encode())]})
            store.revoke_key(a['key']['id'])
            with self.assertRaises(PermissionError):
                await enforce_key_policy(ctx, next_call)
        finally:
            http_principal.reset(token)


if __name__ == '__main__':
    unittest.main()
