"""GET /history — the caller's own recent queries, newest first."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.auth import User
from app.contracts import QueryHistoryItem
from app.history import get_sync_session, list_recent_for_user

router = APIRouter(prefix="/history", tags=["history"])

_UNAUTHORIZED_DETAIL = {
    "message": "Missing or invalid access token.",
    "reason_code": "UNAUTHORIZED",
    "suggested_action": "Log in and retry with a valid Authorization: Bearer header.",
}


@router.get("", response_model=list[QueryHistoryItem])
def get_history(_user: User | None = Depends(get_current_user)) -> list[QueryHistoryItem]:
    if _user is None:
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED_DETAIL)
    with get_sync_session() as session:
        rows = list_recent_for_user(session, user_id=_user.id, limit=20)
        return [
            QueryHistoryItem(
                id=row.id,
                query_text=row.query_text,
                answer_text=row.answer_text,
                confidence=row.confidence,
                modality=row.modality,
                created_at=row.created_at,
            )
            for row in rows
        ]
