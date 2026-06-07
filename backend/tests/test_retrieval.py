"""Test delle primitive di retrieval (M8, CP5).

`search_similar` (pgvector, distanza coseno) e' testato contro Postgres reale,
seeding tramite raw SQL via `system_session` (superuser, bypassa RLS).

Il vicinato Neo4j (`get_neighborhood`) non viene testato contro Neo4j reale
(non disponibile in CI): si verifica solo la conformita' strutturale del
FakeGraphStore, cioe' che firma e tipo di ritorno siano corretti.

Vettori usati: 768 dim, versore sull'asse i (1.0 in posizione i, 0 altrove).
  - cosine_distance(e_i, e_i) = 0   (identico)
  - cosine_distance(e_i, e_j) = 1   (ortogonale, i != j)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from echomind.db.repositories.embedding import EmbeddingRepository, EmbeddingValue
from echomind.services.graph_store import GraphData

# =============================================================================
# Helpers vettori
# =============================================================================
DIM = 768


def _unit_vec(i: int) -> list[float]:
    """Versore 768-dim con 1.0 all'indice i (distanza coseno deterministica)."""
    v = [0.0] * DIM
    v[i] = 1.0
    return v


def _vec_to_pg(v: list[float]) -> str:
    """Converte una lista float nel formato letterale vector di pgvector."""
    return "[" + ",".join(str(x) for x in v) + "]"


# =============================================================================
# Fixture condivise (seed)
# =============================================================================
@pytest_asyncio.fixture
async def owner_with_doc(
    system_session: AsyncSession,
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> tuple[UUID, UUID]:
    """Crea un owner + un documento, ritorna (owner_id, doc_id)."""
    owner_id = uuid4()
    await seed_auth_user(owner_id)
    await system_session.execute(
        text("INSERT INTO public.profiles (id, display_name) VALUES (:id, 'u')"),
        {"id": str(owner_id)},
    )
    doc_id = uuid4()
    await system_session.execute(
        text(
            "INSERT INTO public.documents "
            "(id, owner_id, filename, mime_type, size_bytes, storage_key) "
            "VALUES (:id, :owner, 'f.txt', 'text/plain', 100, :key)"
        ),
        {"id": str(doc_id), "owner": str(owner_id), "key": f"users/{owner_id}/{doc_id}"},
    )
    await system_session.commit()
    return owner_id, doc_id


async def _insert_embedding(
    session: AsyncSession,
    *,
    doc_id: UUID,
    owner_id: UUID,
    entity_id: UUID,
    name: str,
    vec_index: int,
) -> None:
    """Inserisce una riga in entity_embeddings (raw SQL per bypassare RLS)."""
    await session.execute(
        text(
            "INSERT INTO public.entity_embeddings "
            "(id, document_id, owner_id, entity_id, name, embedding) "
            "VALUES (:id, :doc, :owner, :eid, :name, CAST(:emb AS vector))"
        ),
        {
            "id": str(uuid4()),
            "doc": str(doc_id),
            "owner": str(owner_id),
            "eid": str(entity_id),
            "name": name,
            "emb": _vec_to_pg(_unit_vec(vec_index)),
        },
    )


# =============================================================================
# Test search_similar
# =============================================================================
@pytest.mark.asyncio
async def test_search_similar_returns_ordered_by_distance(
    system_session: AsyncSession,
    owner_with_doc: tuple[UUID, UUID],
) -> None:
    """Le entita' restituite sono ordinate per distanza coseno crescente."""
    owner_id, doc_id = owner_with_doc
    e0, e1, e2 = uuid4(), uuid4(), uuid4()

    await _insert_embedding(
        system_session, doc_id=doc_id, owner_id=owner_id, entity_id=e0, name="E0", vec_index=0
    )
    await _insert_embedding(
        system_session, doc_id=doc_id, owner_id=owner_id, entity_id=e1, name="E1", vec_index=1
    )
    await _insert_embedding(
        system_session, doc_id=doc_id, owner_id=owner_id, entity_id=e2, name="E2", vec_index=2
    )
    await system_session.commit()

    repo = EmbeddingRepository(system_session)
    results = await repo.search_similar(
        document_id=doc_id,
        owner_id=owner_id,
        query_vector=_unit_vec(0),  # identico a E0
        k=3,
    )

    assert len(results) == 3
    # E0 e' la piu' vicina (distanza ~ 0), E1/E2 sono ortogonali (distanza ~ 1)
    assert results[0].entity_id == e0
    assert results[0].distance < 0.01  # distanza coseno 0 -> identici
    assert results[1].distance > 0.9
    assert results[2].distance > 0.9
    # Distanze non decrescenti
    for i in range(len(results) - 1):
        assert results[i].distance <= results[i + 1].distance


@pytest.mark.asyncio
async def test_search_similar_respects_k_limit(
    system_session: AsyncSession,
    owner_with_doc: tuple[UUID, UUID],
) -> None:
    """Il parametro k limita il numero di risultati restituiti."""
    owner_id, doc_id = owner_with_doc

    for idx in range(5):
        await _insert_embedding(
            system_session,
            doc_id=doc_id,
            owner_id=owner_id,
            entity_id=uuid4(),
            name=f"E{idx}",
            vec_index=idx,
        )
    await system_session.commit()

    repo = EmbeddingRepository(system_session)
    results = await repo.search_similar(
        document_id=doc_id,
        owner_id=owner_id,
        query_vector=_unit_vec(0),
        k=2,
    )

    assert len(results) == 2


@pytest.mark.asyncio
async def test_search_similar_scoped_by_document(
    system_session: AsyncSession,
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    """La query e' scoped per document_id: entita' di un altro doc non appaiono."""
    owner_id = uuid4()
    await seed_auth_user(owner_id)
    await system_session.execute(
        text("INSERT INTO public.profiles (id, display_name) VALUES (:id, 'u')"),
        {"id": str(owner_id)},
    )

    # Due documenti dello stesso owner
    doc_a, doc_b = uuid4(), uuid4()
    for doc_id in (doc_a, doc_b):
        await system_session.execute(
            text(
                "INSERT INTO public.documents "
                "(id, owner_id, filename, mime_type, size_bytes, storage_key) "
                "VALUES (:id, :owner, 'f.txt', 'text/plain', 100, :key)"
            ),
            {"id": str(doc_id), "owner": str(owner_id), "key": f"users/{owner_id}/{doc_id}"},
        )

    e_a, e_b = uuid4(), uuid4()
    await _insert_embedding(
        system_session, doc_id=doc_a, owner_id=owner_id, entity_id=e_a, name="EA", vec_index=0
    )
    await _insert_embedding(
        system_session, doc_id=doc_b, owner_id=owner_id, entity_id=e_b, name="EB", vec_index=0
    )
    await system_session.commit()

    repo = EmbeddingRepository(system_session)

    results_a = await repo.search_similar(
        document_id=doc_a,
        owner_id=owner_id,
        query_vector=_unit_vec(0),
        k=5,
    )
    assert len(results_a) == 1
    assert results_a[0].entity_id == e_a

    results_b = await repo.search_similar(
        document_id=doc_b,
        owner_id=owner_id,
        query_vector=_unit_vec(0),
        k=5,
    )
    assert len(results_b) == 1
    assert results_b[0].entity_id == e_b


@pytest.mark.asyncio
async def test_search_similar_defense_in_depth_owner_filter(
    system_session: AsyncSession,
    seed_auth_user: Callable[[UUID], Awaitable[None]],
) -> None:
    """Defense-in-depth: il filtro owner_id esclude le entita' di un altro utente
    anche in sessione di sistema (oltre alla policy RLS)."""
    owner_a, owner_b = uuid4(), uuid4()
    for uid in (owner_a, owner_b):
        await seed_auth_user(uid)
        await system_session.execute(
            text("INSERT INTO public.profiles (id, display_name) VALUES (:id, 'u')"),
            {"id": str(uid)},
        )

    # Stesso document_id per entrambi gli owner (caso boundary)
    shared_doc_id = uuid4()
    for owner_id in (owner_a, owner_b):
        await system_session.execute(
            text(
                "INSERT INTO public.documents "
                "(id, owner_id, filename, mime_type, size_bytes, storage_key) "
                "VALUES (:id, :owner, 'f.txt', 'text/plain', 100, :key)"
            ),
            {
                "id": str(uuid4()),
                "owner": str(owner_id),
                "key": f"users/{owner_id}/{shared_doc_id}",
            },
        )

    doc_a = uuid4()
    doc_b = uuid4()
    await system_session.execute(
        text(
            "INSERT INTO public.documents "
            "(id, owner_id, filename, mime_type, size_bytes, storage_key) "
            "VALUES (:id, :owner, 'f.txt', 'text/plain', 100, :key)"
        ),
        {"id": str(doc_a), "owner": str(owner_a), "key": f"users/{owner_a}/{doc_a}"},
    )
    await system_session.execute(
        text(
            "INSERT INTO public.documents "
            "(id, owner_id, filename, mime_type, size_bytes, storage_key) "
            "VALUES (:id, :owner, 'f.txt', 'text/plain', 100, :key)"
        ),
        {"id": str(doc_b), "owner": str(owner_b), "key": f"users/{owner_b}/{doc_b}"},
    )

    e_a, e_b = uuid4(), uuid4()
    await _insert_embedding(
        system_session, doc_id=doc_a, owner_id=owner_a, entity_id=e_a, name="EA", vec_index=0
    )
    await _insert_embedding(
        system_session, doc_id=doc_b, owner_id=owner_b, entity_id=e_b, name="EB", vec_index=0
    )
    await system_session.commit()

    repo = EmbeddingRepository(system_session)

    # owner_a vede solo la propria entita'
    results = await repo.search_similar(
        document_id=doc_a,
        owner_id=owner_a,
        query_vector=_unit_vec(0),
        k=10,
    )
    assert all(r.entity_id == e_a for r in results)

    # Nessun risultato per una combinazione (owner_a, doc_b) che non esiste
    results_cross = await repo.search_similar(
        document_id=doc_b,
        owner_id=owner_a,  # owner sbagliato per doc_b
        query_vector=_unit_vec(0),
        k=10,
    )
    assert results_cross == []


@pytest.mark.asyncio
async def test_search_similar_empty_when_no_embeddings(
    system_session: AsyncSession,
    owner_with_doc: tuple[UUID, UUID],
) -> None:
    """Ritorna lista vuota se il documento non ha ancora embeddings."""
    owner_id, doc_id = owner_with_doc

    repo = EmbeddingRepository(system_session)
    results = await repo.search_similar(
        document_id=doc_id,
        owner_id=owner_id,
        query_vector=_unit_vec(0),
        k=5,
    )
    assert results == []


# =============================================================================
# Test conformita' strutturale FakeGraphStore.get_neighborhood
# =============================================================================
class _LocalFakeGraphStore:
    """Fake minimo che implementa get_neighborhood: verifica conformita' al Protocol."""

    async def get_neighborhood(
        self,
        *,
        owner_id: UUID,
        document_id: UUID,
        entity_ids: Any,
        hops: int = 1,
    ) -> GraphData:
        return GraphData(entities=[], relations=[])


@pytest.mark.asyncio
async def test_fake_graph_store_get_neighborhood_returns_graph_data() -> None:
    """_FakeGraphStore.get_neighborhood rispetta il contratto del Protocol:
    ritorna sempre un GraphData (anche vuoto), senza sollevare eccezioni."""
    fake = _LocalFakeGraphStore()
    result = await fake.get_neighborhood(
        owner_id=uuid4(),
        document_id=uuid4(),
        entity_ids=[uuid4(), uuid4()],
        hops=1,
    )
    assert isinstance(result, GraphData)
    assert result.entities == []
    assert result.relations == []


@pytest.mark.asyncio
async def test_fake_graph_store_get_neighborhood_hops_ignored() -> None:
    """Il fake non lancia eccezioni con qualsiasi valore di hops."""
    fake = _LocalFakeGraphStore()
    for hops in (1, 2, 3):
        result = await fake.get_neighborhood(
            owner_id=uuid4(),
            document_id=uuid4(),
            entity_ids=[],
            hops=hops,
        )
        assert isinstance(result, GraphData)


# =============================================================================
# Test EmbeddingRepository.replace_for_document (round-trip)
# =============================================================================
@pytest.mark.asyncio
async def test_replace_for_document_replaces_old_embeddings(
    system_session: AsyncSession,
    owner_with_doc: tuple[UUID, UUID],
) -> None:
    """replace_for_document elimina le righe vecchie e inserisce le nuove."""
    owner_id, doc_id = owner_with_doc

    repo = EmbeddingRepository(system_session)
    e_old = uuid4()
    # Prima scrittura: 1 embedding
    await repo.replace_for_document(
        document_id=doc_id,
        owner_id=owner_id,
        values=[EmbeddingValue(entity_id=e_old, name="Vecchio", vector=_unit_vec(0))],
    )
    await system_session.commit()

    count_after_first = await repo.count_for_document(doc_id)
    assert count_after_first == 1

    e_new1, e_new2 = uuid4(), uuid4()
    # Replace: 2 embeddings nuovi, il vecchio sparisce
    await repo.replace_for_document(
        document_id=doc_id,
        owner_id=owner_id,
        values=[
            EmbeddingValue(entity_id=e_new1, name="Nuovo1", vector=_unit_vec(1)),
            EmbeddingValue(entity_id=e_new2, name="Nuovo2", vector=_unit_vec(2)),
        ],
    )
    await system_session.commit()

    count_after_replace = await repo.count_for_document(doc_id)
    assert count_after_replace == 2

    # Il vecchio entity_id non e' piu' cercabile
    results = await repo.search_similar(
        document_id=doc_id,
        owner_id=owner_id,
        query_vector=_unit_vec(0),  # vicino all'old (ora cancellato)
        k=10,
    )
    returned_ids = {r.entity_id for r in results}
    assert e_old not in returned_ids
    assert e_new1 in returned_ids or e_new2 in returned_ids
