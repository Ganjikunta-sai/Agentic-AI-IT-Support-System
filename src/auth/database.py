
"""Authentication database access using the application's existing SQLAlchemy engine.

Creates only the auth_users table; does not modify existing ticket tables.
"""

from __future__ import annotations

from contextlib import contextmanager
from importlib import import_module
from typing import Iterator

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.auth.models import UserBase


_ENGINE_MODULES = (
    "src.database.database",
    "src.database",
)


def get_existing_engine() -> Engine:
    """Reuse the existing ticket database engine; never create a second database."""
    failures: list[str] = []

    for module_name in _ENGINE_MODULES:
        try:
            module = import_module(module_name)
        except ImportError as exc:
            failures.append(f"{module_name}: {exc}")
            continue

        candidate = getattr(module, "engine", None)

        if isinstance(candidate, Engine):
            return candidate

        failures.append(
            f"{module_name}: no SQLAlchemy Engine named 'engine'"
        )

    raise RuntimeError(
        "Cannot locate the existing ticket database engine. "
        "Update _ENGINE_MODULES to include the module that exports your "
        "existing SQLAlchemy 'engine'. Details: "
        + "; ".join(failures)
    )


# Lazy initialization avoids opening a DB connection during module import.
_SessionFactory: sessionmaker[Session] | None = None


def get_auth_session_factory() -> sessionmaker[Session]:
    """Return a session factory bound to the existing ticket database."""
    global _SessionFactory

    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_existing_engine(),
            autoflush=False,
            expire_on_commit=False,
        )

    return _SessionFactory


@contextmanager
def auth_session() -> Iterator[Session]:
    """Open a session, commit on success, roll back on failure."""
    session = get_auth_session_factory()()

    try:
        yield session
        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def initialize_auth_database() -> None:
    """Create only missing authentication tables in the existing database.

    This does not drop, truncate, or alter existing ticket tables.
    For future changes to existing auth tables, use migrations.
    """
    engine = get_existing_engine()

    UserBase.metadata.create_all(
        bind=engine,
        checkfirst=True,
    )
