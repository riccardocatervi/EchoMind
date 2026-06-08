"""Schemi HTTP per il RAG (M8) -- boundary tra API e service layer.

Separati da `rag/schema.py` (tipi di dominio interni) per due motivi:
  1. `AskRequest`/`AskResponse` sono schemi HTTP (Pydantic v2, serializzazione
     JSON, validazione input): non devono essere importati dal service layer.
  2. `CitationRead` e' una proiezione pubblica di `Citation` (rag/schema.py):
     consente di aggiungere campi futuri (es. excerpt) senza toccare lo
     structured output LLM.

Vincoli:
  - `question` ha min_length=1 e max_length corrispondente a `rag_max_question_chars`
    (default 2000). La costante qui rispecchia il default di config: se si modifica
    il limite, aggiornare entrambi.
  - `citations` e' una lista vuota di default: la risposta rimane valida anche
    quando il contesto non contiene entita' rilevanti.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Limite massimo caratteri della domanda: deve combaciare con il default di
# Settings.rag_max_question_chars in core/config.py.
_MAX_QUESTION_CHARS: int = 2000


class AskRequest(BaseModel):
    """Corpo della POST /documents/{id}/ask."""

    question: str = Field(
        min_length=1,
        max_length=_MAX_QUESTION_CHARS,
        description=(
            f"Domanda sul contenuto del documento (1-{_MAX_QUESTION_CHARS} caratteri). "
            "La risposta viene generata nella lingua indicata dall'header Accept-Language."
        ),
    )


class CitationRead(BaseModel):
    """Entita' del grafo citata come fonte nella risposta RAG."""

    entity_id: str = Field(description="ID UUID (stringa) dell'entita' citata.")
    name: str = Field(description="Nome dell'entita' nel grafo.")
    type: str = Field(description="Tipo dell'entita' (es. PERSON, LOCATION, CONCEPT).")


class AskResponse(BaseModel):
    """Risposta dell'endpoint /ask: testo in linguaggio naturale + citazioni."""

    answer: str = Field(description="Risposta completa alla domanda, nella lingua richiesta.")
    citations: list[CitationRead] = Field(
        default_factory=list,
        description=(
            "Entita' del grafo usate come fonte. Vuota se il contesto non contiene "
            "informazioni sufficienti o se la domanda non richiede citazioni specifiche."
        ),
    )
