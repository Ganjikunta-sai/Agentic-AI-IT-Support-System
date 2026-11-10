
from sqlalchemy import update

from src.database.database import SessionLocal
from src.database.models import Ticket
from src.database.ticket_lifecycle import (
    validate_status_transition,
)
from src.utils.error_handler import log_info


# ============================================================
# ESCALATE SUPPORT TICKET
# ============================================================

def escalate_ticket(ticket_id, reason):
    """
    Escalate a ticket and save the reason in one
    PostgreSQL transaction.

    Returns ticket ID, previous status, new status,
    and escalation reason.
    """

    reason = str(reason or "").strip()

    if not reason:
        raise ValueError(
            "Escalation reason cannot be empty."
        )

    db = SessionLocal()

    try:
        ticket = db.get(Ticket, ticket_id)

        if ticket is None:
            raise ValueError(
                f"Ticket not found: {ticket_id}"
            )

        previous_status = ticket.status

        if not validate_status_transition(
            previous_status,
            "Escalated",
        ):
            raise ValueError(
                "Escalation is not allowed from "
                f"status: {previous_status}"
            )

        # Atomic conditional update
        statement = (
            update(Ticket)
            .where(
                Ticket.ticket_id == ticket_id,
                Ticket.status == previous_status,
            )
            .values(
                status="Escalated",
                escalation_reason=reason,
            )
        )

        result = db.execute(statement)

        if result.rowcount != 1:
            raise RuntimeError(
                "Ticket status changed during escalation. "
                "Refresh and try again."
            )

        db.commit()

        log_info(
            f"Ticket escalated: {ticket_id}"
        )

        return {
            "ticket_id": ticket_id,
            "previous_status": previous_status,
            "status": "Escalated",
            "reason": reason,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# CHECK WHETHER ESCALATION IS ALLOWED
# ============================================================

def can_escalate(ticket_id):

    db = SessionLocal()

    try:
        ticket = db.get(Ticket, ticket_id)

        if ticket is None:
            return False

        return validate_status_transition(
            ticket.status,
            "Escalated",
        )

    finally:
        db.close()
