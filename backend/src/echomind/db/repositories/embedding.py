"""Repository per gli embeddings delle entita' -- tabella `entity_embeddings`.

Scritto dal worker (sessione di sistema). Pattern di scrittura: **replace-by-document**
(delete di tutte le righe del documento + insert delle nuove). Le righe sono
immutabili e si rigenerano in blocco a ogni estrazione, quindi non serve un upsert
per-riga; il replace garantisce l'idempotenza della ri-estrazione.

Per il RAG (M8): `search_similar` esegue retrieval vettoriale via pgvector
(distanza coseno) scoped per document_id. La sessione puo' essere RLS-bound (API)
o di sistema (worker/test); in ogni caso si filtra esplicitamente per owner_id
(defense-in-depth oltre la policy RLS).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomind.db.models import EntityEmbedding


@dataclass(frozen=True, slots=True)
class SimilarEntity:
    """Un'entita' restituita dal retrieval vettoriale, con la sua distanza."""

    entity_id: UUID
    name: str
    distance: float


@dataclass(frozen=True, slots=True)
class EmbeddingValue:
    """Una riga di embedding da persistere (input del repository)."""

    entity_id: UUID
    name: str
    vector: list[float]


class EmbeddingRepository:
    """Accesso alla tabella `entity_embeddings`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_for_document(
        self,
        *,
        document_id: UUID,
        owner_id: UUID,
        values: Sequence[EmbeddingValue],
    ) -> int:
        """Sostituisce TUTTI gli embeddings di un documento (delete + insert).

        Idempotente: ri-estrarre lo stesso documento azzera e riscrive, senza
        accumulare duplicati. Ritorna il numero di righe inserite.
        """
        await self._session.execute(
            delete(EntityEmbedding).where(EntityEmbedding.document_id == document_id)
        )
        if values:
            self._session.add_all(
                [
                    EntityEmbedding(
                        document_id=document_id,
                        owner_id=owner_id,
                        entity_id=v.entity_id,
                        name=v.name,
                        embedding=v.vector,
                    )
                    for v in values
                ]
            )
        return len(values)

    async def count_for_document(self, document_id: UUID) -> int:
        """Numero di embeddings persistiti per un documento."""
        result = await self._session.execute(
            select(func.count())
            .select_from(EntityEmbedding)
            .where(EntityEmbedding.document_id == document_id)
        )
        return result.scalar_one()

    async def search_similar(
        self,
        *,
        document_id: UUID,
        owner_id: UUID,
        query_vector: list[float],
        k: int,
    ) -> list[SimilarEntity]:
        """Restituisce le `k` entita' piu' vicine al `query_vector` (distanza coseno).

        Scoped per document_id: il retrieval e' sempre per-documento.
        Il filtro owner_id e' defense-in-depth oltre la policy RLS della sessione.
        L'ordinamento e' per distanza crescente (0 = identico, 1 = ortogonale).
        """
        dist = EntityEmbedding.embedding.cosine_distance(query_vector)
        result = await self._session.execute(
            select(
                EntityEmbedding.entity_id,
                EntityEmbedding.name,
                dist.label("distance"),
            )
            .where(
                EntityEmbedding.document_id == document_id,
                EntityEmbedding.owner_id == owner_id,
            )
            .order_by(dist)
            .limit(k)
        )
        return [
            SimilarEntity(
                entity_id=row.entity_id,
                name=row.name,
                distance=float(row.distance),
            )
            for row in result
        ]
