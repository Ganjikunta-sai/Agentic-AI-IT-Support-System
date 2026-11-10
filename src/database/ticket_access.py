"""Ticket ownership and authorization for the IT Support application.

This module adds an independent ownership table, without altering existing
support-ticket tables. Existing tickets remain unassigned until an authorized
migration explicitly associates them with an employee.

IMPORTANT: bind_new_ticket_owner must only be called by trusted backend code
immediately after creating a new ticket. Never expose it to arbitrary clients.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from src.auth.database import auth_session, get_existing_engine
from src.auth.models import User, UserBase, UserRole


class TicketOwner(UserBase):
    __tablename__ = "ticket_owners"

    ticket_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    employee_user_id: Mapped[int] = mapped_column(
        ForeignKey("auth_users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class TicketAccessDenied(PermissionError):
    """The authenticated user cannot access the requested ticket."""


class TicketOwnershipConflict(ValueError):
    """Ticket already has an owner or ownership information is invalid."""


def initialize_ticket_access() -> None:
    """Create only the ownership table, preserving all existing ticket data."""
    TicketOwner.__table__.create(bind=get_existing_engine(), checkfirst=True)


def _active_user(session: Any, user_id: int) -> User:
    if type(user_id) is not int or user_id <= 0:
        raise TicketAccessDenied("Authentication required.")
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise TicketAccessDenied("Active account required.")
    return user


def _ticket_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 100:
        raise ValueError("Invalid ticket ID.")
    return value.strip()


def bind_new_ticket_owner(ticket_id: str, employee_user_id: int) -> None:
    """Associate a newly created ticket with its employee exactly once.

    Call ONLY from trusted ticket-creation backend code, after the ticket is
    successfully saved. A failed ownership write must be treated as failed
    ticket creation by the caller; ideally use one database transaction for
    ticket creation and ownership assignment when integrating existing CRUD.
    """
    ticket_id = _ticket_id(ticket_id)
    try:
        with auth_session() as session:
            user = _active_user(session, employee_user_id)
            if user.role != UserRole.EMPLOYEE.value:
                raise TicketAccessDenied("Ticket owner must be an employee.")
            if session.get(TicketOwner, ticket_id) is not None:
                raise TicketOwnershipConflict("Ticket already has an owner.")
            session.add(TicketOwner(ticket_id=ticket_id, employee_user_id=user.id))
            session.flush()
    except IntegrityError as exc:
        raise TicketOwnershipConflict("Ticket ownership could not be saved.") from exc


def can_view_ticket(ticket_id: str, authenticated_user_id: int) -> bool:
    """Return True only for the owner or active IT staff.

    Caller must obtain authenticated_user_id from the validated server-side
    login session, never from a user-editable input field.
    """
    ticket_id = _ticket_id(ticket_id)
    with auth_session() as session:
        user = _active_user(session, authenticated_user_id)
        owner = session.get(TicketOwner, ticket_id)
        if owner is None:
            return False  # Fail closed for legacy/unassigned tickets.
        if user.role in (UserRole.IT_SUPPORT.value, UserRole.IT_ADMIN.value):
            return True
        return user.role == UserRole.EMPLOYEE.value and owner.employee_user_id == user.id


def require_ticket_access(ticket_id: str, authenticated_user_id: int) -> None:
    """Raise if this user is not authorized to access the ticket."""
    if not can_view_ticket(ticket_id, authenticated_user_id):
        raise TicketAccessDenied("Ticket not found or access denied.")


def list_employee_ticket_ids(authenticated_user_id: int) -> list[str]:
    """List IDs owned by the authenticated employee only."""
    with auth_session() as session:
        user = _active_user(session, authenticated_user_id)
        if user.role != UserRole.EMPLOYEE.value:
            raise TicketAccessDenied("Employee account required.")
        return list(session.scalars(
            select(TicketOwner.ticket_id)
            .where(TicketOwner.employee_user_id == user.id)
            .order_by(TicketOwner.created_at.desc())
        ).all())


def get_ticket_owner_id(ticket_id: str, authenticated_staff_id: int) -> int | None:
    """Return owner ID to authorized staff; None for legacy/unassigned tickets."""
    ticket_id = _ticket_id(ticket_id)
    with auth_session() as session:
        staff = _active_user(session, authenticated_staff_id)
        if staff.role not in (UserRole.IT_SUPPORT.value, UserRole.IT_ADMIN.value):
            raise TicketAccessDenied("IT Desk access required.")
        owner = session.get(TicketOwner, ticket_id)
        return owner.employee_user_id if owner else None
