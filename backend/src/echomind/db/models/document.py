"""Modello SQLAlchemy `Document` — file caricato da un utente.

Lifecycle:
    POST /documents     →  riga creata con status='pending', genera presigned URL
    PUT  <b2 url>       →  client carica direttamente su B2 (zero banda backend)
    POST /confirm       →  HEAD object + magic-bytes validation
                           - tutto ok → status='uploaded'
                           - mismatch → status='failed', failure_reason popolato

Vedi:
- Migration: backend/alembic/versions/0002_documents_table.py
- Service:   backend/src/echomind/services/document.py (Step 6)
- Storage:   backend/src/echomind/services/storage.py  (Step 5)
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Enum, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from echomind.db.base import Base


class DocumentStatus(enum.StrEnum):
    """Stati del lifecycle di un documento.

    `StrEnum` (Python 3.11+) eredita da `str` ed Enum: i valori sono
    JSON-serializable nativi (FastAPI/Pydantic convertono in stringa
    senza encoder custom).
    """

    PENDING = "pending"
    UPLOADED = "uploaded"
    FAILED = "failed"


class Document(Base):
    """Documento caricato da un utente.

    `owner_id` è FK a `profiles.id` con ON DELETE CASCADE: se l'utente
    elimina il profile, anche i suoi documenti spariscono dal DB
    (l'object B2 va eliminato esplicitamente dal service — vedi
    `DocumentService.delete_document`).
    """

    __tablename__ = "documents"

    # -------------------------------------------------------------------------
    # Primary key (UUID server-generated)
    # -------------------------------------------------------------------------
    # `default=uuid4` (Python-side): generato dall'app se non esplicito.
    # `server_default=gen_random_uuid()`: backup DB-side se l'app dimentica.
    # Entrambi → robustezza in qualunque scenario.
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )

    # -------------------------------------------------------------------------
    # FK al profile owner
    # -------------------------------------------------------------------------
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        # Riferimento al tablename senza schema esplicito: `Profile` è dichiarato
        # senza `schema="public"`, quindi SQLAlchemy lo cerca come "profiles".
        # In Postgres la risoluzione avviene comunque su `public.profiles` per
        # default del search_path.
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Metadati file
    # -------------------------------------------------------------------------
    filename: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Nome originale del file (UX). NON usato come key B2.",
    )

    mime_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="MIME dichiarato dal client. Validato server-side post-upload.",
    )

    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Dimensione attesa. CHECK constraint nel DB la limita a 50MB.",
    )

    storage_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
        comment="Object key in B2. UUID server-generated, UNIQUE.",
    )

    # -------------------------------------------------------------------------
    # Lifecycle status
    # -------------------------------------------------------------------------
    # `Enum(DocumentStatus, name='document_status', create_type=False)`:
    # - name='document_status' matcha il tipo PostgreSQL già creato nella migration 0002
    # - create_type=False evita che SQLAlchemy tenti di ricreare il tipo (errore)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", create_type=False),
        nullable=False,
        default=DocumentStatus.PENDING,
        server_default=text("'pending'::document_status"),
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Popolato solo se status=FAILED.",
    )

    # -------------------------------------------------------------------------
    # Audit timestamps (server-side defaults)
    # -------------------------------------------------------------------------
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
            f"Document(id={self.id!r}, owner_id={self.owner_id!r}, "
            f"filename={self.filename!r}, status={self.status!r})"
        )
