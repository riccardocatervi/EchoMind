"""`Summarizer`: produce un riassunto multilivello (overview + sezioni) dai chunk.

L'implementazione reale (Gemini, CP6) fa map-reduce: riassume ogni chunk, poi
sintetizza una panoramica e le sezioni tematiche. Protocol per testabilita'.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from echomind.extraction.schema import DocumentSummary


class Summarizer(Protocol):
    """Riassume i chunk di un documento in un `DocumentSummary` multilivello."""

    def summarize(self, chunks: Sequence[str]) -> DocumentSummary: ...
