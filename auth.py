"""
auth.py — Role resolution and session helpers for RCBA Event Reporter.

Roles:
  secretariat  → full admin (was 'admin')
  editor       → view all reports, download, submit own
  director     → submit own reports, view only own

'admin' role is kept as an alias for 'secretariat' for backwards compatibility.
"""

import os
import json
from typing import Literal

ROLES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "roles.json")

RoleType = Literal["admin", "secretariat", "editor", "director"]


def load_roles() -> dict:
    if not os.path.exists(ROLES_FILE):
        return {"admin_emails": [], "secretariat_emails": [], "director_emails": [], "editor_emails": [], "roles": {}}
    with open(ROLES_FILE) as f:
        return json.load(f)


def get_role(email: str) -> RoleType:
    """
    Returns one of: 'admin', 'secretariat', 'editor', 'director'.
    Precedence: admin > secretariat > editor > director (default).
    """
    data = load_roles()
    email = email.strip().lower()

    admin        = [e.strip().lower() for e in data.get("admin_emails", [])]
    secretariat  = [e.strip().lower() for e in data.get("secretariat_emails", [])]
    editors      = [e.strip().lower() for e in data.get("editor_emails", [])]
    directors    = [e.strip().lower() for e in data.get("director_emails", [])]
    roles_map    = {k.strip().lower(): v for k, v in data.get("roles", {}).items()}

    if email in admin:
        return "admin"
    if email in secretariat:
        return "secretariat"
    if email in editors:
        return "editor"
    if email in directors:
        return "director"

    # legacy roles map
    mapped = roles_map.get(email, "")
    if mapped == "admin":
        return "admin"
    if mapped == "secretariat":
        return "secretariat"
    if mapped == "editor":
        return "editor"

    return "director"  # default for all whitelisted members


def is_admin(role: str) -> bool:
    return role == "admin"


def is_secretariat(role: str) -> bool:
    return role == "secretariat"


def is_admin_or_secretariat(role: str) -> bool:
    return role in ("admin", "secretariat")


def can_approve_reject(role: str) -> bool:
    return is_admin_or_secretariat(role)


def can_view_all_reports(role: str) -> bool:
    return role in ("admin", "secretariat", "editor")


def can_submit_report(role: str) -> bool:
    return role in ("admin", "secretariat", "director", "editor")


def can_mark_late(role: str) -> bool:
    return is_admin_or_secretariat(role)


def role_display_label(role: str) -> str:
    mapping = {
        "admin": "Admin",
        "secretariat": "Secretariat",
        "editor": "Editor",
        "director": "Director",
    }
    return mapping.get(role, "Member")


def role_badge_class(role: str) -> str:
    mapping = {
        "admin": "admin",
        "secretariat": "secretariat",
        "editor": "editor",
        "director": "director",
    }
    return mapping.get(role, "director")
