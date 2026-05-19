"""Async engine, sessionmaker, helper RLS.

Tre concetti chiave riassunti qui:

1. **Engine**: pool di connessioni TCP verso Postgres (asyncpg).
   Singleton di processo — creato all'avvio, chiuso allo shutdown.

2. **SessionMaker**: factory che produce `AsyncSession` (una "conversazione"
   col DB). Ogni richiesta HTTP riceve la sua sessione (scoping per-request).

3. **RLS binding**: helper `set_rls_user(session, user_id)` esegue
   `SET LOCAL request.jwt.claim.sub = '<uuid>'` nella transazione corrente.
   Le RLS policy del DB leggono questo valore → filtraggio automatico.

Pattern di vita di una sessione:

    async with session_maker() as session:
        async with session.begin():           # apre transazione
            await set_rls_user(session, uid)  # attiva RLS per questa tx
            # ... query ...
        # commit automatico all'uscita del begin()
    # close automatico all'uscita del context manager
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from echomind.core.config import Settings


# -----------------------------------------------------------------------------
# Engine factory
# -----------------------------------------------------------------------------
def create_engine(settings: Settings) -> AsyncEngine:
    """Crea l'engine async con pool configurato.

    Parametri del pool:
      - pool_size: connessioni base sempre aperte (5 → buon default MVP)
      - max_overflow: connessioni extra in caso di picco (10)
      - pool_pre_ping: verifica connection liveness prima di usarla
        (paga 1 round-trip ma evita "connection reset by peer" su connessioni
        idle killed da firewall/proxy)
      - pool_recycle: ricicla connessioni più vecchie di N secondi
        (Postgres ha `idle_in_transaction_session_timeout` di default)

    `echo=False`: niente SQL spammato nei log. Per debugging si setta a True
    o si abilita via env var dedicata in M9.
    """
    return create_async_engine(
        url=str(settings.database_url),
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=1800,  # 30 minuti
        # future=True è il default in 2.0, lo esplicitiamo per chiarezza
        future=True,
    )


# -----------------------------------------------------------------------------
# Sessionmaker factory
# -----------------------------------------------------------------------------
def create_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Crea la factory di AsyncSession.

    `expire_on_commit=False` è cruciale in async:
      - Default True: dopo commit() gli oggetti sono "scaduti" → ogni accesso
        attributo triggera un round-trip per ricaricarli → in async questo
        causa errori "MissingGreenlet" se l'accesso avviene fuori contesto.
      - Con False: dopo commit, gli oggetti restano usabili senza re-fetch.
        È il comportamento atteso 99% delle volte.

    `autoflush=False`: niente flush automatici prima delle query. Più
    prevedibile per debugging. Quando vogliamo flushare, lo facciamo
    esplicitamente con `await session.flush()`.
    """
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
        class_=AsyncSession,
    )


# -----------------------------------------------------------------------------
# RLS binding helper
# -----------------------------------------------------------------------------
async def set_rls_user(session: AsyncSession, user_id: UUID) -> None:
    """Setta `request.jwt.claim.sub` per la transazione corrente.

    Le RLS policy delle tabelle (definite in Alembic migrations) leggono
    questo valore con `current_setting('request.jwt.claim.sub', true)`.
    Settarlo qui = abilitare RLS in modo trasparente.

    `SET LOCAL` è scoped alla transazione: quando la tx termina (commit/rollback),
    il setting sparisce. Questo previene leak di stato tra richieste HTTP
    diverse che potrebbero condividere la stessa connessione del pool.

    Importante: questa funzione DEVE essere chiamata dentro una transazione
    aperta (`session.begin()`), altrimenti SET LOCAL non ha effetto.

    Args:
        session: AsyncSession aperta, dentro una transazione attiva.
        user_id: UUID dell'utente corrente (dal claim 'sub' del JWT).

    Raises:
        sqlalchemy.exc.* in caso di problemi di connessione/transazione.
    """
    # Usiamo `text(...)` con parametro bindato per prevenire SQL injection
    # anche se user_id è già un UUID validato (defense in depth).
    # NB: `set_config(name, value, is_local)` è la funzione Postgres
    # equivalente a `SET LOCAL`, ma supporta parametri bindati.
    await session.execute(
        text("SELECT set_config('request.jwt.claim.sub', :uid, true)"),
        {"uid": str(user_id)},
    )


# -----------------------------------------------------------------------------
# Dependency provider (placeholder per FastAPI)
# -----------------------------------------------------------------------------
async def get_session_unauthenticated(
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Apre una sessione SENZA RLS binding.

    Usata per:
      - healthcheck e endpoint pubblici (no user)
      - migrazioni / job di sistema che bypassano RLS

    Non chiamare per endpoint protetti: i dati non sarebbero filtrati
    per utente! Per quelli usa `get_session_for_user(session_maker, user_id)`.
    """
    async with session_maker() as session:
        yield session


async def get_session_for_user(
    session_maker: async_sessionmaker[AsyncSession],
    user_id: UUID,
) -> AsyncGenerator[AsyncSession, None]:
    """Apre una sessione con RLS attiva per l'utente specificato.

    Pattern: apri sessione → apri transazione → setta RLS → yield.
    Quando il caller esce dal contesto, transazione commit (se nessun errore)
    + connessione restituita al pool.
    """
    async with session_maker() as session, session.begin():
        await set_rls_user(session, user_id)
        yield session
