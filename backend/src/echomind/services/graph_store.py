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

    async def get_neighborhood(
        self,
        *,
        owner_id: UUID,
        document_id: UUID,
        entity_ids: Sequence[UUID],
        hops: int = 1,
    ) -> GraphData:
        """Restituisce i nodi seme + il loro vicinato fino a `hops` passi.

        Usato dal RAG (M8): i nodi recuperati dal retrieval vettoriale
        (entity_ids) diventano i semi da cui si espande il grafo locale.
        `hops=1` include i vicini diretti; hops>1 allarga la finestra.
        Il risultato e' sempre filtrato per owner + document (multi-tenancy).
        """
        ...

    async def delete_document_graph(self, *, owner_id: UUID, document_id: UUID) -> None: ...

    async def delete_owner_graph(self, *, owner_id: UUID) -> None:
        """Rimuove TUTTI i nodi ed archi di un utente (usato al delete account)."""
        ...


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
# Elimina tutti i nodi (e di conseguenza tutti gli archi) di un owner.
# Usato al delete account: rimuove l'intero sottografo dell'utente in un solo round-trip.
_DELETE_OWNER_GRAPH = "MATCH (e:Entity {owner_id: $owner_id}) DETACH DELETE e"
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


# Vicinato RAG (M8): nodi seme + vicini a `hops` passi (direzione libera) +
# tutti gli archi tra i nodi del vicinato. Il numero di hops e' iniettato via
# .format() al momento della chiamata (e' un intero validato dalle Settings,
# non un input utente). Il pattern {{ }} produce { } letterali nell'f-string.
def _neighborhood_nodes_cypher(hops: int) -> str:
    """Nodi seme + vicini fino a `hops` passi (UNION deduplica automaticamente)."""
    rel = f"[:RELATES*1..{hops}]"
    return (
        "MATCH (seed:Entity {owner_id: $owner_id, document_id: $document_id})\n"
        "WHERE seed.id IN $entity_ids\n"
        "RETURN seed.id AS id, seed.name AS name, seed.type AS type,\n"
        "       seed.description AS description, seed.community AS community\n"
        "UNION\n"
        "MATCH (seed:Entity {owner_id: $owner_id, document_id: $document_id})\n"
        "WHERE seed.id IN $entity_ids\n"
        f"MATCH (seed)-{rel}-(nbr:Entity {{owner_id: $owner_id, document_id: $document_id}})\n"
        "RETURN DISTINCT nbr.id AS id, nbr.name AS name, nbr.type AS type,\n"
        "       nbr.description AS description, nbr.community AS community"
    )


def _neighborhood_edges_cypher(hops: int) -> str:
    """Archi tra i nodi del vicinato (semi + vicini fino a `hops` passi)."""
    rel = f"[:RELATES*1..{hops}]"
    return (
        "MATCH (seed:Entity {owner_id: $owner_id, document_id: $document_id})\n"
        "WHERE seed.id IN $entity_ids\n"
        f"OPTIONAL MATCH (seed)-{rel}-(nbr:Entity {{owner_id: $owner_id, document_id: $document_id}})\n"
        "WITH collect(DISTINCT seed.id) + collect(DISTINCT nbr.id) AS all_ids\n"
        "MATCH (s:Entity {owner_id: $owner_id, document_id: $document_id})\n"
        "      -[r:RELATES]->\n"
        "      (t:Entity {owner_id: $owner_id, document_id: $document_id})\n"
        "WHERE s.id IN all_ids AND t.id IN all_ids\n"
        "RETURN DISTINCT s.id AS source, t.id AS target,\n"
        "       r.type AS type, r.description AS description"
    )


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
    # Neighborhood RAG (M8)
    # -------------------------------------------------------------------------
    async def get_neighborhood(
        self,
        *,
        owner_id: UUID,
        document_id: UUID,
        entity_ids: Sequence[UUID],
        hops: int = 1,
    ) -> GraphData:
        """Nodi seme + vicinato `hops`-hop + archi del sottografo locale."""
        return await asyncio.to_thread(
            self._get_neighborhood_sync,
            str(owner_id),
            str(document_id),
            [str(eid) for eid in entity_ids],
            hops,
        )

    def _get_neighborhood_sync(
        self,
        owner_id: str,
        document_id: str,
        entity_ids: list[str],
        hops: int,
    ) -> GraphData:
        try:
            with self._driver.session() as session:
                node_rows = session.execute_read(
                    self._neighborhood_nodes_tx,
                    owner_id,
                    document_id,
                    entity_ids,
                    hops,
                )
                edge_rows = session.execute_read(
                    self._neighborhood_edges_tx,
                    owner_id,
                    document_id,
                    entity_ids,
                    hops,
                )
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
    def _neighborhood_nodes_tx(
        tx: ManagedTransaction,
        owner_id: str,
        document_id: str,
        entity_ids: list[str],
        hops: int,
    ) -> list[dict[str, Any]]:
        result = tx.run(
            _neighborhood_nodes_cypher(hops),
            owner_id=owner_id,
            document_id=document_id,
            entity_ids=entity_ids,
        )
        return [record.data() for record in result]

    @staticmethod
    def _neighborhood_edges_tx(
        tx: ManagedTransaction,
        owner_id: str,
        document_id: str,
        entity_ids: list[str],
        hops: int,
    ) -> list[dict[str, Any]]:
        result = tx.run(
            _neighborhood_edges_cypher(hops),
            owner_id=owner_id,
            document_id=document_id,
            entity_ids=entity_ids,
        )
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

    # -------------------------------------------------------------------------
    # Delete owner (cancellazione account: rimuove TUTTI i nodi dell'utente)
    # -------------------------------------------------------------------------
    async def delete_owner_graph(self, *, owner_id: UUID) -> None:
        """Rimuove tutti i nodi ed archi del proprietario in un unico round-trip."""
        await asyncio.to_thread(self._delete_owner_sync, str(owner_id))

    def _delete_owner_sync(self, owner_id: str) -> None:
        try:
            with self._driver.session() as session:
                session.execute_write(self._delete_owner_tx, owner_id)
        except Exception as exc:
            raise _to_graph_store_error(exc) from exc

    @staticmethod
    def _delete_owner_tx(tx: ManagedTransaction, owner_id: str) -> None:
        tx.run(_DELETE_OWNER_GRAPH, owner_id=owner_id)
