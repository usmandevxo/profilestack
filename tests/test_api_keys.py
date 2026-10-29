"""API key management must require an administrator web session."""
import unittest
import tempfile
from pathlib import Path
import os
from unittest.mock import patch
import httpx
from app.server import app


class APIKeyRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.db_patch = patch("app.api_key_store.DB_PATH", Path(self.temp.name) / "keys.sqlite3")
        self.db_patch.start()

    async def asyncTearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    async def test_admin_can_create_named_key(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://testserver") as client:
            with patch("app.auth_manager.validate_session", return_value={"username": "admin"}), patch("app.auth_manager.load_users", return_value={"admin": {"role": "admin"}}):
                response = await client.post("/api/api-keys", json={"name": "Test client", "expires_in_days": 30}, headers={"Cookie": "ps_session=test", "X-ProfileStack-Management": "1", "Origin": "https://testserver"})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["secret"].startswith("psk_"))

    async def test_admin_policy_editor_and_secure_defaults(self):
        with patch("app.auth_manager.validate_session", return_value={"username": "admin"}), patch("app.auth_manager.load_users", return_value={"admin": {"role": "admin"}}), patch("app.api_key_routes.pm.list_profiles", return_value=[{'name':'alpha','folder':'default'}]):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://testserver", headers={"Cookie":"ps_session=test", "X-ProfileStack-Management":"1"}) as client:
                created = (await client.post('/api/api-keys', json={'name':'Restricted'})).json()
                self.assertEqual(created['key']['profile_access'], 'selected')
                self.assertEqual(created['key']['profiles'], [])
                self.assertNotIn('profiles.create', created['key']['permissions'])
                path = '/api/api-keys/' + created['key']['id'] + '/permissions'
                policy = {'permissions':['profiles.read','profiles.create'], 'profile_access':'selected', 'profiles':['alpha']}
                edited = await client.patch(path, json=policy)
                self.assertEqual(edited.status_code, 200)
                self.assertEqual(edited.json()['key']['profiles'], ['alpha'])
                self.assertEqual((await client.get('/api/api-keys')).json()['keys'][0]['permissions'], sorted(policy['permissions']))
                group_policy = {'permissions':['profiles.read','profiles.create','profiles.update','profiles.delete'], 'profile_access':'group', 'folders':['default']}
                group_edited = await client.patch(path, json=group_policy)
                self.assertEqual(group_edited.status_code, 200)
                self.assertEqual(group_edited.json()['key']['profile_access'], 'group')
                self.assertEqual(group_edited.json()['key']['folders'], ['default'])
                for change in ({'permissions':['unknown']}, {'permissions':['system.read']}, {'profiles':['missing']}):
                    self.assertEqual((await client.patch(path,json={**policy,**change})).status_code,422)
                self.assertEqual((await client.patch(path,json=policy,headers={'X-API-Key':created['secret']})).status_code,403)

    async def test_created_key_authorizes_mcp_and_revocation_is_immediate(self):
        from app import api_key_store as store
        result = store.create_key("Client", 30)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://testserver") as client:
            r = await client.post("/mcp/messages/?session_id=00000000000000000000000000000000", json={}, headers={"X-API-Key": result["secret"]})
            self.assertEqual(r.status_code, 404)
            store.revoke_key(result["key"]["id"])
            r = await client.post("/mcp/messages/", json={}, headers={"X-API-Key": result["secret"]})
            self.assertEqual(r.status_code, 401)

    async def test_key_lifecycle_and_secret_never_listed(self):
        from app import api_key_store as store
        with patch("app.auth_manager.validate_session", return_value={"username": "admin"}), patch("app.auth_manager.load_users", return_value={"admin": {"role": "admin"}}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://testserver", headers={"Cookie": "ps_session=test", "X-ProfileStack-Management": "1"}) as client:
                created = (await client.post("/api/api-keys", json={"name": "Cursor", "expires_in_days": 7})).json()
                key_id = created["key"]["id"]
                secret = created["secret"]
                listed = await client.get("/api/api-keys")
                self.assertNotIn(secret, listed.text)
                self.assertNotIn("digest", listed.text)
                self.assertEqual(listed.headers["cache-control"], "no-store")
                r = await client.patch("/api/api-keys/" + key_id, json={"name": "Renamed"})
                self.assertEqual(r.json()["key"]["name"], "Renamed")
                self.assertTrue(store.validate_key(secret))
                listed = (await client.get("/api/api-keys")).json()
                self.assertIsNotNone(listed["keys"][0]["last_used_at"])
                await client.delete("/api/api-keys/" + key_id)
                self.assertFalse(store.validate_key(secret))
                self.assertEqual((await client.get("/api/api-keys")).json()["keys"][0]["status"], "revoked")
                self.assertNotIn(secret.encode(), (Path(self.temp.name)/"keys.sqlite3").read_bytes())
                self.assertEqual((Path(self.temp.name)/"keys.sqlite3").stat().st_mode & 0o777, 0o600)

    async def test_mcp_headers_cannot_manage_keys_even_with_admin_cookie(self):
        with patch("app.auth_manager.validate_session", return_value={"username": "admin"}), patch("app.auth_manager.load_users", return_value={"admin": {"role": "admin"}}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://testserver") as client:
                for header in ({"X-API-Key": "test-key"}, {"Authorization": "Bearer test-key"}):
                    headers = {**header, "Cookie": "ps_session=test", "X-ProfileStack-Management": "1"}
                    for method, path in [("GET", "/api/api-keys"), ("POST", "/api/api-keys"), ("DELETE", "/api/api-keys/legacy"), ("GET", "/api-keys")]:
                        r = await client.request(method, path, headers=headers, json={"name": "denied"})
                        self.assertEqual(r.status_code, 403)

    async def test_expired_key_is_declined(self):
        from app import api_key_store as store
        import time
        with patch("app.api_key_store.time.time", return_value=time.time() - 10 * 86400):
            result = store.create_key("Expired", 7)
        self.assertFalse(store.validate_key(result["secret"]))
        self.assertEqual(store.list_keys()[0]["status"], "expired")

    async def test_management_access_controls(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://testserver") as client:
            self.assertEqual((await client.get("/api/api-keys")).status_code, 401)
            with patch("app.auth_manager.validate_session", return_value={"username": "viewer"}), patch("app.auth_manager.load_users", return_value={"viewer": {"role": "viewer"}}):
                self.assertEqual((await client.get("/api/api-keys", headers={"Cookie": "ps_session=test"})).status_code, 403)
            with patch("app.auth_manager.validate_session", return_value={"username": "Admin"}), patch("app.auth_manager.load_users", return_value={"admin": {"role": "admin"}}):
                self.assertEqual((await client.get("/api/api-keys", headers={"Cookie": "ps_session=test"})).status_code, 200)
            with patch("app.auth_manager.validate_session", return_value={"username": "Usmandevx"}), patch("app.auth_manager.load_users", return_value={"admin": {"role": "admin"}}):
                self.assertEqual((await client.get("/api/api-keys", headers={"Cookie": "ps_session=test"})).status_code, 200)
            with patch("app.auth_manager.validate_session", return_value={"username": "admin"}), patch("app.auth_manager.load_users", return_value={"admin": {"role": "admin"}}):
                self.assertEqual((await client.get("/api/api-keys", headers={"Cookie": "ps_session=test", "Origin": "https://evil.example"})).status_code, 403)
                body = {"name": "Client", "expires_in_days": 30}
                self.assertEqual((await client.post("/api/api-keys", json=body, headers={"Cookie": "ps_session=test"})).status_code, 403)
                headers = {"Cookie": "ps_session=test", "X-ProfileStack-Management": "1", "Origin": "https://evil.example"}
                self.assertEqual((await client.post("/api/api-keys", json=body, headers=headers)).status_code, 403)
                headers.pop("Origin")
                for name in ["", "   ", "x" * 81]:
                    self.assertEqual((await client.post("/api/api-keys", json={"name": name}, headers=headers)).status_code, 422)
                self.assertEqual((await client.post("/api/api-keys", json={"name": "test", "expires_in_days": -1}, headers=headers)).status_code, 422)

    async def test_legacy_can_be_revoked_without_disabling_new_key(self):
        from app import api_key_store as store
        from app.mcp_auth import valid_mcp_key
        from starlette.datastructures import Headers
        legacy = "legacy-test-" + "x" * 40
        result = store.create_key("Replacement", None)
        with patch("app.mcp_auth.MCP_API_KEY", legacy):
            self.assertTrue(valid_mcp_key(Headers({"X-API-Key": legacy})))
            store.revoke_legacy()
            self.assertFalse(valid_mcp_key(Headers({"X-API-Key": legacy})))
            self.assertTrue(valid_mcp_key(Headers({"X-API-Key": result["secret"]})))


if __name__ == "__main__":
    unittest.main()
