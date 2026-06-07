"""Tipi di dominio del RAG (M8).

Due famiglie, come in `extraction/schema.py`:

- **dataclass di dominio** (`RetrievedContext`): il contesto assemblato dal servizio RAG
  prima di chiamare l'LLM. Immutabile, indipendente dall'LLM.

- **Pydantic** (`Citation`, `RagAnswer`): structured output dell'LLM. Passati a Gemini
  come `response_schema` --> JSON valido e tipizzato. Le `description` dei Field guidano
  il modello nella compilazione dei campi.

Nota su `entity_id` in `Citation`: e' `str` (non `UUID`) perche' Gemini restituisce
stringhe. Il servizio (CP7) esegue la conversione `str -> UUID` con validazione.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from echomind.extraction.schema import Entity, Relation


# -----------------------------------------------------------------------------
# Dominio: contesto recuperato dal retrieval (pgvector + Neo4j)
# -----------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RetrievedContext:
    """Contesto assemblato prima di interrogare l'LLM.

    `entities` e `relations` provengono da `get_neighborhood` (Neo4j).
    `summary_overview` e' aggiunto opzionalmente per arricchire il contesto
    con la panoramica del documento estratta in fase di elaborazione.
    """

    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    summary_overview: str | None = None


# -----------------------------------------------------------------------------
# Structured output LLM (Gemini riempie questi schemi)
# -----------------------------------------------------------------------------
class Citation(BaseModel):
    """Entita' del contesto citata come fonte nella risposta RAG."""

    entity_id: str = Field(
        description=(
            "ID UUID (stringa) dell'entita' citata, copiato esattamente dal contesto fornito."
        )
    )
    name: str = Field(description="Nome dell'entita' citata, copiato dal contesto.")
    type: str = Field(description="Tipo dell'entita' citata, copiato dal contesto.")


class RagAnswer(BaseModel):
    """Risposta strutturata alla domanda dell'utente (structured output Gemini)."""

    answer: str = Field(
        description=(
            "Risposta completa alla domanda, basata ESCLUSIVAMENTE sulle informazioni "
            "del contesto fornito. Se il contesto non e' sufficiente, dichiaralo."
        )
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description=(
            "Elenco delle entita' del contesto usate come fonte per la risposta. "
            "Ometti entita' non rilevanti."
        ),
    )
