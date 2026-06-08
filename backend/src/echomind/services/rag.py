"""RagService -- orchestrazione del Q&A per-documento (GraphRAG, M8).

Flusso `ask`:
  1. Verifica ownership del documento + status COMPLETED (doppia barriera come
     GraphService: RLS Postgres nasconde le righe altrui, piu' check esplicito
     dello status).
  2. Embedding della domanda tramite GeminiEmbedder (sincrono in asyncio.to_thread,
     stesso pattern del worker).
  3. Retrieval vettoriale: `search_similar` (EmbeddingRepository, pgvector,
     distanza coseno, top-K scoped per documento).
  4. Vicinato semantico: `get_neighborhood` (GraphStore, Neo4j, hops configurabili).
     Se nessuna entita' simile: contesto vuoto, il modello dichiarera' di non avere
     informazioni (anti-allucinazione garantita dal system prompt di `rag/prompt.py`).
  5. Panoramica del documento (SummaryRepository, best-effort: assenza non blocca).
  6. Risposta: `RagAnswerer.answer(language=...)` --> RagAnswer con citazioni.

Lingua della risposta: viene dall'header Accept-Language della HTTP request
(clampata a it/en dal chiamante); e' la lingua dell'INTERFACCIA, non del documento.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from echomind.db.models.document import DocumentStatus
from echomind.db.repositories.document import DocumentRepository
from echomind.db.repositories.embedding import EmbeddingRepository
from echomind.db.repositories.summary import SummaryRepository
from echomind.extraction.gemini import GeminiEmbedder
from echomind.rag.answerer import RagAnswerer
from echomind.rag.schema import RagAnswer, RetrievedContext
from echomind.services.graph_store import GraphData, GraphStore


# =============================================================================
# Errori di dominio (mappati a HTTP dagli exception handler in main.py)
# =============================================================================
class RagError(Exception):
    """Base per gli errori del dominio RAG."""


class RagNotReadyError(RagError):
    """Documento inesistente/non tuo (RLS) oppure non ancora completamente elaborato.

    Indistinguibili by design (sicurezza): non rivela se il documento esiste
    ma appartiene a un altro utente. --> 404.
    """


class RagUnavailableError(RagError):
    """RAG non configurato (GEMINI_API_KEY assente o componenti non inizializzati).

    --> 503 Service Unavailable: il client puo' riprovare quando la configurazione
    e' corretta (o quando il servizio torna disponibile).
    """


# =============================================================================
# Service
# =============================================================================
class RagService:
    """Orchestrazione del Q&A per-documento (GraphRAG).

    Dipendenze iniettate dal dep `get_rag_service` in `api/deps.py`:
    - `documents`    : DocumentRepository RLS-bound (verifica ownership + status).
    - `embeddings`   : EmbeddingRepository RLS-bound (retrieval vettoriale pgvector).
    - `summaries`    : SummaryRepository RLS-bound (arricchimento panoramica).
    - `graph_store`  : GraphStore Neo4j (vicinato semantico delle entita' seme).
    - `embedder`     : GeminiEmbedder (embedding sincrono della domanda, in thread).
    - `answerer`     : RagAnswerer Protocol (LLM structured output: RagAnswer).
    - `top_k`        : quante entita' seme recuperare con pgvector.
    - `neighbor_hops`: profondita' del vicinato Neo4j (1 = vicini diretti).
    """

    def __init__(
        self,
        *,
        documents: DocumentRepository,
        embeddings: EmbeddingRepository,
        summaries: SummaryRepository,
        graph_store: GraphStore,
        embedder: GeminiEmbedder,
        answerer: RagAnswerer,
        top_k: int,
        neighbor_hops: int,
    ) -> None:
        self._documents = documents
        self._embeddings = embeddings
        self._summaries = summaries
        self._graph_store = graph_store
        self._embedder = embedder
        self._answerer = answerer
        self._top_k = top_k
        self._neighbor_hops = neighbor_hops

    async def ask(
        self,
        *,
        owner_id: UUID,
        document_id: UUID,
        question: str,
        language: str,
    ) -> RagAnswer:
        """Risponde a una domanda su un documento tramite GraphRAG.

        Args:
            owner_id    : UUID dell'utente autenticato (da JWT claim "sub").
            document_id : UUID del documento su cui fare Q&A.
            question    : domanda in linguaggio naturale.
            language    : codice lingua ISO 639-1 (it/en) della risposta.

        Returns:
            `RagAnswer` con risposta testuale e lista di `Citation`.

        Raises:
            RagNotReadyError  : documento non trovato, non tuo (RLS), o non COMPLETED.
            GraphStoreError   : Neo4j non raggiungibile.
            LLMError          : errore LLM (embedding o risposta).
            EmbeddingError    : errore calcolo embedding.
        """
        # ------------------------------------------------------------------ #
        # 1. Verifica ownership + status (doppia barriera)                    #
        # ------------------------------------------------------------------ #
        document = await self._documents.get_by_id(document_id)
        if document is None or document.status != DocumentStatus.COMPLETED:
            raise RagNotReadyError(
                f"Document {document_id} not available for Q&A "
                "(not found, not yours, or not yet completed)."
            )

        # ------------------------------------------------------------------ #
        # 2. Embedding della domanda (sincrono in thread)                     #
        # ------------------------------------------------------------------ #
        vectors = await asyncio.to_thread(self._embedder.embed, [question])
        query_vector: list[float] = vectors[0]

        # ------------------------------------------------------------------ #
        # 3. Retrieval vettoriale: top-K entita' piu' vicine (pgvector)       #
        # ------------------------------------------------------------------ #
        similar = await self._embeddings.search_similar(
            document_id=document_id,
            owner_id=owner_id,
            query_vector=query_vector,
            k=self._top_k,
        )
        entity_ids = [s.entity_id for s in similar]

        # ------------------------------------------------------------------ #
        # 4. Vicinato semantico (Neo4j): seme + vicini + archi tra loro       #
        # ------------------------------------------------------------------ #
        if entity_ids:
            graph_data: GraphData = await self._graph_store.get_neighborhood(
                owner_id=owner_id,
                document_id=document_id,
                entity_ids=entity_ids,
                hops=self._neighbor_hops,
            )
        else:
            graph_data = GraphData(entities=[], relations=[])

        # ------------------------------------------------------------------ #
        # 5. Panoramica del documento (best-effort, non blocca)               #
        # ------------------------------------------------------------------ #
        summary_overview: str | None = None
        summary = await self._summaries.get_by_document_id(document_id)
        if summary is not None:
            summary_overview = summary.overview

        # ------------------------------------------------------------------ #
        # 6. Assembla contesto + risposta                                     #
        # ------------------------------------------------------------------ #
        context = RetrievedContext(
            entities=graph_data.entities,
            relations=graph_data.relations,
            summary_overview=summary_overview,
        )
        return await self._answerer.answer(
            question=question,
            context=context,
            language=language,
        )
