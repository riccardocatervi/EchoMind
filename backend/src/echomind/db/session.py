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
async def set_rls_user(
    session: AsyncSession,
    user_id: UUID,
    *,
    runtime_role: str = "app_runtime",
) -> None:
    """Attiva RLS per la transazione corrente impersonando un ruolo non-superuser.

    Due passaggi, da eseguire in ordine DENTRO una transazione aperta:

    1. `SET LOCAL ROLE app_runtime` — abbassa i privilegi al ruolo non-superuser.
       Solo così le policy RLS sono effettive (i superuser bypassano sempre RLS).
       Replica il pattern Supabase: `authenticator` → `authenticated`.

    2. `set_config('request.jwt.claim.sub', user_id, true)` — popola il claim
       letto dalle policy: `USING (id::text = current_setting(...))`.

    `SET LOCAL` è scoped alla transazione: alla fine, il ruolo torna quello
    del connection user (`echomind`) e il claim sparisce. Niente leak tra
    richieste HTTP diverse che potrebbero condividere la stessa connection
    fisica del pool.

    Args:
        session: AsyncSession aperta, dentro una transazione attiva.
        user_id: UUID dell'utente corrente (claim 'sub' del JWT).
        runtime_role: ruolo da impersonare. Default `app_runtime`.
            In Supabase prod sarebbe `authenticated`.

    Raises:
        sqlalchemy.exc.* in caso di problemi di connessione/transazione,
        o se il ruolo non esiste / non è grantato al connection user.
    """
    # 1. De-eleva i privilegi (necessario perché RLS bypassa i superuser).
    # `SET LOCAL ROLE` NON supporta parametri bindati, quindi usiamo
    # interpolazione diretta dopo whitelisting del nome ruolo.
    if not runtime_role.replace("_", "").isalnum():
        raise ValueError(f"Invalid runtime_role name: {runtime_role!r}")
    await session.execute(text(f"SET LOCAL ROLE {runtime_role}"))

    # 2. Setta il claim JWT letto dalle policy RLS.
    # `set_config(name, value, is_local)` è la funzione Postgres equivalente
    # a `SET LOCAL`, e supporta parametri bindati (defense in depth).
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
