"""Live scoped-key checks; no existing profile mutations or secrets printed."""
import asyncio
import json
import logging
import os
import uuid
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
from app import api_key_store as store

logging.disable(logging.CRITICAL)
BASE = os.environ.get('PROFILESTACK_VERIFY_URL', 'https://profilestack.rerouter.online')


async def main():
    keys = []
    try:
        a = store.create_key('Permission verification ' + uuid.uuid4().hex[:8], 7, permissions=['profiles.read','folders.read'], profile_access='selected')
        b = store.create_key('Permission verification peer ' + uuid.uuid4().hex[:8], 7, permissions=['profiles.read'], profile_access='selected')
        keys.extend([a,b])
        async with sse_client(BASE+'/mcp/sse', headers={'X-API-Key':a['secret']}, timeout=20) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {t.name for t in tools.tools} == {'list_profiles','get_profile_details','list_folders'}
                for name in ('list_profiles','list_folders'):
                    result = await session.call_tool(name,{})
                    assert not result.is_error
                    assert json.loads(result.content[0].text) == []
                for name,args in [('create_profile',{'profile_name':'must-not-be-created'}),('delete_profile',{'profile_name':'not-allowed'}),('get_profile_details',{'profile_name':'not-allowed'}),('evaluate_javascript',{'profile_name':'not-allowed','javascript':'1'}),('list_proxies',{})]:
                    result = await session.call_tool(name,args)
                    assert result.is_error, name
                    assert 'Permission denied' in result.content[0].text
                store.update_policy(a['key']['id'], ['profiles.read','profiles.create'], 'selected', [])
                assert 'create_profile' in {t.name for t in (await session.list_tools()).tools}
                store.update_policy(a['key']['id'], [], 'selected', [])
                assert not (await session.list_tools()).tools
                result = await session.call_tool('list_profiles',{})
                assert result.is_error
        # Cross-key POST into another SSE stream must never execute.
        async with httpx.AsyncClient(timeout=10) as client:
            async with client.stream('GET',BASE+'/mcp/sse',headers={'X-API-Key':b['secret']}) as stream:
                endpoint = None
                lines = stream.aiter_lines()
                async for line in lines:
                    if line.startswith('data: '):
                        endpoint = line[6:]
                        break
                assert endpoint
                # Transport ownership must reject before initialization or dispatch.
                r = await client.post(BASE+endpoint,headers={'X-API-Key':a['secret']},json={'jsonrpc':'2.0','id':101,'method':'initialize','params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'isolation-check','version':'1'}}})
                assert r.status_code == 404, r.status_code
                store.revoke_key(b['key']['id'])
                r = await client.post(BASE+endpoint,headers={'X-API-Key':b['secret']},json={})
                assert r.status_code == 401, r.status_code
        # Use a fresh temporary key after the revocation probe.
        b = store.create_key('Permission verification selected ' + uuid.uuid4().hex[:8], 7, permissions=['profiles.read'], profile_access='selected')
        keys.append(b)
        from app import profile_manager as pm
        existing = pm.list_profiles()
        if len(existing) >= 2:
            chosen, other = existing[0]['name'], existing[1]['name']
            store.update_policy(b['key']['id'], ['profiles.read'], 'selected', [chosen])
            async with sse_client(BASE+'/mcp/sse', headers={'Authorization':'Bearer '+b['secret']}, timeout=20) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    result = await session.call_tool('list_profiles',{})
                    listed = json.loads(result.content[0].text)
                    assert [p['name'] for p in listed] == [chosen]
                    result = await session.call_tool('get_profile_details',{'profile_name':chosen})
                    assert not result.is_error
                    assert json.loads(result.content[0].text)['name'] == chosen
                    result = await session.call_tool('get_profile_details',{'profile_name':other})
                    assert result.is_error
            print('Live selected-profile allow/deny and filtered real profile listing passed (no names or data logged).')
        else:
            raise AssertionError('Need two existing profiles to verify selected-profile boundary live.')

        # Live group-scoped verification
        g = store.create_key('Permission verification group ' + uuid.uuid4().hex[:8], 7, permissions=['profiles.read','profiles.create','profiles.update','profiles.delete','folders.read'], profile_access='group', folders=['marketplaces'])
        keys.append(g)
        async with sse_client(BASE+'/mcp/sse', headers={'X-API-Key':g['secret']}, timeout=20) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                # 1. list_folders should only return 'marketplaces'
                folders_res = await session.call_tool('list_folders',{})
                assert not folders_res.is_error
                folders = json.loads(folders_res.content[0].text)
                assert all(f['id'] == 'marketplaces' for f in folders)

                # 2. list_profiles should only return profiles in 'marketplaces'
                profiles_res = await session.call_tool('list_profiles',{})
                assert not profiles_res.is_error
                profiles = json.loads(profiles_res.content[0].text)
                for p in profiles:
                    assert p.get('folder') == 'marketplaces'

                # 3. create_profile targeting another group must be denied
                res = await session.call_tool('create_profile',{'profile_name':'attempt-other-group','folder':'google_acc'})
                assert res.is_error
                assert 'Permission denied' in res.content[0].text

                # 4. access to any profile outside marketplaces must be denied
                non_market_profiles = [p['name'] for p in existing if p.get('folder') != 'marketplaces']
                if non_market_profiles:
                    other_name = non_market_profiles[0]
                    res = await session.call_tool('get_profile_details',{'profile_name':other_name})
                    assert res.is_error
                    assert 'Permission denied' in res.content[0].text
                    res = await session.call_tool('delete_profile',{'profile_name':other_name})
                    assert res.is_error
                    assert 'Permission denied' in res.content[0].text
                    res = await session.call_tool('update_profile',{'profile_name':other_name})
                    assert res.is_error
                    assert 'Permission denied' in res.content[0].text
        print('Live group-scoped folder isolation, profile listing, and create/update/delete boundaries passed.')
        print('Live scoped tool discovery, empty selections, direct-call denial, live permission edits and cross-key isolation passed.')
    finally:
        for item in keys:
            store.revoke_key(item['key']['id'])
            assert store.get_active_principal(item['key']['id']) is None
        print('Temporary verification keys revoked and read back.')


if __name__ == '__main__':
    asyncio.run(main())
