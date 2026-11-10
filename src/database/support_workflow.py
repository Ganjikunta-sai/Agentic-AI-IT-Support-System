"""Human IT support workflow stored separately from LangGraph checkpoints.

Requires SQLAlchemy 2.x and the existing auth models/database modules.

IMPORTANT: Every public mutation requires a *server-validated* authenticated
actor ID. Do not accept actor_user_id directly from an untrusted UI input.
The original ticket table remains untouched; call the existing ticket CRUD
functions separately if you need to mirror human statuses there.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from src.database.models import Ticket
from sqlalchemy.orm import Mapped, Session, mapped_column
from src.auth.models import UserBase

from src.auth.database import auth_session, get_existing_engine
from src.auth.models import User, UserRole


class SupportStatus(str, Enum):
    PENDING_CONTACT = "Pending Contact"
    AWAITING_EMPLOYEE = "Awaiting Employee Confirmation"
    ESCALATED = "Escalated"
    REVIEW_IN_PROGRESS = "Review in Progress"
    RESOLVED = "Resolved"


class SupportWorkflowError(Exception):
    """Raised when a human-support operation cannot be completed."""


class PermissionDenied(SupportWorkflowError):
    """The actor is not permitted to perform this operation."""


class InvalidTransition(SupportWorkflowError):
    """The requested status change is not permitted."""


SupportBase = UserBase  # Share metadata so auth_users foreign keys resolve.


class SupportCase(SupportBase):
    __tablename__ = "support_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=SupportStatus.PENDING_CONTACT.value)
    assigned_to_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("auth_users.id"), nullable=True)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class SupportEvent(SupportBase):
    __tablename__ = "support_events"
    __table_args__ = (UniqueConstraint("id", "ticket_id", name="uq_support_event_id_ticket"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("auth_users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


def initialize_support_workflow() -> None:
    """Create only the two new human-support tables, if missing."""
    SupportBase.metadata.create_all(
        bind=get_existing_engine(),
        tables=[SupportCase.__table__, SupportEvent.__table__],
        checkfirst=True,
    )


def _actor(session: Session, actor_user_id: int, *, admin_only: bool = False) -> User:
    if type(actor_user_id) is not int or actor_user_id <= 0:
        raise PermissionDenied("A validated staff session is required.")
    user = session.get(User, actor_user_id)
    if user is None or not user.is_active:
        raise PermissionDenied("Staff account is unavailable or inactive.")
    allowed = {UserRole.IT_ADMIN.value} if admin_only else {UserRole.IT_SUPPORT.value, UserRole.IT_ADMIN.value}
    if user.role not in allowed:
        raise PermissionDenied("Insufficient staff permissions.")
    return user


def _ticket_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 100:
        raise ValueError("A valid ticket ID (up to 100 characters) is required.")
    return value.strip()


def _note(value: str, field: str, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text.")
    value = value.strip()
    if required and len(value) < 5:
        raise ValueError(f"{field} must contain at least five characters.")
    if len(value) > 5000:
        raise ValueError(f"{field} must not exceed 5000 characters.")
    return value


def _ensure_ticket_exists(ticket_id: str) -> None:
    """Check the original ticket via its existing CRUD API before starting a case."""
    from src.database.crud import get_ticket_by_id

    if get_ticket_by_id(ticket_id) is None:
        raise SupportWorkflowError(f"Ticket {ticket_id!r} does not exist.")


def _mirror_ticket(session: Session, ticket_id: str, status: str, *,
                   escalation_reason: str | None = None,
                   resolution_note: str | None = None) -> None:
    """Keep legacy ticket status and human-support status in one transaction."""
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise SupportWorkflowError(f"Ticket {ticket_id!r} no longer exists.")
    ticket.status = status
    if escalation_reason is not None:
        ticket.escalation_reason = escalation_reason
        ticket.needs_human_review = True
    if resolution_note is not None:
        ticket.human_decision = "Resolved"
        ticket.needs_human_review = False


def _event(session: Session, ticket_id: str, actor_id: int, action: str, note: str = "") -> None:
    session.add(SupportEvent(ticket_id=ticket_id, actor_user_id=actor_id, action=action, note=note))


def _case(session: Session, ticket_id: str) -> SupportCase:
    case = session.scalar(select(SupportCase).where(SupportCase.ticket_id == ticket_id).with_for_update())
    if case is None:
        raise SupportWorkflowError("Support case not started. Call start_support_case first.")
    return case


def _serialize(case: SupportCase) -> dict[str, Any]:
    return {
        "ticket_id": case.ticket_id,
        "status": case.status,
        "assigned_to_id": case.assigned_to_id,
        "escalation_reason": case.escalation_reason,
        "resolution_note": case.resolution_note,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }


def start_support_case(ticket_id: str, actor_user_id: int) -> dict[str, Any]:
    """Start or return a case for an existing ticket; callable by staff only."""
    ticket_id = _ticket_id(ticket_id)
    with auth_session() as session:
        _actor(session, actor_user_id)
        existing = session.scalar(select(SupportCase).where(SupportCase.ticket_id == ticket_id))
        if existing is not None:
            return _serialize(existing)
        _ensure_ticket_exists(ticket_id)
        case = SupportCase(ticket_id=ticket_id, status=SupportStatus.PENDING_CONTACT.value)
        session.add(case)
        session.flush()
        _event(session, ticket_id, actor_user_id, "case_started")
        return _serialize(case)


def record_employee_contact(ticket_id: str, actor_user_id: int, note: str) -> dict[str, Any]:
    """Record an offline call/message and wait for employee confirmation."""
    ticket_id = _ticket_id(ticket_id)
    note = _note(note, "Contact note")
    with auth_session() as session:
        _actor(session, actor_user_id)
        case = _case(session, ticket_id)
        if case.status == SupportStatus.RESOLVED.value:
            raise InvalidTransition("Resolved cases cannot be contacted without reopening.")
        if case.status in {SupportStatus.ESCALATED.value, SupportStatus.REVIEW_IN_PROGRESS.value}:
            # Contact is allowed during investigation, but must not remove escalation.
            _event(session, ticket_id, actor_user_id, "employee_contacted", note)
            return _serialize(case)
        case.status = SupportStatus.AWAITING_EMPLOYEE.value
        _mirror_ticket(session, ticket_id, case.status)
        _event(session, ticket_id, actor_user_id, "employee_contacted", note)
        session.flush()
        return _serialize(case)


def resolve_ticket(ticket_id: str, actor_user_id: int, resolution_note: str, *, employee_confirmed: bool) -> dict[str, Any]:
    """Resolve only after explicit employee confirmation, recorded in the audit log."""
    ticket_id = _ticket_id(ticket_id)
    resolution_note = _note(resolution_note, "Resolution note")
    if employee_confirmed is not True:
        raise InvalidTransition("Employee confirmation is required before resolving.")
    with auth_session() as session:
        _actor(session, actor_user_id)
        case = _case(session, ticket_id)
        if case.status == SupportStatus.RESOLVED.value:
            raise InvalidTransition("Ticket is already resolved.")
        if case.status in {SupportStatus.ESCALATED.value, SupportStatus.REVIEW_IN_PROGRESS.value}:
            _actor(session, actor_user_id, admin_only=True)
        case.status = SupportStatus.RESOLVED.value
        case.resolution_note = resolution_note
        _mirror_ticket(session, ticket_id, case.status, resolution_note=resolution_note)
        _event(session, ticket_id, actor_user_id, "resolved_employee_confirmed", resolution_note)
        session.flush()
        return _serialize(case)


def escalate_ticket(ticket_id: str, actor_user_id: int, reason: str) -> dict[str, Any]:
    """Escalate an unresolved case with a mandatory reason."""
    ticket_id = _ticket_id(ticket_id)
    reason = _note(reason, "Escalation reason")
    with auth_session() as session:
        _actor(session, actor_user_id)
        case = _case(session, ticket_id)
        if case.status == SupportStatus.RESOLVED.value:
            raise InvalidTransition("Resolved cases cannot be escalated.")
        if case.status in {SupportStatus.ESCALATED.value, SupportStatus.REVIEW_IN_PROGRESS.value}:
            raise InvalidTransition("Case is already in the Human Review workflow.")
        case.status = SupportStatus.ESCALATED.value
        case.escalation_reason = reason
        _mirror_ticket(session, ticket_id, case.status, escalation_reason=reason)
        _event(session, ticket_id, actor_user_id, "escalated", reason)
        session.flush()
        return _serialize(case)


def begin_human_review(ticket_id: str, actor_user_id: int, note: str = "") -> dict[str, Any]:
    """IT Admin claims an escalated case for Human Review."""
    ticket_id = _ticket_id(ticket_id)
    note = _note(note, "Review note", required=False)
    with auth_session() as session:
        _actor(session, actor_user_id, admin_only=True)
        case = _case(session, ticket_id)
        if case.status != SupportStatus.ESCALATED.value:
            raise InvalidTransition("Only escalated cases can enter Human Review.")
        case.status = SupportStatus.REVIEW_IN_PROGRESS.value
        case.assigned_to_id = actor_user_id
        _mirror_ticket(session, ticket_id, case.status)
        _event(session, ticket_id, actor_user_id, "review_started", note)
        session.flush()
        return _serialize(case)


def add_review_note(ticket_id: str, actor_user_id: int, note: str) -> dict[str, Any]:
    """Append an investigation note without changing the current status."""
    ticket_id = _ticket_id(ticket_id)
    note = _note(note, "Review note")
    with auth_session() as session:
        _actor(session, actor_user_id, admin_only=True)
        case = _case(session, ticket_id)
        if case.status not in {SupportStatus.ESCALATED.value, SupportStatus.REVIEW_IN_PROGRESS.value}:
            raise InvalidTransition("Case is not in the Human Review queue.")
        _event(session, ticket_id, actor_user_id, "review_note", note)
        return _serialize(case)


def get_support_case(ticket_id: str, actor_user_id: int) -> dict[str, Any] | None:
    """Staff-only support case lookup."""
    ticket_id = _ticket_id(ticket_id)
    with auth_session() as session:
        _actor(session, actor_user_id)
        case = session.scalar(select(SupportCase).where(SupportCase.ticket_id == ticket_id))
        return _serialize(case) if case else None


def list_support_cases(actor_user_id: int, *, status: str | None = None) -> list[dict[str, Any]]:
    """All active IT staff can see case statuses; only admins can act on review."""
    with auth_session() as session:
        _actor(session, actor_user_id)
        if status is not None and status not in {s.value for s in SupportStatus}:
            raise ValueError("Unknown support status.")
        statement = select(SupportCase)
        if status is not None:
            statement = statement.where(SupportCase.status == status)
        statement = statement.order_by(SupportCase.updated_at.desc(), SupportCase.id.desc())
        return [_serialize(case) for case in session.scalars(statement).all()]


def get_support_history(ticket_id: str, actor_user_id: int) -> list[dict[str, Any]]:
    """Return an audit trail of human actions for authorized staff."""
    ticket_id = _ticket_id(ticket_id)
    with auth_session() as session:
        _actor(session, actor_user_id)
        events = session.scalars(
            select(SupportEvent)
            .where(SupportEvent.ticket_id == ticket_id)
            .order_by(SupportEvent.id.asc())
        ).all()
        return [
            {
                "action": event.action,
                "actor_user_id": event.actor_user_id,
                "note": event.note,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ]
