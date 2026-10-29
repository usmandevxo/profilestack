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

## Dashboard key management

Open `/api-keys` from **API Keys** in the sidebar while signed in as an administrator.

- Create separately named client keys with 7-, 30-, or 90-day expiration, or no expiry.
- Copy the secret once at creation. Closing the dialog clears it; it cannot be retrieved later.
- Rename keys, view creation/expiration/last-used timestamps, and revoke individual clients without restarting the service.
- Managed keys are cryptographically random; only SHA-256 digests and metadata are stored in `data/api-keys.sqlite3` (mode `0600`, excluded from Git).
- Management requires an administrator web-session cookie, same-origin requests, and a mutation-specific header. MCP keys cannot create or revoke other keys.
- Named keys carry explicit action permissions and either all-profile access or a selected-profile allowlist. New keys default to read-only permissions with zero selected profiles (no existing-profile access). Existing named keys migrate to full compatibility access, so review them in **Edit access**.
- The legacy server key remains unrestricted until disabled; it cannot be assigned a granular policy.
- The original file/environment key appears as **Legacy server key**. Migrate existing clients first, then disable it from the page. Disabling is persistent and does not reveal or delete its original secret file.
- Revocation and expiry reject subsequent authenticated requests immediately, including MCP message POSTs. Already-executing tool calls cannot be undone.

## Per-key permissions and profile boundary

Create a key or choose **Edit access** to configure:

| Permission | Operations |
| --- | --- |
| `profiles.read` | List and inspect accessible profiles |
| `profiles.create` | Create new profiles |
| `profiles.update` | Edit profile settings and move profiles |
| `profiles.delete` | Delete profiles and their stored browser data |
| `lifecycle.start`, `lifecycle.stop`, `lifecycle.restart` | Independently allow each lifecycle action |
| `browser.read` | Read pages and capture screenshots |
| `browser.control` | Navigate, click, type, execute browser JavaScript |
| `folders.read` | View accessible folders and scoped counts |
| `folders.manage` | Global folder creation/edit/deletion |
| `proxies.read`, `proxies.manage` | Global proxy catalog access, mutation/testing |
| `system.read` | Global host telemetry |

**All profiles** includes current and future profiles, but does not imply every action permission. **Selected profiles** allows only the checked profile names. Empty selection grants no existing-profile access. A profile successfully created by a selected-scope key is automatically added to that key's allowlist. Creation does not implicitly grant read, lifecycle, or browser permissions. Global folder management, proxy access and host telemetry require all-profile scope; selected-scope policies cannot grant them.

Presets: **Read-only** selects profile/folder/browser reads; **Operator** additionally selects creation, profile edits, lifecycle and browser control (not deletion); **Full** explicitly selects every permission and all profiles. Admin changes preserve the secret. Revoked/expired keys do not reactivate when their policy is edited.

MCP dispatch checks both action permission and target profile before executing. Tool discovery is filtered, but manually calling a hidden tool is also denied. Profile lists and folder counts are scoped. Remote profile results omit raw CDP/VNC ports, proxy configuration and host file paths to avoid bypassing operation permissions. Direct raw browser transports are not authorized by these keys. Administrator web sessions remain separate and retain their own dashboard authority.

Each SSE connection is bound to its opening key. Message POSTs with a different valid key receive a generic `404`, and missing/invalid keys receive `401`. Permissions, revocation and expiry refresh on subsequent messages, including existing SSE connections; no restart/reconnect is needed for policy edits. In-flight operations cannot be undone. Local stdio remains trusted OS-local access, not a per-key remote session.

These policies govern the MCP/API boundary, not hostile-browser network confinement. Browser-control permission is powerful; do not grant it to an untrusted agent as if it were read-only. Network sandboxing and separately exposed CDP/shell access must be handled independently.

## MCP separation from key administration

- No API-key listing, creation, retrieval, or revocation tools are registered in MCP. Supplying an MCP key to the management REST API does not authorize it.
- Key-management routes additionally reject API-key/Authorization headers even if an administrator cookie is present. Only the administrator web-cookie workflow is supported.
- MCP refuses host-folder mounts and refuses starting, restarting, or browser-controlling profiles configured with such mounts.
- Before MCP browser inspection, scripting, interaction, navigation, or screenshots, page URLs are checked. Known ProfileStack administration hosts, loopback/private IP literals, local files and non-web schemes are denied. Direct navigation/start URLs receive the same guard.
- These URL checks are defense in depth, not a browser/network sandbox. Arbitrary browser JavaScript, redirects, alternate DNS names, browser state races, and separately granted host/CDP/shell access are outside a simple URL guard's security guarantee. Never sign in to ProfileStack administration inside an MCP-controlled profile or share administrator cookies, credentials, or server access with an untrusted agent. Host administrators can access the service's files by OS authority; MCP authentication cannot restrict that independent authority.

## Legacy server configuration

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
env -u PYTHONPATH .venv/bin/python scripts/verify_key_permissions.py
```

The live verification performs read-only MCP initialization and tool discovery for both supported headers, checks unauthenticated request methods and private-file guards, and checks VNC authorization. It never prints the real key or user profile contents.

These controls address the tested access paths; they are not a guarantee that every possible data leak has been eliminated. Changing default dashboard credentials, protecting the host, and auditing who holds the MCP key remain administrator responsibilities.
