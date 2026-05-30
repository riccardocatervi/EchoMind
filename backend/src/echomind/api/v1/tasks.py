"""Endpoint /tasks -- enqueue e consultazione dei job asincroni.

3 endpoint:
- POST /api/v1/tasks/echo   --> accoda un task echo (demo della pipeline async)
- GET  /api/v1/tasks        --> lista paginata (RLS-filtered)
- GET  /api/v1/tasks/{id}   --> stato/dettaglio di un task

Tutta la business logic vive in TaskService. Qui solo: validazione body,
mapping query params, conversione Task ORM --> TaskRead.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from echomind.api.deps import TaskServiceDep, UserIdDep
from echomind.schemas.task import EchoTaskCreate, TaskEnqueuedResponse, TaskRead

router = APIRouter(prefix="/tasks", tags=["tasks"])


# -----------------------------------------------------------------------------
# Enqueue echo
# -----------------------------------------------------------------------------
@router.post(
    "/echo",
    response_model=TaskEnqueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Accoda un task 'echo' (demo della pipeline asincrona)",
    description=(
        "Crea il record `tasks` in stato `queued` e accoda il messaggio su RabbitMQ. "
        "Ritorna 202 Accepted con il task_id: usa GET /tasks/{id} per seguirne lo stato. "
        "Con `fail=true` il task fallisce di proposito (retry --> failed --> dead-letter)."
    ),
    responses={
        401: {"description": "Token mancante, invalido o scaduto"},
        422: {"description": "Payload malformato (message vuoto o campi extra)"},
        503: {"description": "Broker non disponibile (enqueue fallito)"},
    },
)
async def enqueue_echo(
    user_id: UserIdDep,
    payload: EchoTaskCreate,
    service: TaskServiceDep,
) -> TaskEnqueuedResponse:
    task = await service.enqueue_echo(
        owner_id=user_id,
        message=payload.message,
        fail=payload.fail,
    )
    return TaskEnqueuedResponse(task_id=task.id, status=task.status)


# -----------------------------------------------------------------------------
# List
# -----------------------------------------------------------------------------
@router.get(
    "",
    response_model=list[TaskRead],
    summary="Lista paginata dei propri task",
    description="Ordinati dal piu' recente. Sfrutta indice composito `(owner_id, created_at DESC)`.",
)
async def list_tasks(
    user_id: UserIdDep,
    service: TaskServiceDep,
    limit: Annotated[int, Query(ge=1, le=100, description="Max risultati (1-100)")] = 20,
    offset: Annotated[int, Query(ge=0, description="Skip dei primi N")] = 0,
) -> list[TaskRead]:
    tasks = await service.list_tasks(owner_id=user_id, limit=limit, offset=offset)
    return [TaskRead.model_validate(t) for t in tasks]


# -----------------------------------------------------------------------------
# Detail / stato
# -----------------------------------------------------------------------------
@router.get(
    "/{task_id}",
    response_model=TaskRead,
    summary="Stato/dettaglio di un task",
    responses={404: {"description": "Task non trovato (o nascosto da RLS)"}},
)
async def get_task(
    user_id: UserIdDep,
    task_id: UUID,
    service: TaskServiceDep,
) -> TaskRead:
    task = await service.get_task(task_id=task_id)
    return TaskRead.model_validate(task)
