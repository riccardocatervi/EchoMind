"""Modello SQLAlchemy `Task` -- job asincrono eseguito da un worker Celery.

Lifecycle:
    POST /tasks/echo   -->  riga creata con status='queued' + enqueue su RabbitMQ
    worker prende      -->  status='running' (started_at)
    worker completa    -->  status='succeeded' (result, finished_at)
    worker fallisce N  -->  retry con backoff; esauriti --> status='failed' (error,
                          finished_at) + messaggio dead-letterato nella DLQ

La verità di dominio sullo stato vive QUI (Postgres), non nel result backend
di Celery (Redis): così l'API può esporla filtrata per-utente via RLS.

Vedi:
- Migration: backend/alembic/versions/0003_tasks_table.py
- Repository: backend/src/echomind/db/repositories/task.py
- Worker:     backend/src/echomind/worker/tasks/echo.py
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from echomind.db.base import Base


class TaskStatus(enum.StrEnum):
    """Stati del lifecycle di un task asincrono.

    `StrEnum` (Python 3.11+): i valori sono stringhe native --> serializzazione
    JSON gratuita (FastAPI/Pydantic li trattano come str).
    """

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TaskType(enum.StrEnum):
    """Tipi di task supportati. Cresce a ogni milestone (M3: solo `echo`).

    Persistito come TEXT nel DB (non ENUM): l'insieme evolve spesso e un
    TEXT + validazione applicativa evita `ALTER TYPE ... ADD VALUE` ripetuti.
    """

    ECHO = "echo"


# Stati oltre i quali un task non transiziona più. Usato dal worker per
# l'idempotenza: una re-delivery (at-least-once) su una riga già terminale
# è un no-op.
TERMINAL_STATUSES: frozenset[TaskStatus] = frozenset({TaskStatus.SUCCEEDED, TaskStatus.FAILED})


class Task(Base):
    """Job asincrono di un utente.

    `owner_id` è FK a `profiles.id` con ON DELETE CASCADE: eliminato il profile,
    spariscono i suoi task.
    """

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )

    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    task_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Tipo logico del task ('echo' in M3). Validato lato app (TaskType).",
    )

    # `values_callable`: SQLAlchemy serializzerebbe il NOME del member ('QUEUED'),
    # ma Postgres accetta solo i VALORI lowercase ('queued'). Forziamo i valori.
    status: Mapped[TaskStatus] = mapped_column(
        Enum(
            TaskStatus,
            name="task_status",
            create_type=False,
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        default=TaskStatus.QUEUED,
        server_default=text("'queued'::task_status"),
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,  # callable --> nuovo dict per insert, niente mutable condiviso
        server_default=text("'{}'::jsonb"),
        comment="Input del task.",
    )

    result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Output del task (popolato a status='succeeded').",
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Messaggio dell'ultimo errore (popolato a status='failed').",
    )

    retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Tentativi già consumati (per backoff e soglia DLQ).",
    )

    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    def __repr__(self) -> str:
        return (
            f"Task(id={self.id!r}, owner_id={self.owner_id!r}, "
            f"task_type={self.task_type!r}, status={self.status!r})"
        )
