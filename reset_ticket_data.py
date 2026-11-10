
"""
Reset ticket-related PostgreSQL data.

Deletes:
- Tickets
- Support cases
- Support events
- Other ticket-linked tables only when explicitly reviewed

Preserves:
- Employee accounts
- IT Support accounts
- IT Admin accounts

IMPORTANT:
Create a PostgreSQL backup before running this script.
"""

from sqlalchemy import text, func
from src.database.database import SessionLocal
from src.database.models import Ticket


EXPECTED_DATABASE = "support_ticket_db"

# Only tables explicitly approved for deletion.
# Do not add auth_users or other account tables.
TABLES_TO_CLEAR = [
    "support_events",
    "support_cases",
    "tickets",
]


def main():
    db = SessionLocal()

    try:
        engine = db.get_bind()

        print("\nDATABASE INFORMATION")
        print("-" * 45)
        print("Database type:", engine.dialect.name)
        print("Database name:", engine.url.database)
        print("Database host:", engine.url.host)

        if engine.dialect.name != "postgresql":
            raise RuntimeError("Not connected to PostgreSQL.")

        if engine.url.database != EXPECTED_DATABASE:
            raise RuntimeError("Wrong database. Reset cancelled.")

        actual_ticket_table = Ticket.__table__.name

        if actual_ticket_table != "tickets":
            raise RuntimeError(
                f"Ticket table is {actual_ticket_table!r}, "
                "not 'tickets'. Review the table names first."
            )

        tables = db.execute(
            text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
            """)
        ).scalars().all()

        existing = set(tables)

        print("\nTABLES FOUND")
        print("-" * 45)

        for table in sorted(existing):
            print(table)

        missing = set(TABLES_TO_CLEAR) - existing

        if missing:
            raise RuntimeError(
                f"Missing expected tables: {sorted(missing)}. "
                "Reset cancelled."
            )

        print("\nRECORD COUNTS BEFORE RESET")
        print("-" * 45)

        for table in TABLES_TO_CLEAR:
            count = db.execute(
                text(f'SELECT COUNT(*) FROM public."{table}"')
            ).scalar()

            print(f"{table}: {count}")

        print("\nChecking foreign-key dependencies...")

        dependencies = db.execute(
            text("""
                SELECT
                    conrelid::regclass::text AS child_table,
                    confrelid::regclass::text AS parent_table
                FROM pg_constraint
                WHERE contype = 'f'
                  AND confrelid IN (
                      'public.tickets'::regclass,
                      'public.support_cases'::regclass,
                      'public.support_events'::regclass
                  )
            """)
        ).all()

        for child, parent in dependencies:
            print(f"{child} references {parent}")

        # Reject dependencies outside the approved tables.
        unexpected = []

        for child, parent in dependencies:
            child_name = child.split(".")[-1].strip('"')

            if child_name not in TABLES_TO_CLEAR:
                unexpected.append((child, parent))

        if unexpected:
            raise RuntimeError(
                "Other tables reference ticket data. "
                "Reset cancelled. Review these dependencies first: "
                f"{unexpected}"
            )

        print("\nWARNING: THIS WILL PERMANENTLY DELETE")
        print("ticket-related records from PostgreSQL.")
        print("Employee and IT Desk accounts will be preserved.")

        confirmation = input(
            "\nType RESET TICKET DATA to continue: "
        )

        if confirmation != "RESET TICKET DATA":
            print("Reset cancelled.")
            return

        # Delete children before parents.
        # This requires the table relationships to permit this order.
        for table in TABLES_TO_CLEAR:
            result = db.execute(
                text(f'DELETE FROM public."{table}"')
            )
            print(f"Deleted from {table}: {result.rowcount}")

        print("\nVERIFYING RESET")
        print("-" * 45)

        for table in TABLES_TO_CLEAR:
            remaining = db.execute(
                text(f'SELECT COUNT(*) FROM public."{table}"')
            ).scalar()

            print(f"{table}: {remaining}")

            if remaining != 0:
                raise RuntimeError(
                    f"Reset verification failed for {table}."
                )

        db.commit()
        print("\nSUCCESS: Ticket-related tables are empty.")

    except Exception as error:
        db.rollback()
        print("\nRESET FAILED — TRANSACTION ROLLED BACK")
        print(error)

    finally:
        db.close()


if __name__ == "__main__":
    main()
