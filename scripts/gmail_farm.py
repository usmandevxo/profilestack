#!/usr/bin/env python3
"""
Gmail Session Farm - 70 persistent profiles
Each profile keeps Chromium cookies on disk, so one human-verified sign-in
per account results in a permanently logged-in browser session.

Subcommands:
  create                 create profiles g01..g70 (idempotent)
  start A B [--n N]      start profiles A..B, max N concurrent
  check A B              report login state for A..B (Inbox = logged in)
  stop A B               stop profiles A..B
  status                 print table of all farm profiles + state
  dashboard              write HTML dashboard with viewer links
"""
import asyncio, json, sys, time, html
from pathlib import Path

ROOT = Path("/www/wwwroot/profilestack")
sys.path.insert(0, str(ROOT))
import app.profile_manager as pm
import app.folder_manager as fm
import app.cdp_client as cdp

FOLDER = "gmail-bulk-70"
COUNT = 70
STATE = ROOT / "data" / "gmail_farm_state.json"
DASH = ROOT / "data" / "gmail_farm_dashboard.html"
BASE_URL = "https://profilestack.rerouter.online"


def pname(n): return f"g{n:02d}"
def email(n): return f"usmankhalidb{n}@gmail.com"


def load_state():
    if STATE.exists():
        try: return json.loads(STATE.read_text())
        except Exception: return {}
    return {}


def save_state(s):
    STATE.write_text(json.dumps(s, indent=2))


def ensure_folder():
    if not fm.get_folder(FOLDER):
        fm.create_folder(name="Gmail Farm 70", folder_id=FOLDER,
                         description="70 persistent Gmail sessions", color="#dc2626")


def cmd_create():
    ensure_folder()
    reg = pm._load_registry()
    made = 0
    for n in range(1, COUNT + 1):
        name = pname(n)
        if name in reg:
            continue
        try:
            pm.create_profile(name=name, folder=FOLDER,
                              start_url="https://accounts.google.com/",
                              note=f"{email(n)} | persistent session")
            made += 1
            print(f"  created {name} -> {email(n)}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")
    print(f"created {made} new profiles (total farm = {COUNT})")


async def login_state(port):
    """Return dict describing whether this browser is signed in to Gmail."""
    try:
        tabs = await cdp.get_browser_tabs(port)
        cur = [t for t in tabs if t.get("type") == "page"]
        cur_url = cur[0].get("url") if cur else ""
        # try to detect session via gmail redirect
        val = await cdp.evaluate_script(port, """
        (() => {
          const t = (document.body && document.body.innerText || '').slice(0, 400);
          return {url: location.href, title: document.title, text: t};
        })()
        """)
        v = val or {}
        url = v.get("url", cur_url)
        txt = (v.get("text") or "").lower()
        if "mail.google.com" in url:
            return {"state": "logged_in", "url": url}
        if "accounts.google.com" in url and ("verify" in txt or "challenge" in url):
            return {"state": "needs_verification", "url": url}
        if "signin" in url or "identifier" in url or "Sign in" in (v.get("title") or ""):
            return {"state": "signed_out", "url": url}
        # probe gmail
        await cdp.navigate_tab(port, "https://mail.google.com/mail/u/0/")
        await asyncio.sleep(4)
        v2 = await cdp.evaluate_script(port, "({url: location.href, title: document.title})") or {}
        u2 = v2.get("url", "")
        if "mail.google.com" in u2 and "signin" not in u2:
            return {"state": "logged_in", "url": u2}
        return {"state": "signed_out", "url": u2 or url}
    except Exception as e:
        return {"state": "error", "error": str(e)}


def start_one(name):
    info = pm.get_profile(name)
    if not info: return {"error": "not found"}
    if info["status"] != "running":
        try:
            pm.start_profile(name)
        except Exception as e:
            return {"error": str(e)}
        for _ in range(20):
            time.sleep(1.5)
            i2 = pm.get_profile(name)
            if i2 and i2["status"] == "running" and i2.get("cdp_port"):
                return {"status": "running", "cdp": i2["cdp_port"], "vnc": i2.get("vnc_port")}
        return {"error": "did not come up"}
    return {"status": "running", "cdp": info.get("cdp_port"), "vnc": info.get("vnc_port")}


def cmd_start(a, b, conc):
    ensure_folder()
    st = load_state()
    names = [pname(n) for n in range(a, b + 1)]
    running = []
    for chunk_start in range(0, len(names), conc):
        chunk = names[chunk_start:chunk_start + conc]
        # stop previously started chunk to respect concurrency
        for name in chunk:
            r = start_one(name)
            info = pm.get_profile(name) or {}
            print(f"  {name}: {r}  viewer={BASE_URL}/viewer/{name}")
            st.setdefault(name, {})["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            st[name]["vnc_port"] = info.get("vnc_port")
            st[name]["cdp_port"] = info.get("cdp_port")
        save_state(st)
        if chunk_start + conc < len(names):
            prev = names[chunk_start:chunk_start + conc]
            for name in prev:
                try: pm.stop_profile(name)
                except Exception: pass
    save_state(st)


def cmd_check(a, b):
    ensure_folder()
    st = load_state()
    out = []
    for n in range(a, b + 1):
        name = pname(n)
        info = pm.get_profile(name)
        if not info or info["status"] != "running" or not info.get("cdp_port"):
            r = {"state": "stopped"}
        else:
            r = asyncio.run(login_state(int(info["cdp_port"])))
        st.setdefault(name, {})
        st[name].update({"state": r.get("state"), "url": r.get("url"),
                         "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        out.append((n, name, r.get("state"), r.get("url")))
        print(f"  g{n:02d} {email(n):32s} {r.get('state')}")
    save_state(st)
    from collections import Counter
    print(Counter([o[2] for o in out]))


def cmd_stop(a, b):
    for n in range(a, b + 1):
        try:
            pm.stop_profile(pname(n))
            print(f"  stopped {pname(n)}")
        except Exception as e:
            print(f"  {pname(n)}: {e}")


def cmd_status():
    st = load_state()
    reg = pm._load_registry()
    print(f"{'#':>3} {'profile':7s} {'email':32s} {'state':20s} {'vnc':>5s}")
    for n in range(1, COUNT + 1):
        name = pname(n)
        s = st.get(name, {})
        print(f"{n:>3} {name:7s} {email(n):32s} {s.get('state','not_created' if name not in reg else 'unknown'):20s} {str(s.get('vnc_port') or ''):>5s}")


def cmd_dashboard():
    st = load_state()
    reg = pm._load_registry()
    rows = []
    for n in range(1, COUNT + 1):
        name = pname(n)
        s = st.get(name, {})
        state = s.get("state", "not_created" if name not in reg else "unknown")
        color = {"logged_in": "#059669", "needs_verification": "#d97706",
                 "signed_out": "#dc2626", "stopped": "#64748b"}.get(state, "#64748b")
        rows.append(f"""<tr>
<td>{n}</td><td><code>{email(n)}</code></td>
<td><span style="color:{color};font-weight:600">{state}</span></td>
<td><a href="{BASE_URL}/viewer/{name}" target="_blank">Open viewer</a></td>
</tr>""")
    logged = sum(1 for n in range(1, COUNT + 1) if st.get(pname(n), {}).get("state") == "logged_in")
    DASH.write_text(f"""<!doctype html><html><head><meta charset="utf-8">
<title>Gmail Farm Status</title><style>
body{{font-family:ui-sans-serif,system-ui,sans-serif;background:#f8fafc;color:#0f172a;margin:0;padding:32px}}
h1{{font-size:20px;margin:0 0 4px}}p{{color:#475569;margin:0 0 20px;font-size:14px}}
table{{border-collapse:collapse;width:100%;background:#fff;border:1px solid #e2e8f0;font-size:13px}}
th,td{{padding:8px 12px;text-align:left;border-bottom:1px solid #e2e8f0}}
th{{background:#f1f5f9;font-weight:600}}tr:hover{{background:#f8fafc}}
a{{color:#2563eb;text-decoration:none}}code{{font-size:12px}}
.badge{{display:inline-block;padding:2px 10px;border-radius:999px;background:#ecfdf5;color:#065f46;font-size:12px;font-weight:600}}
</style></head><body>
<h1>Gmail Session Farm — 70 accounts</h1>
<p>Logged in: <span class="badge">{logged} / 70</span> &nbsp;·&nbsp; generated {time.strftime('%Y-%m-%d %H:%M')}</p>
<table><thead><tr><th>#</th><th>Account</th><th>Session state</th><th>Action</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></body></html>""")
    print(f"dashboard -> {DASH}  (logged_in {logged}/70)")


# ---------------------------------------------------------------- sign-in flow
PASSWORDS = ["3262932629", "3272932729"]


async def _type_email(port, email_addr):
    await cdp.navigate_tab(port, "https://accounts.google.com/signin/v2/identifier?flowName=GlifWebSignIn&flowEntry=ServiceLogin")
    await asyncio.sleep(4.5)
    ok = await cdp.evaluate_script(port, """
    (() => {
      const el = document.querySelector('input[type=email]') || document.querySelector('#identifierId');
      if (!el) return false;
      el.focus(); el.click();
      return true;
    })()
    """)
    if not ok:
        await asyncio.sleep(3)
        ok = await cdp.evaluate_script(port, """
        (() => {
          const el = document.querySelector('input[type=email]') || document.querySelector('#identifierId');
          if (!el) return false;
          el.focus(); el.click(); return true;
        })()
        """)
    if not ok:
        return {"ok": False, "reason": "email field missing"}
    await cdp.send_text_input(port, email_addr)
    await asyncio.sleep(1.2)
    await cdp.evaluate_script(port, """
    (() => { const b = document.querySelector('#identifierNext button') ||
        Array.from(document.querySelectorAll('button')).find(x => /next/i.test(x.innerText));
        if (b) { b.click(); return true; } return false; })()
    """)
    await asyncio.sleep(5.5)
    return {"ok": True}


async def _snapshot(port):
    v = await cdp.evaluate_script(port, """
    (() => ({url: location.href, title: document.title,
             text: ((document.body && document.body.innerText) || '').slice(0, 1200)}))()
    """) or {}
    return v


def _classify(v):
    url = (v.get("url") or "").lower()
    text = (v.get("text") or "").lower()
    if "mail.google.com" in url or "myaccount.google.com" in url:
        return "logged_in"
    if "wrong password" in text or "incorrect password" in text:
        return "wrong_password"
    if "couldn" in text and "find" in text and "account" in text:
        return "account_not_found"
    if "challenge/recaptcha" in url or "not a robot" in text:
        return "captcha"
    if "challenge/" in url or "verify it" in text or "2-step" in text:
        return "needs_verification"
    if "enter your password" in text:
        return "password_page"
    if "identifier" in url or "signin" in url:
        return "signed_out"
    return "unknown"


async def sign_in_one(port, email_addr):
    """Automate email+password. Stops at any Google challenge for human completion."""
    r = await _type_email(port, email_addr)
    if not r.get("ok"):
        return {"state": "email_field_missing", "detail": r}

    v = await _snapshot(port)
    cls = _classify(v)
    if cls == "account_not_found":
        return {"state": "account_not_found", "url": v.get("url")}
    if cls in ("needs_verification", "captcha"):
        return {"state": cls, "url": v.get("url")}

    # password stage
    for i, pwd in enumerate(PASSWORDS):
        focused = await cdp.evaluate_script(port, """
        (() => { const el = document.querySelector('input[type=password]') ||
            document.querySelector('input[name=password]');
            if (!el) return false; el.focus(); el.click(); return true; })()
        """)
        if not focused:
            await asyncio.sleep(3)
            focused = await cdp.evaluate_script(port, """
            (() => { const el = document.querySelector('input[type=password]');
                if (!el) return false; el.focus(); el.click(); return true; })()
            """)
            if not focused:
                v = await _snapshot(port)
                return {"state": _classify(v), "url": v.get("url"), "note": "no password field"}

        await cdp.send_text_input(port, pwd)
        await asyncio.sleep(1.0)
        await cdp.evaluate_script(port, """
        (() => { const b = document.querySelector('#passwordNext button') ||
            Array.from(document.querySelectorAll('button')).find(x => /next|sign in/i.test(x.innerText));
            if (b) { b.click(); return true; } return false; })()
        """)
        await asyncio.sleep(6.0)

        v = await _snapshot(port)
        cls = _classify(v)
        if cls == "logged_in":
            return {"state": "logged_in", "password": pwd, "url": v.get("url")}
        if cls in ("needs_verification", "captcha"):
            return {"state": cls, "password": pwd, "url": v.get("url")}
        if cls == "wrong_password":
            if i == len(PASSWORDS) - 1:
                return {"state": "wrong_password_all", "url": v.get("url")}
            await asyncio.sleep(2.5)
            continue
        return {"state": cls, "password": pwd, "url": v.get("url")}
    return {"state": "unknown"}


async def _signin_range(a, b, conc):
    ensure_folder()
    st = load_state()
    for n in range(a, b + 1):
        name = pname(n)
        em = email(n)
        info = pm.get_profile(name)
        if not info:
            print(f"  g{n:02d} missing profile"); continue
        if info["status"] != "running" or not info.get("cdp_port"):
            start_one(name)
            info = pm.get_profile(name) or {}
        port = info.get("cdp_port")
        if not port:
            print(f"  g{n:02d} no cdp port"); continue
        print(f"  [{n}] {em} signing in ...", flush=True)
        try:
            res = await sign_in_one(int(port), em)
        except Exception as e:
            res = {"state": "error", "error": str(e)}
        st.setdefault(name, {})
        st[name].update({"state": res.get("state"),
                         "password": res.get("password"),
                         "url": res.get("url"),
                         "signin_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        st[name]["vnc_port"] = (pm.get_profile(name) or {}).get("vnc_port")
        save_state(st)
        print(f"      -> {res.get('state')}  viewer={BASE_URL}/viewer/{name}", flush=True)
        await asyncio.sleep(1.0)
    from collections import Counter
    print(Counter(st.get(pname(n), {}).get("state") for n in range(a, b + 1)))


def cmd_signin(a, b):
    asyncio.run(_signin_range(a, b, 1))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    args = sys.argv[2:]
    if cmd == "create": cmd_create()
    elif cmd == "start":
        conc = 6
        if "--n" in args:
            i = args.index("--n"); conc = int(args[i + 1]); args = args[:i] + args[i+2:]
        cmd_start(int(args[0]), int(args[1]), conc)
    elif cmd == "check": cmd_check(int(args[0]), int(args[1]))
    elif cmd == "stop": cmd_stop(int(args[0]), int(args[1]))
    elif cmd == "status": cmd_status()
    elif cmd == "dashboard": cmd_dashboard()
    elif cmd == "signin": cmd_signin(int(args[0]), int(args[1]))
    else: print(__doc__)