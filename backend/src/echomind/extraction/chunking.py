"""Chunking del testo per l'estrazione: finestre di caratteri con overlap.

Perche': i transcript lunghi superano il context utile dell'LLM e degradano
qualita' e costi. Spezziamo in finestre con un piccolo overlap che preserva il
contesto ai confini -- un'entita' a cavallo di due chunk non si perde. Puro e
deterministico.
"""

from __future__ import annotations


def chunk_text(text: str, *, max_chars: int, overlap: int = 0) -> list[str]:
    """Spezza `text` in finestre di al piu' `max_chars`, con `overlap` caratteri
    condivisi tra finestre consecutive.

    Args:
        text: il testo da spezzare.
        max_chars: dimensione massima di una finestra (> 0).
        overlap: caratteri sovrapposti tra finestre (0 <= overlap < max_chars;
            valori incoerenti vengono trattati come 0).

    Returns:
        Lista di chunk in ordine. `[]` se il testo e' vuoto; `[text]` se entra in
        una sola finestra.
    """
    if max_chars <= 0:
        raise ValueError("max_chars deve essere > 0")
    if not 0 <= overlap < max_chars:
        overlap = 0

    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]

    step = max_chars - overlap
    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(start + max_chars, length)
        chunks.append(cleaned[start:end])
        if end == length:
            break
        start += step
    return chunks
