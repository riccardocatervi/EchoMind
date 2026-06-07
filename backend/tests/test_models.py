"""Test del modello Profile (metadata + schema dichiarato).

Non testiamo qui l'I/O contro Postgres (servirebbe DB attivo): quello
arriva nei test di integrazione una volta wirata Alembic.

Qui verifichiamo che lo schema dichiarato in Python sia coerente con
le aspettative: nomi tabella/colonne, tipi, vincoli.
"""

from __future__ import annotations

from sqlalchemy import inspect

from echomind.db.base import Base
from echomind.db.models import Document, DocumentStatus, Profile


def test_profile_is_registered_on_metadata() -> None:
    """Profile deve apparire nel metadata di Base (per Alembic autogen)."""
    assert "profiles" in Base.metadata.tables


def test_profile_tablename_is_plural_snake_case() -> None:
    """Convenzione SQL: tabelle plurali in snake_case."""
    assert Profile.__tablename__ == "profiles"


def test_profile_columns_match_design() -> None:
    """Verifica nomi e tipi delle colonne come da design (M1)."""
    mapper = inspect(Profile)
    columns = {col.key: col for col in mapper.columns}

    expected_keys = {"id", "display_name", "created_at", "updated_at"}
    assert set(columns.keys()) == expected_keys


def test_profile_primary_key_is_id() -> None:
    """id è PK (singolo, non composto)."""
    mapper = inspect(Profile)
    pk_cols = [col.key for col in mapper.primary_key]
    assert pk_cols == ["id"]


def test_profile_id_is_not_nullable() -> None:
    """id è il PK → mai NULL."""
    mapper = inspect(Profile)
    assert mapper.columns["id"].nullable is False


def test_profile_display_name_is_nullable() -> None:
    """display_name è opzionale (creazione just-in-time senza nome)."""
    mapper = inspect(Profile)
    assert mapper.columns["display_name"].nullable is True


def test_profile_timestamps_have_server_default() -> None:
    """created_at/updated_at devono avere default lato DB (non lato Python)."""
    mapper = inspect(Profile)
    assert mapper.columns["created_at"].server_default is not None
    assert mapper.columns["updated_at"].server_default is not None


def test_profile_naming_convention_for_pk() -> None:
    """La PK deve seguire la naming convention `pk_<table>`.

    `mapper.primary_key` ritorna una tupla di Column; per il nome del
    constraint dobbiamo passare per `Table.primary_key` (lì è un
    PrimaryKeyConstraint con attributo `name`).
    """
    pk_constraint = Base.metadata.tables["profiles"].primary_key
    assert pk_constraint.name == "pk_profiles"


def test_profile_repr_does_not_explode_on_unset_fields() -> None:
    """repr non deve sollevare anche se i campi non sono ancora settati."""
    profile = Profile()
    rendered = repr(profile)
    assert "Profile(" in rendered


# =============================================================================
# Document (M2)
# =============================================================================
def test_document_is_registered_on_metadata() -> None:
    assert "documents" in Base.metadata.tables


def test_document_tablename() -> None:
    assert Document.__tablename__ == "documents"


def test_document_columns_match_design() -> None:
    """Tutte e 10 le colonne previste sono mappate."""
    mapper = inspect(Document)
    columns = {col.key: col for col in mapper.columns}
    expected = {
        "id",
        "owner_id",
        "filename",
        "mime_type",
        "size_bytes",
        "storage_key",
        "status",
        "failure_reason",
        "created_at",
        "updated_at",
    }
    assert set(columns.keys()) == expected


def test_document_nullable_constraints() -> None:
    """Solo failure_reason è nullable. Tutto il resto NOT NULL."""
    mapper = inspect(Document)
    assert mapper.columns["id"].nullable is False
    assert mapper.columns["owner_id"].nullable is False
    assert mapper.columns["filename"].nullable is False
    assert mapper.columns["mime_type"].nullable is False
    assert mapper.columns["size_bytes"].nullable is False
    assert mapper.columns["storage_key"].nullable is False
    assert mapper.columns["status"].nullable is False
    assert mapper.columns["failure_reason"].nullable is True
    assert mapper.columns["created_at"].nullable is False
    assert mapper.columns["updated_at"].nullable is False


def test_document_storage_key_is_unique() -> None:
    """storage_key UNIQUE: previene B2 object collision."""
    mapper = inspect(Document)
    assert mapper.columns["storage_key"].unique is True


def test_document_status_uses_enum_type() -> None:
    """status mappato all'ENUM PostgreSQL `document_status`."""
    from sqlalchemy import Enum as SQLEnum

    mapper = inspect(Document)
    status_col = mapper.columns["status"]
    assert isinstance(status_col.type, SQLEnum)
    assert status_col.type.name == "document_status"


def test_document_status_enum_values() -> None:
    """L'Enum Python ha esattamente i 6 valori del DDL (pending/uploaded/transcribed/extracted/completed/failed)."""
    assert {s.value for s in DocumentStatus} == {
        "pending",
        "uploaded",
        "transcribed",
        "extracted",
        "completed",
        "failed",
    }


def test_document_owner_fk_cascades() -> None:
    """FK owner_id deve cancellare in CASCADE quando il profile sparisce."""
    fk = next(iter(Base.metadata.tables["documents"].foreign_keys))
    assert fk.column.table.name == "profiles"
    assert fk.ondelete == "CASCADE"


def test_document_naming_convention_pk_fk() -> None:
    """Verifica nomi deterministici di PK e FK (naming convention)."""
    table = Base.metadata.tables["documents"]
    assert table.primary_key.name == "pk_documents"
    # `constraint.name` può essere None o un sentinel; convertiamo a str safe.
    fk_names = {str(c.name) for c in table.constraints if c.name and "fk_" in str(c.name)}
    assert "fk_documents_owner_id_profiles" in fk_names


def test_document_repr_does_not_explode_on_unset_fields() -> None:
    document = Document()
    rendered = repr(document)
    assert "Document(" in rendered
