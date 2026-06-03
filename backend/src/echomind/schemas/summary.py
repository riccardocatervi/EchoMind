"""Pydantic schemas per la risorsa Summary (output di KnowledgeExtraction).

Il riassunto NON viene creato via input HTTP (lo scrive il worker): qui serve
solo lo schema di lettura.

- `SummaryRead` --> cio' che l'API RITORNA su GET /documents/{id}/summary
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SummarySection(BaseModel):
    """Una sezione di dettaglio del riassunto multilivello."""

    title: str
    content: str


class SummaryRead(BaseModel):
    """Vista del riassunto esposta dall'API."""

    id: UUID
    document_id: UUID
    owner_id: UUID
    overview: str
    sections: list[SummarySection]
    meta: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
