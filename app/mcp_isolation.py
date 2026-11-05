"""Defence-in-depth guardrails for MCP: never expose credential administration."""
import ipaddress
from urllib.parse import urlsplit

DENIED = "MCP access to administration or host files is not allowed."
ADMIN_HOSTS = {"profilestack.rerouter.online", "profilestack.apanel.eu.cc"}


def check_browser_url(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme in ("about", "chrome", "chrome-untrusted"):
        if url in ("about:blank", "chrome://newtab/", "chrome://new-tab-page/"):
            return
        raise ValueError(DENIED)
    if parsed.scheme not in ("https", "http") or not host or parsed.username or parsed.password:
        raise ValueError(DENIED)
    if host in ADMIN_HOSTS or host in ("localhost", "host.docker.internal") or host.endswith(".localhost"):
        raise ValueError(DENIED)
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError(DENIED)
    except ValueError as exc:
        if str(exc) == DENIED:
            raise


def check_profile(profile):
    if profile and profile.get("host_mount"):
        raise ValueError(DENIED)


async def check_browser(port, cdp):
    tabs = await cdp.get_browser_tabs(port)
    for tab in tabs:
        if tab.get("type") == "page":
            check_browser_url(tab.get("url", ""))
