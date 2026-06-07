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

import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from echomind.core.logging import get_logger
from echomind.db.models import Task, TaskType
from echomind.db.repositories import TaskRepository
from echomind.worker.celery_app import WORK_QUEUE

# NB: i task Celery (echo_task, transcribe_task) sono importati LAZY dentro i
# metodi di enqueue, non qui a livello di modulo. Motivo: spezzare un ciclo di
# import. Il worker avvia importando `worker.tasks.echo` per primo, che importa
# `worker.runtime` --> `services.storage` --> (services/__init__) -->
# `services.document` --> QUESTO modulo. Se qui importassimo i task a livello di
# modulo, si richiuderebbe il cerchio su `worker.tasks.echo` ancora "partially
# initialized" (ImportError). Un import a livello di funzione rompe il ciclo: al
# momento della chiamata, i moduli task sono ormai completamente inizializzati.
# (La soluzione piu' disaccoppiata -- enqueue per nome con celery_app.send_task,
# senza importare affatto i task -- e' annotata in ADR-0006 come evoluzione M9.)

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

        # Import lazy: vedi nota in cima al modulo (rottura del ciclo di import).
        from echomind.worker.tasks.echo import echo_task

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

        # Import lazy: vedi nota in cima al modulo (rottura del ciclo di import).
        from echomind.worker.tasks.transcribe import transcribe_task

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

    async def enqueue_extract(self, *, owner_id: UUID, document_id: UUID) -> Task:
        """Crea la riga (status=queued, type=extract) e accoda il task sul broker.

        Il payload porta il document_id: il worker carica il transcript di quel
        documento (sorgente di verita') e ne estrae il grafo. task_id Celery == id riga.

        Raises:
            TaskEnqueueError: se l'enqueue sul broker fallisce. La transazione del
            chiamante fara' rollback, quindi la riga non resta orfana.
        """
        payload: dict[str, Any] = {"document_id": str(document_id)}
        task = await self._repository.create(
            owner_id=owner_id,
            task_type=TaskType.EXTRACT.value,
            payload=payload,
        )

        # Import lazy: vedi nota in cima al modulo (rottura del ciclo di import).
        from echomind.worker.tasks.extract import extract_task

        try:
            extract_task.apply_async(
                args=[str(task.id)],
                task_id=str(task.id),
                queue=WORK_QUEUE,
            )
        except Exception as exc:
            log.error("task_enqueue_failed", task_id=str(task.id), error=str(exc))
            raise TaskEnqueueError("Impossibile accodare il task di estrazione") from exc

        log.info(
            "task_enqueued",
            task_id=str(task.id),
            task_type=TaskType.EXTRACT.value,
            document_id=str(document_id),
        )
        return task

    async def revoke_active_tasks_for_document(self, document_id: UUID) -> None:
        """Revoca (best-effort) i task Celery attivi per un documento.

        Chiamato da DocumentService.delete_document PRIMA dell'eliminazione
        per interrompere Whisper/Gemini in esecuzione e risparmiare crediti API.

        Strategia di revoca:
        - `terminate=True`  --> invia SIGTERM al processo worker child che
          esegue il task (solo se running; no-op se ancora queued).
        - `signal='SIGTERM'` --> graceful: il child puo' eseguire cleanup prima
          di morire (l'HTTP request in corso viene comunque abortita).
        - `reply=False` (default Celery) --> fire-and-forget: non aspettiamo
          ack dai worker; la funzione torna subito.

        Idempotenza in caso di re-delivery (task_acks_late=True):
        - Se il task era 'running' e SIGTERM lo ha ucciso, RabbitMQ riconsegna
          il messaggio. Il worker tenta di eseguirlo di nuovo ma la riga `tasks`
          e' gia' stata cascade-deleted con il documento --> ritorna `already_done`
          senza fare alcuna chiamata API. Zero sprechi di crediti.
        - Se il task era 'queued' (non ancora preso dal worker), Celery registra
          il task_id come revocato nel suo state store; il worker lo salta
          quando lo dequeue senza eseguirlo.

        L'import di celery_app e' lazy (pattern gia' usato negli enqueue):
        evita che future evoluzioni del grafo di import possano creare cicli.

        celery_app.control.revoke e' sincrono (pubblica sul control exchange di
        RabbitMQ). Lo eseguiamo in asyncio.to_thread per non bloccare il loop
        di FastAPI anche per i pochi ms richiesti dall'operazione.
        """
        active_tasks = await self._repository.list_active_by_document(document_id)
        if not active_tasks:
            return

        task_ids = [str(t.id) for t in active_tasks]
        log.info(
            "document_tasks_revoking",
            document_id=str(document_id),
            count=len(task_ids),
            task_ids=task_ids,
        )

        # Import lazy: vedi nota in cima al modulo.
        from echomind.worker.celery_app import celery_app

        def _revoke_all() -> None:
            for task_id in task_ids:
                try:
                    celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
                except Exception as exc:
                    log.warning(
                        "task_revoke_broker_error",
                        task_id=task_id,
                        error=str(exc),
                    )

        await asyncio.to_thread(_revoke_all)
        log.info(
            "document_tasks_revoked",
            document_id=str(document_id),
            count=len(task_ids),
        )

    async def get_task(self, *, task_id: UUID) -> Task:
        """Dettaglio singolo. Solleva TaskNotFoundError se assente/nascosto da RLS."""
        task = await self._repository.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found")
        return task

    async def list_tasks(self, *, owner_id: UUID, limit: int, offset: int) -> Sequence[Task]:
        """Lista paginata dei task dell'utente, dal piu' recente."""
        return await self._repository.list_by_owner(owner_id, limit=limit, offset=offset)
