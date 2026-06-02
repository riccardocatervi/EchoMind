"""`Embedder`: calcola gli embedding di una lista di testi.

Usato dalla pipeline per la deduplicazione semantica delle entita' (similarita'
coseno) e per persistere gli embedding su pgvector (fondamenta RAG, M8). Protocol
per testabilita': i test iniettano un embedder finto e deterministico.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    """Mappa una lista di testi nei rispettivi vettori di embedding."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...
