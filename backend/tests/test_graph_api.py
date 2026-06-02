"""Test integration di GET /api/v1/documents/{id}/graph.

Il grafo vive su Neo4j: nei test sostituiamo il `GraphStore` con un fake via
`dependency_overrides` (come moto per B2). La verifica di ownership del documento
e' REALE (RLS su Postgres): doppia barriera.

Copre: 200 (nodi/archi/conteggi), 404 documento altrui (RLS), 404 grafo vuoto/non
pronto, 503 graph store giu', 503 Neo4j non configurato, 401.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from echomind.api.deps import get_graph_store
from echomind.extraction.schema import Entity, Relation
from echomind.services.graph_store import GraphData, GraphStoreError

pytestmark = pytest.mark.asyncio


class _FakeGraphStore:
    def __init__(self, graph: GraphData | None = None, *, exc: Exception | None = None) -> None:
        self._graph = graph if graph is not None else GraphData(entities=[], relations=[])
        self._exc = exc

    async def ensure_constraints(self) -> None: ...

    async def replace_document_graph(self, **kwargs: Any) -> None: ...

    async def get_document_graph(self, *, owner_id: UUID, document_id: UUID) -> GraphData:
        if self._exc is not None:
            raise self._exc
        return self._graph

    async def delete_document_graph(self, **kwargs: Any) -> None: ...


async def _seed_document(session: AsyncSession, owner_id: UUID) -> UUID:
    """Crea profile + document per `owner_id`. Ritorna il document_id."""
    await session.execute(
        text(
            "INSERT INTO public.profiles (id, display_name) VALUES (:id, 'u') ON CONFLICT (id) DO NOTHING"
        ),
        {"id": str(owner_id)},
    )
    doc_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO public.documents (id, owner_id, filename, mime_type, size_bytes, storage_key) "
            "VALUES (:id, :owner, 'f.txt', 'text/plain', 100, :key)"
        ),
        {"id": str(doc_id), "owner": str(owner_id), "key": f"users/{owner_id}/{doc_id}"},
    )
    await session.commit()
    return doc_id


def _sample_graph() -> tuple[GraphData, UUID, UUID]:
    e1, e2 = uuid4(), uuid4()
    graph = GraphData(
        entities=[
            Entity(id=e1, name="Alpha", type="CONCEPT", description="d", community=0),
            Entity(id=e2, name="Beta", type="CONCEPT", description="", community=1),
        ],
        relations=[Relation(source_id=e1, target_id=e2, type="related_to", description="")],
    )
    return graph, e1, e2


async def test_returns_graph(
    app: Any,
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
) -> None:
    user_id = uuid4()
    await seed_auth_user(user_id)
    doc_id = await _seed_document(system_session, user_id)
    graph, e1, e2 = _sample_graph()
    app.dependency_overrides[get_graph_store] = lambda: _FakeGraphStore(graph)

    response = await client.get(f"/api/v1/documents/{doc_id}/graph", headers=auth_headers(user_id))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_id"] == str(doc_id)
    assert body["node_count"] == 2
    assert body["relationship_count"] == 1
    assert body["community_count"] == 2
    assert {n["name"] for n in body["nodes"]} == {"Alpha", "Beta"}
    assert body["edges"][0]["source"] == str(e1)
    assert body["edges"][0]["target"] == str(e2)


async def test_404_for_other_users_document(
    app: Any,
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
) -> None:
    """RLS: anche se il fake avrebbe un grafo, l'ownership check fallisce prima --> 404."""
    alice_id, bob_id = uuid4(), uuid4()
    await seed_auth_user(alice_id)
    await seed_auth_user(bob_id)
    bob_doc_id = await _seed_document(system_session, bob_id)
    graph, _, _ = _sample_graph()
    app.dependency_overrides[get_graph_store] = lambda: _FakeGraphStore(graph)

    response = await client.get(
        f"/api/v1/documents/{bob_doc_id}/graph", headers=auth_headers(alice_id)
    )
    assert response.status_code == 404


async def test_404_when_graph_empty(
    app: Any,
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
) -> None:
    user_id = uuid4()
    await seed_auth_user(user_id)
    doc_id = await _seed_document(system_session, user_id)
    app.dependency_overrides[get_graph_store] = lambda: _FakeGraphStore()  # vuoto

    response = await client.get(f"/api/v1/documents/{doc_id}/graph", headers=auth_headers(user_id))
    assert response.status_code == 404
    assert response.json()["code"] == "graph_not_found"


async def test_503_when_graph_store_unavailable(
    app: Any,
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
) -> None:
    user_id = uuid4()
    await seed_auth_user(user_id)
    doc_id = await _seed_document(system_session, user_id)
    app.dependency_overrides[get_graph_store] = lambda: _FakeGraphStore(
        exc=GraphStoreError("neo4j down")
    )

    response = await client.get(f"/api/v1/documents/{doc_id}/graph", headers=auth_headers(user_id))
    assert response.status_code == 503
    assert response.json()["code"] == "graph_unavailable"


async def test_503_when_graph_not_configured(
    client: httpx.AsyncClient,
    auth_headers: Callable[[UUID | None], dict[str, str]],
    seed_auth_user: Callable[[UUID], Awaitable[None]],
    system_session: AsyncSession,
) -> None:
    """Niente override --> app.state.graph_store e' None (Neo4j non configurato) --> 503."""
    user_id = uuid4()
    await seed_auth_user(user_id)
    doc_id = await _seed_document(system_session, user_id)

    response = await client.get(f"/api/v1/documents/{doc_id}/graph", headers=auth_headers(user_id))
    assert response.status_code == 503


async def test_requires_auth(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/v1/documents/{uuid4()}/graph")
    assert response.status_code == 401
