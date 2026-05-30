"""Pydantic schemas per la risorsa Task (job asincroni).

Convenzione naming (CQS):
- `EchoTaskCreate`       --> ciò che l'API ACCETTA (input POST /tasks/echo)
- `TaskEnqueuedResponse` --> output di POST /tasks/echo (202 Accepted)
- `TaskRead`             --> ciò che l'API RITORNA (GET /tasks, GET /tasks/{id})
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from echomind.db.models import TaskStatus


# -----------------------------------------------------------------------------
# Input schema: POST /api/v1/tasks/echo
# -----------------------------------------------------------------------------
class EchoTaskCreate(BaseModel):
    """Payload per accodare un task 'echo' (il task fittizio di M3)."""

    message: Annotated[
        str,
        Field(min_length=1, max_length=10_000, description="Messaggio che il task restituirà."),
    ]
    fail: bool = Field(
        default=False,
        description=(
            "Se True, il task fallisce di proposito ad ogni tentativo: esercita il "
            "percorso retry --> stato terminale 'failed' --> dead-letter queue. "
            "Serve per demo e test del path di errore."
        ),
    )

    # extra='forbid': un campo di troppo (typo del client) --> 422 esplicito.
    model_config = ConfigDict(extra="forbid")


# -----------------------------------------------------------------------------
# Output schemas
# -----------------------------------------------------------------------------
class TaskEnqueuedResponse(BaseModel):
    """Risposta 202 Accepted di POST /tasks/echo.

    202 (non 200/201): la richiesta è stata ACCETTATA per elaborazione
    asincrona, ma NON è ancora completata. Il client fa polling su
    GET /tasks/{task_id} per conoscerne l'esito.
    """

    task_id: UUID = Field(description="ID del task. Usa GET /tasks/{id} per lo stato.")
    status: TaskStatus = Field(description="Stato iniziale: sempre 'queued'.")


class TaskRead(BaseModel):
    """Vista del task esposta dall'API."""

    id: UUID
    owner_id: UUID
    task_type: str
    status: TaskStatus
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    retries: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
