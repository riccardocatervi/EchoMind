"""Add tasks table with RLS, trigger, composite index

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-30

Crea l'infrastruttura di persistenza per i job asincroni (M3):
  1. ENUM `task_status` (queued, running, succeeded, failed)
  2. Tabella `public.tasks` con FK a `profiles(id)` ON DELETE CASCADE.
     - payload/result come JSONB (input/output strutturati del task)
     - retries: contatore tentativi (per backoff e DLQ)
     - started_at / finished_at: timestamp del ciclo di vita
  3. Indice composito (owner_id, created_at DESC) per "lista mia paginata"
  4. Trigger updated_at (riusa public.touch_updated_at della 0001)
  5. RLS abilitata + FORCE + 2 policy (SELECT, INSERT)
     Lifecycle: l'utente crea (enqueue) e legge i propri task; gli UPDATE di
     stato li fa il worker come ruolo di sistema (superuser → bypassa RLS),
     quindi non servono policy UPDATE/DELETE lato utente in M3.

Nota su `task_type`: TEXT e non ENUM. L'insieme dei tipi cresce a ogni
milestone (echo → transcribe → extract → ...): un TEXT con validazione
applicativa (StrEnum) è più comodo di ripetuti ALTER TYPE ADD VALUE.
`status` resta ENUM perché è un insieme piccolo e stabile.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. ENUM type
    # -------------------------------------------------------------------------
    op.execute("CREATE TYPE task_status AS ENUM ('queued', 'running', 'succeeded', 'failed')")

    # -------------------------------------------------------------------------
    # 2. Tabella tasks
    # -------------------------------------------------------------------------
    op.create_table(
        "tasks",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment=(
                "UUID v4 generato dal DB. Usato anche come task_id Celery "
                "(apply_async(task_id=...)): un solo id, niente tabella di mapping."
            ),
        ),
        sa.Column(
            "owner_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.profiles.id", ondelete="CASCADE"),
            nullable=False,
            comment="FK a public.profiles(id). CASCADE: profile eliminato → suoi task via.",
        ),
        sa.Column(
            "task_type",
            sa.Text(),
            nullable=False,
            comment="Tipo logico del task ('echo' in M3). Validato lato app (StrEnum).",
        ),
        sa.Column(
            "status",
            sa.dialects.postgresql.ENUM(
                "queued",
                "running",
                "succeeded",
                "failed",
                name="task_status",
                create_type=False,  # già creato sopra in modo esplicito
            ),
            nullable=False,
            server_default=sa.text("'queued'::task_status"),
            comment="Lifecycle: queued → running → (succeeded | failed).",
        ),
        sa.Column(
            "payload",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment='Input del task (es. {"message": "...", "fail": false}).',
        ),
        sa.Column(
            "result",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
            comment="Output del task. Popolato quando status='succeeded'.",
        ),
        sa.Column(
            "error",
            sa.Text(),
            nullable=True,
            comment="Messaggio dell'ultimo errore. Popolato quando status='failed'.",
        ),
        sa.Column(
            "retries",
            sa.Integer(),
            sa.CheckConstraint("retries >= 0", name="ck_tasks_retries_non_negative"),
            nullable=False,
            server_default=sa.text("0"),
            comment="Numero di tentativi già consumati (per backoff e soglia DLQ).",
        ),
        sa.Column(
            "started_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Istante in cui il worker ha iniziato l'esecuzione.",
        ),
        sa.Column(
            "finished_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Istante di completamento (succeeded o failed terminale).",
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
    # Stesso ragionamento di documents: owner_id (filtro) + created_at DESC
    # (sort) materializzati nel B-tree → niente sort separato.
    op.create_index(
        "ix_tasks_owner_id_created_at",
        "tasks",
        ["owner_id", sa.text("created_at DESC")],
        schema="public",
    )

    # -------------------------------------------------------------------------
    # 4. Trigger updated_at (riusa la funzione di 0001)
    # -------------------------------------------------------------------------
    op.execute(
        """
        CREATE TRIGGER tasks_updated_at
            BEFORE UPDATE ON public.tasks
            FOR EACH ROW
            EXECUTE FUNCTION public.touch_updated_at()
        """
    )

    # -------------------------------------------------------------------------
    # 5. Row-Level Security: 2 policy (SELECT-own + INSERT-own)
    # -------------------------------------------------------------------------
    # L'utente accoda (INSERT) e consulta (SELECT) i propri task. Gli UPDATE di
    # stato (running/succeeded/failed) li scrive il worker come ruolo di sistema
    # (superuser, che bypassa RLS): non serve una policy UPDATE lato utente, e la
    # sua assenza è essa stessa una garanzia (gli utenti non possono falsificare
    # lo stato dei propri task). Nessun DELETE/cancel in M3.
    op.execute("ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.tasks FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY task_select_own ON public.tasks
            FOR SELECT
            USING (owner_id::text = current_setting('request.jwt.claim.sub', true))
        """
    )
    op.execute(
        """
        CREATE POLICY task_insert_own ON public.tasks
            FOR INSERT
            WITH CHECK (owner_id::text = current_setting('request.jwt.claim.sub', true))
        """
    )


def downgrade() -> None:
    """Rollback completo. Le policy/trigger droppano in cascata con la tabella;
    li listiamo comunque esplicitamente per leggibilità."""
    op.execute("DROP POLICY IF EXISTS task_insert_own ON public.tasks")
    op.execute("DROP POLICY IF EXISTS task_select_own ON public.tasks")

    op.execute("DROP TRIGGER IF EXISTS tasks_updated_at ON public.tasks")

    op.drop_index("ix_tasks_owner_id_created_at", table_name="tasks", schema="public")
    op.drop_table("tasks", schema="public")

    op.execute("DROP TYPE IF EXISTS task_status")

    # NB: la funzione public.touch_updated_at NON viene droppata qui — è
    # condivisa con profiles (0001) e documents (0002).
