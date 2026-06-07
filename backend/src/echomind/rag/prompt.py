"""Costruttori di prompt per il RAG (M8).

Due funzioni pure (niente side effects, niente I/O):
  - `build_context_text`: formatta il `RetrievedContext` come testo strutturato.
  - `build_system_prompt`: system instruction che vincola lingua e comportamento.

Design del formato testo:
  - Sezione ENTITA': ID + nome + tipo + descrizione.
    L'ID e' incluso in modo che il modello possa compilare correttamente il campo
    `entity_id` delle citazioni.
  - Sezione RELAZIONI: nome sorgente --> nome destinazione + tipo + descrizione.
  - Sezione PANORAMICA: opzionale, aggiunge contesto documentale di alto livello.

Il formato e' human-readable e chunked: il modello riceve un testo strutturato
invece di JSON grezzo, il che migliora la qualita' delle citazioni.
"""

from __future__ import annotations

from echomind.core.language import language_name
from echomind.rag.schema import RetrievedContext


def build_context_text(context: RetrievedContext) -> str:
    """Formatta il contesto recuperato come testo strutturato per l'LLM.

    Output di esempio:
        ENTITA':
          [a1b2...] Nome (TIPO): Descrizione dell'entita'.
          ...

        RELAZIONI:
          [NomeSrc] --[TIPO_REL]--> [NomeTgt]: Descrizione.
          ...

        PANORAMICA:
        Breve panoramica del documento...
    """
    parts: list[str] = []

    if context.entities:
        parts.append("ENTITA':")
        for e in context.entities:
            desc = f": {e.description}" if e.description else ""
            parts.append(f"  [{e.id}] {e.name} ({e.type}){desc}")

    if context.relations:
        entity_name: dict[object, str] = {e.id: e.name for e in context.entities}
        parts.append("\nRELAZIONI:")
        for r in context.relations:
            src = entity_name.get(r.source_id, str(r.source_id))
            tgt = entity_name.get(r.target_id, str(r.target_id))
            desc = f": {r.description}" if r.description else ""
            parts.append(f"  [{src}] --[{r.type}]--> [{tgt}]{desc}")

    if context.summary_overview:
        parts.append(f"\nPANORAMICA:\n{context.summary_overview}")

    return "\n".join(parts)


def build_system_prompt(language: str) -> str:
    """System instruction che vincola lingua di output e comportamento del modello.

    Regole chiave:
      - Rispondere SOLO con le informazioni presenti nel contesto (no hallucination).
      - Dichiarare esplicitamente se il contesto e' insufficiente.
      - Citare le entita' usate (campo `citations` dello structured output).
      - Scrivere in `language` (nome esteso, es. "Italian", "English").
    """
    name = language_name(language)
    return (
        "Sei un assistente di analisi documentale. "
        "Rispondi alla domanda dell'utente basandoti ESCLUSIVAMENTE sulle informazioni "
        "contenute nel contesto fornito (sezioni ENTITA', RELAZIONI, PANORAMICA). "
        f"Scrivi la risposta in {name}. "
        "Per ogni affermazione popola il campo `citations` con le entita' del contesto "
        "che la supportano, copiando esattamente `entity_id`, `name` e `type` dal contesto. "
        "Se il contesto non contiene informazioni sufficienti per rispondere, dichiaralo "
        "esplicitamente nella risposta e lascia `citations` vuoto. "
        "Non inventare fatti, nomi o relazioni assenti dal contesto."
    )
