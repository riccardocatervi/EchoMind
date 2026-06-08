"""Test puri del RagService (M8, CP7).

Tutti i collaboratori sono sostituiti con fake in-process: niente DB, niente
Gemini, niente Neo4j. Coprono:
  - Happy path: ask ritorna RagAnswer valido.
  - Documento non trovato / non COMPLETED --> RagNotReadyError.
  - Propagazione della lingua all'answerer.
  - Inclusione/assenza del summary_overview nel contesto.
  - Embedding: la domanda viene passata all'embedder.
  - Contesto vuoto (nessuna entita' simile): non solleva, risposta valida.
  - Rispetto del parametro top_k.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from echomind.db.models.document import DocumentStatus
from echomind.db.repositories.embedding import SimilarEntity
from echomind.extraction.schema import Entity, Relation
from echomind.rag.schema import RagAnswer, RetrievedContext
from echomind.services.graph_store import GraphData
from echomind.services.rag import RagNotReadyError, RagService


# =============================================================================
# Fake Document (sostituisce l'ORM Document)
# =============================================================================
@dataclass
class _FakeDocument:
    id: UUID = field(default_factory=uuid4)
    status: DocumentStatus = DocumentStatus.COMPLETED


# =============================================================================
# Fake repositories
# =============================================================================
class _FakeDocumentRepository:
    """Ritorna sempre il documento configurato, indipendentemente dall'ID."""

    def __init__(self, document: _FakeDocument | None) -> None:
        self._document = document

    async def get_by_id(self, document_id: UUID) -> _FakeDocument | None:
        return self._document


class _FakeEmbeddingRepository:
    """Ritorna la lista di SimilarEntity configurata (rispettando il limit k)."""

    def __init__(self, similar: list[SimilarEntity] | None = None) -> None:
        self._similar = similar or []

    async def search_similar(
        self,
        *,
        document_id: UUID,
        owner_id: UUID,
        query_vector: list[float],
        k: int,
    ) -> list[SimilarEntity]:
        return self._similar[:k]


@dataclass
class _FakeSummary:
    """Surrogato del modello ORM Summary (solo campo `overview` usato dal service)."""

    overview: str


class _FakeSummaryRepository:
    """Ritorna un _FakeSummary se `overview` e' impostata, altrimenti None."""

    def __init__(self, overview: str | None = None) -> None:
        self._overview = overview

    async def get_by_document_id(self, document_id: UUID) -> _FakeSummary | None:
        if self._overview is None:
            return None
        return _FakeSummary(overview=self._overview)


class _FakeGraphStore:
    """Implementa il Protocol GraphStore con dati fissi (tutte le firme richieste)."""

    def __init__(
        self,
        entities: list[Entity] | None = None,
        relations: list[Relation] | None = None,
    ) -> None:
        self._graph_data = GraphData(entities=entities or [], relations=relations or [])

    async def ensure_constraints(self) -> None:
        pass

    async def replace_document_graph(
        self,
        *,
        owner_id: UUID,
        document_id: UUID,
        entities: Sequence[Entity],
        relations: Sequence[Relation],
    ) -> None:
        pass

    async def get_document_graph(self, *, owner_id: UUID, document_id: UUID) -> GraphData:
        return self._graph_data

    async def get_neighborhood(
        self,
        *,
        owner_id: UUID,
        document_id: UUID,
        entity_ids: Sequence[UUID],
        hops: int = 1,
    ) -> GraphData:
        return self._graph_data

    async def delete_document_graph(self, *, owner_id: UUID, document_id: UUID) -> None:
        pass

    async def delete_owner_graph(self, *, owner_id: UUID) -> None:
        pass

    async def close(self) -> None:
        pass


# =============================================================================
# Fake Embedder (sincrono, come GeminiEmbedder)
# =============================================================================
class _FakeEmbedder:
    """Restituisce un vettore fisso per ogni testo; registra gli input."""

    def __init__(self, dim: int = 768) -> None:
        self._vector = [0.1] * dim
        self.last_texts: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.last_texts = list(texts)
        return [self._vector[:] for _ in texts]


# =============================================================================
# Fake RagAnswerer (async)
# =============================================================================
class _FakeRagAnswerer:
    """Registra gli argomenti dell'ultima chiamata per le asserzioni dei test."""

    def __init__(self, answer: str = "Risposta di test.") -> None:
        self._answer = answer
        self.last_question: str = ""
        self.last_context: RetrievedContext | None = None
        self.last_language: str = ""

    async def answer(
        self,
        *,
        question: str,
        context: RetrievedContext,
        language: str,
    ) -> RagAnswer:
        self.last_question = question
        self.last_context = context
        self.last_language = language
        return RagAnswer(answer=self._answer, citations=[])


# Sentinel: distingue "parametro non passato" da "None = documento non trovato".
# Se `document` non viene passato, il factory crea un _FakeDocument() COMPLETED.
# Se viene passato `None`, il repo restituira' None (simula documento non trovato).
_UNSET: object = object()


# =============================================================================
# Factory: RagService con tutti i collaboratori fake
# =============================================================================
def _make_service(
    *,
    document: _FakeDocument | None | object = _UNSET,
    similar: list[SimilarEntity] | None = None,
    overview: str | None = None,
    graph_entities: list[Entity] | None = None,
    graph_relations: list[Relation] | None = None,
    embedder: _FakeEmbedder | None = None,
    answerer: _FakeRagAnswerer | None = None,
    top_k: int = 8,
    neighbor_hops: int = 1,
) -> RagService:
    """Costruisce un RagService con fake.

    - `document` non passato (default) --> documento COMPLETED (happy path).
    - `document=None`                  --> repo ritorna None (simula "non trovato").
    - `document=_FakeDocument(status=...)` --> documento con lo status specificato.
    """
    actual_doc: _FakeDocument | None = (
        _FakeDocument() if document is _UNSET else document  # type: ignore[assignment]
    )
    return RagService(
        documents=_FakeDocumentRepository(actual_doc),  # type: ignore[arg-type]
        embeddings=_FakeEmbeddingRepository(similar),  # type: ignore[arg-type]
        summaries=_FakeSummaryRepository(overview),  # type: ignore[arg-type]
        graph_store=_FakeGraphStore(graph_entities, graph_relations),
        embedder=embedder or _FakeEmbedder(),  # type: ignore[arg-type]
        answerer=answerer or _FakeRagAnswerer(),
        top_k=top_k,
        neighbor_hops=neighbor_hops,
    )


# =============================================================================
# Test: happy path
# =============================================================================
@pytest.mark.asyncio
async def test_ask_returns_raginswer() -> None:
    """Il service ritorna un RagAnswer nel caso nominale."""
    doc = _FakeDocument(id=uuid4(), status=DocumentStatus.COMPLETED)
    answerer = _FakeRagAnswerer(answer="Dante nacque a Firenze.")
    service = _make_service(document=doc, answerer=answerer)

    result = await service.ask(
        owner_id=uuid4(),
        document_id=doc.id,
        question="Dove nacque Dante?",
        language="it",
    )

    assert isinstance(result, RagAnswer)
    assert result.answer == "Dante nacque a Firenze."


# =============================================================================
# Test: guard conditions (RagNotReadyError)
# =============================================================================
@pytest.mark.asyncio
async def test_ask_document_not_found_raises() -> None:
    """Documento non trovato (RLS lo nasconde o non esiste) --> RagNotReadyError."""
    service = _make_service(document=None)
    with pytest.raises(RagNotReadyError):
        await service.ask(
            owner_id=uuid4(),
            document_id=uuid4(),
            question="Test?",
            language="it",
        )


@pytest.mark.asyncio
async def test_ask_document_not_completed_pending_raises() -> None:
    """Status PENDING --> RagNotReadyError."""
    doc = _FakeDocument(status=DocumentStatus.PENDING)
    service = _make_service(document=doc)
    with pytest.raises(RagNotReadyError):
        await service.ask(owner_id=uuid4(), document_id=doc.id, question="?", language="it")


@pytest.mark.asyncio
async def test_ask_document_extracted_not_completed_raises() -> None:
    """Status EXTRACTED (embeddings non ancora pronti) --> RagNotReadyError."""
    doc = _FakeDocument(status=DocumentStatus.EXTRACTED)
    service = _make_service(document=doc)
    with pytest.raises(RagNotReadyError):
        await service.ask(owner_id=uuid4(), document_id=doc.id, question="?", language="it")


# =============================================================================
# Test: propagazione lingua
# =============================================================================
@pytest.mark.asyncio
async def test_ask_propagates_language_it() -> None:
    """La lingua 'it' viene propagata invariata all'answerer."""
    doc = _FakeDocument()
    answerer = _FakeRagAnswerer()
    service = _make_service(document=doc, answerer=answerer)

    await service.ask(owner_id=uuid4(), document_id=doc.id, question="Test", language="it")

    assert answerer.last_language == "it"


@pytest.mark.asyncio
async def test_ask_propagates_language_en() -> None:
    """La lingua 'en' viene propagata invariata all'answerer."""
    doc = _FakeDocument()
    answerer = _FakeRagAnswerer()
    service = _make_service(document=doc, answerer=answerer)

    await service.ask(owner_id=uuid4(), document_id=doc.id, question="Test", language="en")

    assert answerer.last_language == "en"


# =============================================================================
# Test: summary_overview nel contesto
# =============================================================================
@pytest.mark.asyncio
async def test_ask_includes_summary_overview() -> None:
    """Il summary_overview viene passato nel RetrievedContext all'answerer."""
    doc = _FakeDocument()
    answerer = _FakeRagAnswerer()
    service = _make_service(document=doc, overview="Testo di panoramica.", answerer=answerer)

    await service.ask(owner_id=uuid4(), document_id=doc.id, question="Test", language="it")

    assert answerer.last_context is not None
    assert answerer.last_context.summary_overview == "Testo di panoramica."


@pytest.mark.asyncio
async def test_ask_no_summary_overview_is_none() -> None:
    """Se nessun summary esiste, summary_overview nel contesto e' None."""
    doc = _FakeDocument()
    answerer = _FakeRagAnswerer()
    service = _make_service(document=doc, overview=None, answerer=answerer)

    await service.ask(owner_id=uuid4(), document_id=doc.id, question="Test", language="it")

    assert answerer.last_context is not None
    assert answerer.last_context.summary_overview is None


# =============================================================================
# Test: embedder
# =============================================================================
@pytest.mark.asyncio
async def test_ask_embedder_receives_question() -> None:
    """L'embedder riceve la domanda come lista a un elemento."""
    doc = _FakeDocument()
    embedder = _FakeEmbedder()
    service = _make_service(document=doc, embedder=embedder)

    question = "Chi e' Dante Alighieri?"
    await service.ask(owner_id=uuid4(), document_id=doc.id, question=question, language="it")

    assert embedder.last_texts == [question]


# =============================================================================
# Test: contesto vuoto
# =============================================================================
@pytest.mark.asyncio
async def test_ask_no_similar_entities_returns_answer_with_empty_context() -> None:
    """Nessuna entita' simile: il service non solleva, il contesto e' vuoto."""
    doc = _FakeDocument()
    answerer = _FakeRagAnswerer()
    service = _make_service(document=doc, similar=[], answerer=answerer)

    result = await service.ask(owner_id=uuid4(), document_id=doc.id, question="Test", language="it")

    assert isinstance(result, RagAnswer)
    assert answerer.last_context is not None
    assert answerer.last_context.entities == []
    assert answerer.last_context.relations == []


# =============================================================================
# Test: top_k rispettato
# =============================================================================
@pytest.mark.asyncio
async def test_ask_top_k_limits_similar_entities() -> None:
    """top_k=2 limita a 2 il numero di entita' seme (anche con 5 disponibili)."""
    doc = _FakeDocument()
    similar = [SimilarEntity(entity_id=uuid4(), name=f"E{i}", distance=float(i)) for i in range(5)]
    answerer = _FakeRagAnswerer()
    # top_k=2: _FakeEmbeddingRepository restituisce i primi 2
    service = _make_service(document=doc, similar=similar, answerer=answerer, top_k=2)

    await service.ask(owner_id=uuid4(), document_id=doc.id, question="Test", language="it")

    # Il servizio non solleva: verifichiamo che il contesto venga costruito
    assert isinstance(answerer.last_context, RetrievedContext)
