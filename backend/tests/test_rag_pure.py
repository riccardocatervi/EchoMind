"""Test puri del pacchetto rag/ (M8, CP6).

"Puri" = nessun DB, nessun Gemini, nessuna rete. Coprono:
  - `build_context_text`: formattazione del contesto (entita', relazioni, panoramica).
  - `build_system_prompt`: la lingua corretta appare nel prompt.
  - `RagAnswer` / `Citation`: validazione Pydantic dello structured output.
  - `RetrievedContext`: costruzione e accesso ai campi.
  - Conformita' strutturale di un `_FakeRagAnswerer` al Protocol `RagAnswerer`.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from echomind.extraction.schema import Entity, Relation
from echomind.rag.answerer import RagAnswerer
from echomind.rag.prompt import build_context_text, build_system_prompt
from echomind.rag.schema import Citation, RagAnswer, RetrievedContext


# =============================================================================
# Helpers
# =============================================================================
def _make_entity(name: str, typ: str = "CONCEPT", desc: str = "") -> Entity:
    return Entity(id=uuid4(), name=name, type=typ, description=desc)


def _make_relation(src: Entity, tgt: Entity, rel_type: str, desc: str = "") -> Relation:
    return Relation(source_id=src.id, target_id=tgt.id, type=rel_type, description=desc)


# =============================================================================
# build_context_text
# =============================================================================
def test_build_context_text_empty_context() -> None:
    """Contesto vuoto (nessuna entita', nessuna relazione, nessuna panoramica)."""
    ctx = RetrievedContext()
    text = build_context_text(ctx)
    assert text == ""


def test_build_context_text_entities_only() -> None:
    """Solo entita': la sezione ENTITA' appare, nessuna sezione RELAZIONI."""
    e = _make_entity("Mario Rossi", "PERSON", "Protagonista del racconto.")
    ctx = RetrievedContext(entities=[e])
    text = build_context_text(ctx)

    assert "ENTITA'" in text
    assert "Mario Rossi" in text
    assert "PERSON" in text
    assert "Protagonista del racconto." in text
    assert str(e.id) in text
    assert "RELAZIONI" not in text


def test_build_context_text_relations_include_source_target_names() -> None:
    """Le relazioni usano i NOMI delle entita' (non gli UUID) per sorgente/destinazione."""
    e1 = _make_entity("Roma", "LOCATION")
    e2 = _make_entity("Italia", "LOCATION")
    rel = _make_relation(e1, e2, "PARTE_DI", "Roma e' la capitale d'Italia.")
    ctx = RetrievedContext(entities=[e1, e2], relations=[rel])
    text = build_context_text(ctx)

    assert "RELAZIONI" in text
    # Nomi visibili nella sezione relazioni
    assert "Roma" in text
    assert "Italia" in text
    assert "PARTE_DI" in text
    assert "Roma e' la capitale d'Italia." in text


def test_build_context_text_summary_overview_included() -> None:
    """La panoramica appare come sezione PANORAMICA separata."""
    ctx = RetrievedContext(summary_overview="Questo e' un testo di prova sull'Italia.")
    text = build_context_text(ctx)

    assert "PANORAMICA" in text
    assert "Questo e' un testo di prova sull'Italia." in text


def test_build_context_text_full_context() -> None:
    """Contesto completo: tutte le sezioni presenti nell'ordine corretto."""
    e1 = _make_entity("Dante", "PERSON", "Poeta italiano.")
    e2 = _make_entity("Firenze", "LOCATION", "Citta' natale di Dante.")
    rel = _make_relation(e1, e2, "NATO_A")
    ctx = RetrievedContext(
        entities=[e1, e2],
        relations=[rel],
        summary_overview="La Divina Commedia e' il capolavoro di Dante Alighieri.",
    )
    text = build_context_text(ctx)

    ent_pos = text.index("ENTITA'")
    rel_pos = text.index("RELAZIONI")
    pan_pos = text.index("PANORAMICA")
    # Ordine: ENTITA' --> RELAZIONI --> PANORAMICA
    assert ent_pos < rel_pos < pan_pos


def test_build_context_text_relation_with_unknown_ids_falls_back_to_uuid() -> None:
    """Se l'entita' sorgente/destinazione non e' nel contesto, si usa l'UUID."""
    orphan_id = uuid4()
    e = _make_entity("Dante", "PERSON")
    rel = Relation(source_id=orphan_id, target_id=e.id, type="CONOSCE", description="")
    # Solo e in context, orphan non c'e'
    ctx = RetrievedContext(entities=[e], relations=[rel])
    text = build_context_text(ctx)

    assert str(orphan_id) in text  # fallback all'UUID
    assert "Dante" in text


# =============================================================================
# build_system_prompt
# =============================================================================
def test_build_system_prompt_contains_italian() -> None:
    """Per la lingua 'it' il prompt deve contenere 'Italian'."""
    prompt = build_system_prompt("it")
    assert "Italian" in prompt


def test_build_system_prompt_contains_english() -> None:
    """Per la lingua 'en' il prompt deve contenere 'English'."""
    prompt = build_system_prompt("en")
    assert "English" in prompt


def test_build_system_prompt_unknown_language_defaults() -> None:
    """Una lingua sconosciuta non solleva eccezioni (language_name ha un default)."""
    prompt = build_system_prompt("zz")
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_build_system_prompt_instructs_no_hallucination() -> None:
    """Il prompt deve vietare esplicitamente l'invenzione di fatti non nel contesto."""
    prompt = build_system_prompt("it")
    # Qualsiasi formulazione che vieti di inventare
    text_lower = prompt.lower()
    assert "non inventare" in text_lower or "esclusivamente" in text_lower


# =============================================================================
# RagAnswer e Citation (validazione Pydantic)
# =============================================================================
def test_rag_answer_valid() -> None:
    """RagAnswer si costruisce con campi validi."""
    ans = RagAnswer(
        answer="Dante e' nato a Firenze.",
        citations=[Citation(entity_id=str(uuid4()), name="Dante", type="PERSON")],
    )
    assert ans.answer == "Dante e' nato a Firenze."
    assert len(ans.citations) == 1
    assert ans.citations[0].name == "Dante"


def test_rag_answer_empty_citations_default() -> None:
    """Le citazioni sono facoltative (default: lista vuota)."""
    ans = RagAnswer(answer="Non ho informazioni sufficienti.")
    assert ans.citations == []


def test_rag_answer_json_round_trip() -> None:
    """RagAnswer sopravvive a serializzazione + deserializzazione JSON."""
    original = RagAnswer(
        answer="Risposta di test.",
        citations=[
            Citation(entity_id="abc-123", name="Entita'", type="CONCEPT"),
        ],
    )
    json_str = original.model_dump_json()
    restored = RagAnswer.model_validate_json(json_str)
    assert restored.answer == original.answer
    assert restored.citations[0].entity_id == "abc-123"


def test_citation_fields() -> None:
    """Citation ha i tre campi obbligatori: entity_id, name, type."""
    c = Citation(entity_id="uuid-placeholder", name="Firenze", type="LOCATION")
    assert c.entity_id == "uuid-placeholder"
    assert c.name == "Firenze"
    assert c.type == "LOCATION"


# =============================================================================
# RetrievedContext
# =============================================================================
def test_retrieved_context_defaults() -> None:
    """RetrievedContext ha valori di default per tutti i campi."""
    ctx = RetrievedContext()
    assert ctx.entities == []
    assert ctx.relations == []
    assert ctx.summary_overview is None


def test_retrieved_context_with_data() -> None:
    """RetrievedContext accetta entita' e relazioni."""
    e = _make_entity("Test")
    ctx = RetrievedContext(entities=[e], summary_overview="Panoramica.")
    assert len(ctx.entities) == 1
    assert ctx.summary_overview == "Panoramica."


# =============================================================================
# Conformita' strutturale FakeRagAnswerer al Protocol
# =============================================================================
class _FakeRagAnswerer:
    """Fake minimo che implementa il Protocol RagAnswerer."""

    async def answer(
        self,
        *,
        question: str,
        context: RetrievedContext,
        language: str,
    ) -> RagAnswer:
        return RagAnswer(answer=f"Risposta fake a: {question}", citations=[])


@pytest.mark.asyncio
async def test_fake_rag_answerer_conforms_to_protocol() -> None:
    """_FakeRagAnswerer restituisce un RagAnswer valido (conformita' al Protocol)."""
    fake: RagAnswerer = _FakeRagAnswerer()
    result = await fake.answer(
        question="Chi e' Dante?",
        context=RetrievedContext(),
        language="it",
    )
    assert isinstance(result, RagAnswer)
    assert "Dante" in result.answer
    assert result.citations == []


@pytest.mark.asyncio
async def test_fake_rag_answerer_propagates_question() -> None:
    """Il fake include la domanda nella risposta (utile per asserzioni nei test di servizio)."""
    fake = _FakeRagAnswerer()
    question = "Dove si trova Roma?"
    result = await fake.answer(question=question, context=RetrievedContext(), language="en")
    assert question in result.answer


@pytest.mark.asyncio
async def test_fake_rag_answerer_works_with_full_context() -> None:
    """Il fake non solleva eccezioni con un contesto pieno."""
    e1 = _make_entity("Roma", "LOCATION")
    e2 = _make_entity("Italia", "LOCATION")
    rel = _make_relation(e1, e2, "PARTE_DI")
    ctx = RetrievedContext(
        entities=[e1, e2],
        relations=[rel],
        summary_overview="Testo di prova.",
    )
    fake = _FakeRagAnswerer()
    result = await fake.answer(question="Dove si trova Roma?", context=ctx, language="it")
    assert isinstance(result, RagAnswer)
