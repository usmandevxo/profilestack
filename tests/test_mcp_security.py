"""Regression tests: remote MCP must never rely on browser login or public access."""
import asyncio
import os
import unittest
from unittest.mock import patch

import httpx

TEST_KEY = "test-only-" + "a" * 48
with patch.dict(os.environ, {"PROFILESTACK_MCP_API_KEY": TEST_KEY}):
    from app.server import app


class MCPSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://testserver"
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_missing_key_rejects_message_transport(self):
        response = await asyncio.wait_for(self.client.post(
            "/mcp/messages/?session_id=00000000000000000000000000000000", json={}
        ), timeout=3)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Unauthorized"})
        self.assertEqual(response.headers.get("cache-control"), "no-store")

    async def test_missing_or_invalid_keys_rejected_on_all_mcp_paths(self):
        for path in ["/mcp", "/mcp/", "/mcp/sse", "/mcp/messages/", "/mcp/unknown"]:
            for headers in [{}, {"Authorization": "Bearer wrong"}, {"X-API-Key": "wrong"}]:
                with self.subTest(path=path, headers=headers):
                    r = await asyncio.wait_for(self.client.get(path, headers=headers), 3)
                    self.assertEqual(r.status_code, 401)
                    self.assertEqual(r.json(), {"detail": "Unauthorized"})

    async def test_credentials_in_url_do_not_authorize(self):
        for name in ["api_key", "key", "token", "access_token"]:
            r = await self.client.get("/mcp/sse", params={name: TEST_KEY})
            self.assertEqual(r.status_code, 401)
            self.assertNotIn(TEST_KEY, r.text)

    async def test_browser_session_does_not_authorize_mcp(self):
        with patch("app.auth_manager.validate_session", return_value={"username": "admin"}):
            r = await self.client.get("/mcp/sse", headers={"Cookie": "ps_session=valid-session"})
        self.assertEqual(r.status_code, 401)

    async def test_valid_header_keys_reach_transport(self):
        for headers in [{"Authorization": "Bearer " + TEST_KEY}, {"X-API-Key": TEST_KEY}]:
            r = await self.client.post(
                "/mcp/messages/?session_id=00000000000000000000000000000000",
                json={}, headers=headers,
            )
            self.assertEqual(r.status_code, 404)  # Unknown MCP session, not authentication failure.
            self.assertEqual(r.headers.get("cache-control"), "no-store")

    async def test_missing_server_key_fails_closed(self):
        with patch("app.mcp_auth.MCP_API_KEY", ""):
            r = await self.client.get("/mcp/sse", headers={"X-API-Key": TEST_KEY})
        self.assertEqual(r.status_code, 401)

    async def test_ambiguous_credentials_rejected(self):
        for headers in [
            [("Authorization", "Bearer " + TEST_KEY), ("Authorization", "Bearer wrong")],
            [("X-API-Key", TEST_KEY), ("X-API-Key", "wrong")],
            {"Authorization": "Bearer " + TEST_KEY, "X-API-Key": TEST_KEY},
        ]:
            r = await self.client.get("/mcp/sse", headers=headers)
            self.assertEqual(r.status_code, 401)

    async def test_screenshots_are_private(self):
        r = await self.client.get("/screenshots/nonexistent.png")
        self.assertIn(r.status_code, (401, 303))

    async def test_similar_public_prefix_is_not_exempt(self):
        r = await self.client.get("/login-confidential")
        self.assertEqual(r.status_code, 303)

    async def test_vnc_auth_check_requires_session_not_mcp_key(self):
        r = await self.client.get("/api/auth/check", headers={"X-API-Key": TEST_KEY})
        self.assertEqual(r.status_code, 401)
        with patch("app.auth_manager.validate_session", return_value={"username": "admin"}):
            r = await self.client.get("/api/auth/check", headers={"Cookie": "ps_session=valid-session"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"authenticated": True})
        self.assertEqual(r.headers.get("cache-control"), "no-store")

    async def test_encoded_static_traversal_cannot_bypass_auth(self):
        r = await self.client.get("/static/css/%2e%2e/Gmail_Bulk_Login_Report_70.pdf")
        self.assertIn(r.status_code, (400, 401, 303, 404))

    async def test_confidential_static_documents_are_private(self):
        r = await self.client.get("/static/Gmail_Bulk_Login_Report_70.pdf")
        self.assertIn(r.status_code, (401, 303))


if __name__ == "__main__":
    unittest.main()
