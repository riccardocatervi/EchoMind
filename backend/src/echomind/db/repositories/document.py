"""Repository per la risorsa Document — query SQLAlchemy CRUD primitives.

Responsabilità esclusiva: query sulla tabella `documents`. Niente business
logic ("just-in-time create", "validate MIME"), niente FastAPI, niente B2.
Solo persistenza tipizzata.

Sotto sessione RLS-bound (`set_rls_user` chiamato in deps.py), Postgres
filtra automaticamente per `owner_id == sub_claim`: questo repository
non duplica i filtri `WHERE owner_id = ...`.

Naming convention:
- `get_*`     → singolo oggetto o None
- `list_*`    → sequenza (paginata)
- `create_*`  → INSERT + ritorna l'oggetto
- `update_*`  → in-place + ritorna l'oggetto aggiornato
- `delete_*`  → rimozione (idempotente, no errore se non esiste)
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomind.db.models import Document, DocumentStatus


class DocumentRepository:
    """Accesso CRUD alla tabella `documents`.

    Istanziata per-request (la sessione è scoped per HTTP request).
    Costruita tipicamente da `DocumentService` o dependency FastAPI.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -------------------------------------------------------------------------
    # READ
    # -------------------------------------------------------------------------
    async def get_by_id(self, document_id: UUID) -> Document | None:
        """Ritorna il documento con quell'ID, o None.

        Sotto RLS attiva: ritorna None ANCHE se il documento esiste ma
        appartiene a un altro utente. Comportamento desiderato.
        """
        result = await self._session.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()

    async def list_by_owner(self, owner_id: UUID, *, limit: int, offset: int) -> Sequence[Document]:
        """Lista dei documenti di un utente, ordinati dal più recente.

        Sfrutta l'indice composito `(owner_id, created_at DESC)`:
        query risolta interamente in indice, niente sort separato.

        Args:
            owner_id: ID dell'utente. Sotto RLS dovrebbe matchare il claim.
            limit: max risultati (caller decide; tipicamente 1-100).
            offset: skip dei primi N risultati (per paginazione).
        """
        result = await self._session.execute(
            select(Document)
            .where(Document.owner_id == owner_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    # -------------------------------------------------------------------------
    # WRITE
    # -------------------------------------------------------------------------
    async def create(
        self,
        *,
        owner_id: UUID,
        filename: str,
        mime_type: str,
        size_bytes: int,
        storage_key: str,
    ) -> Document:
        """Inserisce un nuovo Document con status=pending.

        Sotto RLS, l'INSERT richiede la policy `document_insert_own`
        (definita in 0002): owner_id deve matchare il claim corrente.
        Se non matcha → IntegrityError sollevata da Postgres.
        """
        document = Document(
            owner_id=owner_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            # status default 'pending' applicato dal DB/Python
        )
        self._session.add(document)
        await self._session.flush()  # forza INSERT, popola server-side defaults
        await self._session.refresh(document)  # rilegge i defaults (created_at, ecc.)
        return document

    async def mark_uploaded(self, document: Document) -> Document:
        """Aggiorna status → 'uploaded'. Chiamato dopo conferma + validation."""
        document.status = DocumentStatus.UPLOADED
        document.failure_reason = None
        await self._session.flush()
        await self._session.refresh(document)
        return document

    async def mark_failed(self, document: Document, reason: str) -> Document:
        """Aggiorna status → 'failed' con la motivazione."""
        document.status = DocumentStatus.FAILED
        document.failure_reason = reason
        await self._session.flush()
        await self._session.refresh(document)
        return document

    async def delete(self, document_id: UUID) -> bool:
        """Cancella per id. Ritorna True se ha eliminato una riga, False se assente.

        Idempotente: chiamarla due volte per lo stesso id non solleva errori,
        ritorna semplicemente False la seconda volta.
        """
        from sqlalchemy.engine import CursorResult

        result = await self._session.execute(delete(Document).where(Document.id == document_id))
        await self._session.flush()
        # delete()/update() statements producono CursorResult con `rowcount`.
        # mypy non lo inferisce dal tipo Result generico, cast esplicito.
        cursor_result = cast(CursorResult[Any], result)
        return int(cursor_result.rowcount) > 0
