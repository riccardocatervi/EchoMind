"""Task 'extract' -- il SECONDO worker reale di EchoMind (M5).

Aggancia la pipeline di KnowledgeExtraction al motore async: data una riga `tasks`
di tipo 'extract' (payload con document_id), carica il `transcript` di quel
documento, ne estrae il grafo (entita' + relazioni + community) e un riassunto
multilivello via Gemini, persiste il grafo su Neo4j e summary + embeddings su
Postgres, aggiornando lo stato del task lungo il percorso.

Architettura in DUE livelli, identica a transcribe (ADR-0005/0006):
- `run_extract()`  -- coroutine ASYNC: logica di dominio, pura e testabile (graph
  store ed adapter Gemini INIETTATI come Protocol --> fake nei test).
- `extract_task()` -- wrapper SINCRONO Celery: DI delle risorse di processo e
  traduzione dell'esito in self.retry / Reject.

Idempotenza cross-store: re-eseguire SOSTITUISCE (grafo Neo4j ricreato, summary
upsert, embeddings replace), quindi un retry o una ri-estrazione non duplicano.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from celery import Task
from celery.exceptions import Reject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from echomind.core.config import get_settings
from echomind.core.logging import get_logger
from echomind.db.models import Transcript
from echomind.db.models.task import TERMINAL_STATUSES
from echomind.db.repositories import (
    EmbeddingRepository,
    EmbeddingValue,
    SummaryRepository,
    TaskRepository,
    TranscriptRepository,
)
from echomind.extraction import ExtractionError, ExtractionResult, extract_knowledge
from echomind.extraction.embedder import Embedder
from echomind.extraction.extractor import GraphExtractor
from echomind.extraction.summarize import Summarizer
from echomind.services.graph_store import GraphStore, GraphStoreError
from echomind.worker.celery_app import celery_app
from echomind.worker.runtime import (
    get_worker_embedder,
    get_worker_extractor,
    get_worker_graph_store,
    get_worker_session_maker,
    get_worker_summarizer,
    run_async,
)

log = get_logger(__name__)


class ExtractTaskError(Exception):
    """Causa propagata a Celery sul retry (finisce nei log / result backend)."""


@dataclass(frozen=True, slots=True)
class ExtractOutcome:
    """Esito del core async, tradotto dal wrapper sincrono in azioni Celery."""

    kind: Literal["succeeded", "retry", "failed_terminal", "already_done"]
    result: dict[str, Any] | None = None
    error: str | None = None


def _classify_error(exc: Exception) -> tuple[bool, str]:
    """Mappa un'eccezione in (retryable, messaggio).

    - ExtractionError (LLM/embedding): usa il suo flag `retryable` (429/5xx
      transiente, 4xx permanente).
    - GraphStoreError (Neo4j): idem (connessione transiente, errore server permanente).
    - Qualunque altra: transiente, ma limitata dal tetto dei retry.
    """
    if isinstance(exc, ExtractionError):
        return exc.retryable, str(exc)
    if isinstance(exc, GraphStoreError):
        return exc.retryable, str(exc)
    return True, f"Errore inatteso durante l'estrazione: {exc}"


async def _load_transcript(session: AsyncSession, payload: dict[str, Any]) -> Transcript | None:
    """Carica il transcript referenziato dal payload (sessione di sistema).

    Ritorna None se il payload non ha un document_id valido o se non esiste un
    transcript per quel documento: in entrambi i casi e' un fallimento permanente.
    """
    raw = payload.get("document_id")
    if not isinstance(raw, str):
        return None
    try:
        document_id = UUID(raw)
    except ValueError:
        return None
    return await TranscriptRepository(session).get_by_document_id(document_id)


async def run_extract(
    *,
    task_id: UUID,
    attempt: int,
    is_last_attempt: bool,
    session_maker: async_sessionmaker[AsyncSession],
    graph_store: GraphStore,
    extractor: GraphExtractor,
    embedder: Embedder,
    summarizer: Summarizer,
    max_chunk_chars: int,
    chunk_overlap_chars: int,
    dedup_threshold: float,
) -> ExtractOutcome:
    """Core async dell'estrazione: dal transcript al grafo + summary + embeddings.

    Idempotente (re-delivery at-least-once): no-op su righe gia' terminali. Usa una
    sessione di SISTEMA (no RLS): il worker e' un componente fidato. Commit separati
    per stato cosi' l'API osserva 'running' DURANTE il lavoro (puo' durare minuti).
    """
    async with session_maker() as session:
        task_repo = TaskRepository(session)

        # 1. Carica task + guardia di idempotenza + risolvi il transcript (stessa txn).
        async with session.begin():
            task = await task_repo.get_by_id(task_id)
            if task is None:
                log.warning("extract_task_row_missing", task_id=str(task_id))
                return ExtractOutcome(kind="already_done")
            if task.status in TERMINAL_STATUSES:
                log.info(
                    "extract_task_already_terminal",
                    task_id=str(task_id),
                    status=task.status.value,
                )
                return ExtractOutcome(kind="already_done", result=task.result)
            await task_repo.mark_running(task, retries=attempt)
            transcript = await _load_transcript(session, task.payload)

        log.info("extract_task_running", task_id=str(task_id), attempt=attempt + 1)

        # 2. Transcript assente --> fallimento permanente (l'estrazione lo richiede).
        if transcript is None:
            error = "Transcript non trovato: l'estrazione richiede una trascrizione pronta"
            async with session.begin():
                await task_repo.mark_failed(task, error=error)
            log.error("extract_task_transcript_missing", task_id=str(task_id))
            return ExtractOutcome(kind="failed_terminal", error=error)

        document_id = transcript.document_id
        owner_id = transcript.owner_id

        # 3. Estrai (LLM, in un thread) --> persisti grafo (Neo4j) + summary/embeddings (PG).
        try:
            result: ExtractionResult = await asyncio.to_thread(
                extract_knowledge,
                text=transcript.content,
                extractor=extractor,
                embedder=embedder,
                summarizer=summarizer,
                max_chunk_chars=max_chunk_chars,
                chunk_overlap_chars=chunk_overlap_chars,
                dedup_threshold=dedup_threshold,
            )
            await graph_store.replace_document_graph(
                owner_id=owner_id,
                document_id=document_id,
                entities=result.entities,
                relations=result.relations,
            )
            async with session.begin():
                summary_row = await SummaryRepository(session).upsert(
                    document_id=document_id,
                    owner_id=owner_id,
                    overview=result.summary.overview,
                    sections=[
                        {"title": section.title, "content": section.content}
                        for section in result.summary.sections
                    ],
                    meta=result.meta,
                )
                await EmbeddingRepository(session).replace_for_document(
                    document_id=document_id,
                    owner_id=owner_id,
                    values=[
                        EmbeddingValue(entity_id=item.entity_id, name=item.name, vector=item.vector)
                        for item in result.embeddings
                    ],
                )
        except Exception as exc:
            retryable, error = _classify_error(exc)
            if retryable and not is_last_attempt:
                log.warning(
                    "extract_task_will_retry",
                    task_id=str(task_id),
                    attempt=attempt + 1,
                    error=error,
                )
                return ExtractOutcome(kind="retry", error=error)
            async with session.begin():
                await task_repo.mark_failed(task, error=error)
            log.error(
                "extract_task_failed_terminal",
                task_id=str(task_id),
                attempt=attempt + 1,
                retryable=retryable,
            )
            return ExtractOutcome(kind="failed_terminal", error=error)

        # 4. Marca succeeded con il sommario dei conteggi.
        summary: dict[str, Any] = {
            "document_id": str(document_id),
            "summary_id": str(summary_row.id),
            "node_count": result.meta["node_count"],
            "relationship_count": result.meta["relationship_count"],
            "community_count": result.meta["community_count"],
        }
        async with session.begin():
            await task_repo.mark_succeeded(task, result=summary)
        log.info(
            "extract_task_succeeded",
            task_id=str(task_id),
            node_count=result.meta["node_count"],
            relationship_count=result.meta["relationship_count"],
        )
        return ExtractOutcome(kind="succeeded", result=summary)


def _retry_countdown(attempt: int, *, base: int) -> int:
    """Ritardo (secondi) prima del prossimo retry: backoff esponenziale + jitter."""
    exponential = base * (2**attempt)
    jitter = random.uniform(0, base)  # noqa: S311 - jitter non crittografico
    return int(exponential + jitter)


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="echomind.extract",
    max_retries=get_settings().task_max_retries,
    soft_time_limit=get_settings().extraction_soft_time_limit_seconds,
    time_limit=get_settings().extraction_soft_time_limit_seconds + 30,
)
def extract_task(self: Task, task_id: str) -> dict[str, Any] | None:
    """Wrapper sincrono Celery. Fa DI delle risorse di processo e traduce l'esito.

    Riceve solo `task_id`: il document_id vive nel payload della riga `tasks`
    (sorgente di verita'), letto da run_extract.
    """
    settings = get_settings()
    attempt: int = self.request.retries
    is_last_attempt = (attempt + 1) >= settings.task_max_retries

    outcome = run_async(
        run_extract(
            task_id=UUID(task_id),
            attempt=attempt,
            is_last_attempt=is_last_attempt,
            session_maker=get_worker_session_maker(),
            graph_store=get_worker_graph_store(),
            extractor=get_worker_extractor(),
            embedder=get_worker_embedder(),
            summarizer=get_worker_summarizer(),
            max_chunk_chars=settings.extraction_max_chunk_chars,
            chunk_overlap_chars=settings.extraction_chunk_overlap_chars,
            dedup_threshold=settings.entity_dedup_similarity_threshold,
        )
    )

    if outcome.kind == "retry":
        countdown = _retry_countdown(attempt, base=settings.task_retry_backoff_seconds)
        log.warning(
            "extract_task_retry_scheduled",
            task_id=task_id,
            attempt=attempt + 1,
            countdown=countdown,
        )
        raise self.retry(exc=ExtractTaskError(outcome.error or "retry"), countdown=countdown)

    if outcome.kind == "failed_terminal":
        log.error("extract_task_dead_lettered", task_id=task_id)
        raise Reject(requeue=False)

    return outcome.result
