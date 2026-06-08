"""Knowledge extraction (M5): transcript --> grafo + riassunto + embeddings.

Pipeline PURA (chunking, dedup, community detection, orchestrazione) + i Protocol
degli adapter (`GraphExtractor`, `Embedder`, `Summarizer`). Le implementazioni reali
basate su Gemini vivono in `extraction/gemini.py` (CP6). Stessa filosofia di
`processing` (M4): logica testabile con fake, adapter esterni iniettati.
"""

from echomind.extraction.chunking import chunk_text
from echomind.extraction.community import detect_communities
from echomind.extraction.dedup import (
    EmbeddedEntity,
    MergedEntity,
    collapse_exact_duplicates,
    merge_entities,
    normalize_name,
)
from echomind.extraction.embedder import Embedder
from echomind.extraction.errors import EmbeddingError, ExtractionError, LLMError
from echomind.extraction.extractor import GraphExtractor
from echomind.extraction.pipeline import ExtractionResult, extract_knowledge
from echomind.extraction.schema import (
    ChunkGraph,
    DocumentSummary,
    Entity,
    EntityVector,
    ExtractedEntity,
    ExtractedRelation,
    Relation,
    SummarySection,
)
from echomind.extraction.summarize import Summarizer

__all__ = [
    "ChunkGraph",
    "DocumentSummary",
    "EmbeddedEntity",
    "Embedder",
    "EmbeddingError",
    "Entity",
    "EntityVector",
    "ExtractedEntity",
    "ExtractedRelation",
    "ExtractionError",
    "ExtractionResult",
    "GraphExtractor",
    "LLMError",
    "MergedEntity",
    "Relation",
    "Summarizer",
    "SummarySection",
    "chunk_text",
    "collapse_exact_duplicates",
    "detect_communities",
    "extract_knowledge",
    "merge_entities",
    "normalize_name",
]
