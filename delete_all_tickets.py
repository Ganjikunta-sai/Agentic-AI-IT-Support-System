
from sqlalchemy import func
from src.database.database import SessionLocal
from src.database.models import Ticket

def main():
    db = SessionLocal()

    try:
        engine = db.get_bind()
        count = db.query(func.count()).select_from(Ticket).scalar()

        print("Database:", engine.url.database)
        print("Database type:", engine.dialect.name)
        print("Ticket table:", Ticket.__table__.fullname)
        print("Tickets found:", count)

        if engine.dialect.name != "postgresql":
            print("Cancelled: Not PostgreSQL.")
            return

        if engine.url.database != "support_ticket_db":
            print("Cancelled: Wrong database.")
            return

        if count != 12:
            print("Cancelled: Expected 12 tickets.")
            return

        confirmation = input(
            "\nType DELETE 12 TICKETS to confirm: "
        )

        if confirmation != "DELETE 12 TICKETS":
            print("Deletion cancelled.")
            return

        deleted = db.query(Ticket).delete(
            synchronize_session=False
        )

        db.commit()

        print("\nSuccessfully deleted:", deleted)

        remaining = db.query(func.count()).select_from(Ticket).scalar()
        print("Remaining tickets:", remaining)

    except Exception as error:
        db.rollback()
        print("Deletion failed:", error)

    finally:
        db.close()


if __name__ == "__main__":
    main()
