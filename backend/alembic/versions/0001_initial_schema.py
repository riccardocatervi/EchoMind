"""Initial schema: auth (dev fallback) + profiles + RLS

Revision ID: 0001
Revises:
Create Date: 2026-04-26

Crea:
  1. Schema `auth` + tabella `auth.users(id uuid)` SE NON ESISTE
     - In dev locale: lo creiamo noi (Supabase non c'è)
     - In Supabase prod: esiste già → IF NOT EXISTS è no-op
  2. Tabella `public.profiles` con FK 1:1 a `auth.users.id`
  3. Funzione + trigger per auto-update di `updated_at`
  4. Row-Level Security su `profiles` con 2 policy:
     - SELECT: vedo solo il mio profile
     - UPDATE: posso modificare solo il mio
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. Schema `auth` + tabella `users` (idempotente per Supabase compat)
    # -------------------------------------------------------------------------
    # NB: in Supabase prod questo è no-op (lo schema/tabella esistono già).
    # In dev locale lo creiamo noi così la FK di profiles.id può puntarlo.
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")
    op.execute(
        "CREATE TABLE IF NOT EXISTS auth.users (  id uuid PRIMARY KEY DEFAULT gen_random_uuid())"
    )

    # -------------------------------------------------------------------------
    # 2. Tabella public.profiles
    # -------------------------------------------------------------------------
    op.create_table(
        "profiles",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auth.users.id", ondelete="CASCADE"),
            primary_key=True,
            comment="UUID dell'utente Supabase (FK a auth.users.id)",
        ),
        sa.Column(
            "display_name",
            sa.String(length=120),
            nullable=True,
            comment="Nome visualizzato pubblicamente (max 120 char)",
        ),
        sa.Column(
            "created_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="Timestamp di creazione (UTC), settato dal DB",
        ),
        sa.Column(
            "updated_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="Timestamp ultimo aggiornamento. Aggiornato da trigger.",
        ),
        schema="public",
    )

    # -------------------------------------------------------------------------
    # 3. Trigger per auto-update di `updated_at`
    # -------------------------------------------------------------------------
    # Server-side default funziona solo all'INSERT. Per gli UPDATE, serve
    # un trigger BEFORE UPDATE che riassegna NEW.updated_at = NOW().
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.touch_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER profiles_updated_at
            BEFORE UPDATE ON public.profiles
            FOR EACH ROW
            EXECUTE FUNCTION public.touch_updated_at()
        """
    )

    # -------------------------------------------------------------------------
    # 4. Row-Level Security
    # -------------------------------------------------------------------------
    # Abilitiamo RLS e creiamo due policy minimal: SELECT-own + UPDATE-own.
    # Niente policy INSERT/DELETE in M1: l'INSERT lo facciamo lato app come
    # superuser (just-in-time provisioning); DELETE è gestito da Supabase
    # cascade su auth.users.
    op.execute("ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY")
    # FORCE: applica RLS anche al table owner, non solo agli altri ruoli.
    # Importante per dev locale dove il connection user E' il table owner.
    op.execute("ALTER TABLE public.profiles FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY profile_select_own ON public.profiles
            FOR SELECT
            USING (id::text = current_setting('request.jwt.claim.sub', true))
        """
    )
    op.execute(
        """
        CREATE POLICY profile_update_own ON public.profiles
            FOR UPDATE
            USING (id::text = current_setting('request.jwt.claim.sub', true))
            WITH CHECK (id::text = current_setting('request.jwt.claim.sub', true))
        """
    )


def downgrade() -> None:
    """Rollback completo. Idempotente."""
    # Le policy vengono droppate automaticamente con la tabella, ma
    # esplicitarle rende il downgrade leggibile.
    op.execute("DROP POLICY IF EXISTS profile_update_own ON public.profiles")
    op.execute("DROP POLICY IF EXISTS profile_select_own ON public.profiles")

    op.execute("DROP TRIGGER IF EXISTS profiles_updated_at ON public.profiles")
    op.execute("DROP FUNCTION IF EXISTS public.touch_updated_at()")

    op.drop_table("profiles", schema="public")

    # NB: NON droppiamo lo schema auth qui — in Supabase prod sarebbe
    # catastrofico. In dev, se serve, fai un reset completo del container.
