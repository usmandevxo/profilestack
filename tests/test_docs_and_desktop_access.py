import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import httpx

from app.server import app
from app import auth_manager as auth


class DocsAndDesktopAccessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)

        self.p_users = patch("app.auth_manager.USERS_FILE", self.data_dir / "users.json")
        self.p_sessions = patch("app.auth_manager.SESSIONS_FILE", self.data_dir / "sessions.json")
        self.p_users.start()
        self.p_sessions.start()

        auth.create_user(
            username="admin",
            password="adminpassword123",
            role="admin",
            status="active",
            mcp_profile="full"
        )
        self.admin_session = auth.create_session("admin")

        auth.create_user(
            username="alice",
            password="alicepassword123",
            role="user",
            status="active",
            mcp_profile="standard"
        )
        self.alice_session = auth.create_session("alice")

    def tearDown(self):
        self.p_sessions.stop()
        self.p_users.stop()
        self.temp.cleanup()

    async def test_api_docs_hidden_from_public_view(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://testserver",
            follow_redirects=False,
        ) as client:
            # 1. Unauthenticated request must NOT see docs, must redirect to login
            res = await client.get("/api/docs")
            self.assertEqual(res.status_code, 303)
            self.assertIn("/login", res.headers.get("location", ""))

            # 2. Unauthenticated request to /openapi.json must also redirect to login
            res_open = await client.get("/openapi.json")
            self.assertEqual(res_open.status_code, 303)
            self.assertIn("/login", res_open.headers.get("location", ""))

    async def test_api_docs_restricted_by_role(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://testserver",
            follow_redirects=False,
        ) as client:
            # 1. Normal user (role: 'user') must get 404 Not Found for docs and openapi.json
            user_cookies = {auth.COOKIE_NAME: self.alice_session}
            res_user_docs = await client.get("/api/docs", cookies=user_cookies)
            self.assertEqual(res_user_docs.status_code, 404)

            res_user_json = await client.get("/openapi.json", cookies=user_cookies)
            self.assertEqual(res_user_json.status_code, 404)

            # 2. Administrator (role: 'admin') can access docs and openapi.json
            admin_cookies = {auth.COOKIE_NAME: self.admin_session}
            res_admin_docs = await client.get("/api/docs", cookies=admin_cookies)
            self.assertEqual(res_admin_docs.status_code, 200)
            self.assertIn("swagger-ui", res_admin_docs.text.lower())

            res_admin_json = await client.get("/openapi.json", cookies=admin_cookies)
            self.assertEqual(res_admin_json.status_code, 200)
            data = res_admin_json.json()
            self.assertEqual(data.get("info", {}).get("title"), "ProfileStack")

    async def test_launcher_scripts_restricted_to_admin(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://testserver",
            follow_redirects=False,
        ) as client:
            # 1. Unauthenticated request must be redirected to login
            res = await client.get("/install-launcher.sh")
            self.assertEqual(res.status_code, 303)

            res = await client.get("/install-desktop.sh")
            self.assertEqual(res.status_code, 303)

            # 2. Normal user (role: 'user') must get 404 Not Found
            user_cookies = {auth.COOKIE_NAME: self.alice_session}
            res_user_sh = await client.get("/install-launcher.sh", cookies=user_cookies)
            self.assertEqual(res_user_sh.status_code, 404)

            res_user_desk = await client.get("/install-desktop.sh", cookies=user_cookies)
            self.assertEqual(res_user_desk.status_code, 404)

            # 3. Admin user (role: 'admin') can download scripts if they exist
            admin_cookies = {auth.COOKIE_NAME: self.admin_session}
            res_admin_sh = await client.get("/install-launcher.sh", cookies=admin_cookies)
            self.assertIn(res_admin_sh.status_code, (200, 404))  # 200 if file exists on disk
