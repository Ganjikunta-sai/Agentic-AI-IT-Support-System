
"""Secure password hashing and verification using Argon2id."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from argon2.low_level import Type


MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 10

_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


def hash_password(password: str) -> str:
    """Hash a new password after validating its length."""

    if not isinstance(password, str):
        raise TypeError("Password must be a string.")

    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError(
            "Password must contain between 8 and 10 characters."
        )

    return _PASSWORD_HASHER.hash(password)


def verify_password(
    password: str,
    stored_hash: str | None,
) -> bool:
    """Verify a password against its stored Argon2id hash."""

    if not isinstance(password, str):
        return False

    if not isinstance(stored_hash, str):
        return False

    if not password or not stored_hash:
        return False

    try:
        return bool(
            _PASSWORD_HASHER.verify(stored_hash, password)
        )

    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
        ValueError,
    ):
        return False


def password_needs_rehash(stored_hash: str) -> bool:
    """Check whether an existing password hash needs updating."""

    if not isinstance(stored_hash, str) or not stored_hash:
        return True

    try:
        return _PASSWORD_HASHER.check_needs_rehash(stored_hash)

    except (InvalidHashError, ValueError):
        return True
