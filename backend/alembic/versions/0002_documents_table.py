"""Add documents table with RLS, trigger, composite index

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-28

Crea:
  1. ENUM `document_status` (pending, uploaded, failed)
  2. Tabella `public.documents` con FK a `profiles(id)` ON DELETE CASCADE
  3. Indice composito (owner_id, created_at DESC) per "lista mia paginata"
  4. Trigger updated_at (riusa la funzione public.touch_updated_at della 0001)
  5. RLS abilitata + FORCE + 4 policy (SELECT, INSERT, UPDATE, DELETE)
     Lifecycle user-driven: l'utente crea/legge/aggiorna/cancella i propri documenti.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Limite duplicato del MAX_UPLOAD_SIZE_BYTES applicativo (50 MB).
# In linea di principio andrebbe parametrizzato, ma nel DDL serve un literal
# CHECK constraint: lo cristallizziamo qui. Cambiarlo richiederà una migration
# di ALTER CONSTRAINT, che è il comportamento giusto (modifiche schema = migration).
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. ENUM type
    # -------------------------------------------------------------------------
    # ENUM PostgreSQL nativo: type-safe nel DB, più snello di una lookup table
    # per pochi valori conosciuti. Per estendere in futuro: ALTER TYPE ... ADD VALUE.
    op.execute("CREATE TYPE document_status AS ENUM ('pending', 'uploaded', 'failed')")

    # -------------------------------------------------------------------------
    # 2. Tabella documents
    # -------------------------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="UUID v4 generato dal DB. Stabile per tutta la vita del documento.",
        ),
        sa.Column(
            "owner_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.profiles.id", ondelete="CASCADE"),
            nullable=False,
            comment="FK a public.profiles(id). CASCADE: profile eliminato → documenti suoi via",
        ),
        sa.Column(
            "filename",
            sa.Text(),
            nullable=False,
            comment="Nome originale del file (UX). NON usato come key B2.",
        ),
        sa.Column(
            "mime_type",
            sa.Text(),
            nullable=False,
            comment=(
                "MIME dichiarato dal client. Validato server-side post-upload "
                "con magic bytes. Se mismatch → status=failed."
            ),
        ),
        sa.Column(
            "size_bytes",
            sa.BigInteger(),
            sa.CheckConstraint(
                f"size_bytes > 0 AND size_bytes <= {MAX_UPLOAD_SIZE_BYTES}",
                name="ck_documents_size_bytes_in_range",
            ),
            nullable=False,
            comment="Dimensione attesa in bytes. Verificata HEAD post-upload.",
        ),
        sa.Column(
            "storage_key",
            sa.Text(),
            nullable=False,
            unique=True,
            comment=(
                "Chiave usata come object key in B2. UUID server-generated, "
                "UNIQUE per evitare collisioni e B2 object condivisi."
            ),
        ),
        sa.Column(
            "status",
            sa.dialects.postgresql.ENUM(
                "pending",
                "uploaded",
                "failed",
                name="document_status",
                create_type=False,  # già creato sopra in modo esplicito
            ),
            nullable=False,
            server_default=sa.text("'pending'::document_status"),
            comment="Lifecycle: pending → (confirm) → uploaded | failed",
        ),
        sa.Column(
            "failure_reason",
            sa.Text(),
            nullable=True,
            comment="Popolato solo se status='failed' (es. 'mime_mismatch', 'size_exceeded').",
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

    # -------------------------------------------------------------------------
    # 3. Indice composito per "lista mia ordinata dal più recente"
    # -------------------------------------------------------------------------
    # Ordine colonne deliberato:
    #   1) owner_id: filtro WHERE — alta cardinalità + selettività massima
    #   2) created_at DESC: sort già materializzato nel B-tree
    # Risultato: query SELECT * FROM documents WHERE owner_id=$1 ORDER BY created_at DESC
    # risolta interamente in indice, niente sort separato.
    op.create_index(
        "ix_documents_owner_id_created_at",
        "documents",
        ["owner_id", sa.text("created_at DESC")],
        schema="public",
    )

    # -------------------------------------------------------------------------
    # 4. Trigger updated_at (riusa la funzione di 0001)
    # -------------------------------------------------------------------------
    op.execute(
        """
        CREATE TRIGGER documents_updated_at
            BEFORE UPDATE ON public.documents
            FOR EACH ROW
            EXECUTE FUNCTION public.touch_updated_at()
        """
    )

    # -------------------------------------------------------------------------
    # 5. Row-Level Security: 4 policy (lifecycle user-driven completo)
    # -------------------------------------------------------------------------
    op.execute("ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.documents FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY document_select_own ON public.documents
            FOR SELECT
            USING (owner_id::text = current_setting('request.jwt.claim.sub', true))
        """
    )
    op.execute(
        """
        CREATE POLICY document_insert_own ON public.documents
            FOR INSERT
            WITH CHECK (owner_id::text = current_setting('request.jwt.claim.sub', true))
        """
    )
    op.execute(
        """
        CREATE POLICY document_update_own ON public.documents
            FOR UPDATE
            USING (owner_id::text = current_setting('request.jwt.claim.sub', true))
            WITH CHECK (owner_id::text = current_setting('request.jwt.claim.sub', true))
        """
    )
    op.execute(
        """
        CREATE POLICY document_delete_own ON public.documents
            FOR DELETE
            USING (owner_id::text = current_setting('request.jwt.claim.sub', true))
        """
    )


def downgrade() -> None:
    """Rollback completo. Le policy/trigger droppano in cascata con la tabella;
    li listiamo comunque esplicitamente per leggibilità."""
    op.execute("DROP POLICY IF EXISTS document_delete_own ON public.documents")
    op.execute("DROP POLICY IF EXISTS document_update_own ON public.documents")
    op.execute("DROP POLICY IF EXISTS document_insert_own ON public.documents")
    op.execute("DROP POLICY IF EXISTS document_select_own ON public.documents")

    op.execute("DROP TRIGGER IF EXISTS documents_updated_at ON public.documents")

    op.drop_index("ix_documents_owner_id_created_at", table_name="documents", schema="public")
    op.drop_table("documents", schema="public")

    op.execute("DROP TYPE IF EXISTS document_status")

    # NB: la funzione public.touch_updated_at NON viene droppata qui — è
    # condivisa con profiles (creata in 0001). Sopravvive a questo downgrade.
