"""Pydantic schemas per il grafo di conoscenza (output di KnowledgeExtraction).

Il grafo vive su Neo4j; questi schemi sono la sua rappresentazione JSON esposta
dall'API su GET /documents/{id}/graph. Sola lettura: il grafo lo scrive il worker.

- `GraphNode` / `GraphEdge` --> nodi e archi
- `GraphRead`               --> il grafo completo di un documento + conteggi
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class GraphNode(BaseModel):
    """Un'entita' del grafo (nodo :Entity su Neo4j)."""

    id: UUID
    name: str
    type: str
    description: str | None = None
    community: int | None = None


class GraphEdge(BaseModel):
    """Una relazione tra due entita' (arco :RELATES su Neo4j)."""

    source: UUID
    target: UUID
    type: str
    description: str | None = None


class GraphRead(BaseModel):
    """Grafo di conoscenza di un documento, con i conteggi di sintesi."""

    document_id: UUID
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    node_count: int
    relationship_count: int
    community_count: int
