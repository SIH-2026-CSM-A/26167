"""Query-history response contract — explicit field list, no ORM leakage."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class QueryHistoryItem(BaseModel):
    """One persisted query+answer, safe to return to the client that owns it."""

    model_config = ConfigDict(frozen=True)

    id: int
    query_text: str
    answer_text: str
    confidence: float
    modality: str
    created_at: datetime
