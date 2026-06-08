"""Add profiles.preferred_language: output language preference.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-07

Aggiunge la preferenza di lingua di OUTPUT al profilo utente. Da M8 il riassunto,
le descrizioni del grafo e le risposte del Q&A (GraphRAG) seguono la lingua scelta
dall'utente nell'interfaccia, non la lingua del documento. Il worker di estrazione
e' un processo separato che non conosce la UI: la preferenza va quindi persistita
su Postgres, dove il worker la legge al momento dell'estrazione.

Colonna NOT NULL con DEFAULT 'it': le righe esistenti vengono riempite con il
default (italiano) durante la migration, senza bisogno di backfill manuale. La
colonna eredita le RLS policy gia' presenti su public.profiles (filtro per riga,
non per colonna), quindi non servono nuove policy.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "preferred_language",
            sa.String(length=8),
            nullable=False,
            server_default=sa.text("'it'"),
            comment="Lingua di output preferita (it/en): summary, grafo, risposte RAG.",
        ),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column("profiles", "preferred_language", schema="public")
