"""Modello SQLAlchemy `Profile` — dati custom per ogni utente Supabase.

Relazione concettuale:

    auth.users (gestita da Supabase, una riga per utente registrato)
        ↓ 1:1
    public.profiles (questa tabella: dati custom dell'app)

Decisioni di design:

1. **PK = FK**: `profiles.id` è sia primary key sia foreign key a
   `auth.users.id`. Garantisce naturalmente la relazione 1:1 e l'eliminazione
   in cascata quando l'utente viene cancellato da Supabase.

2. **UUID**: standard moderno per i PK. Generabile client-side, non rivela
   il volume di righe, compatibile con `auth.users.id` di Supabase.

3. **Niente FK dichiarata nel modello Python**: la tabella `auth.users` è
   esterna (gestita da Supabase / dalla migration). La FK la dichiariamo
   nel SQL della migration Alembic. Mantenere il modello "puro" evita
   coupling tra ORM e schema esterni.

4. **Audit timestamp server-side**: `created_at` e `updated_at` con
   `server_default=NOW()`. Il DB è l'unica sorgente di verità per il tempo.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from echomind.db.base import Base


class Profile(Base):
    """Profile custom dell'utente.

    Una riga per ogni utente Supabase autenticato. Creata "just-in-time"
    alla prima richiesta autenticata (vedi `services/profile.py` in step
    successivi).
    """

    __tablename__ = "profiles"

    # -------------------------------------------------------------------------
    # Primary key + FK a auth.users.id
    # -------------------------------------------------------------------------
    # `as_uuid=True` --> Python lavora con `uuid.UUID`, non con `str`.
    # Niente `default=uuid4()`: l'ID viene SEMPRE da auth.users (Supabase),
    # mai generato lato app.
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        comment="UUID dell'utente Supabase (FK a auth.users.id)",
    )

    # -------------------------------------------------------------------------
    # Dati di profilo (nullable in M1; espanderemo in milestone successive)
    # -------------------------------------------------------------------------
    display_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        comment="Nome visualizzato pubblicamente (max 120 char)",
    )

    # -------------------------------------------------------------------------
    # Audit timestamp (server-side defaults)
    # -------------------------------------------------------------------------
    # TIMESTAMP(timezone=True) --> "TIMESTAMPTZ" in Postgres (raccomandato).
    # `server_default=text("NOW()")` → il DEFAULT è nel DDL; nessun bisogno
    # che Python passi un valore al INSERT.
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        comment="Timestamp di creazione (UTC), settato dal DB",
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        comment="Timestamp ultimo aggiornamento. Aggiornato da trigger.",
    )

    # -------------------------------------------------------------------------
    # Repr utile per debugging
    # -------------------------------------------------------------------------
    def __repr__(self) -> str:
        # r! alla fine del nome della variabile serve per non stampare la variabile come
        # stringa normale, ma di usare la rappresentazione ufficiale (chiamando a sua volta
        # il __repr__ di quella variabile).
        return f"Profile(id={self.id!r}, display_name={self.display_name!r})"
