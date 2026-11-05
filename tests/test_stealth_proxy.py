import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import httpx

from app.server import app
from app import auth_manager as auth
from app import profile_manager as pm
from app import folder_manager as fm


class StealthProxyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)

        # Patch storage locations
        self.p_users = patch("app.auth_manager.USERS_FILE", self.data_dir / "users.json")
        self.p_sessions = patch("app.auth_manager.SESSIONS_FILE", self.data_dir / "sessions.json")
        self.p_folders = patch("app.folder_manager.FOLDERS_FILE", self.data_dir / "folders.json")
        self.p_profiles = patch("app.profile_manager.REGISTRY_FILE", self.data_dir / "profiles.json")

        self.p_users.start()
        self.p_sessions.start()
        self.p_folders.start()
        self.p_profiles.start()

        # Seed admin and standard user "bob"
        auth.create_user("admin", "AdminPass123", role="admin")
        self.admin_session = auth.create_session("admin")

        auth.create_user("bob", "BobPass123", role="user")
        self.bob_session = auth.create_session("bob")

    def tearDown(self):
        self.p_profiles.stop()
        self.p_folders.stop()
        self.p_sessions.stop()
        self.p_users.stop()
        self.temp.cleanup()

    def test_admin_can_set_and_clear_user_proxy(self):
        assigned = "socks5://proxyuser:proxypass@192.168.1.100:1080"
        res = auth.set_user_proxy("bob", assigned)
        self.assertEqual(res.get("assigned_proxy"), assigned)

        # Retrieval check
        self.assertEqual(auth.get_user_assigned_proxy("bob"), assigned)

        # Admin lists users -> assigned_proxy is visible to admin
        admin_view = auth.list_users(is_admin=True)
        bob_admin_view = next(u for u in admin_view if u["username"] == "bob")
        self.assertEqual(bob_admin_view.get("assigned_proxy"), assigned)

        # Non-admin views user -> assigned_proxy is stripped and never disclosed
        bob_view = auth.get_user("bob", is_admin=False)
        self.assertIsNotNone(bob_view)
        if bob_view:
            self.assertNotIn("assigned_proxy", bob_view)

        # Admin clears proxy
        auth.set_user_proxy("bob", "")
        self.assertEqual(auth.get_user_assigned_proxy("bob"), "")

    def test_effective_proxy_resolution_with_stealth_and_custom_override(self):
        stealth_proxy = "socks5://stealth-host:1080"
        auth.set_user_proxy("bob", stealth_proxy)

        # Bob profile without custom proxy
        entry = {
            "name": "bob-work",
            "owner": "bob",
            "proxy": "",
            "start_url": "https://example.com"
        }

        # 1. Effective proxy must resolve to admin stealth proxy
        resolved = pm.resolve_effective_profile_proxy(entry, owner="bob")
        self.assertEqual(resolved, stealth_proxy)

        # 2. Profile metadata proxy field remains empty so user is not told
        self.assertEqual(entry.get("proxy"), "")

        # 3. Bob adds their own custom proxy
        custom_proxy = "http://bob-custom-proxy.org:8080"
        entry["proxy"] = custom_proxy

        # Effective proxy must use user's custom proxy, NOT the admin stealth proxy
        resolved_override = pm.resolve_effective_profile_proxy(entry, owner="bob")
        self.assertEqual(resolved_override, custom_proxy)

        # 4. Bob clears their custom proxy -> falls back to stealth proxy
        entry["proxy"] = ""
        resolved_reverted = pm.resolve_effective_profile_proxy(entry, owner="bob")
        self.assertEqual(resolved_reverted, stealth_proxy)

        # 5. Admin clears user stealth proxy -> falls back to direct
        auth.set_user_proxy("bob", "")
        resolved_none = pm.resolve_effective_profile_proxy(entry, owner="bob")
        self.assertEqual(resolved_none, "")

    @patch("app.profile_manager._docker.start_profile")
    def test_start_profile_injects_stealth_proxy_silently(self, mock_docker_start):
        mock_docker_start.return_value = {"id": "cid123", "vnc_port": 6201, "cdp_port": 9401}

        stealth_proxy = "socks5://admin-stealth-ip:1080"
        auth.set_user_proxy("bob", stealth_proxy)

        p = pm.create_profile(name="bob-profile-1", owner="bob", proxy="")
        self.assertEqual(p.get("proxy"), "")

        pm.start_profile("bob-profile-1", owner="bob")

        mock_docker_start.assert_called_once()
        _, kwargs = mock_docker_start.call_args
        self.assertEqual(kwargs.get("proxy_val"), stealth_proxy)

        fetched = pm.get_profile("bob-profile-1", owner="bob")
        self.assertIsNotNone(fetched)
        if fetched:
            self.assertEqual(fetched.get("proxy"), "")

    @patch("app.profile_manager._docker.start_profile")
    def test_start_profile_uses_user_override_proxy(self, mock_docker_start):
        mock_docker_start.return_value = {"id": "cid456", "vnc_port": 6202, "cdp_port": 9402}

        stealth_proxy = "socks5://admin-stealth-ip:1080"
        auth.set_user_proxy("bob", stealth_proxy)

        user_proxy = "http://bob-custom:8080"
        p = pm.create_profile(name="bob-profile-custom", owner="bob", proxy=user_proxy)
        self.assertEqual(p.get("proxy"), user_proxy)

        pm.start_profile("bob-profile-custom", owner="bob")

        mock_docker_start.assert_called_once()
        _, kwargs = mock_docker_start.call_args
        self.assertEqual(kwargs.get("proxy_val"), user_proxy)

    async def test_api_security_user_proxy_endpoints(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://testserver") as client:
            # 1. Non-admin Bob attempts to set stealth proxy -> 403 Forbidden
            res = await client.post(
                "/api/users/bob/proxy",
                headers={"Cookie": f"ps_session={self.bob_session}"},
                json={"proxy": "http://evil:8080"}
            )
            self.assertEqual(res.status_code, 403)

            res = await client.delete(
                "/api/users/bob/proxy",
                headers={"Cookie": f"ps_session={self.bob_session}"}
            )
            self.assertEqual(res.status_code, 403)

            # Bob viewing own user info -> assigned_proxy must NOT exist
            res = await client.get(
                "/api/users/bob",
                headers={"Cookie": f"ps_session={self.bob_session}"}
            )
            self.assertEqual(res.status_code, 200)
            self.assertNotIn("assigned_proxy", res.json())

            # 2. Admin sets proxy for bob via API -> 200 OK
            res = await client.post(
                "/api/users/bob/proxy",
                headers={"Cookie": f"ps_session={self.admin_session}"},
                json={"proxy": "socks5://10.0.0.1:1080"}
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json().get("assigned_proxy"), "socks5://10.0.0.1:1080")

            # Admin inspecting bob via /api/users/bob -> assigned_proxy is visible to admin
            res = await client.get(
                "/api/users/bob",
                headers={"Cookie": f"ps_session={self.admin_session}"}
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json().get("assigned_proxy"), "socks5://10.0.0.1:1080")

            # Admin clears proxy for bob via DELETE -> 200 OK
            res = await client.delete(
                "/api/users/bob/proxy",
                headers={"Cookie": f"ps_session={self.admin_session}"}
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json().get("assigned_proxy"), "")
            self.assertEqual(auth.get_user_assigned_proxy("bob"), "")


if __name__ == "__main__":
    unittest.main()
