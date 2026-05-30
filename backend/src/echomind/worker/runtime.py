"""Worker runtime: engine DB dedicato + ponte sync→async.

Il worker Celery (prefork) è un processo SEPARATO dall'API e SINCRONO: non
condivide `app.state` né l'engine dell'app FastAPI. Qui forniamo:
- un engine async dedicato al processo worker, lazy e con `NullPool`
- `run_async()`, per eseguire coroutine dal corpo sincrono di un task

Perché `NullPool`:
    Con `asyncio.run()` ogni task gira in un NUOVO event loop. Le connessioni
    asyncpg sono legate al loop su cui nascono; riusarle su un loop diverso
    esplode ("attached to a different loop"). NullPool non trattiene connessioni
    tra un uso e l'altro: ne apre una fresca per ogni operazione, sul loop
    corrente, e la chiude. Costo: una connessione nuova per task (accettabile al
    nostro volume). Beneficio: zero problemi di affinità loop↔connessione.

Perché lazy / post-fork:
    In prefork il padre forka i figli DOPO l'import del modulo. Creare l'engine
    all'import (nel padre) farebbe ereditare ai figli strutture asyncio/socket
    → corruzione. Creandolo al primo task (nel figlio già forkato) lo evitiamo.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from echomind.core.config import get_settings

# Singleton di PROCESSO (un worker = un processo): inizializzato pigramente al
# primo task, così la creazione avviene dopo il fork.
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_worker_session_maker() -> async_sessionmaker[AsyncSession]:
    """Ritorna il sessionmaker del worker (engine lazy con NullPool).

    Le sessioni prodotte sono di SISTEMA (nessun `SET LOCAL ROLE app_runtime`,
    nessun claim RLS): il worker gira come ruolo `echomind` (superuser) e
    bypassa RLS, perché è un componente fidato che aggiorna lo stato dei task
    per conto del sistema, non di un utente.
    """
    global _session_maker
    if _session_maker is None:
        settings = get_settings()
        engine = create_async_engine(
            str(settings.database_url),
            poolclass=NullPool,
            future=True,
        )
        _session_maker = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession,
        )
    return _session_maker


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Esegue una coroutine fino al completamento dal corpo sincrono di un task.

    Usa `asyncio.run()`, che crea e chiude un event loop dedicato. Funziona
    perché il processo worker prefork NON ha un event loop attivo.

    Caveat: invocata dentro un loop già in esecuzione (es. `task_always_eager`
    in un test pytest-asyncio) solleverebbe RuntimeError. È il motivo per cui i
    test NON usano eager mode e testano direttamente la coroutine `run_echo`
    (vedi ADR-0005).
    """
    return asyncio.run(coro)
