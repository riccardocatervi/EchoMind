"""Modello SQLAlchemy `Transcript` -- testo derivato da un documento.

E' l'output di MediaProcessing (M4): il testo estratto da un documento
(PDF/DOCX/TXT) oppure trascritto da un audio (Whisper). Relazione 1:1 con
`Document` (`document_id` UNIQUE): un documento ha al piu' un transcript.

Lifecycle:
    documento 'uploaded'  -->  enqueue task 'transcribe'
    worker processa       -->  upsert del Transcript (sessione di sistema)
    GET /documents/{id}/transcript  -->  l'utente legge il proprio (RLS)

`owner_id` e' denormalizzato da `Document.owner_id`: serve a far valere la
policy RLS sulla riga senza un join a `documents` (stesso pattern di tasks).

Vedi:
- Migration:  backend/alembic/versions/0004_transcripts_table.py
- Repository: backend/src/echomind/db/repositories/transcript.py
- Worker:     backend/src/echomind/worker/tasks/transcribe.py
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from echomind.db.base import Base


class SourceType(enum.StrEnum):
    """Origine del transcript.

    - DOCUMENT: testo estratto da un file testuale (PDF/DOCX/TXT) via parsing.
    - AUDIO:    testo trascritto da un file audio via Whisper.

    Persistito come TEXT (non ENUM), coerente con `task_type`: validazione
    lato app tramite questo StrEnum.
    """

    DOCUMENT = "document"
    AUDIO = "audio"


class Transcript(Base):
    """Testo derivato da un documento (1:1 con `Document`)."""

    __tablename__ = "transcripts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )

    # FK 1:1 al documento. UNIQUE --> abilita l'upsert ON CONFLICT (document_id)
    # lato worker, rendendo idempotente il ri-processing dello stesso documento.
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="FK 1:1 a documents(id). UNIQUE --> abilita upsert ON CONFLICT.",
    )

    # Denormalizzato da Document.owner_id: la policy RLS lo confronta col claim
    # JWT senza dover fare un join a documents.
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="'document' | 'audio'. Validato lato app (SourceType).",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Testo normalizzato completo (estratto o trascritto).",
    )

    language: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Lingua rilevata da Whisper. NULL per documenti parsati.",
    )

    char_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Lunghezza del testo in caratteri (CHECK >= 0 nel DB).",
    )

    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,  # callable --> nuovo dict per insert, niente mutable condiviso
        server_default=text("'{}'::jsonb"),
        comment="Metadati di processing (es. chunks, duration_seconds, pages).",
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
        return (
            f"Transcript(id={self.id!r}, document_id={self.document_id!r}, "
            f"source_type={self.source_type!r}, char_count={self.char_count!r})"
        )
