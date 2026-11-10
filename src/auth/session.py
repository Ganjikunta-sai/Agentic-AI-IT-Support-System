
"""Streamlit session helpers for the two IT Support login portals.

This is a Streamlit session-state implementation for an internal/demo app.
For a public Render deployment, use an external identity provider or a
server-validated, revocable session mechanism, plus login rate limiting.
Never treat a user ID received from a form as proof of authentication.
"""

from __future__ import annotations

import time
from typing import Any, Iterable

import streamlit as st

from src.auth.models import UserRole
from src.auth.service import authenticate_user, get_user_by_id, AuthorizationError

SESSION_KEY = "_it_support_auth_session"
SESSION_LIFETIME_SECONDS = 8 * 60 * 60
EMPLOYEE_ROLE = UserRole.EMPLOYEE.value
STAFF_ROLES = frozenset({UserRole.IT_SUPPORT.value, UserRole.IT_ADMIN.value})
ADMIN_ROLES = frozenset({UserRole.IT_ADMIN.value})
VALID_PORTALS = frozenset({"employee", "it_desk"})


def _clear_auth_state() -> None:
    st.session_state.pop(SESSION_KEY, None)


def login(email: str, password: str, portal: str) -> dict[str, Any] | None:
    """Verify credentials and establish the Streamlit session.

    Returns a safe user profile on success, or None on invalid credentials.
    The calling page should display a generic failure message and apply
    rate limiting before invoking this function.
    """
    if portal not in VALID_PORTALS:
        raise ValueError("Portal must be 'employee' or 'it_desk'.")

    _clear_auth_state()
    user = authenticate_user(email=email, password=password, portal=portal)
    if user is None:
        return None

    st.session_state[SESSION_KEY] = {
        "user_id": user["id"],
        "portal": portal,
        "authenticated_at": time.time(),
    }
    return user


def logout() -> None:
    """End this Streamlit session's authentication state."""
    _clear_auth_state()


def current_user() -> dict[str, Any] | None:
    """Return the current active user after checking the database.

    Refreshing on each call ensures that disabled accounts and role changes
    take effect on the next interaction. This does not make session_state a
    production-grade authentication store.
    """
    session = st.session_state.get(SESSION_KEY)
    if not isinstance(session, dict):
        return None

    user_id = session.get("user_id")
    portal = session.get("portal")
    authenticated_at = session.get("authenticated_at")

    if (
        type(user_id) is not int
        or user_id <= 0
        or portal not in VALID_PORTALS
        or type(authenticated_at) not in (int, float)
        or authenticated_at > time.time() + 60
        or time.time() - authenticated_at >= SESSION_LIFETIME_SECONDS
    ):
        _clear_auth_state()
        return None

    user = get_user_by_id(user_id)
    if not user or not user.get("is_active"):
        _clear_auth_state()
        return None

    role = user.get("role")
    if portal == "employee" and role != EMPLOYEE_ROLE:
        _clear_auth_state()
        return None
    if portal == "it_desk" and role not in STAFF_ROLES:
        _clear_auth_state()
        return None

    return user


def is_logged_in() -> bool:
    return current_user() is not None


def require_login(portal: str | None = None) -> dict[str, Any]:
    """Protect a Streamlit page; stop rendering if not authenticated."""
    if portal is not None and portal not in VALID_PORTALS:
        raise ValueError("Invalid portal.")

    user = current_user()
    session = st.session_state.get(SESSION_KEY)
    if user is None or (portal is not None and session["portal"] != portal):
        st.error("Please log in to access this page.")
        st.stop()
    return user


def require_roles(roles: Iterable[str], portal: str | None = None) -> dict[str, Any]:
    """Require an active user with one of the specified database roles."""
    allowed = frozenset(roles)
    if not allowed or not allowed.issubset({r.value for r in UserRole}):
        raise ValueError("Provide one or more valid roles.")

    user = require_login(portal=portal)
    if user["role"] not in allowed:
        st.error("You do not have permission to access this page.")
        st.stop()
    return user


def require_employee() -> dict[str, Any]:
    return require_roles({EMPLOYEE_ROLE}, portal="employee")


def require_it_staff() -> dict[str, Any]:
    return require_roles(STAFF_ROLES, portal="it_desk")


def require_it_admin() -> dict[str, Any]:
    return require_roles(ADMIN_ROLES, portal="it_desk")


def has_role(role: str) -> bool:
    user = current_user()
    return bool(user and user["role"] == role)


def get_authenticated_user_id() -> int | None:
    """Only use after current_user() has validated the active session."""
    user = current_user()
    return user["id"] if user else None
