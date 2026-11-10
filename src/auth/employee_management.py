"""Admin-only employee activation management.

Uses the existing PostgreSQL engine and auth_users model. Does not delete
accounts or modify ticket tables. Call only with actor_user_id obtained from
a validated server-side authentication session, never from a form field.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from src.auth.database import auth_session, get_existing_engine
from src.auth.models import User, UserBase, UserRole


class EmployeeManagementError(Exception):
    """Base error for employee management operations."""


class PermissionDenied(EmployeeManagementError):
    """The actor is not an active IT administrator."""


class EmployeeNotFound(EmployeeManagementError):
    """The requested employee account does not exist."""


class InvalidEmployeeAction(EmployeeManagementError):
    """The requested operation is invalid for this account."""


class EmployeeAccountEvent(UserBase):
    """Append-only audit trail for employee activation changes."""

    __tablename__ = "employee_account_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actor_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


def initialize_employee_management() -> None:
    """Create only the new audit table; do not modify existing ticket tables."""
    EmployeeAccountEvent.__table__.create(bind=get_existing_engine(), checkfirst=True)


def _require_admin(session: Any, actor_user_id: int) -> User:
    if type(actor_user_id) is not int or actor_user_id <= 0:
        raise PermissionDenied("A valid authenticated administrator is required.")
    actor = session.scalar(
        select(User).where(User.id == actor_user_id).with_for_update()
    )
    if actor is None or not actor.is_active or actor.role != UserRole.IT_ADMIN.value:
        raise PermissionDenied("Only an active IT Admin may manage employee accounts.")
    return actor


def _change_employee_status(
    *, actor_user_id: int, employee_user_id: int, active: bool, reason: str
) -> dict[str, Any]:
    if type(employee_user_id) is not int or employee_user_id <= 0:
        raise EmployeeNotFound("Invalid employee account ID.")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("A reason is required for this action.")
    reason = reason.strip()
    if len(reason) > 1000:
        raise ValueError("Reason must be 1000 characters or fewer.")

    # Create the audit table before starting the account update transaction.
    initialize_employee_management()
    with auth_session() as session:
        _require_admin(session, actor_user_id)
        employee = session.scalar(
            select(User).where(User.id == employee_user_id).with_for_update()
        )
        if employee is None:
            raise EmployeeNotFound("Employee account not found.")
        if employee.role != UserRole.EMPLOYEE.value:
            raise InvalidEmployeeAction("Only employee accounts can be changed here.")
        if active:
            last_action = session.scalar(
                select(EmployeeAccountEvent.action)
                .where(EmployeeAccountEvent.employee_user_id == employee_user_id)
                .order_by(EmployeeAccountEvent.id.desc())
                .limit(1)
            )
            if last_action == "soft_deleted":
                raise InvalidEmployeeAction(
                    "Soft-deleted accounts cannot be reactivated from the normal screen."
                )
        if employee.is_active == active:
            state = "active" if active else "inactive"
            raise InvalidEmployeeAction(f"Employee account is already {state}.")

        employee.is_active = active
        action = "reactivated" if active else "deactivated"
        session.add(EmployeeAccountEvent(
            employee_user_id=employee.id,
            actor_user_id=actor_user_id,
            action=action,
            reason=reason,
        ))
        session.flush()
        result = {
            "employee_id": employee.id,
            "email": employee.email,
            "is_active": employee.is_active,
            "action": action,
        }
    return result


def deactivate_employee(
    *, actor_user_id: int, employee_user_id: int, reason: str
) -> dict[str, Any]:
    """Disable an employee's login, preserving all records and ticket history."""
    return _change_employee_status(
        actor_user_id=actor_user_id,
        employee_user_id=employee_user_id,
        active=False,
        reason=reason,
    )


def reactivate_employee(
    *, actor_user_id: int, employee_user_id: int, reason: str
) -> dict[str, Any]:
    """Restore login access to an existing inactive employee account."""
    return _change_employee_status(
        actor_user_id=actor_user_id,
        employee_user_id=employee_user_id,
        active=True,
        reason=reason,
    )


def soft_delete_employee(
    *, actor_user_id: int, employee_user_id: int, reason: str
) -> dict[str, Any]:
    """Disable login and hide employee from normal listings, retaining all data.

    Records the soft deletion in the append-only account audit table. This
    operation does not delete or anonymize any ticket or account record.
    """
    if type(employee_user_id) is not int or employee_user_id <= 0:
        raise EmployeeNotFound("Invalid employee account ID.")
    if not isinstance(reason, str) or len(reason.strip()) < 5:
        raise ValueError("Provide a deletion reason of at least 5 characters.")
    reason = reason.strip()
    if len(reason) > 1000:
        raise ValueError("Reason must be 1000 characters or fewer.")

    initialize_employee_management()
    with auth_session() as session:
        _require_admin(session, actor_user_id)
        employee = session.scalar(
            select(User).where(User.id == employee_user_id).with_for_update()
        )
        if employee is None:
            raise EmployeeNotFound("Employee account not found.")
        if employee.role != UserRole.EMPLOYEE.value:
            raise InvalidEmployeeAction("Only employee accounts can be soft deleted.")
        already_deleted = session.scalar(
            select(EmployeeAccountEvent.id)
            .where(EmployeeAccountEvent.employee_user_id == employee_user_id)
            .where(EmployeeAccountEvent.action == "soft_deleted")
            .order_by(EmployeeAccountEvent.id.desc())
            .limit(1)
        )
        # A prior soft deletion remains effective until explicitly restored.
        if already_deleted is not None:
            latest = session.scalar(
                select(EmployeeAccountEvent.action)
                .where(EmployeeAccountEvent.employee_user_id == employee_user_id)
                .order_by(EmployeeAccountEvent.id.desc())
                .limit(1)
            )
            if latest == "soft_deleted":
                raise InvalidEmployeeAction("Employee is already soft deleted.")
        employee.is_active = False
        session.add(EmployeeAccountEvent(
            employee_user_id=employee.id,
            actor_user_id=actor_user_id,
            action="soft_deleted",
            reason=reason,
        ))
        session.flush()
        return {
            "employee_id": employee.id,
            "email": employee.email,
            "is_active": False,
            "action": "soft_deleted",
        }


def list_employees(
    *, actor_user_id: int, include_deleted: bool = False
) -> list[dict[str, Any]]:
    """List employee accounts, hiding soft-deleted accounts by default."""
    initialize_employee_management()
    with auth_session() as session:
        _require_admin(session, actor_user_id)
        employees = session.scalars(
            select(User)
            .where(User.role == UserRole.EMPLOYEE.value)
            .order_by(User.id)
        ).all()
        # A subsequent reactivation restores visibility.
        latest_actions = {}
        for event in session.scalars(
            select(EmployeeAccountEvent)
            .order_by(EmployeeAccountEvent.id)
        ).all():
            latest_actions[event.employee_user_id] = event.action
        result = []
        for user in employees:
            deleted = latest_actions.get(user.id) == "soft_deleted"
            if deleted and not include_deleted:
                continue
            result.append({
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "is_active": user.is_active,
                "is_deleted": deleted,
            })
        return result


def get_employee_account_history(
    *, actor_user_id: int, employee_user_id: int
) -> list[dict[str, Any]]:
    """Return recorded activation/deactivation actions for one employee."""
    initialize_employee_management()
    with auth_session() as session:
        _require_admin(session, actor_user_id)
        employee = session.get(User, employee_user_id)
        if employee is None or employee.role != UserRole.EMPLOYEE.value:
            raise EmployeeNotFound("Employee account not found.")
        events = session.scalars(
            select(EmployeeAccountEvent)
            .where(EmployeeAccountEvent.employee_user_id == employee_user_id)
            .order_by(EmployeeAccountEvent.id.desc())
        ).all()
        return [
            {"id": event.id, "action": event.action,
             "actor_user_id": event.actor_user_id,
             "reason": event.reason, "created_at": event.created_at}
            for event in events
        ]
