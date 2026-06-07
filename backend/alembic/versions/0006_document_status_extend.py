"""Extend document_status enum: add transcribed, extracted, completed.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-06

Aggiunge tre nuovi stati al lifecycle del documento per un pipeline tracking
piu' granulare (il frontend fa polling su GET /documents/{id} e si ferma
quando lo stato diventa 'completed' o 'failed'):

  pending  ---(confirm_upload)--->  uploaded
  uploaded ---(M4 worker)--------->  transcribed   (transcript pronto)
  transcribed ---(M5, Neo4j)------->  extracted     (grafo in Neo4j)
  extracted ---(M5, Postgres)------>  completed     (summary + embeddings pronti)
  [qualsiasi step]  ----(errore)---> failed

Nota tecnica: ALTER TYPE ... ADD VALUE IF NOT EXISTS e' idempotente e
transazionale su PostgreSQL 12+ (Supabase >= PG15, Docker image ufficiale >= PG14).
AFTER '<valore>' preserva l'ordinamento logico dell'enum.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Ordine rilevante per la semantica del lifecycle:
    # pending < uploaded < transcribed < extracted < completed; failed e' terminale.
    op.execute(
        "ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'transcribed' AFTER 'uploaded'"
    )
    op.execute(
        "ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'extracted' AFTER 'transcribed'"
    )
    op.execute(
        "ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'completed' AFTER 'extracted'"
    )


def downgrade() -> None:
    # PostgreSQL non supporta DROP VALUE da un ENUM esistente.
    # Rollback manuale (eseguire nell'ordine):
    #
    #   ALTER TABLE public.documents ALTER COLUMN status TYPE text;
    #   UPDATE public.documents
    #     SET status = 'uploaded'
    #     WHERE status IN ('transcribed', 'extracted', 'completed');
    #   DROP TYPE document_status;
    #   CREATE TYPE document_status AS ENUM ('pending', 'uploaded', 'failed');
    #   ALTER TABLE public.documents
    #     ALTER COLUMN status TYPE document_status
    #     USING status::document_status;
    #
    # Non automatizzabile: richiede intervento manuale in produzione.
    pass
