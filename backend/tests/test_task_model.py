"""Test del modello Task (metadata + schema dichiarato).

Verifica statica (niente DB): nomi tabella/colonne, nullabilita', tipo ENUM
dello status, task_type come TEXT, FK CASCADE, naming convention.
"""

from __future__ import annotations

from sqlalchemy import inspect

from echomind.db.base import Base
from echomind.db.models import Task, TaskStatus, TaskType
from echomind.db.models.task import TERMINAL_STATUSES


def test_task_is_registered_on_metadata() -> None:
    assert "tasks" in Base.metadata.tables


def test_task_tablename() -> None:
    assert Task.__tablename__ == "tasks"


def test_task_columns_match_design() -> None:
    """Tutte e 12 le colonne previste sono mappate."""
    mapper = inspect(Task)
    columns = {col.key for col in mapper.columns}
    expected = {
        "id",
        "owner_id",
        "task_type",
        "status",
        "payload",
        "result",
        "error",
        "retries",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    }
    assert columns == expected


def test_task_nullable_constraints() -> None:
    """Nullable: result, error, started_at, finished_at. Tutto il resto NOT NULL."""
    mapper = inspect(Task)
    assert mapper.columns["id"].nullable is False
    assert mapper.columns["owner_id"].nullable is False
    assert mapper.columns["task_type"].nullable is False
    assert mapper.columns["status"].nullable is False
    assert mapper.columns["payload"].nullable is False
    assert mapper.columns["retries"].nullable is False
    assert mapper.columns["created_at"].nullable is False
    assert mapper.columns["updated_at"].nullable is False
    # Opzionali
    assert mapper.columns["result"].nullable is True
    assert mapper.columns["error"].nullable is True
    assert mapper.columns["started_at"].nullable is True
    assert mapper.columns["finished_at"].nullable is True


def test_task_status_uses_enum_type() -> None:
    """status mappato all'ENUM PostgreSQL `task_status`."""
    from sqlalchemy import Enum as SQLEnum

    mapper = inspect(Task)
    status_col = mapper.columns["status"]
    assert isinstance(status_col.type, SQLEnum)
    assert status_col.type.name == "task_status"


def test_task_type_is_plain_text_not_enum() -> None:
    """task_type e' TEXT (insieme in crescita), non un ENUM."""
    from sqlalchemy import Enum as SQLEnum

    mapper = inspect(Task)
    type_col = mapper.columns["task_type"]
    assert not isinstance(type_col.type, SQLEnum)


def test_task_status_enum_values() -> None:
    """L'Enum Python ha esattamente i 4 valori del DDL (lowercase)."""
    assert {s.value for s in TaskStatus} == {"queued", "running", "succeeded", "failed"}


def test_task_type_enum_values() -> None:
    """In M3 esiste solo il tipo 'echo'."""
    assert {t.value for t in TaskType} == {"echo"}


def test_terminal_statuses() -> None:
    """Gli stati terminali sono succeeded + failed (usati per l'idempotenza)."""
    assert frozenset({TaskStatus.SUCCEEDED, TaskStatus.FAILED}) == TERMINAL_STATUSES


def test_task_owner_fk_cascades() -> None:
    """FK owner_id --> profiles ON DELETE CASCADE."""
    fk = next(iter(Base.metadata.tables["tasks"].foreign_keys))
    assert fk.column.table.name == "profiles"
    assert fk.ondelete == "CASCADE"


def test_task_naming_convention_pk_fk() -> None:
    table = Base.metadata.tables["tasks"]
    assert table.primary_key.name == "pk_tasks"
    fk_names = {str(c.name) for c in table.constraints if c.name and "fk_" in str(c.name)}
    assert "fk_tasks_owner_id_profiles" in fk_names


def test_task_repr_does_not_explode_on_unset_fields() -> None:
    task = Task()
    rendered = repr(task)
    assert "Task(" in rendered
