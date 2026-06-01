"""Worker runtime: engine DB dedicato + ponte sync-->async.

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
    nostro volume). Beneficio: zero problemi di affinità loop<->connessione.

Perché lazy / post-fork:
    In prefork il padre forka i figli DOPO l'import del modulo. Creare l'engine
    all'import (nel padre) farebbe ereditare ai figli strutture asyncio/socket
    --> corruzione. Creandolo al primo task (nel figlio già forkato) lo evitiamo.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from echomind.core.config import get_settings
from echomind.processing.transcription import OpenAIWhisperTranscriber
from echomind.services.storage import B2StorageService

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


# Singleton di PROCESSO per storage e transcriber, lazy come l'engine: costruiti
# al primo uso (post-fork --> fork-safe) e riusati per tutti i task del worker.
_storage: B2StorageService | None = None
_transcriber: OpenAIWhisperTranscriber | None = None


def get_worker_storage() -> B2StorageService:
    """Storage B2 del worker (lazy, post-fork). Serve a scaricare il file da processare.

    Solleva StorageError se le credenziali B2 sono incomplete (in produzione il
    worker le ha sempre; vedi Settings._validate_b2_credentials_in_production).
    """
    global _storage
    if _storage is None:
        _storage = B2StorageService.from_settings(get_settings())
    return _storage


def get_worker_transcriber() -> OpenAIWhisperTranscriber:
    """Transcriber Whisper del worker (lazy, post-fork).

    Costruito SOLO quando serve davvero (un task audio lo invoca via factory):
    solleva se manca OPENAI_API_KEY. I task su DOCUMENTI non lo chiamano affatto
    (process_media non usa il transcriber per i documenti), quindi processare un
    PDF non richiede alcuna API key OpenAI.
    """
    global _transcriber
    if _transcriber is None:
        settings = get_settings()
        if settings.openai_api_key is None:
            raise RuntimeError(
                "OPENAI_API_KEY mancante: la trascrizione audio richiede una API key OpenAI"
            )
        client = OpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            organization=settings.openai_org_id,
        )
        _transcriber = OpenAIWhisperTranscriber(client=client, model=settings.whisper_model)
    return _transcriber
