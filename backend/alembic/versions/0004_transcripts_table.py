"""Add transcripts table with RLS, trigger, composite index

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-31

Crea la persistenza dell'output di MediaProcessing (M4): il testo estratto da
un documento (PDF/DOCX/TXT) o trascritto da un audio (Whisper).

  1. Tabella `public.transcripts`, relazione 1:1 con `documents`:
     - document_id: FK UNIQUE a documents(id) ON DELETE CASCADE --> un documento
       ha al piu' un transcript; eliminato il documento, sparisce il transcript.
       L'UNIQUE abilita l'upsert (INSERT ... ON CONFLICT (document_id)) lato worker.
     - owner_id: FK a profiles(id), DENORMALIZZATO (gia' derivabile da document).
       Serve a far valere la policy RLS direttamente sulla riga, senza join
       (stesso pattern di documents/tasks: la policy confronta owner_id col claim).
     - source_type: 'document' | 'audio' (TEXT, validato app-side via StrEnum).
     - content: il testo normalizzato completo.
     - language: lingua rilevata da Whisper (NULL per i documenti parsati).
     - char_count: lunghezza del testo (per UX/quote, CHECK >= 0).
     - meta: JSONB con metadati di processing (chunks, duration_seconds, pages...).
  2. Indice composito (owner_id, created_at DESC) per "lista miei transcript".
  3. Trigger updated_at (riusa public.touch_updated_at della 0001).
  4. RLS abilitata + FORCE + UNA sola policy (SELECT-own).
     I transcript li SCRIVE il worker come ruolo di sistema (superuser --> bypassa
     RLS): gli utenti li leggono soltanto. L'assenza di policy INSERT/UPDATE e'
     essa stessa una garanzia (un utente non puo' fabbricare/alterare un transcript).

Nota su `source_type`: TEXT e non ENUM, coerente con `task_type` (0003) e con la
filosofia "insieme validato lato app". `meta` (non `metadata`): `metadata` e'
attributo riservato del Declarative Base di SQLAlchemy.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. Tabella transcripts
    # -------------------------------------------------------------------------
    op.create_table(
        "transcripts",
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
            "source_type",
            sa.Text(),
            nullable=False,
            comment="'document' | 'audio'. Validato lato app (StrEnum).",
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            comment="Testo normalizzato completo (estratto o trascritto).",
        ),
        sa.Column(
            "language",
            sa.Text(),
            nullable=True,
            comment="Lingua rilevata da Whisper. NULL per documenti parsati.",
        ),
        sa.Column(
            "char_count",
            sa.Integer(),
            # NB: la naming_convention di Base.metadata ("ck_%(table_name)s_...")
            # antepone gia' "ck_transcripts_": qui passiamo solo la parte descrittiva
            # per ottenere "ck_transcripts_char_count_non_negative" (niente doppio prefisso).
            sa.CheckConstraint("char_count >= 0", name="char_count_non_negative"),
            nullable=False,
            comment="Lunghezza del testo in caratteri.",
        ),
        sa.Column(
            "meta",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment='Metadati di processing (es. {"chunks": 3, "duration_seconds": 312}).',
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
    # 2. Indice composito per "lista miei transcript ordinati dal piu' recente"
    # -------------------------------------------------------------------------
    op.create_index(
        "ix_transcripts_owner_id_created_at",
        "transcripts",
        ["owner_id", sa.text("created_at DESC")],
        schema="public",
    )

    # -------------------------------------------------------------------------
    # 3. Trigger updated_at (riusa la funzione di 0001)
    # -------------------------------------------------------------------------
    op.execute(
        """
        CREATE TRIGGER transcripts_updated_at
            BEFORE UPDATE ON public.transcripts
            FOR EACH ROW
            EXECUTE FUNCTION public.touch_updated_at()
        """
    )

    # -------------------------------------------------------------------------
    # 4. Row-Level Security: 1 policy (SELECT-own)
    # -------------------------------------------------------------------------
    # I transcript sono OUTPUT DI SISTEMA: li scrive il worker (ruolo superuser
    # `echomind`, che bypassa RLS). Gli utenti li leggono soltanto. Niente policy
    # INSERT/UPDATE/DELETE lato utente: la loro assenza garantisce che un utente
    # non possa creare o alterare un transcript (ne' falsificarne il contenuto).
    op.execute("ALTER TABLE public.transcripts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.transcripts FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY transcript_select_own ON public.transcripts
            FOR SELECT
            USING (owner_id::text = current_setting('request.jwt.claim.sub', true))
        """
    )


def downgrade() -> None:
    """Rollback completo. Policy/trigger droppano in cascata con la tabella;
    li listiamo comunque esplicitamente per leggibilita'."""
    op.execute("DROP POLICY IF EXISTS transcript_select_own ON public.transcripts")

    op.execute("DROP TRIGGER IF EXISTS transcripts_updated_at ON public.transcripts")

    op.drop_index("ix_transcripts_owner_id_created_at", table_name="transcripts", schema="public")
    op.drop_table("transcripts", schema="public")

    # NB: la funzione public.touch_updated_at NON viene droppata qui -- e'
    # condivisa con profiles (0001), documents (0002) e tasks (0003).
