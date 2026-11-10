"""Authentication and user management for the IT Support application.

Uses the existing PostgreSQL engine and auth_users table.
The public registration function always creates employee accounts.
Staff creation and role changes require a verified admin identity supplied by
an authenticated, trusted server-side session.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.auth.database import auth_session
from src.auth.models import User, UserRole
from src.auth.passwords import hash_password, password_needs_rehash, verify_password

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
VALID_ROLES = {role.value for role in UserRole}
STAFF_ROLES = {UserRole.IT_SUPPORT.value, UserRole.IT_ADMIN.value}


class AuthenticationError(Exception):
    """Invalid login credentials or login portal."""


class AuthorizationError(PermissionError):
    """Authenticated user lacks the required role."""


class DuplicateEmailError(ValueError):
    """An account already exists with the supplied email."""


def normalize_email(email: str) -> str:
    if not isinstance(email, str):
        raise ValueError("A valid email address is required.")
    value = email.strip().lower()
    if len(value) > 255 or not EMAIL_PATTERN.fullmatch(value):
        raise ValueError("A valid email address is required.")
    return value


def validate_full_name(full_name: str) -> str:
    if not isinstance(full_name, str):
        raise ValueError("Full name is required.")
    value = " ".join(full_name.split())
    if not 2 <= len(value) <= 150:
        raise ValueError("Full name must contain 2 to 150 characters.")
    return value


def user_to_dict(user: User) -> dict[str, Any]:
    """Return safe account details; never expose the password hash."""
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
    }


def register_employee(full_name: str, email: str, password: str) -> dict[str, Any]:
    """Public registration: the role is always employee, never caller-selected."""
    name = validate_full_name(full_name)
    normalized_email = normalize_email(email)
    password_digest = hash_password(password)

    try:
        with auth_session() as session:
            existing = session.scalar(
                select(User.id).where(func.lower(User.email) == normalized_email)
            )
            if existing is not None:
                raise DuplicateEmailError("An account with this email already exists.")
            user = User(
                full_name=name,
                email=normalized_email,
                password_hash=password_digest,
                role=UserRole.EMPLOYEE.value,
                is_active=True,
            )
            session.add(user)
            session.flush()
            return user_to_dict(user)
    except IntegrityError as exc:
        raise DuplicateEmailError("An account with this email already exists.") from exc


def authenticate_user(email: str, password: str, portal: str) -> dict[str, Any] | None:
    """Authenticate for 'employee' or 'it_desk'; return safe details or None.

    A generic failure prevents disclosing whether an account exists or is inactive.
    Callers should apply login rate limiting and secure session management.
    """
    if portal not in {"employee", "it_desk"}:
        raise ValueError("Portal must be 'employee' or 'it_desk'.")
    try:
        normalized_email = normalize_email(email)
    except ValueError:
        return None
    if not isinstance(password, str) or not password:
        return None

    with auth_session() as session:
        user = session.scalar(
            select(User).where(func.lower(User.email) == normalized_email)
        )
        if user is None or not user.is_active:
            return None
        if portal == "employee" and user.role != UserRole.EMPLOYEE.value:
            return None
        if portal == "it_desk" and user.role not in STAFF_ROLES:
            return None
        if not verify_password(password, user.password_hash):
            return None
        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        return user_to_dict(user)


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    """Return a user's safe profile; authorize access at the caller boundary."""
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        return None
    with auth_session() as session:
        user = session.get(User, user_id)
        return user_to_dict(user) if user else None


def get_user_by_email(email: str) -> dict[str, Any] | None:
    """Administrative lookup; never expose this publicly without authorization."""
    normalized_email = normalize_email(email)
    with auth_session() as session:
        user = session.scalar(
            select(User).where(func.lower(User.email) == normalized_email)
        )
        return user_to_dict(user) if user else None


def require_role(user_id: int, allowed_roles: set[str] | frozenset[str]) -> dict[str, Any]:
    """Recheck the current database role for protected operations."""
    user = get_user_by_id(user_id)
    if not user or not user["is_active"] or user["role"] not in allowed_roles:
        raise AuthorizationError("You do not have permission for this action.")
    return user


def create_staff_account(
    acting_admin_id: int,
    full_name: str,
    email: str,
    password: str,
    role: str = UserRole.IT_SUPPORT.value,
) -> dict[str, Any]:
    """Provision IT Support or IT Admin accounts; admin authorization required.

    acting_admin_id must come from a verified server-side authenticated session,
    not a user-editable form field.
    """
    if role not in STAFF_ROLES:
        raise ValueError("Staff role must be 'it_support' or 'it_admin'.")
    name = validate_full_name(full_name)
    normalized_email = normalize_email(email)
    password_digest = hash_password(password)

    try:
        with auth_session() as session:
            admin = session.get(User, acting_admin_id)
            if not admin or not admin.is_active or admin.role != UserRole.IT_ADMIN.value:
                raise AuthorizationError("Only an active IT Admin can create staff accounts.")
            existing = session.scalar(
                select(User.id).where(func.lower(User.email) == normalized_email)
            )
            if existing is not None:
                raise DuplicateEmailError("An account with this email already exists.")
            user = User(
                full_name=name,
                email=normalized_email,
                password_hash=password_digest,
                role=role,
                is_active=True,
            )
            session.add(user)
            session.flush()
            return user_to_dict(user)
    except IntegrityError as exc:
        raise DuplicateEmailError("An account with this email already exists.") from exc


def set_user_active(acting_admin_id: int, target_user_id: int, active: bool) -> dict[str, Any]:
    """Enable/disable an account. Admin cannot disable their own account."""
    with auth_session() as session:
        admin = session.get(User, acting_admin_id)
        if not admin or not admin.is_active or admin.role != UserRole.IT_ADMIN.value:
            raise AuthorizationError("Only an active IT Admin can manage accounts.")
        target = session.get(User, target_user_id)
        if target is None:
            raise ValueError("User not found.")
        if target.id == admin.id and not active:
            raise ValueError("You cannot disable your own admin account.")
        target.is_active = bool(active)
        session.flush()
        return user_to_dict(target)
