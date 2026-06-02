"""Tipi dell'estrazione: structured output dell'LLM + dataclass di dominio.

Due famiglie nettamente separate:

- **Pydantic** (`ChunkGraph`, `DocumentSummary`, ...): cio' che l'LLM RIEMPIE.
  Passati a Gemini come `response_schema` --> il modello restituisce JSON valido e
  tipizzato (niente parsing fragile di testo libero). Le `description` dei Field
  guidano l'estrazione.

- **dataclass di dominio** (`Entity`, `Relation`, `EntityVector`): il grafo FINALE,
  dopo dedup + assegnazione degli id + community detection. Immutabili, pure,
  indipendenti dall'LLM. Sono cio' che il worker persiste (Neo4j + Postgres).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Structured output dell'LLM (Gemini riempie questi schemi)
# -----------------------------------------------------------------------------
class ExtractedEntity(BaseModel):
    """Un'entita' estratta da un chunk (nome + categoria + descrizione)."""

    name: str = Field(
        description="Nome dell'entita' (concetto, persona, organizzazione, luogo...)."
    )
    type: str = Field(description="Categoria, es. PERSON, ORGANIZATION, CONCEPT, LOCATION, EVENT.")
    description: str = Field(default="", description="Breve descrizione dell'entita' nel contesto.")


class ExtractedRelation(BaseModel):
    """Una relazione diretta tra due entita' (per nome)."""

    source: str = Field(description="Nome dell'entita' di partenza.")
    target: str = Field(description="Nome dell'entita' di arrivo.")
    type: str = Field(description="Tipo di relazione, es. works_at, part_of, causes, related_to.")
    description: str = Field(default="", description="Breve descrizione della relazione.")


class ChunkGraph(BaseModel):
    """Output dell'estrazione su UN chunk: entita' + relazioni."""

    entities: list[ExtractedEntity] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)


class SummarySection(BaseModel):
    """Una sezione tematica del riassunto multilivello."""

    title: str = Field(description="Titolo breve della sezione tematica.")
    content: str = Field(description="Riassunto della sezione.")


class DocumentSummary(BaseModel):
    """Riassunto multilivello: una panoramica + sezioni di dettaglio."""

    overview: str = Field(description="Panoramica complessiva del documento, un paragrafo.")
    sections: list[SummarySection] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Dominio: il grafo finale (dopo dedup + id + community)
# -----------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Entity:
    """Nodo :Entity del grafo, con id stabile e community assegnata."""

    id: UUID
    name: str
    type: str
    description: str
    community: int | None = None


@dataclass(frozen=True, slots=True)
class Relation:
    """Arco :RELATES del grafo, per id (non piu' per nome)."""

    source_id: UUID
    target_id: UUID
    type: str
    description: str


@dataclass(frozen=True, slots=True)
class EntityVector:
    """Embedding di un'entita' canonica, pronto per la persistenza pgvector."""

    entity_id: UUID
    name: str
    vector: list[float]
