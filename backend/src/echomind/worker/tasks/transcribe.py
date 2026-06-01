"""Task 'transcribe' -- il PRIMO worker reale di EchoMind (M4).

Aggancia il motore asincrono di M3 alla pipeline di processing di M4: data una
riga `tasks` di tipo 'transcribe' (il cui payload contiene il document_id),
scarica il file da B2, lo trasforma in testo (parsing o Whisper) e persiste il
risultato come riga `transcripts`, aggiornando lo stato del task lungo il percorso.

Architettura in DUE livelli, identica all'echo (vedi ADR-0005):
- `run_transcribe()` -- coroutine ASYNC: tutta la logica di dominio, pura e
  testabile (storage e transcriber INIETTATI). Niente Celery, niente event loop
  annidati.
- `transcribe_task()` -- wrapper SINCRONO su Celery: fa dependency injection
  delle risorse di processo (session maker, storage, transcriber) e traduce
  l'esito nelle primitive di controllo (self.retry / Reject).

Retry vs dead-letter: a differenza dell'echo (guidato dal flag `fail`), qui
decide la NATURA dell'errore. ProcessingError porta `retryable`; un 404 di
storage e' permanente, un errore di rete e' transiente. Permanente --> dritto a
'failed' senza sprecare retry; transiente --> ritenta col backoff.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID

from celery import Task
from celery.exceptions import Reject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from echomind.core.config import get_settings
from echomind.core.logging import get_logger
from echomind.db.models import Document
from echomind.db.models.task import TERMINAL_STATUSES
from echomind.db.repositories import DocumentRepository, TaskRepository, TranscriptRepository
from echomind.processing import AUDIO_MIME_TYPES, ProcessingError, Transcriber, process_media
from echomind.services.storage import StorageError, StorageObjectNotFoundError
from echomind.worker.celery_app import celery_app
from echomind.worker.runtime import (
    get_worker_session_maker,
    get_worker_storage,
    get_worker_transcriber,
    run_async,
)

log = get_logger(__name__)


class TranscribeTaskError(Exception):
    """Causa propagata a Celery sul retry (finisce nei log / result backend)."""


class ObjectStore(Protocol):
    """Sottoinsieme dello storage che serve al task: scaricare un oggetto.

    Protocol (non il B2StorageService concreto) per testabilita': i test
    iniettano un fake che ritorna byte in memoria, senza toccare B2.
    """

    async def get_object(self, key: str) -> bytes: ...


@dataclass(frozen=True, slots=True)
class TranscribeOutcome:
    """Esito del core async, tradotto dal wrapper sincrono in azioni Celery.

    - succeeded:       transcript persistito; `result` e' il sommario.
    - retry:           fallimento transiente non terminale --> self.retry.
    - failed_terminal: fallimento permanente o retry esauriti (DB gia' 'failed')
                       --> Reject(requeue=False) --> dead-letter queue.
    - already_done:    riga gia' terminale o assente: no-op idempotente.
    """

    kind: Literal["succeeded", "retry", "failed_terminal", "already_done"]
    result: dict[str, Any] | None = None
    error: str | None = None


def _classify_error(exc: Exception) -> tuple[bool, str]:
    """Mappa un'eccezione del processing in (retryable, messaggio).

    - ProcessingError: usa il suo flag `retryable` (corrotto/vuoto = permanente;
      Whisper di rete/5xx = transiente).
    - StorageObjectNotFoundError: permanente (il file non c'e', ritentare e' inutile).
    - StorageError (altri): transiente (problema di rete verso B2).
    - Qualunque altra: transiente, ma comunque limitata dal tetto dei retry.
    """
    if isinstance(exc, ProcessingError):
        return exc.retryable, str(exc)
    if isinstance(exc, StorageObjectNotFoundError):
        return False, f"Oggetto storage mancante: {exc}"
    if isinstance(exc, StorageError):
        return True, f"Errore storage transiente: {exc}"
    return True, f"Errore inatteso durante il processing: {exc}"


async def _load_document(session: AsyncSession, payload: dict[str, Any]) -> Document | None:
    """Carica il documento referenziato dal payload del task (sessione di sistema).

    Ritorna None se il payload non ha un document_id valido o se il documento non
    esiste piu' (cancellato): in entrambi i casi e' un fallimento permanente.
    """
    raw = payload.get("document_id")
    if not isinstance(raw, str):
        return None
    try:
        document_id = UUID(raw)
    except ValueError:
        return None
    return await DocumentRepository(session).get_by_id(document_id)


async def run_transcribe(
    *,
    task_id: UUID,
    attempt: int,
    is_last_attempt: bool,
    session_maker: async_sessionmaker[AsyncSession],
    storage: ObjectStore,
    transcriber_factory: Callable[[], Transcriber],
    max_chunk_bytes: int,
) -> TranscribeOutcome:
    """Core async del task di trascrizione: da 'queued' al transcript persistito.

    Idempotente (re-delivery at-least-once): no-op su righe gia' terminali.
    Usa una sessione di SISTEMA (no RLS): il worker e' un componente fidato.
    Commit separati per stato cosi' l'API osserva 'running' DURANTE il lavoro
    (per un audio lungo puo' durare minuti).

    Il transcriber e' costruito (via factory) SOLO per gli input audio: un
    documento testuale non richiede una API key OpenAI.
    """
    async with session_maker() as session:
        task_repo = TaskRepository(session)

        # 1. Carica task + guardia di idempotenza.
        async with session.begin():
            task = await task_repo.get_by_id(task_id)
            if task is None:
                log.warning("transcribe_task_row_missing", task_id=str(task_id))
                return TranscribeOutcome(kind="already_done")
            if task.status in TERMINAL_STATUSES:
                log.info(
                    "transcribe_task_already_terminal",
                    task_id=str(task_id),
                    status=task.status.value,
                )
                return TranscribeOutcome(kind="already_done", result=task.result)
            await task_repo.mark_running(task, retries=attempt)
            # Risolviamo il documento DENTRO la stessa transazione: una SELECT
            # fuori da un blocco `session.begin()` aprirebbe una transazione
            # implicita (autobegin) che confliggerebbe col successivo
            # `async with session.begin()` ("a transaction is already begun").
            document = await _load_document(session, task.payload)

        log.info("transcribe_task_running", task_id=str(task_id), attempt=attempt + 1)

        # 2. Documento assente --> fallimento permanente.
        if document is None:
            error = "Documento non trovato o payload privo di document_id valido"
            async with session.begin():
                await task_repo.mark_failed(task, error=error)
            log.error("transcribe_task_document_missing", task_id=str(task_id))
            return TranscribeOutcome(kind="failed_terminal", error=error)

        # 3. Scarica + processa. Il lavoro e' sincrono e potenzialmente lungo
        #    (parsing/ffmpeg/Whisper): lo eseguiamo in un thread per non bloccare
        #    l'event loop. Il transcriber serve solo all'audio.
        try:
            data = await storage.get_object(document.storage_key)
            transcriber = transcriber_factory() if document.mime_type in AUDIO_MIME_TYPES else None
            result = await asyncio.to_thread(
                process_media,
                mime_type=document.mime_type,
                data=data,
                transcriber=transcriber,
                max_chunk_bytes=max_chunk_bytes,
            )
        except Exception as exc:
            retryable, error = _classify_error(exc)
            if retryable and not is_last_attempt:
                log.warning(
                    "transcribe_task_will_retry",
                    task_id=str(task_id),
                    attempt=attempt + 1,
                    error=error,
                )
                return TranscribeOutcome(kind="retry", error=error)
            async with session.begin():
                await task_repo.mark_failed(task, error=error)
            log.error(
                "transcribe_task_failed_terminal",
                task_id=str(task_id),
                attempt=attempt + 1,
                retryable=retryable,
            )
            return TranscribeOutcome(kind="failed_terminal", error=error)

        # 4. Persisti il transcript (upsert idempotente) e marca succeeded.
        char_count = len(result.content)
        async with session.begin():
            await TranscriptRepository(session).upsert(
                document_id=document.id,
                owner_id=document.owner_id,
                source_type=result.source_type.value,
                content=result.content,
                language=result.language,
                char_count=char_count,
                meta=result.meta,
            )

        summary: dict[str, Any] = {
            "document_id": str(document.id),
            "source_type": result.source_type.value,
            "char_count": char_count,
            "language": result.language,
            **result.meta,
        }
        async with session.begin():
            await task_repo.mark_succeeded(task, result=summary)
        log.info(
            "transcribe_task_succeeded",
            task_id=str(task_id),
            char_count=char_count,
            source_type=result.source_type.value,
        )
        return TranscribeOutcome(kind="succeeded", result=summary)


def _retry_countdown(attempt: int, *, base: int) -> int:
    """Ritardo (secondi) prima del prossimo retry: backoff esponenziale + jitter.

    Stessa logica di echo._retry_countdown: `base * 2**attempt` cresce
    geometricamente; il jitter (fino a `base`) sfasa i retry concomitanti
    evitando il thundering herd.
    """
    exponential = base * (2**attempt)
    jitter = random.uniform(0, base)  # noqa: S311 - jitter non crittografico
    return int(exponential + jitter)


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="echomind.transcribe",
    max_retries=get_settings().task_max_retries,
    soft_time_limit=get_settings().transcription_soft_time_limit_seconds,
    time_limit=get_settings().transcription_soft_time_limit_seconds + 30,
)
def transcribe_task(self: Task, task_id: str) -> dict[str, Any] | None:
    """Wrapper sincrono Celery. Fa DI delle risorse di processo e traduce l'esito.

    Riceve solo `task_id`: il document_id vive nel payload della riga `tasks`
    (sorgente di verita'), letto da run_transcribe. `bind=True` --> `self` per
    self.request.retries / self.retry.
    """
    settings = get_settings()
    attempt: int = self.request.retries
    is_last_attempt = (attempt + 1) >= settings.task_max_retries

    outcome = run_async(
        run_transcribe(
            task_id=UUID(task_id),
            attempt=attempt,
            is_last_attempt=is_last_attempt,
            session_maker=get_worker_session_maker(),
            storage=get_worker_storage(),
            transcriber_factory=get_worker_transcriber,
            max_chunk_bytes=settings.whisper_max_chunk_bytes,
        )
    )

    if outcome.kind == "retry":
        countdown = _retry_countdown(attempt, base=settings.task_retry_backoff_seconds)
        log.warning(
            "transcribe_task_retry_scheduled",
            task_id=task_id,
            attempt=attempt + 1,
            countdown=countdown,
        )
        raise self.retry(exc=TranscribeTaskError(outcome.error or "retry"), countdown=countdown)

    if outcome.kind == "failed_terminal":
        log.error("transcribe_task_dead_lettered", task_id=task_id)
        raise Reject(requeue=False)

    return outcome.result
