"""Repository per la risorsa Transcript -- query CRUD sulla tabella `transcripts`.

Usato da DUE chiamanti con sessioni diverse (come TaskRepository):
- **Worker** (`upsert`): sessione di SISTEMA (ruolo `echomind` superuser, che
  bypassa RLS) --> scrive l'output del processing per conto del sistema.
- **API** (`get_by_document_id`): sessione RLS-bound --> l'utente legge solo i
  propri transcript (policy `transcript_select_own` filtra per owner_id).

Il repository non conosce la differenza: usa la sessione che riceve.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from echomind.db.models import Transcript


class TranscriptRepository:
    """Accesso CRUD alla tabella `transcripts`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -------------------------------------------------------------------------
    # READ
    # -------------------------------------------------------------------------
    async def get_by_id(self, transcript_id: UUID) -> Transcript | None:
        """Ritorna il transcript con quell'ID, o None.

        Sotto RLS attiva: None anche se esiste ma e' di un altro utente.
        """
        result = await self._session.execute(
            select(Transcript).where(Transcript.id == transcript_id)
        )
        return result.scalar_one_or_none()

    async def get_by_document_id(self, document_id: UUID) -> Transcript | None:
        """Ritorna il transcript di un documento (relazione 1:1), o None.

        Sotto RLS attiva: None anche se esiste ma appartiene a un altro utente.
        """
        result = await self._session.execute(
            select(Transcript).where(Transcript.document_id == document_id)
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
        source_type: str,
        content: str,
        language: str | None,
        char_count: int,
        meta: dict[str, Any],
    ) -> Transcript:
        """Inserisce o aggiorna il transcript di un documento (ON CONFLICT document_id).

        Idempotente sul ri-processing: un nuovo task sullo stesso documento
        SOSTITUISCE il contenuto invece di violare il vincolo UNIQUE. Il trigger
        BEFORE UPDATE aggiorna `updated_at` da solo sul ramo di update (per cui
        non lo settiamo qui).

        Nota su `populate_existing`: l'INSERT ... ON CONFLICT ... RETURNING viene
        eseguito come statement Core; chiediamo a SQLAlchemy di mappare la riga
        ritornata su un'istanza ORM aggiornata (utile se l'oggetto era gia' in
        identity map dopo un update).
        """
        stmt = (
            pg_insert(Transcript)
            .values(
                document_id=document_id,
                owner_id=owner_id,
                source_type=source_type,
                content=content,
                language=language,
                char_count=char_count,
                meta=meta,
            )
            .on_conflict_do_update(
                index_elements=[Transcript.document_id],
                set_={
                    "source_type": source_type,
                    "content": content,
                    "language": language,
                    "char_count": char_count,
                    "meta": meta,
                },
            )
            .returning(Transcript)
        )
        result = await self._session.execute(stmt, execution_options={"populate_existing": True})
        return result.scalar_one()
