
from sqlalchemy import update

from src.database.database import SessionLocal
from src.database.models import Ticket
from src.utils.error_handler import log_info


# ============================================================
# TICKET STATUS DEFINITIONS
# ============================================================

OPEN = "Open"
IN_PROGRESS = "In Progress"
RESOLVED = "Resolved"
CLOSED = "Closed"
ESCALATED = "Escalated"

WAITING_REVIEW = "Waiting for Human Review"
REVIEW_IN_PROGRESS = "Review in Progress"

APPROVED = "Human Approved - Ready for IT Action"
REJECTED = "Human Rejected - Further Investigation Required"

MANUAL_CLASSIFICATION = (
    "Human Review Accepted - Manual Classification Required"
)

RECOMMENDATION_GENERATED = "Recommendation Generated"


# ============================================================
# ALLOWED STATUS TRANSITIONS
# ============================================================

ALLOWED_TRANSITIONS = {

    OPEN: {
        IN_PROGRESS,
        ESCALATED,
    },

    RECOMMENDATION_GENERATED: {
        IN_PROGRESS,
        ESCALATED,
    },

    APPROVED: {
        IN_PROGRESS,
        ESCALATED,
    },

    REJECTED: {
        ESCALATED,
    },

    MANUAL_CLASSIFICATION: {
        ESCALATED,
    },

    IN_PROGRESS: {
        RESOLVED,
        ESCALATED,
    },

    ESCALATED: {
        IN_PROGRESS,
    },

    RESOLVED: {
        CLOSED,
        IN_PROGRESS,
    },

    CLOSED: set(),

    # Managed by LangGraph human review.
    WAITING_REVIEW: set(),
    REVIEW_IN_PROGRESS: set(),
}


# ============================================================
# VALIDATE STATUS TRANSITION
# ============================================================

def validate_status_transition(current_status, new_status):

    return new_status in ALLOWED_TRANSITIONS.get(
        current_status,
        set(),
    )


# ============================================================
# GET AVAILABLE NEXT STATUSES
# ============================================================

def get_available_statuses(current_status):

    return sorted(
        ALLOWED_TRANSITIONS.get(
            current_status,
            set(),
        )
    )


# ============================================================
# CHANGE TICKET STATUS
# ============================================================

def change_ticket_status(ticket_id, new_status):
    """
    Change ticket status with a conditional database update.

    Prevents invalid transitions and avoids overwriting
    another status update that happened concurrently.
    """

    db = SessionLocal()

    try:

        ticket = db.get(Ticket, ticket_id)

        if ticket is None:
            raise ValueError(
                f"Ticket not found: {ticket_id}"
            )

        current_status = ticket.status

        if not validate_status_transition(
            current_status,
            new_status,
        ):
            raise ValueError(
                f"Invalid status transition: "
                f"{current_status} -> {new_status}"
            )

        statement = (
            update(Ticket)
            .where(
                Ticket.ticket_id == ticket_id,
                Ticket.status == current_status,
            )
            .values(status=new_status)
        )

        result = db.execute(statement)

        if result.rowcount != 1:

            db.rollback()

            raise RuntimeError(
                "Ticket status changed concurrently. "
                "Refresh and try again."
            )

        db.commit()

        log_info(
            f"Ticket {ticket_id}: "
            f"{current_status} -> {new_status}"
        )

        return {
            "ticket_id": ticket_id,
            "previous_status": current_status,
            "new_status": new_status,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# TEST LIFECYCLE RULES
# ============================================================

if __name__ == "__main__":

    examples = [
        (OPEN, IN_PROGRESS),
        (IN_PROGRESS, RESOLVED),
        (RESOLVED, CLOSED),
        (CLOSED, IN_PROGRESS),
        (WAITING_REVIEW, RESOLVED),
    ]

    print("\nTICKET LIFECYCLE TEST")
    print("=" * 50)

    for current, new in examples:

        valid = validate_status_transition(
            current,
            new,
        )

        print(
            f"{current} -> {new}: "
            f"{'ALLOWED' if valid else 'BLOCKED'}"
        )
