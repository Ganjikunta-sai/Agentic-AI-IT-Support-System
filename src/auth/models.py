
"""SQLAlchemy user model and role definitions for the IT Support application.

Import User and UserRole from this module. To create the table, import
UserBase and run UserBase.metadata.create_all(bind=engine) using the
existing application's SQLAlchemy engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class UserRole(str, Enum):
    EMPLOYEE = "employee"
    IT_SUPPORT = "it_support"
    IT_ADMIN = "it_admin"


class UserBase(DeclarativeBase):
    """Independent metadata to avoid modifying existing ticket models."""


class User(UserBase):
    """Authentication account. Never store plaintext passwords."""

    __tablename__ = "auth_users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('employee', 'it_support', 'it_admin')",
            name="ck_auth_users_valid_role",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.EMPLOYEE.value,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @property
    def is_staff(self) -> bool:
        return self.role in {
            UserRole.IT_SUPPORT.value,
            UserRole.IT_ADMIN.value,
        }

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.IT_ADMIN.value

    def __repr__(self) -> str:
        return (
            f"User(id={self.id!r}, "
            f"email={self.email!r}, "
            f"role={self.role!r})"
        )
