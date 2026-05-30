"""Task 'echo' -- il task fittizio di M3.

Dimostra l'intera pipeline asincrona end-to-end: enqueue --> broker --> worker -->
stato persistito in DB. Con payload `{"fail": true}` esercita il percorso di
errore: retry con backoff esponenziale --> stato terminale 'failed' --> dead-letter.

Architettura in DUE livelli (deliberata):
- `run_echo()`  -- coroutine ASYNC: tutta la logica di dominio (transizioni di
  stato in DB). Pura e testabile in isolamento, SENZA Celery né event loop
  annidati (i test la chiamano direttamente).
- `echo_task()` -- wrapper SINCRONO registrato su Celery: traduce l'esito di
  `run_echo` nelle primitive di controllo di Celery (`self.retry`, `Reject`).
  Queste vivono qui, nel contesto sincrono dove Celery se le aspetta -- non
  dentro la coroutine.

Conteggio tentativi: `self.request.retries` è 0-based (0 alla prima esecuzione).
Con `task_max_retries=3` il task fallisce ai tentativi 1, 2 e 3; il 3° è
terminale (--> DLQ). Quindi "fallisce 3 volte --> dead-letter".
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from celery import Task
from celery.exceptions import Reject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from echomind.core.config import get_settings
from echomind.core.logging import get_logger
from echomind.db.models.task import TERMINAL_STATUSES
from echomind.db.repositories import TaskRepository
from echomind.worker.celery_app import celery_app
from echomind.worker.runtime import get_worker_session_maker, run_async

log = get_logger(__name__)


class EchoTaskError(Exception):
    """Errore simulato dall'echo task quando il payload chiede `fail=true`."""


@dataclass(frozen=True, slots=True)
class EchoOutcome:
    """Esito del core async, tradotto dal wrapper sincrono in azioni Celery.

    - succeeded:       il task è completato; `result` contiene l'output.
    - retry:           fallimento non terminale; il wrapper richiama self.retry.
    - failed_terminal: fallimento terminale (DB già marcato 'failed'); il
                       wrapper fa Reject(requeue=False) --> dead-letter queue.
    - already_done:    riga già in stato terminale (o assente): no-op idempotente.
    """

    kind: Literal["succeeded", "retry", "failed_terminal", "already_done"]
    result: dict[str, Any] | None = None
    error: str | None = None


async def run_echo(
    *,
    task_id: UUID,
    message: str,
    fail: bool,
    attempt: int,
    is_last_attempt: bool,
    session_maker: async_sessionmaker[AsyncSession],
) -> EchoOutcome:
    """Core async dell'echo task: gestisce le transizioni di stato in DB.

    Idempotente: su una riga già terminale (re-delivery at-least-once) è no-op.
    Usa una sessione di SISTEMA (no RLS): il worker è un componente fidato.

    Commit separati per stato così l'API osserva 'running' DURANTE l'esecuzione
    (per l'echo è istantaneo, ma è il pattern corretto per i task lunghi di M4).
    """
    async with session_maker() as session:
        repo = TaskRepository(session)

        # 1. Carica + guardia di idempotenza (in una transazione breve).
        async with session.begin():
            task = await repo.get_by_id(task_id)
            if task is None:
                log.warning("echo_task_row_missing", task_id=str(task_id))
                return EchoOutcome(kind="already_done")
            if task.status in TERMINAL_STATUSES:
                log.info(
                    "echo_task_already_terminal",
                    task_id=str(task_id),
                    status=task.status.value,
                )
                return EchoOutcome(kind="already_done", result=task.result)
            await repo.mark_running(task, retries=attempt)

        log.info("echo_task_running", task_id=str(task_id), attempt=attempt + 1, fail=fail)

        # 2. Percorso di fallimento simulato.
        if fail:
            error = f"echo task fallito di proposito (tentativo {attempt + 1})"
            if is_last_attempt:
                async with session.begin():
                    await repo.mark_failed(task, error=error)
                log.error(
                    "echo_task_failed_terminal",
                    task_id=str(task_id),
                    attempt=attempt + 1,
                )
                return EchoOutcome(kind="failed_terminal", error=error)
            log.warning("echo_task_will_retry", task_id=str(task_id), attempt=attempt + 1)
            return EchoOutcome(kind="retry", error=error)

        # 3. Percorso felice.
        result: dict[str, Any] = {
            "echo": message,
            "length": len(message),
            "attempt": attempt + 1,
        }
        async with session.begin():
            await repo.mark_succeeded(task, result=result)
        log.info("echo_task_succeeded", task_id=str(task_id), attempt=attempt + 1)
        return EchoOutcome(kind="succeeded", result=result)


def _retry_countdown(attempt: int, *, base: int) -> int:
    """Ritardo (secondi) prima del prossimo retry: backoff esponenziale + jitter.

    `base * 2**attempt` cresce geometricamente (1° retry ~base, 2° ~2*base, ...).
    Il jitter (rumore casuale fino a `base`) sfasa i retry di task che falliscono
    insieme, evitando il "thundering herd" (tutti riprovano nello stesso istante).
    """
    exponential = base * (2**attempt)
    jitter = random.uniform(0, base)  # noqa: S311 - jitter non crittografico
    return int(exponential + jitter)


# Il decorator di Celery non è tipizzato: in strict mode mypy lo segnala come
# "untyped-decorator". Lo silenziamo qui (Celery è dynamically typed by design).
@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="echomind.echo",
    max_retries=get_settings().task_max_retries,
)
def echo_task(self: Task, task_id: str, message: str, fail: bool = False) -> dict[str, Any] | None:
    """Wrapper sincrono registrato su Celery. Delega a `run_echo` e traduce l'esito.

    `bind=True` --> `self` è l'istanza del task (per self.request.retries / self.retry).
    """
    settings = get_settings()
    attempt: int = self.request.retries  # 0 alla prima esecuzione
    is_last_attempt = (attempt + 1) >= settings.task_max_retries

    outcome = run_async(
        run_echo(
            task_id=UUID(task_id),
            message=message,
            fail=fail,
            attempt=attempt,
            is_last_attempt=is_last_attempt,
            session_maker=get_worker_session_maker(),
        )
    )

    if outcome.kind == "retry":
        countdown = _retry_countdown(attempt, base=settings.task_retry_backoff_seconds)
        log.warning(
            "echo_task_retry_scheduled",
            task_id=task_id,
            attempt=attempt + 1,
            countdown=countdown,
        )
        # self.retry rilancia il task e solleva Retry (il return sotto è irraggiungibile).
        raise self.retry(exc=EchoTaskError(outcome.error or "retry"), countdown=countdown)

    if outcome.kind == "failed_terminal":
        # Reject(requeue=False) --> basic.reject sul broker --> x-dead-letter-exchange
        # instrada il messaggio nella coda echomind.dead. Il DB è GIÀ 'failed'.
        log.error("echo_task_dead_lettered", task_id=task_id)
        raise Reject(requeue=False)

    return outcome.result
