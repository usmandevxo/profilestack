import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
import httpx

from app.server import app
from app import auth_manager as auth
from app import folder_manager as fm
from app import profile_manager as pm
from app import api_key_store as store
from app import key_policy


class MultiTenantUserManagementTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)

        # Patch storage locations
        self.p_users = patch("app.auth_manager.USERS_FILE", self.data_dir / "users.json")
        self.p_sessions = patch("app.auth_manager.SESSIONS_FILE", self.data_dir / "sessions.json")
        self.p_folders = patch("app.folder_manager.FOLDERS_FILE", self.data_dir / "folders.json")
        self.p_profiles = patch("app.profile_manager.REGISTRY_FILE", self.data_dir / "profiles.json")
        self.p_keys_db = patch("app.api_key_store.DB_PATH", self.data_dir / "api-keys.sqlite3")

        self.p_users.start()
        self.p_sessions.start()
        self.p_folders.start()
        self.p_profiles.start()
        self.p_keys_db.start()

        # Seed initial admin
        auth.create_user(
            username="admin",
            password="adminpassword123",
            role="admin",
            status="active",
            mcp_profile="full"
        )
        self.admin_session = auth.create_session("admin")

        # Seed initial tenant user "alice"
        auth.create_user(
            username="alice",
            password="alicepassword123",
            role="user",
            status="active",
            mcp_profile="standard",
            mcp_access={"max_profiles": 2}
        )
        self.alice_session = auth.create_session("alice")

        # Seed initial tenant user "bob"
        auth.create_user(
            username="bob",
            password="bobpassword123",
            role="user",
            status="active",
            mcp_profile="readonly",
            mcp_access={"max_profiles": 5}
        )
        self.bob_session = auth.create_session("bob")

    def tearDown(self):
        self.p_keys_db.stop()
        self.p_profiles.stop()
        self.p_folders.stop()
        self.p_sessions.stop()
        self.p_users.stop()
        self.temp.cleanup()

    async def test_admin_user_crud_and_non_admin_forbidden(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://testserver") as client:
            # 1. Non-admin Alice cannot list users
            res = await client.get("/api/users", headers={"Cookie": f"ps_session={self.alice_session}"})
            self.assertEqual(res.status_code, 403)

            # 2. Admin can list users
            res = await client.get("/api/users", headers={"Cookie": f"ps_session={self.admin_session}"})
            self.assertEqual(res.status_code, 200)
            usernames = [u["username"] for u in res.json()]
            self.assertIn("admin", usernames)
            self.assertIn("alice", usernames)
            self.assertIn("bob", usernames)

            # 3. Admin creates new user "charlie"
            res = await client.post(
                "/api/users",
                json={
                    "username": "charlie",
                    "password": "charliepass123",
                    "role": "user",
                    "status": "active",
                    "mcp_profile": "standard",
                    "notes": "Test user"
                },
                headers={"Cookie": f"ps_session={self.admin_session}"}
            )
            self.assertEqual(res.status_code, 201)
            charlie = res.json()["user"]
            self.assertEqual(charlie["username"], "charlie")
            self.assertEqual(charlie["role"], "user")

            # 4. Admin updates user charlie
            res = await client.put(
                "/api/users/charlie",
                json={"status": "disabled", "notes": "Temporarily disabled"},
                headers={"Cookie": f"ps_session={self.admin_session}"}
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["user"]["status"], "disabled")

            # 5. Admin resets charlie's password
            res = await client.post(
                "/api/users/charlie/reset-password",
                json={"password": "newcharliepass123"},
                headers={"Cookie": f"ps_session={self.admin_session}"}
            )
            self.assertEqual(res.status_code, 200)

            # 6. Admin deletes user charlie
            res = await client.delete("/api/users/charlie", headers={"Cookie": f"ps_session={self.admin_session}"})
            self.assertEqual(res.status_code, 200)

            # 7. Admin cannot delete self
            res = await client.delete("/api/users/admin", headers={"Cookie": f"ps_session={self.admin_session}"})
            self.assertEqual(res.status_code, 400)

            # 8. Another admin can delete admin and reassign assets
            auth.create_user(username="superadmin", password="superpassword123", role="admin")
            super_sess = auth.create_session("superadmin")
            res = await client.delete("/api/users/admin?reassign_to=superadmin", headers={"Cookie": f"ps_session={super_sess}"})
            self.assertEqual(res.status_code, 200)
            self.assertIsNone(auth.get_user("admin"))

    async def test_category_folder_isolation_between_users(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://testserver") as client:
            # Alice creates a folder "alice-work"
            res = await client.post(
                "/api/folders",
                json={"name": "Alice Work", "color": "#10b981", "description": "Work category"},
                headers={"Cookie": f"ps_session={self.alice_session}"}
            )
            self.assertEqual(res.status_code, 200)
            alice_folder_id = res.json()["id"]

            # Bob creates a folder "bob-personal"
            res = await client.post(
                "/api/folders",
                json={"name": "Bob Personal", "color": "#f59e0b", "description": "Personal category"},
                headers={"Cookie": f"ps_session={self.bob_session}"}
            )
            self.assertEqual(res.status_code, 200)
            bob_folder_id = res.json()["id"]

            # Alice lists folders -> sees only her own folders
            res = await client.get("/api/folders", headers={"Cookie": f"ps_session={self.alice_session}"})
            self.assertEqual(res.status_code, 200)
            alice_folders = [f["id"] for f in res.json()]
            self.assertIn(alice_folder_id, alice_folders)
            self.assertNotIn(bob_folder_id, alice_folders)

            # Bob lists folders -> sees only his own folders
            res = await client.get("/api/folders", headers={"Cookie": f"ps_session={self.bob_session}"})
            self.assertEqual(res.status_code, 200)
            bob_folders = [f["id"] for f in res.json()]
            self.assertIn(bob_folder_id, bob_folders)
            self.assertNotIn(alice_folder_id, bob_folders)

            # Bob tries to delete Alice's folder -> fails with 400 / access denied
            res = await client.delete(f"/api/folders/{alice_folder_id}", headers={"Cookie": f"ps_session={self.bob_session}"})
            self.assertEqual(res.status_code, 400)

            # Admin can list all folders or filter by user
            res = await client.get("/api/folders?user=alice", headers={"Cookie": f"ps_session={self.admin_session}"})
            self.assertEqual(res.status_code, 200)
            self.assertTrue(all(f["owner"] == "alice" for f in res.json()))

    async def test_profile_isolation_and_quotas(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://testserver") as client:
            # Alice creates profile "alice-p1"
            res = await client.post(
                "/api/profiles",
                json={"name": "alice-p1", "start_url": "https://example.com"},
                headers={"Cookie": f"ps_session={self.alice_session}"}
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["profile"]["owner"], "alice")

            # Bob creates profile "bob-p1"
            res = await client.post(
                "/api/profiles",
                json={"name": "bob-p1", "start_url": "https://google.com"},
                headers={"Cookie": f"ps_session={self.bob_session}"}
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["profile"]["owner"], "bob")

            # Alice lists profiles -> cannot see Bob's profile
            res = await client.get("/api/profiles", headers={"Cookie": f"ps_session={self.alice_session}"})
            self.assertEqual(res.status_code, 200)
            names = [p["name"] for p in res.json()]
            self.assertIn("alice-p1", names)
            self.assertNotIn("bob-p1", names)

            # Bob attempts to get Alice's profile -> 404 access denied
            res = await client.get("/api/profiles/alice-p1", headers={"Cookie": f"ps_session={self.bob_session}"})
            self.assertEqual(res.status_code, 404)

            # Bob attempts to delete Alice's profile -> 400 access denied
            res = await client.delete("/api/profiles/alice-p1", headers={"Cookie": f"ps_session={self.bob_session}"})
            self.assertEqual(res.status_code, 400)

            # Alice has quota of 2 profiles: create second profile
            res = await client.post(
                "/api/profiles",
                json={"name": "alice-p2"},
                headers={"Cookie": f"ps_session={self.alice_session}"}
            )
            self.assertEqual(res.status_code, 200)

            # Alice attempts to exceed quota (3rd profile) -> 403 Forbidden
            res = await client.post(
                "/api/profiles",
                json={"name": "alice-p3"},
                headers={"Cookie": f"ps_session={self.alice_session}"}
            )
            self.assertEqual(res.status_code, 403)
            self.assertIn("quota", res.json()["detail"].lower())

    async def test_api_key_and_mcp_isolation(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://testserver") as client:
            headers_alice = {"Cookie": f"ps_session={self.alice_session}", "X-ProfileStack-Management": "1"}
            headers_bob = {"Cookie": f"ps_session={self.bob_session}", "X-ProfileStack-Management": "1"}

            # Alice creates API key with access to all her profiles
            res = await client.post(
                "/api/api-keys",
                json={"name": "Alice Key", "expires_in_days": 30, "profile_access": "all"},
                headers=headers_alice
            )
            self.assertEqual(res.status_code, 201)
            alice_key_id = res.json()["key"]["id"]
            alice_secret = res.json()["secret"]
            self.assertEqual(res.json()["key"]["owner"], "alice")

            # Bob lists keys -> does NOT see Alice's key
            res = await client.get("/api/api-keys", headers=headers_bob)
            self.assertEqual(res.status_code, 200)
            bob_key_ids = [k["id"] for k in res.json()["keys"]]
            self.assertNotIn(alice_key_id, bob_key_ids)

            # Bob tries to revoke Alice's key -> 404
            res = await client.delete(f"/api/api-keys/{alice_key_id}", headers=headers_bob)
            self.assertEqual(res.status_code, 404)

            # Alice's API key context check in key_policy
            self.assertTrue(store.validate_key(alice_secret))
            key_record = store.get_principal(alice_secret)
            self.assertIsNotNone(key_record)
            self.assertEqual(key_record["owner"], "alice")

            # Profile visibility under Alice's principal
            key_policy.current_principal.set(key_record)
            self.assertTrue(key_policy.visible_profile({"name": "alice-p1", "owner": "alice"}))
            self.assertFalse(key_policy.visible_profile({"name": "bob-p1", "owner": "bob"}))
            key_policy.current_principal.set(None)
