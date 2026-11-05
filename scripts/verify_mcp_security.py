"""Read-only deployed MCP checks. Never print keys or returned user data."""
import asyncio
import logging
import os
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client

logging.disable(logging.CRITICAL)


async def main():
    base = os.environ.get("PROFILESTACK_VERIFY_URL", "https://profilestack.rerouter.online").rstrip("/")
    key = os.environ.get("PROFILESTACK_MCP_API_KEY")
    if not key:
        key = (Path(__file__).resolve().parents[1] / "data/mcp-api-key").read_text().strip()
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        for path in ("/mcp", "/mcp/", "/mcp/sse", "/mcp/messages/"):
            for method in ("GET", "POST", "HEAD", "OPTIONS"):
                for headers in ({}, {"Authorization": "Bearer invalid"}):
                    r = await client.request(method, base + path, headers=headers)
                    assert r.status_code == 401, (method, path, r.status_code)
                    if method != "HEAD":
                        assert r.json() == {"detail": "Unauthorized"}
        for path in ("/screenshots/nonexistent.png", "/static/Gmail_Bulk_Login_Report_70.pdf", "/static/gmail-farm.html"):
            r = await client.get(base + path)
            assert r.status_code in (401, 303), (path, r.status_code)
        for path in ("/vnc-stream/6201/vnc_lite.html", "/vnc-stream/6201/websockify"):
            r = await client.get(base + path)
            assert r.status_code == 401, (path, r.status_code)
        r = await client.get(base + "/vnc-stream/7800/api/auth/me")
        assert r.status_code == 404
    for headers in ({"Authorization": "Bearer " + key}, {"X-API-Key": key}):
        async with sse_client(base + "/mcp/sse", headers=headers, timeout=15) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert tools.tools
                print(f"Authorized MCP initialize + list_tools passed ({len(tools.tools)} tools).")
    print("Unauthorized methods, private files, and VNC proxy guards passed.")


if __name__ == "__main__":
    asyncio.run(main())
