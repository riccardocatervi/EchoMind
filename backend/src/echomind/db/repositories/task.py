"""Repository per la risorsa Task — query CRUD primitive sulla tabella `tasks`.

Particolarità: questo repository è usato da DUE chiamanti con sessioni diverse:
- **API** (enqueue/list/get): sessione RLS-bound → le query vedono solo i task
  dell'utente corrente, e l'INSERT passa la policy `task_insert_own`.
- **Worker** (mark_*): sessione di SISTEMA (ruolo `echomind` superuser, che
  bypassa RLS) → può aggiornare lo stato di qualunque riga, perché il worker è
  un componente fidato che non agisce "per conto" di un utente.

Il repository non conosce la differenza: riceve la sessione che gli passano.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomind.db.models import Task, TaskStatus


class TaskRepository:
    """Accesso CRUD alla tabella `tasks`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -------------------------------------------------------------------------
    # READ
    # -------------------------------------------------------------------------
    async def get_by_id(self, task_id: UUID) -> Task | None:
        """Ritorna il task con quell'ID, o None.

        Sotto RLS attiva: None anche se il task esiste ma è di un altro utente.
        """
        result = await self._session.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()

    async def list_by_owner(self, owner_id: UUID, *, limit: int, offset: int) -> Sequence[Task]:
        """Lista dei task di un utente, dal più recente.

        Sfrutta l'indice composito `(owner_id, created_at DESC)`.
        """
        result = await self._session.execute(
            select(Task)
            .where(Task.owner_id == owner_id)
            .order_by(Task.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    # -------------------------------------------------------------------------
    # WRITE (enqueue, lato API sotto RLS)
    # -------------------------------------------------------------------------
    async def create(
        self,
        *,
        owner_id: UUID,
        task_type: str,
        payload: dict[str, Any],
    ) -> Task:
        """Inserisce un nuovo Task con status='queued'.

        Sotto RLS richiede la policy `task_insert_own`: owner_id deve matchare
        il claim corrente, altrimenti Postgres solleva IntegrityError.
        """
        task = Task(owner_id=owner_id, task_type=task_type, payload=payload)
        self._session.add(task)
        await self._session.flush()  # forza INSERT + server-side defaults
        await self._session.refresh(task)
        return task

    # -------------------------------------------------------------------------
    # WRITE (transizioni di stato, lato worker con sessione di sistema)
    # -------------------------------------------------------------------------
    async def mark_running(self, task: Task, *, retries: int) -> Task:
        """Transizione → 'running'. Registra started_at e il contatore tentativi."""
        task.status = TaskStatus.RUNNING
        task.retries = retries
        task.started_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(task)
        return task

    async def mark_succeeded(self, task: Task, *, result: dict[str, Any]) -> Task:
        """Transizione terminale → 'succeeded'. Salva il result e finished_at."""
        task.status = TaskStatus.SUCCEEDED
        task.result = result
        task.error = None
        task.finished_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(task)
        return task

    async def mark_failed(self, task: Task, *, error: str) -> Task:
        """Transizione terminale → 'failed'. Salva il messaggio d'errore e finished_at."""
        task.status = TaskStatus.FAILED
        task.error = error
        task.finished_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(task)
        return task
