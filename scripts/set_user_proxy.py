#!/usr/bin/env python3
"""
CLI script to inspect and manage user assigned stealth proxies in ProfileStack.
Usage:
  python3 scripts/set_user_proxy.py list
  python3 scripts/set_user_proxy.py get <username>
  python3 scripts/set_user_proxy.py set <username> <proxy_url>
  python3 scripts/set_user_proxy.py clear <username>
"""
import sys
import os

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.auth_manager import list_users, get_user_assigned_proxy, set_user_proxy

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print("ProfileStack User Stealth Proxy Manager")
        print("Usage:")
        print("  python3 scripts/set_user_proxy.py list")
        print("  python3 scripts/set_user_proxy.py get <username>")
        print("  python3 scripts/set_user_proxy.py set <username> <proxy_url>")
        print("  python3 scripts/set_user_proxy.py clear <username>")
        sys.exit(0)

    cmd = args[0].lower()
    if cmd == "list":
        print("User Assigned Proxies (Hidden from standard users):")
        for u in list_users(is_admin=True):
            proxy = u.get("assigned_proxy") or "(none - direct)"
            print(f"  - {u['username']} (role: {u.get('role', 'user')}): {proxy}")
    elif cmd == "get":
        if len(args) < 2:
            print("Error: Missing username. Usage: python3 scripts/set_user_proxy.py get <username>")
            sys.exit(1)
        uname = args[1].strip()
        proxy = get_user_assigned_proxy(uname)
        if proxy:
            print(f"User '{uname}' assigned proxy: {proxy}")
        else:
            print(f"User '{uname}' has no assigned proxy (Direct).")
    elif cmd == "set":
        if len(args) < 3:
            print("Error: Missing arguments. Usage: python3 scripts/set_user_proxy.py set <username> <proxy_url>")
            sys.exit(1)
        uname = args[1].strip()
        proxy_val = args[2].strip()
        try:
            set_user_proxy(uname, proxy_val)
            print(f"Assigned stealth proxy set for user '{uname}' -> {proxy_val}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif cmd == "clear":
        if len(args) < 2:
            print("Error: Missing username. Usage: python3 scripts/set_user_proxy.py clear <username>")
            sys.exit(1)
        uname = args[1].strip()
        try:
            set_user_proxy(uname, "")
            print(f"Assigned stealth proxy cleared for user '{uname}'.")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        print(f"Unknown command '{cmd}'. Run with --help for usage.")
        sys.exit(1)

if __name__ == "__main__":
    main()
