# ProfileStack UI contract

## API Keys extension
Mode: extend the existing operational application, not a redesign. Audience: cluster administrators connecting MCP clients. Primary journey: inspect active access → create a named key → copy the secret once → configure client → revoke access when no longer needed.

Use existing `app/static/css/style.css` as canonical tokens: Inter 13–16px body, JetBrains Mono for identifiers, slate-50 page (#f8fafc), white surfaces, slate-200 borders (#e2e8f0), slate-900 text (#0f172a), blue actions (#2563eb), red destructive actions (#dc2626). Keep 260px sidebar desktop, 24–32px gutters, 8/12/16/24 spacing, 6–12px radii. Follow existing buttons/forms. No dark code containers or emojis.

Page spine: title and Create API key action; live active/expired/revoked counts; named key table (prefix, status, created, expiry, last used, rename/revoke); connection instructions; legacy key clearly identified and revocable. No invented usage metrics. Keys grant full MCP cluster control; do not imply granular permissions.

Create dialog: name required, expiration select (7/30/90 days or never); submit disables and shows progress; errors inline; successful creation shows secret exactly once with Copy and explicit warning. No secrets in list responses, localStorage, URLs, logs, or screenshots. Clearing the success view removes the secret from DOM and JS state. Native dialog semantics with keyboard Escape/focus behavior. Revocation requires confirmation and gives immediate feedback; revoked rows stay visible as audit metadata. Editing names never reissues secrets.

Responsive: full-width table on desktop, stacked labeled cards below 768px; sidebar collapses to compact top navigation on this page. Controls wrap at 320px. Long names/endpoint wrap, minimum 40px action targets, visible focus. Loading, empty, error, copy-success and disabled states required. All data comes from authenticated endpoints. Security mutations require admin session, same-origin checks, and explicit management header. Legacy key never revealed in the UI.
