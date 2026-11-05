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

    def test_group_scoped_key_enforces_group_boundary(self):
        import json
        from app import mcp_server as ms
        from app.key_policy import current_principal, authorize
        result = store.create_key(
            'Group Key',
            30,
            permissions=['profiles.read', 'profiles.create', 'profiles.update', 'profiles.delete', 'lifecycle.start'],
            profile_access='group',
            folders=['marketplaces'],
        )
        principal = store.get_principal(result['secret'])
        self.assertEqual(principal['profile_access'], 'group')
        self.assertEqual(principal['folders'], ['marketplaces'])

        token = current_principal.set(principal)
        try:
            # 1. create_profile: allowed in marketplaces, denied in google_acc
            authorize('create_profile', {'profile_name': 'm1', 'folder': 'marketplaces'})
            with self.assertRaises(PermissionError):
                authorize('create_profile', {'profile_name': 'g1', 'folder': 'google_acc'})

            # Mock profiles: one in marketplaces, one in google_acc
            mock_m1 = {'name': 'm1', 'folder': 'marketplaces'}
            mock_g1 = {'name': 'g1', 'folder': 'google_acc'}

            with patch.object(ms.pm, 'get_profile', side_effect=lambda n: mock_m1 if n == 'm1' else mock_g1 if n == 'g1' else None):
                # 2. get_profile_details & lifecycle: allowed for m1, denied for g1
                authorize('get_profile_details', {'profile_name': 'm1'})
                authorize('start_profile', {'profile_name': 'm1'})
                with self.assertRaises(PermissionError):
                    authorize('get_profile_details', {'profile_name': 'g1'})
                with self.assertRaises(PermissionError):
                    authorize('start_profile', {'profile_name': 'g1'})

                # 3. update_profile: allowed to update m1 without changing folder or staying in marketplaces
                authorize('update_profile', {'profile_name': 'm1'})
                authorize('update_profile', {'profile_name': 'm1', 'folder': 'marketplaces'})
                # Denied to update g1
                with self.assertRaises(PermissionError):
                    authorize('update_profile', {'profile_name': 'g1'})
                # Denied to move m1 outside marketplaces
                with self.assertRaises(PermissionError):
                    authorize('update_profile', {'profile_name': 'm1', 'folder': 'google_acc'})
                with self.assertRaises(PermissionError):
                    authorize('move_profile_to_folder', {'profile_name': 'm1', 'target_folder_id': 'google_acc'})

                # 4. delete_profile: allowed for m1, denied for g1
                authorize('delete_profile', {'profile_name': 'm1'})
                with self.assertRaises(PermissionError):
                    authorize('delete_profile', {'profile_name': 'g1'})
        finally:
            current_principal.reset(token)

    def test_group_scoped_list_profiles_and_folders(self):
        import json
        from app import mcp_server as ms
        from app.key_policy import current_principal
        result = store.create_key('Group Key', 30, permissions=['profiles.read', 'folders.read'], profile_access='group', folders=['marketplaces'])
        token = current_principal.set(store.get_principal(result['secret']))
        try:
            mock_profiles = [
                {'name': 'm1', 'folder': 'marketplaces'},
                {'name': 'm2', 'folder': 'marketplaces'},
                {'name': 'g1', 'folder': 'google_acc'},
            ]
            mock_folders = [
                {'id': 'default', 'name': 'General', 'total_profiles': 10},
                {'id': 'marketplaces', 'name': 'Marketplaces', 'total_profiles': 2},
                {'id': 'google_acc', 'name': 'Google_Acc', 'total_profiles': 5},
            ]
            with patch.object(ms.pm, 'list_profiles', return_value=mock_profiles), patch.object(ms.fm, 'list_folders_with_stats', return_value=mock_folders):
                listed = json.loads(ms.list_profiles())
                self.assertEqual([p['name'] for p in listed], ['m1', 'm2'])

                folders = json.loads(ms.list_folders())
                self.assertEqual([f['id'] for f in folders], ['marketplaces'])
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

    def test_tenant_can_create_folder_and_profile_in_folder(self):
        import json
        import uuid
        from app.key_policy import current_principal, authorize
        from app import mcp_server as srv
        from app import profile_manager as pm
        from app import folder_manager as fm
        test_uid = uuid.uuid4().hex[:6]
        f_name = f'Project X {test_uid}'
        p_name = f'bob_browser_{test_uid}'
        k = store.create_key('TenantKey', 30, permissions=['folders.manage', 'folders.read', 'profiles.create', 'profiles.read'], owner='tenant_bob')
        p = store.get_principal(k['secret'])
        token = current_principal.set(p)
        f_id = None
        try:
            authorize('create_folder', {'name': f_name})
            folder_res = json.loads(srv.create_folder(name=f_name, description='Desc'))
            self.assertEqual(folder_res.get('status'), 'success')
            f_id = folder_res['folder']['id']
            self.assertEqual(folder_res['folder']['owner'], 'tenant_bob')

            authorize('create_profile', {'profile_name': p_name, 'folder': f_id})
            prof_res = json.loads(srv.create_profile(profile_name=p_name, folder=f_id))
            self.assertEqual(prof_res.get('status'), 'success')
            self.assertEqual(prof_res['profile']['owner'], 'tenant_bob')
            self.assertEqual(prof_res['profile']['folder'], f_id)
        finally:
            try:
                pm.delete_profile(p_name)
            except Exception:
                pass
            if f_id:
                try:
                    fm.delete_folder(f_id)
                except Exception:
                    pass
            current_principal.reset(token)
            store.revoke_key(k['key']['id'])


if __name__ == '__main__':
    unittest.main()
