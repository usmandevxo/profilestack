# Remote MCP security

Remote SSE at `https://profilestack.apanel.eu.cc/mcp/sse` requires a private API key on **every** SSE GET and message POST. Browser sessions do not authorize MCP. Local stdio continues to rely on operating-system access controls.

Supported request headers (choose one):

```text
Authorization: Bearer YOUR_API_KEY
```

```text
X-API-Key: YOUR_API_KEY
```

Missing, invalid, duplicate, or ambiguous credentials return `401` with a generic `{"detail":"Unauthorized"}` response. Keys in query parameters are not accepted. Never put credentials in URLs, source files, screenshots, issue reports, or chat.

## Server configuration

Configuration precedence:

1. `PROFILESTACK_MCP_API_KEY` environment variable.
2. File specified by `PROFILESTACK_MCP_API_KEY_FILE`.
3. `<data directory>/mcp-api-key` (production: `/www/wwwroot/profilestack/data/mcp-api-key`).

Keys must be at least 32 ASCII characters with no whitespace. Missing, unreadable, or invalid server configuration fails closed. Keys are loaded at process startup; restart the daemon after rotation. Production uses a cryptographically random token stored in the default file with mode `0600`, owned by the daemon user. The key file is excluded from Git and is never displayed by the web UI.

Only a trusted server administrator should read the file and transfer its value into an MCP client's secret/header configuration. This key grants full cluster MCP control; it is not a read-only credential. Do not share it with untrusted clients. Rotating it disconnects existing SSE clients when the daemon restarts; all clients must use the replacement key.

## Client example

```json
{
  "name": "profilestack",
  "type": "sse",
  "url": "https://profilestack.apanel.eu.cc/mcp/sse",
  "headers": {
    "Authorization": "Bearer YOUR_API_KEY"
  }
}
```

Ensure the client forwards the header to both the initial SSE connection and the advertised message endpoint.

## Confidential-file and proxy controls

- Screenshots and non-UI files under `/static/` require web-session authentication. Public login CSS, JS, images, and icons remain accessible.
- Nginx forwards static requests through application authentication instead of directly serving private reports from an alias.
- VNC HTTP and WebSocket handshakes require a valid web-session cookie using an internal Nginx `auth_request` endpoint. Only allocated VNC-range ports 6201–6299 can be proxied; arbitrary loopback services cannot be selected.
- MCP requests bypass proxy buffering/caching, return `Cache-Control: no-store`, and have access logging disabled to avoid recording accidental query credentials or session identifiers.
- Plain HTTP redirects to HTTPS without copying query parameters. Clients must use HTTPS directly, not send keys over HTTP.
- The backend remains loopback-only and single-worker because MCP SSE sessions are stored in process memory.

Deploy `deploy/nginx-profilestack.conf` to the existing aaPanel vhost only after validating domain and certificate paths. Validate with Nginx's `-t` before reloading.

## Verification

From the project root:

```sh
env -u PYTHONPATH .venv/bin/python -m unittest discover -s tests -v
env -u PYTHONPATH .venv/bin/python scripts/verify_mcp_security.py
```

The live verification performs read-only MCP initialization and tool discovery for both supported headers, checks unauthenticated request methods and private-file guards, and checks VNC authorization. It never prints the real key or user profile contents.

These controls address the tested access paths; they are not a guarantee that every possible data leak has been eliminated. Changing default dashboard credentials, protecting the host, and auditing who holds the MCP key remain administrator responsibilities.
