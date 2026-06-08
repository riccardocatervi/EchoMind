"""Test dei modelli Summary + EntityEmbedding (metadata dichiarati, niente DB).

Verifica statica: nomi tabella/colonne, nullabilita', FK CASCADE, UNIQUE su
summaries.document_id (abilita upsert), dimensione del vettore pgvector.
"""

from __future__ import annotations

from sqlalchemy import inspect

from echomind.db.base import Base
from echomind.db.models import EntityEmbedding, Summary
from echomind.db.models.embedding import EMBEDDING_DIM


# =============================================================================
# Summary
# =============================================================================
def test_summary_registered_on_metadata() -> None:
    assert "summaries" in Base.metadata.tables


def test_summary_columns_match_design() -> None:
    columns = {col.key for col in inspect(Summary).columns}
    assert columns == {
        "id",
        "document_id",
        "owner_id",
        "overview",
        "sections",
        "meta",
        "created_at",
        "updated_at",
    }


def test_summary_nullable_constraints() -> None:
    mapper = inspect(Summary)
    for required in ("id", "document_id", "owner_id", "overview", "sections", "meta"):
        assert mapper.columns[required].nullable is False


def test_summary_document_id_is_unique() -> None:
    """UNIQUE su document_id: 1:1 + abilita ON CONFLICT (upsert)."""
    assert Base.metadata.tables["summaries"].c["document_id"].unique is True


def test_summary_fks_cascade() -> None:
    table = Base.metadata.tables["summaries"]
    doc_fk = next(fk for fk in table.foreign_keys if fk.column.table.name == "documents")
    owner_fk = next(fk for fk in table.foreign_keys if fk.column.table.name == "profiles")
    assert doc_fk.ondelete == "CASCADE"
    assert owner_fk.ondelete == "CASCADE"


# =============================================================================
# EntityEmbedding
# =============================================================================
def test_embedding_registered_on_metadata() -> None:
    assert "entity_embeddings" in Base.metadata.tables


def test_embedding_columns_match_design() -> None:
    columns = {col.key for col in inspect(EntityEmbedding).columns}
    assert columns == {
        "id",
        "document_id",
        "owner_id",
        "entity_id",
        "name",
        "embedding",
        "created_at",
    }


def test_embedding_has_no_updated_at() -> None:
    """Righe immutabili (replace-by-document): niente trigger/updated_at."""
    assert "updated_at" not in {col.key for col in inspect(EntityEmbedding).columns}


def test_embedding_vector_dimension_matches_constant() -> None:
    column = Base.metadata.tables["entity_embeddings"].c["embedding"]
    assert column.type.dim == EMBEDDING_DIM  # type: ignore[attr-defined]
    assert EMBEDDING_DIM == 768


def test_embedding_fks_cascade() -> None:
    table = Base.metadata.tables["entity_embeddings"]
    doc_fk = next(fk for fk in table.foreign_keys if fk.column.table.name == "documents")
    owner_fk = next(fk for fk in table.foreign_keys if fk.column.table.name == "profiles")
    assert doc_fk.ondelete == "CASCADE"
    assert owner_fk.ondelete == "CASCADE"
