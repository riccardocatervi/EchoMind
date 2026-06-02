"""Pydantic schemas per la risorsa Transcript (output di MediaProcessing).

Il transcript NON viene creato via input HTTP (lo scrive il worker): qui serve
solo lo schema di lettura.

- `TranscriptRead` --> ciò che l'API RITORNA su GET /documents/{id}/transcript
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from echomind.db.models import SourceType


class TranscriptRead(BaseModel):
    """Vista del transcript esposta dall'API."""

    id: UUID
    document_id: UUID
    owner_id: UUID
    source_type: SourceType
    content: str
    language: str | None
    char_count: int
    meta: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
