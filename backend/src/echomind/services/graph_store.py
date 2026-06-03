"""Neo4j graph store: persistenza e lettura del grafo di conoscenza (M5).

Neo4j non ha Row-Level Security: la multi-tenancy e' APPLICATIVA. Ogni nodo e ogni
arco portano `owner_id` + `document_id`, e OGNI query filtra per owner. Il chiamante
passa sempre l'owner (dal claim JWT lato API, dal documento lato worker).

Il driver neo4j e' usato in modalita' SINCRONA, incapsulato dietro metodi async che
delegano a `asyncio.to_thread` (come `B2StorageService` con boto3): il driver sync e'
thread-based, quindi nessuna affinita' loop<->driver tra i task del worker.

Grafo per-documento: re-estrarre SOSTITUISCE il sottografo (DETACH DELETE + create),
mantenendo l'idempotenza. Relazione generica `:RELATES` con il tipo come property -->
niente APOC per i tipi dinamici.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from neo4j import Driver, GraphDatabase, ManagedTransaction
from neo4j.exceptions import DriverError, Neo4jError, TransientError

from echomind.core.config import Settings, require_secret
from echomind.extraction.schema import Entity, Relation


class GraphStoreError(Exception):
    """Errore di accesso al grafo. `retryable` guida il worker (retry vs DLQ) e
    l'API (--> 503 se il grafo non e' raggiungibile)."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class GraphData:
    """Grafo di un documento letto da Neo4j (dominio, non schema HTTP)."""

    entities: list[Entity]
    relations: list[Relation]


class GraphStore(Protocol):
    """Interfaccia del graph store: la usano worker (write) e API (read).

    Tutti i metodi prendono `owner_id`: l'isolamento per-utente e' esplicito a
    ogni chiamata (Neo4j non ha RLS).
    """

    async def ensure_constraints(self) -> None: ...

    async def replace_document_graph(
        self,
        *,
        owner_id: UUID,
        document_id: UUID,
        entities: Sequence[Entity],
        relations: Sequence[Relation],
    ) -> None: ...

    async def get_document_graph(self, *, owner_id: UUID, document_id: UUID) -> GraphData: ...

    async def delete_document_graph(self, *, owner_id: UUID, document_id: UUID) -> None: ...


def _to_graph_store_error(exc: Exception) -> GraphStoreError:
    if isinstance(exc, TransientError):
        return GraphStoreError(f"Neo4j errore transiente: {exc}", retryable=True)
    if isinstance(exc, DriverError):  # connessione/sessione: ritentabile
        return GraphStoreError(f"Neo4j non raggiungibile: {exc}", retryable=True)
    if isinstance(exc, Neo4jError):  # errore server applicativo: permanente
        return GraphStoreError(f"Neo4j ha rifiutato la query: {exc}", retryable=False)
    return GraphStoreError(f"Neo4j errore inatteso: {exc}", retryable=True)


_CREATE_CONSTRAINT = (
    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE"
)
_DELETE_SUBGRAPH = (
    "MATCH (e:Entity {owner_id: $owner_id, document_id: $document_id}) DETACH DELETE e"
)
_CREATE_NODES = """
UNWIND $nodes AS n
CREATE (e:Entity {
    id: n.id, owner_id: $owner_id, document_id: $document_id,
    name: n.name, type: n.type, description: n.description, community: n.community
})
"""
_CREATE_EDGES = """
UNWIND $edges AS edge
MATCH (s:Entity {id: edge.source, owner_id: $owner_id, document_id: $document_id})
MATCH (t:Entity {id: edge.target, owner_id: $owner_id, document_id: $document_id})
CREATE (s)-[:RELATES {
    type: edge.type, description: edge.description,
    owner_id: $owner_id, document_id: $document_id
}]->(t)
"""
_READ_NODES = """
MATCH (e:Entity {owner_id: $owner_id, document_id: $document_id})
RETURN e.id AS id, e.name AS name, e.type AS type,
       e.description AS description, e.community AS community
"""
_READ_EDGES = """
MATCH (s:Entity {owner_id: $owner_id, document_id: $document_id})
      -[r:RELATES]->
      (t:Entity {owner_id: $owner_id, document_id: $document_id})
RETURN s.id AS source, t.id AS target, r.type AS type, r.description AS description
"""


class Neo4jGraphStore:
    """`GraphStore` su Neo4j (driver sync + asyncio.to_thread)."""

    def __init__(self, *, driver: Driver) -> None:
        self._driver = driver

    @classmethod
    def from_settings(cls, settings: Settings) -> Neo4jGraphStore:
        """Costruisce lo store dai Settings. Solleva se Neo4j non e' configurato."""
        if settings.neo4j_uri is None:
            raise GraphStoreError("NEO4J_URI mancante: configura Neo4j", retryable=False)
        password = require_secret(
            settings.neo4j_password, env_name="NEO4J_PASSWORD", hint="Neo4j richiede una password."
        )
        driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, password))
        return cls(driver=driver)

    async def close(self) -> None:
        await asyncio.to_thread(self._driver.close)

    # -------------------------------------------------------------------------
    # Schema
    # -------------------------------------------------------------------------
    async def ensure_constraints(self) -> None:
        await asyncio.to_thread(self._ensure_constraints_sync)

    def _ensure_constraints_sync(self) -> None:
        try:
            with self._driver.session() as session:
                session.run(_CREATE_CONSTRAINT)
        except Exception as exc:
            raise _to_graph_store_error(exc) from exc

    # -------------------------------------------------------------------------
    # Write (worker)
    # -------------------------------------------------------------------------
    async def replace_document_graph(
        self,
        *,
        owner_id: UUID,
        document_id: UUID,
        entities: Sequence[Entity],
        relations: Sequence[Relation],
    ) -> None:
        nodes = [
            {
                "id": str(entity.id),
                "name": entity.name,
                "type": entity.type,
                "description": entity.description,
                "community": entity.community,
            }
            for entity in entities
        ]
        edges = [
            {
                "source": str(relation.source_id),
                "target": str(relation.target_id),
                "type": relation.type,
                "description": relation.description,
            }
            for relation in relations
        ]
        await asyncio.to_thread(self._replace_sync, str(owner_id), str(document_id), nodes, edges)

    def _replace_sync(
        self,
        owner_id: str,
        document_id: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> None:
        try:
            with self._driver.session() as session:
                session.execute_write(self._replace_tx, owner_id, document_id, nodes, edges)
        except Exception as exc:
            raise _to_graph_store_error(exc) from exc

    @staticmethod
    def _replace_tx(
        tx: ManagedTransaction,
        owner_id: str,
        document_id: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> None:
        tx.run(_DELETE_SUBGRAPH, owner_id=owner_id, document_id=document_id)
        if nodes:
            tx.run(_CREATE_NODES, nodes=nodes, owner_id=owner_id, document_id=document_id)
        if edges:
            tx.run(_CREATE_EDGES, edges=edges, owner_id=owner_id, document_id=document_id)

    # -------------------------------------------------------------------------
    # Read (API)
    # -------------------------------------------------------------------------
    async def get_document_graph(self, *, owner_id: UUID, document_id: UUID) -> GraphData:
        return await asyncio.to_thread(self._get_sync, str(owner_id), str(document_id))

    def _get_sync(self, owner_id: str, document_id: str) -> GraphData:
        try:
            with self._driver.session() as session:
                node_rows = session.execute_read(self._read_nodes_tx, owner_id, document_id)
                edge_rows = session.execute_read(self._read_edges_tx, owner_id, document_id)
        except Exception as exc:
            raise _to_graph_store_error(exc) from exc
        entities = [
            Entity(
                id=UUID(row["id"]),
                name=row["name"],
                type=row["type"],
                description=row["description"] or "",
                community=row["community"],
            )
            for row in node_rows
        ]
        relations = [
            Relation(
                source_id=UUID(row["source"]),
                target_id=UUID(row["target"]),
                type=row["type"],
                description=row["description"] or "",
            )
            for row in edge_rows
        ]
        return GraphData(entities=entities, relations=relations)

    @staticmethod
    def _read_nodes_tx(
        tx: ManagedTransaction, owner_id: str, document_id: str
    ) -> list[dict[str, Any]]:
        result = tx.run(_READ_NODES, owner_id=owner_id, document_id=document_id)
        return [record.data() for record in result]

    @staticmethod
    def _read_edges_tx(
        tx: ManagedTransaction, owner_id: str, document_id: str
    ) -> list[dict[str, Any]]:
        result = tx.run(_READ_EDGES, owner_id=owner_id, document_id=document_id)
        return [record.data() for record in result]

    # -------------------------------------------------------------------------
    # Delete (cancellazione documento, consistenza cross-store)
    # -------------------------------------------------------------------------
    async def delete_document_graph(self, *, owner_id: UUID, document_id: UUID) -> None:
        await asyncio.to_thread(self._delete_sync, str(owner_id), str(document_id))

    def _delete_sync(self, owner_id: str, document_id: str) -> None:
        try:
            with self._driver.session() as session:
                session.execute_write(self._delete_tx, owner_id, document_id)
        except Exception as exc:
            raise _to_graph_store_error(exc) from exc

    @staticmethod
    def _delete_tx(tx: ManagedTransaction, owner_id: str, document_id: str) -> None:
        tx.run(_DELETE_SUBGRAPH, owner_id=owner_id, document_id=document_id)
