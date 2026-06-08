"""Repository per la risorsa Summary -- query CRUD sulla tabella `summaries`.

Usato da DUE chiamanti con sessioni diverse (come TranscriptRepository):
- **Worker** (`upsert`): sessione di SISTEMA (ruolo `echomind`, bypassa RLS) -->
  scrive il riassunto prodotto dall'estrazione.
- **API** (`get_by_document_id`): sessione RLS-bound --> l'utente legge solo i
  propri riassunti (policy `summary_select_own`).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from echomind.db.models import Summary


class SummaryRepository:
    """Accesso CRUD alla tabella `summaries`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -------------------------------------------------------------------------
    # READ
    # -------------------------------------------------------------------------
    async def get_by_id(self, summary_id: UUID) -> Summary | None:
        """Ritorna il riassunto con quell'ID, o None (None anche se RLS lo nasconde)."""
        result = await self._session.execute(select(Summary).where(Summary.id == summary_id))
        return result.scalar_one_or_none()

    async def get_by_document_id(self, document_id: UUID) -> Summary | None:
        """Ritorna il riassunto di un documento (relazione 1:1), o None.

        Sotto RLS attiva: None anche se esiste ma appartiene a un altro utente.
        """
        result = await self._session.execute(
            select(Summary).where(Summary.document_id == document_id)
        )
        return result.scalar_one_or_none()

    # -------------------------------------------------------------------------
    # WRITE (worker, sessione di sistema)
    # -------------------------------------------------------------------------
    async def upsert(
        self,
        *,
        document_id: UUID,
        owner_id: UUID,
        overview: str,
        sections: list[dict[str, Any]],
        meta: dict[str, Any],
    ) -> Summary:
        """Inserisce o aggiorna il riassunto di un documento (ON CONFLICT document_id).

        Idempotente sulla ri-estrazione: un nuovo task sullo stesso documento
        SOSTITUISCE il riassunto invece di violare il vincolo UNIQUE. Il trigger
        BEFORE UPDATE aggiorna `updated_at` da solo sul ramo di update.
        """
        stmt = (
            pg_insert(Summary)
            .values(
                document_id=document_id,
                owner_id=owner_id,
                overview=overview,
                sections=sections,
                meta=meta,
            )
            .on_conflict_do_update(
                index_elements=[Summary.document_id],
                set_={
                    "overview": overview,
                    "sections": sections,
                    "meta": meta,
                },
            )
            .returning(Summary)
        )
        result = await self._session.execute(stmt, execution_options={"populate_existing": True})
        return result.scalar_one()
