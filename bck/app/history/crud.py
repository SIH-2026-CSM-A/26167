"""Query-history CRUD. Callers supply a Session; this module never opens one implicitly."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.history.models import QueryHistory


def record_query(
    session: Session,
    *,
    user_id: str | None,
    query_text: str,
    answer_text: str,
    confidence: float,
    modality: str,
) -> None:
    session.add(
        QueryHistory(
            user_id=user_id,
            query_text=query_text,
            answer_text=answer_text,
            confidence=confidence,
            modality=modality,
        )
    )
    session.commit()


def list_recent_for_user(session: Session, *, user_id: str, limit: int = 20) -> list[QueryHistory]:
    return list(
        session.execute(
            select(QueryHistory)
            .where(QueryHistory.user_id == user_id)
            .order_by(QueryHistory.created_at.desc())
            .limit(limit)
        ).scalars()
    )
