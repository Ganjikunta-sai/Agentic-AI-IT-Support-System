
"""Create the first IT Admin account in PostgreSQL.

Run:
    python -m scripts.create_admin
"""

from __future__ import annotations

import getpass
import sys

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.auth.database import (
    auth_session,
    initialize_auth_database,
)
from src.auth.models import User, UserRole
from src.auth.passwords import hash_password


def main() -> int:
    print("\n====================================")
    print("     CREATE FIRST IT ADMIN")
    print("====================================\n")

    full_name = input("Full name: ").strip()
    email = input("Work email: ").strip().lower()

    if not full_name or len(full_name) > 150:
        print("Full name must be 1–150 characters.")
        return 1

    if (
        not email
        or len(email) > 255
        or email.count("@") != 1
        or any(char.isspace() for char in email)
    ):
        print("Enter a valid email address.")
        return 1

    password = getpass.getpass(
        "Password (8–10 characters): "
    )

    confirm_password = getpass.getpass(
        "Confirm password: "
    )

    if password != confirm_password:
        print("Passwords do not match.")
        return 1

    try:
        password_hash = hash_password(password)

    except (TypeError, ValueError) as exc:
        print(f"Invalid password: {exc}")
        return 1

    finally:
        del password
        del confirm_password

    try:
        initialize_auth_database()

        with auth_session() as session:
            existing_admin = session.scalar(
                select(User.id)
                .where(
                    User.role == UserRole.IT_ADMIN.value
                )
                .limit(1)
            )

            if existing_admin is not None:
                print(
                    "An IT Admin already exists. "
                    "Bootstrap is disabled."
                )
                return 1

            existing_email = session.scalar(
                select(User.id)
                .where(User.email == email)
                .limit(1)
            )

            if existing_email is not None:
                print(
                    "This email already belongs "
                    "to an existing account."
                )
                return 1

            admin = User(
                full_name=full_name,
                email=email,
                password_hash=password_hash,
                role=UserRole.IT_ADMIN.value,
                is_active=True,
            )

            session.add(admin)
            session.flush()

            admin_id = admin.id

        print("\n====================================")
        print("IT Admin created successfully!")
        print(f"Admin ID: {admin_id}")
        print(f"Email: {email}")
        print("Role: it_admin")
        print("====================================")
        print("\nLog in using the IT Desk Portal.")

        return 0

    except (IntegrityError, SQLAlchemyError) as exc:
        print(
            f"Database operation failed: "
            f"{type(exc).__name__}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
