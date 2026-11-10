
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError

from src.database.database import SessionLocal
from src.database.models import Ticket
from src.utils.error_handler import log_info, handle_error


# ============================================================
# SAVE NEW SUPPORT TICKET
# ============================================================

def save_ticket(ticket_id, employee_name, issue, result):

    db = SessionLocal()

    try:
        existing_ticket = db.get(Ticket, ticket_id)

        if existing_ticket is not None:
            raise ValueError(
                f"Ticket already exists: {ticket_id}"
            )

        ticket = Ticket(
            ticket_id=ticket_id,
            employee_name=employee_name,
            issue=issue,
            category=result.get("category"),
            issue_type=result.get("issue_type"),
            impact=result.get("impact"),
            urgency=result.get("urgency"),
            summary=result.get("summary"),
            priority=result.get("priority"),
            priority_reason=result.get("priority_reason"),
            recommended_steps=result.get(
                "recommended_steps", []
            ),
            explanation=result.get("explanation"),
            confidence=result.get("confidence"),
            needs_human_review=result.get(
                "needs_human_review", False
            ),
            escalation_reason=result.get(
                "escalation_reason"
            ),
            human_decision=result.get("human_decision"),
            sources=result.get("sources", []),
            status=result.get("status", "Open"),
        )

        db.add(ticket)
        db.commit()

        log_info(f"Ticket saved: {ticket_id}")

        return ticket_id

    except Exception as error:
        db.rollback()
        handle_error(error, context="Save Ticket")
        raise

    finally:
        db.close()


# ============================================================
# GET ALL TICKETS
# ============================================================

def get_all_tickets():

    db = SessionLocal()

    try:
        return (
            db.query(Ticket)
            .order_by(Ticket.created_at.desc())
            .all()
        )

    finally:
        db.close()


# ============================================================
# GET TICKET BY ID
# ============================================================

def get_ticket_by_id(ticket_id):

    db = SessionLocal()

    try:
        return db.get(Ticket, ticket_id)

    finally:
        db.close()


# ============================================================
# UPDATE TICKET
# ============================================================

def update_ticket(ticket_id, result):

    db = SessionLocal()

    try:
        ticket = db.get(Ticket, ticket_id)

        if ticket is None:
            raise ValueError(
                f"Ticket not found: {ticket_id}"
            )

        fields = [
            "category",
            "issue_type",
            "impact",
            "urgency",
            "summary",
            "priority",
            "priority_reason",
            "recommended_steps",
            "explanation",
            "confidence",
            "needs_human_review",
            "escalation_reason",
            "human_decision",
            "sources",
            "status",
        ]

        for field in fields:

            if field in result:
                setattr(ticket, field, result[field])

        db.commit()

        log_info(f"Ticket updated: {ticket_id}")

        return ticket_id

    except Exception as error:
        db.rollback()
        handle_error(error, context="Update Ticket")
        raise

    finally:
        db.close()


# ============================================================
# ATOMICALLY CLAIM TICKET FOR ADMINISTRATOR REVIEW
# ============================================================

def claim_ticket_for_review(ticket_id):
    """
    Only one administrator can successfully claim
    a ticket that is waiting for human review.

    Returns:
        True  - Ticket claimed successfully
        False - Ticket unavailable or already claimed
    """

    db = SessionLocal()

    try:

        statement = (
            update(Ticket)
            .where(
                Ticket.ticket_id == ticket_id,
                Ticket.status == "Waiting for Human Review",
                Ticket.human_decision.is_(None),
            )
            .values(
                status="Review in Progress"
            )
        )

        result = db.execute(statement)

        claimed = result.rowcount == 1

        db.commit()

        if claimed:
            log_info(
                f"Ticket claimed for review: {ticket_id}"
            )

        return claimed

    except Exception as error:

        db.rollback()

        handle_error(
            error,
            context="Claim Ticket for Review",
        )

        raise

    finally:
        db.close()


# ============================================================
# RELEASE REVIEW CLAIM
# ============================================================

def release_review_claim(ticket_id):
    """
    Release a review claim only if no decision
    has been recorded.

    WARNING:
    Call this only after confirming that the
    LangGraph workflow has not already resumed.
    """

    db = SessionLocal()

    try:

        statement = (
            update(Ticket)
            .where(
                Ticket.ticket_id == ticket_id,
                Ticket.status == "Review in Progress",
                Ticket.human_decision.is_(None),
            )
            .values(
                status="Waiting for Human Review"
            )
        )

        result = db.execute(statement)

        released = result.rowcount == 1

        db.commit()

        if released:
            log_info(
                f"Review claim released: {ticket_id}"
            )

        return released

    except Exception as error:

        db.rollback()

        handle_error(
            error,
            context="Release Review Claim",
        )

        raise

    finally:
        db.close()


# ============================================================
# TEST DATABASE OPERATIONS
# ============================================================

if __name__ == "__main__":

    print("\nSAVED SUPPORT TICKETS")
    print("=" * 50)

    tickets = get_all_tickets()

    if not tickets:
        print("No tickets found.")

    for ticket in tickets:

        print("\nTicket ID:", ticket.ticket_id)
        print("Employee:", ticket.employee_name)
        print("Issue:", ticket.issue)
        print("Category:", ticket.category)
        print("Priority:", ticket.priority)
        print("Status:", ticket.status)
        print("Human Decision:", ticket.human_decision)
        print("-" * 50)
