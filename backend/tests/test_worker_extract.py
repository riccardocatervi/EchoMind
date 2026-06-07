"""Test del core async dell'extract task (`run_extract`) con DB reale.

Chiamiamo `run_extract` DIRETTAMENTE (niente Celery/asyncio.run): gira nello stesso
event loop del test. Graph store ed adapter Gemini sono INIETTATI come fake (niente
Neo4j, niente Gemini). Il transcript e' seedato come superuser.

Copre: successo (grafo scritto + summary/embeddings persistiti + task succeeded),
transcript mancante (failed terminale), errore transiente (retry/failed), errore
permanente (failed senza retry), idempotenza, task assente.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from echomind.extraction import (
    ChunkGraph,
    DocumentSummary,
    ExtractedEntity,
    ExtractedRelation,
    LLMError,
    SummarySection,
)
from echomind.services.graph_store import GraphData, GraphStoreError
from echomind.worker.tasks.extract import run_extract

pytestmark = pytest.mark.asyncio

_DIM = 768


def _vec(index: int) -> list[float]:
    """Vettore unitario 768-dim con un 1 in posizione `index`: direzioni distinte
    --> nessun merge semantico (node_count == numero di entita' uniche)."""
    vector = [0.0] * _DIM
    vector[index % _DIM] = 1.0
    return vector


# =============================================================================
# Fake injectables (Protocol-compatible)
# =============================================================================
class _FakeGraphStore:
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.replaced: list[tuple[UUID, UUID, int, int]] = []
        self._fail = fail

    async def ensure_constraints(self) -> None: ...

    async def replace_document_graph(
        self,
        *,
        owner_id: UUID,
        document_id: UUID,
        entities: Sequence[Any],
        relations: Sequence[Any],
    ) -> None:
        if self._fail is not None:
            raise self._fail
        self.replaced.append((owner_id, document_id, len(list(entities)), len(list(relations))))

    async def get_document_graph(self, *, owner_id: UUID, document_id: UUID) -> GraphData:
        return GraphData(entities=[], relations=[])

    async def delete_document_graph(self, *, owner_id: UUID, document_id: UUID) -> None: ...

    async def delete_owner_graph(self, *, owner_id: UUID) -> None: ...


class _FakeExtractor:
    def __init__(self, *, exc: Exception | None = None) -> None:
        self._exc = exc

    def extract(self, text: str) -> ChunkGraph:
        if self._exc is not None:
            raise self._exc
        return ChunkGraph(
            entities=[
                ExtractedEntity(name="Alpha", type="CONCEPT", description="primo"),
                ExtractedEntity(name="Beta", type="CONCEPT", description="secondo"),
            ],
            relations=[ExtractedRelation(source="Alpha", target="Beta", type="related_to")],
        )


class _FakeEmbedder:
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [_vec(i) for i in range(len(texts))]


class _FakeSummarizer:
    def summarize(self, chunks: Sequence[str]) -> DocumentSummary:
        return DocumentSummary(
            overview="panoramica", sections=[SummarySection(title="Tema", content="dettaglio")]
        )


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


async def _seed_document(session: AsyncSession, *, owner_id: UUID) -> UUID:
    doc_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO public.documents (id, owner_id, filename, mime_type, size_bytes, storage_key) "
            "VALUES (:id, :owner, 'f.txt', 'text/plain', 100, :key)"
        ),
        {"id": str(doc_id), "owner": str(owner_id), "key": f"users/{owner_id}/{doc_id}"},
    )
    return doc_id


async def _seed_transcript(session: AsyncSession, *, owner_id: UUID, document_id: UUID) -> None:
    await session.execute(
        text(
            "INSERT INTO public.transcripts (id, document_id, owner_id, source_type, content, char_count) "
            "VALUES (:id, :doc, :owner, 'document', 'testo da estrarre', 17)"
        ),
        {"id": str(uuid4()), "doc": str(document_id), "owner": str(owner_id)},
    )


async def _seed_extract_task(session: AsyncSession, *, owner_id: UUID, document_id: UUID) -> UUID:
    task_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO public.tasks (id, owner_id, task_type, status, payload) "
            "VALUES (:id, :owner, 'extract', 'queued', CAST(:payload AS jsonb))"
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
            "SELECT status::text AS status, error, "
            "result->>'node_count' AS node_count, "
            "result->>'relationship_count' AS relationship_count "
            "FROM public.tasks WHERE id = :id"
        ),
        {"id": str(task_id)},
    )
    return result.mappings().one()


async def _summary_overview(session: AsyncSession, document_id: UUID) -> Any:
    result = await session.execute(
        text("SELECT overview FROM public.summaries WHERE document_id = :d"),
        {"d": str(document_id)},
    )
    return result.scalar_one_or_none()


async def _embedding_count(session: AsyncSession, document_id: UUID) -> int:
    result = await session.execute(
        text("SELECT COUNT(*) FROM public.entity_embeddings WHERE document_id = :d"),
        {"d": str(document_id)},
    )
    return int(result.scalar_one())


async def _full_seed(
    session: AsyncSession, seed_auth_user: Any, *, with_transcript: bool = True
) -> tuple[UUID, UUID, UUID]:
    owner_id = uuid4()
    await seed_auth_user(owner_id)
    await _seed_profile(session, owner_id)
    doc_id = await _seed_document(session, owner_id=owner_id)
    if with_transcript:
        await _seed_transcript(session, owner_id=owner_id, document_id=doc_id)
    task_id = await _seed_extract_task(session, owner_id=owner_id, document_id=doc_id)
    await session.commit()
    return owner_id, doc_id, task_id


# =============================================================================
# Tests
# =============================================================================
async def test_success_persists_graph_summary_embeddings(
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_auth_user: Any,
) -> None:
    _, doc_id, task_id = await _full_seed(system_session, seed_auth_user)
    store = _FakeGraphStore()

    outcome = await run_extract(
        task_id=task_id,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
        graph_store=store,
        extractor=_FakeExtractor(),
        embedder=_FakeEmbedder(),
        summarizer=_FakeSummarizer(),
        max_chunk_chars=10_000,
        chunk_overlap_chars=0,
        dedup_threshold=0.85,
    )

    assert outcome.kind == "succeeded"
    # Grafo scritto su Neo4j (fake): 2 nodi, 1 arco.
    assert len(store.replaced) == 1
    assert store.replaced[0][2] == 2  # entities
    assert store.replaced[0][3] == 1  # relations

    task = await _task_row(system_session, task_id)
    assert task["status"] == "succeeded"
    assert int(task["node_count"]) == 2
    assert int(task["relationship_count"]) == 1

    # Summary + embeddings persistiti su Postgres.
    assert await _summary_overview(system_session, doc_id) == "panoramica"
    assert await _embedding_count(system_session, doc_id) == 2


async def test_missing_transcript_is_terminal(
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_auth_user: Any,
) -> None:
    _, _, task_id = await _full_seed(system_session, seed_auth_user, with_transcript=False)

    outcome = await run_extract(
        task_id=task_id,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
        graph_store=_FakeGraphStore(),
        extractor=_FakeExtractor(),
        embedder=_FakeEmbedder(),
        summarizer=_FakeSummarizer(),
        max_chunk_chars=10_000,
        chunk_overlap_chars=0,
        dedup_threshold=0.85,
    )

    assert outcome.kind == "failed_terminal"
    assert (await _task_row(system_session, task_id))["status"] == "failed"


async def test_transient_error_retries_then_fails_when_exhausted(
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_auth_user: Any,
) -> None:
    _, _, task_id = await _full_seed(system_session, seed_auth_user)
    transient = _FakeExtractor(exc=LLMError("rate limit", retryable=True))

    # Non ultimo --> retry, riga resta 'running'.
    outcome = await run_extract(
        task_id=task_id,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
        graph_store=_FakeGraphStore(),
        extractor=transient,
        embedder=_FakeEmbedder(),
        summarizer=_FakeSummarizer(),
        max_chunk_chars=10_000,
        chunk_overlap_chars=0,
        dedup_threshold=0.85,
    )
    assert outcome.kind == "retry"
    assert (await _task_row(system_session, task_id))["status"] == "running"

    # Ultimo --> failed terminale.
    outcome = await run_extract(
        task_id=task_id,
        attempt=2,
        is_last_attempt=True,
        session_maker=db_session_maker,
        graph_store=_FakeGraphStore(),
        extractor=transient,
        embedder=_FakeEmbedder(),
        summarizer=_FakeSummarizer(),
        max_chunk_chars=10_000,
        chunk_overlap_chars=0,
        dedup_threshold=0.85,
    )
    assert outcome.kind == "failed_terminal"
    assert (await _task_row(system_session, task_id))["status"] == "failed"


async def test_permanent_error_is_terminal_without_retry(
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_auth_user: Any,
) -> None:
    _, _, task_id = await _full_seed(system_session, seed_auth_user)

    outcome = await run_extract(
        task_id=task_id,
        attempt=0,
        is_last_attempt=False,  # NON ultimo: ma l'errore e' permanente
        session_maker=db_session_maker,
        graph_store=_FakeGraphStore(),
        extractor=_FakeExtractor(exc=LLMError("4xx", retryable=False)),
        embedder=_FakeEmbedder(),
        summarizer=_FakeSummarizer(),
        max_chunk_chars=10_000,
        chunk_overlap_chars=0,
        dedup_threshold=0.85,
    )
    assert outcome.kind == "failed_terminal"


async def test_graph_store_transient_error_retries(
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_auth_user: Any,
) -> None:
    """Neo4j giu' durante la scrittura del grafo: errore transiente --> retry."""
    _, _, task_id = await _full_seed(system_session, seed_auth_user)

    outcome = await run_extract(
        task_id=task_id,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
        graph_store=_FakeGraphStore(fail=GraphStoreError("neo4j down", retryable=True)),
        extractor=_FakeExtractor(),
        embedder=_FakeEmbedder(),
        summarizer=_FakeSummarizer(),
        max_chunk_chars=10_000,
        chunk_overlap_chars=0,
        dedup_threshold=0.85,
    )
    assert outcome.kind == "retry"


async def test_idempotent_on_terminal_task(
    system_session: AsyncSession,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_auth_user: Any,
) -> None:
    _, _, task_id = await _full_seed(system_session, seed_auth_user)

    await run_extract(
        task_id=task_id,
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
        graph_store=_FakeGraphStore(),
        extractor=_FakeExtractor(),
        embedder=_FakeEmbedder(),
        summarizer=_FakeSummarizer(),
        max_chunk_chars=10_000,
        chunk_overlap_chars=0,
        dedup_threshold=0.85,
    )
    # Seconda esecuzione: task gia' 'succeeded' --> no-op.
    outcome = await run_extract(
        task_id=task_id,
        attempt=1,
        is_last_attempt=True,
        session_maker=db_session_maker,
        graph_store=_FakeGraphStore(),
        extractor=_FakeExtractor(),
        embedder=_FakeEmbedder(),
        summarizer=_FakeSummarizer(),
        max_chunk_chars=10_000,
        chunk_overlap_chars=0,
        dedup_threshold=0.85,
    )
    assert outcome.kind == "already_done"


async def test_missing_task_is_already_done(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    outcome = await run_extract(
        task_id=uuid4(),
        attempt=0,
        is_last_attempt=False,
        session_maker=db_session_maker,
        graph_store=_FakeGraphStore(),
        extractor=_FakeExtractor(),
        embedder=_FakeEmbedder(),
        summarizer=_FakeSummarizer(),
        max_chunk_chars=10_000,
        chunk_overlap_chars=0,
        dedup_threshold=0.85,
    )
    assert outcome.kind == "already_done"
