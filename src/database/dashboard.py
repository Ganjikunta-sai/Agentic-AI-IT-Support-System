
from sqlalchemy import func

from src.database.database import SessionLocal
from src.database.models import Ticket


def get_dashboard_statistics():

    db = SessionLocal()

    try:
        total = db.query(Ticket).count()

        critical = db.query(Ticket).filter(
            Ticket.priority == "Critical"
        ).count()

        high = db.query(Ticket).filter(
            Ticket.priority == "High"
        ).count()

        pending_review = db.query(Ticket).filter(
            Ticket.needs_human_review == True
        ).count()

        resolved = db.query(Ticket).filter(
            Ticket.status == "Resolved"
        ).count()

        return {
            "total": total,
            "critical": critical,
            "high": high,
            "pending_review": pending_review,
            "resolved": resolved
        }

    finally:
        db.close()


def search_tickets(ticket_id=None, priority=None, category=None):

    db = SessionLocal()

    try:
        query = db.query(Ticket)

        if ticket_id:
            query = query.filter(
                Ticket.ticket_id.ilike(f"%{ticket_id}%")
            )

        if priority and priority != "All":
            query = query.filter(
                Ticket.priority == priority
            )

        if category and category != "All":
            query = query.filter(
                Ticket.category == category
            )

        return query.order_by(
            Ticket.created_at.desc()
        ).all()

    finally:
        db.close()


def get_category_statistics():

    db = SessionLocal()

    try:
        results = (
            db.query(
                Ticket.category,
                func.count(Ticket.ticket_id)
            )
            .group_by(Ticket.category)
            .all()
        )

        return {
            category or "Unknown": count
            for category, count in results
        }

    finally:
        db.close()
