"""Test del modello Profile (metadata + schema dichiarato).

Non testiamo qui l'I/O contro Postgres (servirebbe DB attivo): quello
arriva nei test di integrazione una volta wirata Alembic.

Qui verifichiamo che lo schema dichiarato in Python sia coerente con
le aspettative: nomi tabella/colonne, tipi, vincoli.
"""

from __future__ import annotations

from sqlalchemy import inspect

from echomind.db.base import Base
from echomind.db.models import Profile


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
