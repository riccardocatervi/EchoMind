"""Unit test del TaskService (repository mockato + enqueue Celery patchato).

Niente DB, niente broker: tutto in-memory. La pipeline reale (worker) e'
coperta dallo smoke test; l'isolamento RLS dai test integration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from echomind.db.models import Task, TaskStatus
from echomind.services.task import TaskEnqueueError, TaskNotFoundError, TaskService


@pytest.fixture
def mock_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(mock_repo: AsyncMock) -> TaskService:
    return TaskService(repository=mock_repo)


def _make_task(
    *,
    owner_id: UUID | None = None,
    status: TaskStatus = TaskStatus.QUEUED,
) -> Task:
    task = Task(
        owner_id=owner_id or uuid4(),
        task_type="echo",
        payload={"message": "hi", "fail": False},
    )
    task.id = uuid4()
    task.status = status
    task.result = None
    task.error = None
    task.retries = 0
    task.started_at = None
    task.finished_at = None
    task.created_at = datetime.now(UTC)
    task.updated_at = datetime.now(UTC)
    return task


# =============================================================================
# enqueue_echo
# =============================================================================
class TestEnqueueEcho:
    @pytest.mark.asyncio
    async def test_creates_row_then_enqueues(
        self,
        service: TaskService,
        mock_repo: AsyncMock,
        captured_enqueues: list[dict[str, Any]],
    ) -> None:
        owner_id = uuid4()
        task = _make_task(owner_id=owner_id)
        mock_repo.create.return_value = task

        result = await service.enqueue_echo(owner_id=owner_id, message="hello", fail=False)

        # 1. INSERT con i campi giusti (status di default = queued)
        mock_repo.create.assert_awaited_once()
        kwargs = mock_repo.create.call_args.kwargs
        assert kwargs["owner_id"] == owner_id
        assert kwargs["task_type"] == "echo"
        assert kwargs["payload"] == {"message": "hello", "fail": False}

        # 2. Enqueue: task_id Celery == id riga, args coerenti, coda di lavoro
        assert len(captured_enqueues) == 1
        enq = captured_enqueues[0]["kwargs"]
        assert enq["task_id"] == str(task.id)
        assert enq["args"] == [str(task.id), "hello", False]
        assert enq["queue"] == "echomind.default"

        assert result is task

    @pytest.mark.asyncio
    async def test_enqueue_failure_raises_and_does_not_mark(
        self,
        service: TaskService,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Broker giu': apply_async solleva -> TaskEnqueueError.

        Il service NON marca 'failed' (niente policy UPDATE): la riga e' ancora
        non committata e la transazione della request fara' rollback.
        """
        from echomind.worker.tasks.echo import echo_task

        task = _make_task()
        mock_repo.create.return_value = task

        def _boom(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("broker unreachable")

        monkeypatch.setattr(echo_task, "apply_async", _boom)

        with pytest.raises(TaskEnqueueError):
            await service.enqueue_echo(owner_id=task.owner_id, message="x", fail=False)

        # Nessun mark_* invocato: si fa affidamento sul rollback della request.
        mock_repo.mark_failed.assert_not_awaited()
        mock_repo.mark_succeeded.assert_not_awaited()


# =============================================================================
# enqueue_transcribe
# =============================================================================
class TestEnqueueTranscribe:
    @pytest.mark.asyncio
    async def test_creates_row_then_enqueues(
        self,
        service: TaskService,
        mock_repo: AsyncMock,
        captured_enqueues: list[dict[str, Any]],
    ) -> None:
        owner_id = uuid4()
        document_id = uuid4()
        task = _make_task(owner_id=owner_id)
        mock_repo.create.return_value = task

        result = await service.enqueue_transcribe(owner_id=owner_id, document_id=document_id)

        # 1. INSERT con task_type='transcribe' e payload col document_id
        mock_repo.create.assert_awaited_once()
        kwargs = mock_repo.create.call_args.kwargs
        assert kwargs["owner_id"] == owner_id
        assert kwargs["task_type"] == "transcribe"
        assert kwargs["payload"] == {"document_id": str(document_id)}

        # 2. Enqueue: solo task_id come arg (il document_id vive nella riga DB)
        assert len(captured_enqueues) == 1
        enq = captured_enqueues[0]["kwargs"]
        assert enq["task_id"] == str(task.id)
        assert enq["args"] == [str(task.id)]
        assert enq["queue"] == "echomind.default"

        assert result is task

    @pytest.mark.asyncio
    async def test_enqueue_failure_raises(
        self,
        service: TaskService,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Broker giu': apply_async solleva --> TaskEnqueueError (la request fa rollback)."""
        from echomind.worker.tasks.transcribe import transcribe_task

        mock_repo.create.return_value = _make_task()

        def _boom(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("broker unreachable")

        monkeypatch.setattr(transcribe_task, "apply_async", _boom)

        with pytest.raises(TaskEnqueueError):
            await service.enqueue_transcribe(owner_id=uuid4(), document_id=uuid4())


# =============================================================================
# enqueue_extract
# =============================================================================
class TestEnqueueExtract:
    @pytest.mark.asyncio
    async def test_creates_row_then_enqueues(
        self,
        service: TaskService,
        mock_repo: AsyncMock,
        captured_enqueues: list[dict[str, Any]],
    ) -> None:
        owner_id = uuid4()
        document_id = uuid4()
        task = _make_task(owner_id=owner_id)
        mock_repo.create.return_value = task

        result = await service.enqueue_extract(owner_id=owner_id, document_id=document_id)

        # 1. INSERT con task_type='extract' e payload col document_id + lingua default
        mock_repo.create.assert_awaited_once()
        kwargs = mock_repo.create.call_args.kwargs
        assert kwargs["owner_id"] == owner_id
        assert kwargs["task_type"] == "extract"
        assert kwargs["payload"] == {"document_id": str(document_id), "language": "it"}

        # 2. Enqueue: solo task_id come arg (il document_id vive nella riga DB)
        assert len(captured_enqueues) == 1
        enq = captured_enqueues[0]["kwargs"]
        assert enq["task_id"] == str(task.id)
        assert enq["args"] == [str(task.id)]
        assert enq["queue"] == "echomind.default"

        assert result is task

    @pytest.mark.asyncio
    async def test_enqueue_failure_raises(
        self,
        service: TaskService,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Broker giu': apply_async solleva --> TaskEnqueueError (la request fa rollback)."""
        from echomind.worker.tasks.extract import extract_task

        mock_repo.create.return_value = _make_task()

        def _boom(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("broker unreachable")

        monkeypatch.setattr(extract_task, "apply_async", _boom)

        with pytest.raises(TaskEnqueueError):
            await service.enqueue_extract(owner_id=uuid4(), document_id=uuid4())


# =============================================================================
# get_task / list_tasks
# =============================================================================
class TestReadOperations:
    @pytest.mark.asyncio
    async def test_get_returns_task(self, service: TaskService, mock_repo: AsyncMock) -> None:
        task = _make_task()
        mock_repo.get_by_id.return_value = task

        result = await service.get_task(task_id=task.id)
        assert result is task

    @pytest.mark.asyncio
    async def test_get_raises_not_found(self, service: TaskService, mock_repo: AsyncMock) -> None:
        mock_repo.get_by_id.return_value = None

        with pytest.raises(TaskNotFoundError):
            await service.get_task(task_id=uuid4())

    @pytest.mark.asyncio
    async def test_list_delegates_to_repository(
        self, service: TaskService, mock_repo: AsyncMock
    ) -> None:
        tasks = [_make_task() for _ in range(3)]
        mock_repo.list_by_owner.return_value = tasks

        result = await service.list_tasks(owner_id=uuid4(), limit=10, offset=0)

        assert result == tasks
        mock_repo.list_by_owner.assert_awaited_once()
