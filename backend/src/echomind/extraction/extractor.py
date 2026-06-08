"""`GraphExtractor`: estrae entita' + relazioni da un chunk (structured output).

Protocol (interfaccia strutturale): la pipeline dipende da QUESTO, non dal client
Gemini concreto. Vantaggi identici al `Transcriber` di M4:
- testabilita': i test iniettano un extractor finto, niente rete ne' API key;
- sostituibilita': domani un altro LLM senza toccare la pipeline.

L'implementazione reale (Gemini) e' in `extraction/gemini.py` (CP6). Sincrono di
proposito: il worker invoca l'intera pipeline via `asyncio.to_thread` (come M4).
"""

from __future__ import annotations

from typing import Protocol

from echomind.extraction.schema import ChunkGraph


class GraphExtractor(Protocol):
    """Estrae il grafo (entita' + relazioni) da un singolo chunk di testo.

    `language` e' la lingua di OUTPUT (codice it/en): nomi e descrizioni vengono
    scritti in quella lingua a prescindere dalla lingua del documento.
    """

    def extract(self, text: str, *, language: str) -> ChunkGraph: ...
