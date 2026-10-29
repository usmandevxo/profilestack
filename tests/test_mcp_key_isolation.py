"""MCP must not cross into credential administration or host files."""
import json
import unittest
from unittest.mock import AsyncMock, patch
from app import mcp_server as tools


class MCPIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_cannot_request_host_mount(self):
        with patch.object(tools.pm, "create_profile") as create:
            result = json.loads(tools.create_profile("test", host_mount="/www/wwwroot/profilestack/data"))
            self.assertIn("error", result)
            create.assert_not_called()

    async def test_browser_cannot_inspect_credential_admin_tab(self):
        profile = {"status": "running", "cdp_port": 9401, "host_mount": ""}
        tabs = [{"type": "page", "url": "https://profilestack.apanel.eu.cc/api-keys"}]
        with patch.object(tools.pm, "get_profile", return_value=profile), patch.object(tools.cdp, "get_browser_tabs", new=AsyncMock(return_value=tabs)), patch.object(tools.cdp, "evaluate_script", new=AsyncMock(return_value="confidential")) as evaluate:
            result = json.loads(await tools.evaluate_javascript("test", "document.body.innerText"))
            self.assertIn("error", result)
            evaluate.assert_not_called()

    async def test_all_browser_tools_block_admin_tabs(self):
        profile = {"status": "running", "cdp_port": 9401, "host_mount": ""}
        tabs = [{"type": "page", "url": "https://profilestack.apanel.eu.cc/api-keys"}]
        with patch.object(tools.pm, "get_profile", return_value=profile), patch.object(tools.cdp, "get_browser_tabs", new=AsyncMock(return_value=tabs)):
            for fn, args in [(tools.navigate_browser, ("test", "https://example.com")), (tools.get_active_page_details, ("test",)), (tools.evaluate_javascript, ("test", "1")), (tools.click_element, ("test", "button")), (tools.type_into_element, ("test", "input", "x")), (tools.take_screenshot, ("test",))]:
                result = json.loads(await fn(*args))
                self.assertEqual(result.get("error"), tools.DENIED)

    async def test_navigation_cannot_open_admin_or_local_files(self):
        profile = {"status": "running", "cdp_port": 9401, "host_mount": ""}
        tabs = [{"type": "page", "url": "https://example.com"}]
        with patch.object(tools.pm, "get_profile", return_value=profile), patch.object(tools.cdp, "get_browser_tabs", new=AsyncMock(return_value=tabs)), patch.object(tools.cdp, "navigate_tab", new=AsyncMock()) as navigate:
            for url in ["https://profilestack.apanel.eu.cc/api-keys", "http://127.0.0.1:7800/api/api-keys", "file:///www/wwwroot/profilestack/data/mcp-api-key", "http://[::1]:7800", "http://localhost:7800"]:
                self.assertIn("error", json.loads(await tools.navigate_browser("test", url)))
            navigate.assert_not_called()

    async def test_existing_host_mount_profile_cannot_be_started(self):
        with patch.object(tools.pm, "get_profile", return_value={"host_mount": "/"}), patch.object(tools.pm, "start_profile") as start:
            self.assertEqual(json.loads(tools.start_profile("test"))["error"], tools.DENIED)
            start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
