"""Modello SQLAlchemy `EntityEmbedding` -- embedding di un'entita' del grafo.

Output di KnowledgeExtraction (M5): per ogni entita' canonica del grafo Neo4j
salviamo qui il suo embedding (pgvector). Serve a due cose:
- **dedup semantica** delle entita' durante l'estrazione (similarita' coseno);
- **fondamenta del RAG ibrido** (M8): retrieval vettoriale affiancato al grafo.

Relazione 1:N col documento (molte entita' per documento). `entity_id` e' l'UUID
del nodo :Entity su Neo4j: il ponte tra Postgres e il grafo. Righe immutabili: a
ogni ri-estrazione si fa replace-by-document (delete + insert), quindi niente
`updated_at`.

Vedi:
- Migration:  backend/alembic/versions/0005_summaries_embeddings.py
- Repository: backend/src/echomind/db/repositories/embedding.py
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from echomind.db.base import Base

# Dimensione del vettore: DEVE combaciare con la migration 0005 (vector(768)) e con
# Settings.embedding_dimensions. Centralizzata qui come costante del modello.
EMBEDDING_DIM = 768


class EntityEmbedding(Base):
    """Embedding di un'entita' del grafo (1:N col documento)."""

    __tablename__ = "entity_embeddings"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )

    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK a documents(id). N embeddings per documento.",
    )

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    entity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="UUID del nodo :Entity su Neo4j (ponte Postgres <-> grafo).",
    )

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Nome canonico dell'entita' (per debug/RAG).",
    )

    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIM),
        nullable=False,
        comment="Embedding del nome+descrizione. Dimensione = EMBEDDING_DIM.",
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    def __repr__(self) -> str:
        return (
            f"EntityEmbedding(id={self.id!r}, document_id={self.document_id!r}, name={self.name!r})"
        )
