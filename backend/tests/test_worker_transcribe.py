"""Test del core async del transcribe task (`run_transcribe`) con DB reale.

Chiamiamo `run_transcribe` DIRETTAMENTE (niente Celery/asyncio.run): gira nello
stesso event loop del test. Storage e transcriber sono INIETTATI come fake
(niente B2, niente OpenAI, niente ffmpeg -- usiamo documenti TXT).

Copre: successo documento (queued->running->succeeded + transcript persistito),
documento mancante (failed terminale), errore permanente (failed senza retry),
errore transiente (retry se non ultimo, failed se ultimo), idempotenza su task
terminale, upsert idempotente sul ri-processing dello stesso documento.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from echomind.processing import Transcriber, TranscriptionResult
from echomind.services.storage import StorageError, StorageObjectNotFoundError
from echomind.worker.tasks.transcribe import run_transcribe

pytestmark = pytest.mark.asyncio


# =============================================================================
# Fake injectables (Protocol-compatible)
# =============================================================================
class _FakeStorage:
    """ObjectStore finto: ritorna byte in memoria o solleva un errore."""

    def __init__(self, *, data: bytes | None = None, exc: Exception | None = None) -> None:
        self._data = data
        self._exc = exc

    async def get_object(self, key: str) -> bytes:
        if self._exc is not None:
            raise self._exc
        assert self._data is not None
        return self._data


class _FakeTranscriber:
    def transcribe(self, *, audio: bytes, filename: str) -> TranscriptionResult:
        return TranscriptionResult(text="trascritto", language="italian")


def _no_transcriber_factory() -> Transcriber:
    """Factory che esplode: i documenti NON devono costruire un transcriber."""
    raise AssertionError("il transcriber non deve servire per i documenti")


# =============================================================================
# Seeding helpers (via system_session, superuser --> bypassa RLS)
# =============================================================================
async def _seed_profile(session: AsyncSession, owner_id: UUID) -> None:
    await session.execute(
        text(
            "INSERT INTO public.profiles (id, display_name) VALUES (:id, 'u') ON CONFLICT (id) DO NOTHING"
        ),
        {"id": str(owner_id)},
    )


async def _seed_document(session: AsyncSession, *, owner_id: UUID, mime_type: str) -> UUID:
    doc_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO public.documents (id, owner_id, filename, mime_type, size_bytes, storage_key) "
            "VALUES (:id, :owner, 'f', :mime, 100, :key)"
        ),
        {
            "id": str(doc_id),
            "owner": str(owner_id),
            "mime": mime_type,
            "key": f"users/{owner_id}/{doc_id}",
        },
    )
    return doc_id


async def _seed_transcribe_task(
    session: AsyncSession, *, owner_id: UUID, document_id: UUID
) -> UUID:
    task_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO public.tasks (id, owner_id, task_type, status, payload) "
            "VALUES (:id, :owner, 'transcribe', 'queued', CAST(:payload AS jsonb))"
        ),
        {
            "id": str(task_id),
            "owner": str(owner_id),
            "payload": json.dumps({"document_id": str(document_id)}),
        },
    )
    return task_id


async def _task_row(session: AsyncSession, task_id: UUID) -> Any:
    result = await session.execute(
        text(
            "SELECT status::text AS status, error, retries, "
            "result->>'char_count' AS char_count, "
            "(finished_at IS NOT NULL) AS has_finished "
            "FROM public.tasks WHERE id = :id"
        ),
        {"id": str(task_id)},
    )
    return result.mappings().one()


async def _transcript_row(session: AsyncSession, document_id: UUID) -> Any:
    result = await session.execute(
        text(
            "SELECT source_type, content, language, char_count "
            "FROM public.transcripts WHERE document_id = :d"
        ),
        {"d": str(document_id)},
    )
    return result.mappings().one_or_none()


# =============================================================================
# Tests
# =============================================================================
async def test_document_success_persists_transcript(
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_auth_user: Any,
) -> None:
    owner_id = uuid4()
    await seed_auth_user(owner_id)
    await _seed_profile(system_session, owner_id)
    doc_id = await _seed_document(system_session, owner_id=owner_id, mime_type="text/plain")
    task_id = await _seed_transcribe_task(system_session, owner_id=owner_id, document_id=doc_id)
    await system_session.commit()

    outcome = await run_transcribe(
        task_id=task_id,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
        storage=_FakeStorage(data=b"  ciao    mondo  "),
        transcriber_factory=_no_transcriber_factory,  # documento: non deve servire
        max_chunk_bytes=24 * 1024 * 1024,
    )

    assert outcome.kind == "succeeded"

    task = await _task_row(system_session, task_id)
    assert task["status"] == "succeeded"
    assert task["has_finished"] is True
    assert int(task["char_count"]) == len("ciao mondo")

    transcript = await _transcript_row(system_session, doc_id)
    assert transcript is not None
    assert transcript["source_type"] == "document"
    assert transcript["content"] == "ciao mondo"  # normalizzato
    assert transcript["language"] is None
    assert transcript["char_count"] == len("ciao mondo")


async def test_missing_document_is_terminal(
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_auth_user: Any,
) -> None:
    """Task che punta a un document_id inesistente: fallimento permanente."""
    owner_id = uuid4()
    await seed_auth_user(owner_id)
    await _seed_profile(system_session, owner_id)
    # Task senza documento corrispondente.
    task_id = await _seed_transcribe_task(system_session, owner_id=owner_id, document_id=uuid4())
    await system_session.commit()

    outcome = await run_transcribe(
        task_id=task_id,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
        storage=_FakeStorage(data=b"irrilevante"),
        transcriber_factory=_no_transcriber_factory,
        max_chunk_bytes=24 * 1024 * 1024,
    )

    assert outcome.kind == "failed_terminal"
    task = await _task_row(system_session, task_id)
    assert task["status"] == "failed"
    assert task["error"] is not None


async def test_permanent_processing_error_is_terminal_without_retry(
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_auth_user: Any,
) -> None:
    """Contenuto vuoto --> EmptyContentError (permanente): failed anche se NON ultimo tentativo."""
    owner_id = uuid4()
    await seed_auth_user(owner_id)
    await _seed_profile(system_session, owner_id)
    doc_id = await _seed_document(system_session, owner_id=owner_id, mime_type="text/plain")
    task_id = await _seed_transcribe_task(system_session, owner_id=owner_id, document_id=doc_id)
    await system_session.commit()

    outcome = await run_transcribe(
        task_id=task_id,
        attempt=0,
        is_last_attempt=False,  # NON ultimo: ma l'errore e' permanente
        session_maker=db_session_maker,
        storage=_FakeStorage(data=b"   \n\t  "),  # vuoto dopo normalizzazione
        transcriber_factory=_no_transcriber_factory,
        max_chunk_bytes=24 * 1024 * 1024,
    )

    assert outcome.kind == "failed_terminal"
    task = await _task_row(system_session, task_id)
    assert task["status"] == "failed"
    assert await _transcript_row(system_session, doc_id) is None


async def test_storage_not_found_is_terminal(
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_auth_user: Any,
) -> None:
    """Oggetto storage assente (404): permanente, niente retry."""
    owner_id = uuid4()
    await seed_auth_user(owner_id)
    await _seed_profile(system_session, owner_id)
    doc_id = await _seed_document(system_session, owner_id=owner_id, mime_type="text/plain")
    task_id = await _seed_transcribe_task(system_session, owner_id=owner_id, document_id=doc_id)
    await system_session.commit()

    outcome = await run_transcribe(
        task_id=task_id,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
        storage=_FakeStorage(exc=StorageObjectNotFoundError("gone")),
        transcriber_factory=_no_transcriber_factory,
        max_chunk_bytes=24 * 1024 * 1024,
    )
    assert outcome.kind == "failed_terminal"
    assert (await _task_row(system_session, task_id))["status"] == "failed"


async def test_transient_error_retries_then_fails_when_exhausted(
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_auth_user: Any,
) -> None:
    """Errore di storage transiente: retry se non ultimo, failed se ultimo tentativo."""
    owner_id = uuid4()
    await seed_auth_user(owner_id)
    await _seed_profile(system_session, owner_id)
    doc_id = await _seed_document(system_session, owner_id=owner_id, mime_type="text/plain")
    task_id = await _seed_transcribe_task(system_session, owner_id=owner_id, document_id=doc_id)
    await system_session.commit()

    # Non ultimo tentativo --> retry, la riga resta 'running'.
    outcome = await run_transcribe(
        task_id=task_id,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
        storage=_FakeStorage(exc=StorageError("network blip")),
        transcriber_factory=_no_transcriber_factory,
        max_chunk_bytes=24 * 1024 * 1024,
    )
    assert outcome.kind == "retry"
    assert (await _task_row(system_session, task_id))["status"] == "running"

    # Ultimo tentativo --> failed terminale.
    outcome = await run_transcribe(
        task_id=task_id,
        attempt=2,
        is_last_attempt=True,
        session_maker=db_session_maker,
        storage=_FakeStorage(exc=StorageError("network blip")),
        transcriber_factory=_no_transcriber_factory,
        max_chunk_bytes=24 * 1024 * 1024,
    )
    assert outcome.kind == "failed_terminal"
    assert (await _task_row(system_session, task_id))["status"] == "failed"


async def test_idempotent_on_terminal_task(
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_auth_user: Any,
) -> None:
    """Re-delivery su task gia' terminale: no-op idempotente."""
    owner_id = uuid4()
    await seed_auth_user(owner_id)
    await _seed_profile(system_session, owner_id)
    doc_id = await _seed_document(system_session, owner_id=owner_id, mime_type="text/plain")
    task_id = await _seed_transcribe_task(system_session, owner_id=owner_id, document_id=doc_id)
    await system_session.commit()

    await run_transcribe(
        task_id=task_id,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
        storage=_FakeStorage(data=b"primo"),
        transcriber_factory=_no_transcriber_factory,
        max_chunk_bytes=24 * 1024 * 1024,
    )
    # Seconda esecuzione: task gia' 'succeeded' --> no-op.
    outcome = await run_transcribe(
        task_id=task_id,
        attempt=1,
        is_last_attempt=True,
        session_maker=db_session_maker,
        storage=_FakeStorage(data=b"secondo"),
        transcriber_factory=_no_transcriber_factory,
        max_chunk_bytes=24 * 1024 * 1024,
    )
    assert outcome.kind == "already_done"
    transcript = await _transcript_row(system_session, doc_id)
    assert transcript["content"] == "primo"  # invariato


async def test_upsert_replaces_on_reprocess(
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_auth_user: Any,
) -> None:
    """Due task sullo STESSO documento: il secondo upsert sostituisce, non duplica."""
    owner_id = uuid4()
    await seed_auth_user(owner_id)
    await _seed_profile(system_session, owner_id)
    doc_id = await _seed_document(system_session, owner_id=owner_id, mime_type="text/plain")
    task1 = await _seed_transcribe_task(system_session, owner_id=owner_id, document_id=doc_id)
    task2 = await _seed_transcribe_task(system_session, owner_id=owner_id, document_id=doc_id)
    await system_session.commit()

    await run_transcribe(
        task_id=task1,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
        storage=_FakeStorage(data=b"prima versione"),
        transcriber_factory=_no_transcriber_factory,
        max_chunk_bytes=24 * 1024 * 1024,
    )
    await run_transcribe(
        task_id=task2,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
        storage=_FakeStorage(data=b"seconda versione"),
        transcriber_factory=_no_transcriber_factory,
        max_chunk_bytes=24 * 1024 * 1024,
    )

    # Una sola riga transcript per il documento, col contenuto piu' recente.
    count = await system_session.execute(
        text("SELECT COUNT(*) FROM public.transcripts WHERE document_id = :d"), {"d": str(doc_id)}
    )
    assert count.scalar_one() == 1
    transcript = await _transcript_row(system_session, doc_id)
    assert transcript["content"] == "seconda versione"
    assert transcript["char_count"] == len("seconda versione")
