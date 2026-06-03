"""Modello SQLAlchemy `Summary` -- riassunto multilivello di un documento.

E' un output di KnowledgeExtraction (M5): la panoramica + le sezioni generate
dall'LLM a partire dal transcript. Relazione 1:1 con `Document` (`document_id`
UNIQUE): un documento ha al piu' un riassunto.

`owner_id` e' denormalizzato da `Document.owner_id`: fa valere la policy RLS sulla
riga senza un join a `documents` (stesso pattern di transcripts/tasks). Il GRAFO
(entita'/relazioni) vive su Neo4j, separato; qui resta il riassunto leggibile e i
conteggi del grafo in `meta`.

Vedi:
- Migration:  backend/alembic/versions/0005_summaries_embeddings.py
- Repository: backend/src/echomind/db/repositories/summary.py
- Worker:     backend/src/echomind/worker/tasks/extract.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from echomind.db.base import Base


class Summary(Base):
    """Riassunto multilivello di un documento (1:1 con `Document`)."""

    __tablename__ = "summaries"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )

    # FK 1:1 al documento. UNIQUE --> abilita l'upsert ON CONFLICT (document_id)
    # lato worker, rendendo idempotente la ri-estrazione dello stesso documento.
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="FK 1:1 a documents(id). UNIQUE --> abilita upsert ON CONFLICT.",
    )

    # Denormalizzato da Document.owner_id: la policy RLS lo confronta col claim JWT
    # senza dover fare un join a documents.
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    overview: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Panoramica di alto livello del documento (un paragrafo).",
    )

    sections: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,  # callable --> nuova lista per insert, niente mutable condiviso
        server_default=text("'[]'::jsonb"),
        comment='Sezioni di dettaglio: [{"title": "...", "content": "..."}].',
    )

    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Conteggi del grafo (node_count, relationship_count, community_count, ...).",
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    def __repr__(self) -> str:
        return f"Summary(id={self.id!r}, document_id={self.document_id!r})"
