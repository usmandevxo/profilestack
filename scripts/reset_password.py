#!/usr/bin/env python3
"""
CLI script to reset user passwords in ProfileStack.
Usage:
  python3 scripts/reset_password.py <username> <new_password>
"""
import sys
import os

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.auth_manager import admin_reset_password, list_users, get_user

def main():
    if len(sys.argv) < 3:
        print("ProfileStack Password Reset Tool")
        print("Usage:")
        print("  python3 scripts/reset_password.py <username> <new_password>")
        print("\nRegistered Users:")
        for u in list_users():
            print(f"  - {u['username']} (role: {u.get('role', 'user')}, status: {u.get('status', 'active')})")
        sys.exit(1)

    username = sys.argv[1].strip()
    new_password = sys.argv[2]

    try:
        admin_reset_password(username, new_password)
        print(f"Password reset successfully for user '{username}'.")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
