"""Test del modello Transcript (metadata + schema dichiarato).

Verifica statica (niente DB): nomi tabella/colonne, nullabilita', FK CASCADE
(document_id, owner_id), UNIQUE su document_id (abilita l'upsert), enum SourceType,
naming convention.
"""

from __future__ import annotations

from sqlalchemy import inspect

from echomind.db.base import Base
from echomind.db.models import SourceType, Transcript


def test_transcript_is_registered_on_metadata() -> None:
    assert "transcripts" in Base.metadata.tables


def test_transcript_tablename() -> None:
    assert Transcript.__tablename__ == "transcripts"


def test_transcript_columns_match_design() -> None:
    """Tutte e 10 le colonne previste sono mappate."""
    mapper = inspect(Transcript)
    columns = {col.key for col in mapper.columns}
    expected = {
        "id",
        "document_id",
        "owner_id",
        "source_type",
        "content",
        "language",
        "char_count",
        "meta",
        "created_at",
        "updated_at",
    }
    assert columns == expected


def test_transcript_nullable_constraints() -> None:
    """Nullable solo `language`. Tutto il resto NOT NULL."""
    mapper = inspect(Transcript)
    assert mapper.columns["id"].nullable is False
    assert mapper.columns["document_id"].nullable is False
    assert mapper.columns["owner_id"].nullable is False
    assert mapper.columns["source_type"].nullable is False
    assert mapper.columns["content"].nullable is False
    assert mapper.columns["char_count"].nullable is False
    assert mapper.columns["meta"].nullable is False
    assert mapper.columns["created_at"].nullable is False
    assert mapper.columns["updated_at"].nullable is False
    # Unico opzionale
    assert mapper.columns["language"].nullable is True


def test_source_type_is_plain_text_not_enum() -> None:
    """source_type e' TEXT (insieme validato lato app), non un ENUM Postgres."""
    from sqlalchemy import Enum as SQLEnum

    mapper = inspect(Transcript)
    assert not isinstance(mapper.columns["source_type"].type, SQLEnum)


def test_source_type_enum_values() -> None:
    """SourceType ha esattamente i due valori previsti (lowercase)."""
    assert {s.value for s in SourceType} == {"document", "audio"}


def test_document_id_is_unique() -> None:
    """UNIQUE su document_id: relazione 1:1 + abilita ON CONFLICT (upsert)."""
    column = Base.metadata.tables["transcripts"].c["document_id"]
    assert column.unique is True


def test_document_fk_cascades() -> None:
    """FK document_id --> documents ON DELETE CASCADE."""
    table = Base.metadata.tables["transcripts"]
    fk = next(fk for fk in table.foreign_keys if fk.column.table.name == "documents")
    assert fk.ondelete == "CASCADE"


def test_owner_fk_cascades() -> None:
    """FK owner_id --> profiles ON DELETE CASCADE."""
    table = Base.metadata.tables["transcripts"]
    fk = next(fk for fk in table.foreign_keys if fk.column.table.name == "profiles")
    assert fk.ondelete == "CASCADE"


def test_transcript_naming_convention_pk() -> None:
    table = Base.metadata.tables["transcripts"]
    assert table.primary_key.name == "pk_transcripts"


def test_transcript_repr_does_not_explode_on_unset_fields() -> None:
    transcript = Transcript()
    rendered = repr(transcript)
    assert "Transcript(" in rendered
