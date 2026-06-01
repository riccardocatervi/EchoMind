"""TaskService -- orchestrazione di enqueue e lettura dei task asincroni.

Connette:
- TaskRepository (DB sotto RLS, lato API)
- l'echo task Celery (per l'enqueue su RabbitMQ)

Il service NON conosce FastAPI/HTTP: e' riutilizzabile da CLI, worker, test.

Ordine enqueue (problema del "dual write" DB + broker):
    Inseriamo la riga (flush, NON commit -- il commit lo fa la dependency a fine
    request) e poi accodiamo sul broker. Se l'enqueue fallisce solleviamo
    TaskEnqueueError: l'eccezione risale fuori dalla transazione della request,
    che fa ROLLBACK --> nessuna riga orfana 'queued'. Niente bisogno di marcare
    'failed' (e quindi niente policy UPDATE per gli utenti).

    Resta una finestra teorica (l'apply_async pubblica PRIMA del commit): se il
    worker fosse fulmineo potrebbe leggere la riga prima che sia committata. La
    rete (publish + dispatch al worker) e' molto piu' lenta del commit
    in-process, quindi in pratica non accade; e se accadesse, la guardia
    "riga assente" in run_echo lo gestisce come no-op. La soluzione robusta
    (transactional outbox) e' rimandata a M9. Vedi ADR-0005.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from echomind.core.logging import get_logger
from echomind.db.models import Task, TaskType
from echomind.db.repositories import TaskRepository
from echomind.worker.celery_app import WORK_QUEUE
from echomind.worker.tasks.echo import echo_task
from echomind.worker.tasks.transcribe import transcribe_task

log = get_logger(__name__)


# -----------------------------------------------------------------------------
# Errori di dominio (mappati a HTTP dagli exception handler in main.py)
# -----------------------------------------------------------------------------
class TaskError(Exception):
    """Base per gli errori del dominio Task."""


class TaskNotFoundError(TaskError):
    """Il task non esiste (o RLS lo nasconde) per l'utente corrente."""


class TaskEnqueueError(TaskError):
    """Accodamento sul broker fallito (es. RabbitMQ irraggiungibile)."""


# -----------------------------------------------------------------------------
# Service
# -----------------------------------------------------------------------------
class TaskService:
    """Orchestrazione del lifecycle dei task lato API.

    Riceve un repository legato alla sessione RLS dell'utente: le SELECT sono
    filtrate per owner e l'INSERT passa la policy `task_insert_own`.
    """

    def __init__(self, *, repository: TaskRepository) -> None:
        self._repository = repository

    async def enqueue_echo(self, *, owner_id: UUID, message: str, fail: bool = False) -> Task:
        """Crea la riga (status=queued) e accoda il task echo sul broker.

        Returns:
            Il Task appena creato (status='queued').

        Raises:
            TaskEnqueueError: se l'enqueue sul broker fallisce (--> 503). La
            transazione della request fara' rollback, quindi la riga non resta.
        """
        payload: dict[str, Any] = {"message": message, "fail": fail}
        task = await self._repository.create(
            owner_id=owner_id,
            task_type=TaskType.ECHO.value,
            payload=payload,
        )

        # task_id Celery == id della riga: un solo identificatore, nessuna mappa.
        try:
            echo_task.apply_async(
                args=[str(task.id), message, fail],
                task_id=str(task.id),
                queue=WORK_QUEUE,
            )
        except Exception as exc:
            log.error("task_enqueue_failed", task_id=str(task.id), error=str(exc))
            raise TaskEnqueueError("Impossibile accodare il task sul broker") from exc

        log.info("task_enqueued", task_id=str(task.id), task_type=TaskType.ECHO.value)
        return task

    async def enqueue_transcribe(self, *, owner_id: UUID, document_id: UUID) -> Task:
        """Crea la riga (status=queued, type=transcribe) e accoda il task sul broker.

        Il payload porta il document_id: il worker lo legge dalla riga (sorgente
        di verita') per scaricare e processare il file. task_id Celery == id riga.

        Raises:
            TaskEnqueueError: se l'enqueue sul broker fallisce (--> 503). La
            transazione della request fara' rollback, quindi la riga non resta.
        """
        payload: dict[str, Any] = {"document_id": str(document_id)}
        task = await self._repository.create(
            owner_id=owner_id,
            task_type=TaskType.TRANSCRIBE.value,
            payload=payload,
        )

        try:
            transcribe_task.apply_async(
                args=[str(task.id)],
                task_id=str(task.id),
                queue=WORK_QUEUE,
            )
        except Exception as exc:
            log.error("task_enqueue_failed", task_id=str(task.id), error=str(exc))
            raise TaskEnqueueError("Impossibile accodare il task di trascrizione") from exc

        log.info(
            "task_enqueued",
            task_id=str(task.id),
            task_type=TaskType.TRANSCRIBE.value,
            document_id=str(document_id),
        )
        return task

    async def get_task(self, *, task_id: UUID) -> Task:
        """Dettaglio singolo. Solleva TaskNotFoundError se assente/nascosto da RLS."""
        task = await self._repository.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found")
        return task

    async def list_tasks(self, *, owner_id: UUID, limit: int, offset: int) -> Sequence[Task]:
        """Lista paginata dei task dell'utente, dal piu' recente."""
        return await self._repository.list_by_owner(owner_id, limit=limit, offset=offset)
