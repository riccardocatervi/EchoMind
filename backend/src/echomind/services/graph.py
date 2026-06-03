"""GraphService -- lettura del grafo di conoscenza (output di KnowledgeExtraction).

Il grafo vive su Neo4j, che NON ha Row-Level Security: l'isolamento e' applicativo.
Il service applica una DOPPIA barriera:
1. verifica che il documento sia dell'utente via DocumentRepository (sessione RLS)
   --> se non lo e', 404 (indistinguibile da "grafo non ancora pronto");
2. interroga il graph store filtrando per `owner_id` (preso dal claim JWT).

Solo lettura: il grafo lo scrive il worker.
"""

from __future__ import annotations

from uuid import UUID

from echomind.db.repositories import DocumentRepository
from echomind.services.graph_store import GraphData, GraphStore


# -----------------------------------------------------------------------------
# Errori di dominio (mappati a HTTP dagli exception handler in main.py)
# -----------------------------------------------------------------------------
class GraphError(Exception):
    """Base per gli errori del dominio Graph."""


class GraphNotReadyError(GraphError):
    """Nessun grafo per quel documento: non ancora estratto, vuoto, o RLS nasconde
    il documento (di un altro utente)."""


# -----------------------------------------------------------------------------
# Service
# -----------------------------------------------------------------------------
class GraphService:
    """Lettura del grafo di un documento (RLS su Postgres + filtro owner su Neo4j)."""

    def __init__(self, *, documents: DocumentRepository, graph_store: GraphStore) -> None:
        self._documents = documents
        self._graph_store = graph_store

    async def get_for_document(self, *, owner_id: UUID, document_id: UUID) -> GraphData:
        """Ritorna il grafo di un documento dell'utente.

        Raises:
            GraphNotReadyError: documento inesistente/non tuo (RLS), oppure grafo
                non ancora costruito (vuoto). --> 404, indistinguibili by design.
            GraphStoreError: Neo4j non raggiungibile. --> 503.
        """
        document = await self._documents.get_by_id(document_id)  # RLS: None se non tuo
        if document is None:
            raise GraphNotReadyError(f"Graph for document {document_id} not available")

        graph = await self._graph_store.get_document_graph(
            owner_id=owner_id, document_id=document_id
        )
        if not graph.entities:
            raise GraphNotReadyError(f"Graph for document {document_id} not available")
        return graph
