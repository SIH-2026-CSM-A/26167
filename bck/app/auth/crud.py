"""User CRUD against the users table. Callers supply a Session; this module never opens one
implicitly, so routes can share a transaction across a hash-then-insert sequence.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User


class UserExistsError(Exception):
    """Raised when an insert violates the email (or provider_subject) uniqueness constraint."""


def create_user(
    session: Session,
    *,
    email: str,
    hashed_password: str | None,
    auth_provider: str = "password",
    provider_subject: str | None = None,
    is_verified: bool = False,
) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        hashed_password=hashed_password,
        auth_provider=auth_provider,
        provider_subject=provider_subject,
        is_verified=is_verified,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise UserExistsError(f"a user with email {email!r} already exists") from error
    session.refresh(user)
    return user


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_user_by_id(session: Session, user_id: str) -> User | None:
    return session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def get_user_by_provider_subject(session: Session, provider_subject: str) -> User | None:
    return session.execute(
        select(User).where(User.provider_subject == provider_subject)
    ).scalar_one_or_none()
