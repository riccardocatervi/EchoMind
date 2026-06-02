"""Add summaries + entity_embeddings tables (pgvector) with RLS

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-02

Crea la persistenza dell'output di KnowledgeExtraction (M5). Il GRAFO vive su
Neo4j (fuori da Postgres); qui salviamo i due artefatti relazionali:

  1. Estensione `vector` (pgvector): tipo colonna per gli embeddings. In dev/CI
     l'immagine e' pgvector/pgvector:pg16; in produzione Supabase la include.

  2. Tabella `public.summaries`, relazione 1:1 con `documents`:
     - document_id: FK UNIQUE a documents(id) ON DELETE CASCADE --> un documento
       ha al piu' un riassunto; l'UNIQUE abilita l'upsert ON CONFLICT lato worker.
     - owner_id: FK a profiles(id), DENORMALIZZATO per la policy RLS (no join).
     - overview: la panoramica di alto livello (un paragrafo).
     - sections: JSONB [{title, content}] (livello di dettaglio = "multilivello").
     - meta: JSONB con conteggi del grafo (node_count, relationship_count,
       community_count, chunk_count, model).

  3. Tabella `public.entity_embeddings` (1:N col documento):
     - una riga per entita' canonica del grafo, col suo embedding vector(768).
     - entity_id: UUID del nodo :Entity su Neo4j (ponte Postgres <-> grafo).
     - usata in M5 per la dedup semantica e come fondamenta del RAG ibrido (M8).
     - NIENTE updated_at: le righe sono immutabili e vengono SOSTITUITE in blocco
       a ogni ri-estrazione (delete-by-document + insert).

  4. Entrambe: RLS ENABLE + FORCE + UNA sola policy (SELECT-own). Li SCRIVE il
     worker come ruolo di sistema (superuser --> bypassa RLS); gli utenti li
     leggono soltanto. L'assenza di policy INSERT/UPDATE/DELETE lato utente e'
     essa stessa una garanzia (non si fabbricano/alterano riassunti o embeddings).

Nota `meta` (non `metadata`): `metadata` e' attributo riservato del Declarative
Base. La dimensione del vettore (768) DEVE combaciare con Settings.embedding_dimensions.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. Estensione pgvector (prima delle tabelle che usano il tipo `vector`)
    # -------------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # -------------------------------------------------------------------------
    # 2. Tabella summaries (1:1 con documents)
    # -------------------------------------------------------------------------
    op.create_table(
        "summaries",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="UUID v4 generato dal DB.",
        ),
        sa.Column(
            "document_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.documents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            comment=(
                "FK UNIQUE a public.documents(id). 1:1 col documento. "
                "L'UNIQUE abilita l'upsert ON CONFLICT (document_id) nel worker."
            ),
        ),
        sa.Column(
            "owner_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.profiles.id", ondelete="CASCADE"),
            nullable=False,
            comment="FK a public.profiles(id), denormalizzato per la policy RLS.",
        ),
        sa.Column(
            "overview",
            sa.Text(),
            nullable=False,
            comment="Panoramica di alto livello del documento (un paragrafo).",
        ),
        sa.Column(
            "sections",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment='Sezioni di dettaglio: [{"title": "...", "content": "..."}].',
        ),
        sa.Column(
            "meta",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment='Conteggi del grafo (es. {"node_count": 12, "relationship_count": 18}).',
        ),
        sa.Column(
            "created_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="public",
    )

    op.create_index(
        "ix_summaries_owner_id_created_at",
        "summaries",
        ["owner_id", sa.text("created_at DESC")],
        schema="public",
    )

    # Trigger updated_at (riusa la funzione public.touch_updated_at della 0001).
    op.execute(
        """
        CREATE TRIGGER summaries_updated_at
            BEFORE UPDATE ON public.summaries
            FOR EACH ROW
            EXECUTE FUNCTION public.touch_updated_at()
        """
    )

    # RLS: una sola policy (SELECT-own). Scrive il worker (superuser, bypassa RLS).
    op.execute("ALTER TABLE public.summaries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.summaries FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY summary_select_own ON public.summaries
            FOR SELECT
            USING (owner_id::text = current_setting('request.jwt.claim.sub', true))
        """
    )

    # -------------------------------------------------------------------------
    # 3. Tabella entity_embeddings (1:N col documento)
    # -------------------------------------------------------------------------
    op.create_table(
        "entity_embeddings",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="UUID v4 generato dal DB.",
        ),
        sa.Column(
            "document_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.documents.id", ondelete="CASCADE"),
            nullable=False,
            comment="FK a public.documents(id). N embeddings per documento.",
        ),
        sa.Column(
            "owner_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.profiles.id", ondelete="CASCADE"),
            nullable=False,
            comment="FK a public.profiles(id), denormalizzato per la policy RLS.",
        ),
        sa.Column(
            "entity_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="UUID del nodo :Entity su Neo4j (ponte Postgres <-> grafo).",
        ),
        sa.Column(
            "name",
            sa.Text(),
            nullable=False,
            comment="Nome canonico dell'entita' (per debug/RAG).",
        ),
        sa.Column(
            "embedding",
            Vector(768),
            nullable=False,
            comment="Embedding del nome+descrizione. Dimensione = embedding_dimensions.",
        ),
        sa.Column(
            "created_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="public",
    )

    op.create_index(
        "ix_entity_embeddings_owner_id_document_id",
        "entity_embeddings",
        ["owner_id", "document_id"],
        schema="public",
    )

    # RLS: stessa filosofia di summaries (SELECT-own). L'indice vettoriale HNSW
    # per la ricerca semantica arrivera' in M8 (RAG), qui non serve ancora.
    op.execute("ALTER TABLE public.entity_embeddings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.entity_embeddings FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY embedding_select_own ON public.entity_embeddings
            FOR SELECT
            USING (owner_id::text = current_setting('request.jwt.claim.sub', true))
        """
    )


def downgrade() -> None:
    """Rollback completo. NB: l'estensione `vector` NON viene droppata -- potrebbe
    essere usata altrove e dropparla con colonne dipendenti fallirebbe."""
    op.execute("DROP POLICY IF EXISTS embedding_select_own ON public.entity_embeddings")
    op.drop_index(
        "ix_entity_embeddings_owner_id_document_id",
        table_name="entity_embeddings",
        schema="public",
    )
    op.drop_table("entity_embeddings", schema="public")

    op.execute("DROP POLICY IF EXISTS summary_select_own ON public.summaries")
    op.execute("DROP TRIGGER IF EXISTS summaries_updated_at ON public.summaries")
    op.drop_index("ix_summaries_owner_id_created_at", table_name="summaries", schema="public")
    op.drop_table("summaries", schema="public")

    # La funzione public.touch_updated_at resta: e' condivisa con le altre tabelle.
