
from src.database.database import SessionLocal
from src.database.models import Ticket

from src.workflow.graph import (
    build_support_graph,
    recover_ticket,
)

from src.workflow.checkpointer import get_checkpointer

from src.utils.error_handler import (
    log_info,
    log_warning,
    handle_error,
)


# ============================================================
# VALID COMPLETED HUMAN DECISIONS
# ============================================================

VALID_DECISIONS = {
    "Approved",
    "Rejected",
}


# ============================================================
# RECONCILE ONE TICKET
# ============================================================

def reconcile_ticket(ticket_id, dry_run=True):
    """
    Compare PostgreSQL ticket status with its
    LangGraph checkpoint.

    dry_run=True:
        Inspect only. Do not modify PostgreSQL.

    dry_run=False:
        Repair a completed review when the
        checkpoint contains a valid decision.

    Never automatically resume LangGraph.
    """

    db = SessionLocal()

    try:
        ticket = db.get(Ticket, ticket_id)

        if ticket is None:
            return {
                "ticket_id": ticket_id,
                "result": "NOT_FOUND",
                "message": "Ticket does not exist.",
            }

        with get_checkpointer() as checkpointer:

            graph = build_support_graph(checkpointer)

            try:
                snapshot, config = recover_ticket(
                    app=graph,
                    thread_id=ticket_id,
                )

            except ValueError:
                return {
                    "ticket_id": ticket_id,
                    "result": "MISSING_CHECKPOINT",
                    "message": (
                        "No recoverable LangGraph "
                        "checkpoint was found."
                    ),
                }

            state = dict(snapshot.values)

            workflow_pending = (
                "human_review" in snapshot.next
            )

            workflow_finished = (
                not snapshot.next
            )

            workflow_decision = state.get(
                "human_decision"
            )

            database_decision = ticket.human_decision

            # ------------------------------------------------
            # CASE 1: WORKFLOW FINISHED WITH VALID DECISION
            # ------------------------------------------------

            if (
                workflow_finished
                and workflow_decision in VALID_DECISIONS
            ):

                if (
                    database_decision == workflow_decision
                    and ticket.status == state.get("status")
                ):

                    return {
                        "ticket_id": ticket_id,
                        "result": "ALREADY_SYNCED",
                        "message": (
                            "Database and checkpoint match."
                        ),
                    }

                if (
                    database_decision is not None
                    and database_decision != workflow_decision
                ):

                    return {
                        "ticket_id": ticket_id,
                        "result": "DECISION_CONFLICT",
                        "message": (
                            "Database and workflow decisions "
                            "conflict. Manual investigation required."
                        ),
                    }

                if dry_run:

                    return {
                        "ticket_id": ticket_id,
                        "result": "REPAIR_AVAILABLE",
                        "message": (
                            "Completed workflow can be "
                            "synchronized to PostgreSQL."
                        ),
                    }

                # Lock row before changing it.
                locked_ticket = (
                    db.query(Ticket)
                    .filter(Ticket.ticket_id == ticket_id)
                    .with_for_update()
                    .one()
                )

                # Recheck after acquiring lock.
                if (
                    locked_ticket.human_decision is not None
                    and locked_ticket.human_decision
                    != workflow_decision
                ):
                    db.rollback()

                    return {
                        "ticket_id": ticket_id,
                        "result": "DECISION_CONFLICT",
                        "message": (
                            "Decision changed during repair."
                        ),
                    }

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
                    if field in state:
                        setattr(
                            locked_ticket,
                            field,
                            state[field],
                        )

                db.commit()

                log_info(
                    f"Reconciled completed ticket: {ticket_id}"
                )

                return {
                    "ticket_id": ticket_id,
                    "result": "REPAIRED",
                    "message": (
                        "Ticket synchronized from "
                        "completed LangGraph checkpoint."
                    ),
                }

            # ------------------------------------------------
            # CASE 2: WORKFLOW STILL WAITING FOR REVIEW
            # ------------------------------------------------

            if workflow_pending:

                if ticket.status == "Review in Progress":

                    return {
                        "ticket_id": ticket_id,
                        "result": "STALE_CLAIM_POSSIBLE",
                        "message": (
                            "Workflow is still paused, but "
                            "the ticket is claimed. "
                            "Administrator investigation required."
                        ),
                    }

                if ticket.status == "Waiting for Human Review":

                    return {
                        "ticket_id": ticket_id,
                        "result": "PENDING_REVIEW",
                        "message": (
                            "Ticket is correctly waiting "
                            "for administrator review."
                        ),
                    }

                return {
                    "ticket_id": ticket_id,
                    "result": "STATUS_MISMATCH",
                    "message": (
                        "Workflow is paused but the database "
                        "has a different status."
                    ),
                }

            # ------------------------------------------------
            # CASE 3: UNEXPECTED WORKFLOW STATE
            # ------------------------------------------------

            return {
                "ticket_id": ticket_id,
                "result": "MANUAL_INVESTIGATION",
                "message": (
                    "Checkpoint has no pending review "
                    "and no completed human decision."
                ),
            }

    except Exception as error:

        db.rollback()

        handle_error(
            error,
            context=f"Reconcile Ticket {ticket_id}",
        )

        raise

    finally:
        db.close()


# ============================================================
# RECONCILE ALL REVIEW-RELATED TICKETS
# ============================================================

def reconcile_review_tickets(dry_run=True):

    db = SessionLocal()

    try:
        ticket_ids = [
            row[0]
            for row in (
                db.query(Ticket.ticket_id)
                .filter(
                    Ticket.status.in_(
                        [
                            "Waiting for Human Review",
                            "Review in Progress",
                        ]
                    )
                )
                .all()
            )
        ]

    finally:
        db.close()

    results = []

    for ticket_id in ticket_ids:

        try:
            result = reconcile_ticket(
                ticket_id=ticket_id,
                dry_run=dry_run,
            )

            results.append(result)

        except Exception as error:

            results.append({
                "ticket_id": ticket_id,
                "result": "ERROR",
                "message": str(error),
            })

    return results


# ============================================================
# COMMAND-LINE TEST
# ============================================================

if __name__ == "__main__":

    print("\nLANGGRAPH / POSTGRESQL RECONCILIATION")
    print("=" * 50)

    results = reconcile_review_tickets(
        dry_run=True
    )

    if not results:
        print("No review-related tickets found.")

    for item in results:

        print("\nTicket:", item["ticket_id"])
        print("Result:", item["result"])
        print("Message:", item["message"])
        print("-" * 50)
