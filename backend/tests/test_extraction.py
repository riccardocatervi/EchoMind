"""Test della pipeline di estrazione PURA (M5): chunking, dedup, community, orchestrazione.

Niente Gemini, niente Neo4j, niente DB: fake deterministici dei Protocol. Stessa
filosofia di test_processing.py (M4). I confini algoritmici si verificano qui; gli
adapter reali (Gemini/Neo4j) solo nello smoke.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

import pytest

from echomind.extraction import (
    ChunkGraph,
    DocumentSummary,
    EmbeddedEntity,
    ExtractedEntity,
    ExtractedRelation,
    LLMError,
    SummarySection,
    chunk_text,
    collapse_exact_duplicates,
    detect_communities,
    extract_knowledge,
    merge_entities,
)


# =============================================================================
# chunk_text
# =============================================================================
def test_chunk_text_empty_returns_empty() -> None:
    assert chunk_text("", max_chars=100) == []
    assert chunk_text("   \n\t  ", max_chars=100) == []


def test_chunk_text_single_chunk() -> None:
    assert chunk_text("ciao mondo", max_chars=100) == ["ciao mondo"]


def test_chunk_text_multiple_with_overlap() -> None:
    text = "abcdefghij" * 3  # 30 caratteri
    chunks = chunk_text(text, max_chars=10, overlap=2)
    assert len(chunks) == 4  # step 8: [0:10],[8:18],[16:26],[24:30]
    assert chunks[0] == text[:10]
    assert chunks[-1] == text[24:]
    assert all(len(c) <= 10 for c in chunks)


def test_chunk_text_overlap_ge_max_falls_back_to_zero() -> None:
    chunks = chunk_text("a" * 25, max_chars=10, overlap=10)  # overlap >= max --> 0
    assert chunks == ["a" * 10, "a" * 10, "a" * 5]


def test_chunk_text_rejects_non_positive_max() -> None:
    with pytest.raises(ValueError, match="max_chars"):
        chunk_text("x", max_chars=0)


# =============================================================================
# collapse_exact_duplicates
# =============================================================================
def test_collapse_merges_same_normalized_name_keeping_longest_description() -> None:
    entities = [
        ExtractedEntity(name="Turing", type="PERSON", description="breve"),
        ExtractedEntity(name="  turing ", type="PERSON", description="descrizione piu' lunga"),
    ]
    out = collapse_exact_duplicates(entities)
    assert len(out) == 1
    assert out[0].description == "descrizione piu' lunga"


def test_collapse_skips_empty_names() -> None:
    assert collapse_exact_duplicates([ExtractedEntity(name="   ", type="X")]) == []


# =============================================================================
# merge_entities (clustering coseno + rimappa relazioni)
# =============================================================================
def _embedded(
    name: str, vector: list[float], *, type_: str = "X", desc: str = ""
) -> EmbeddedEntity:
    return EmbeddedEntity(name=name, type=type_, description=desc, embedding=vector)


def test_merge_fuses_similar_and_remaps_relations() -> None:
    entities = [
        _embedded("Alan Turing", [1.0, 0.0, 0.0]),
        _embedded("Turing", [1.0, 0.0, 0.0]),  # coseno 1.0 --> stesso cluster
        _embedded("Computer", [0.0, 1.0, 0.0]),
    ]
    relations = [
        ExtractedRelation(source="Alan Turing", target="Computer", type="invented"),
        ExtractedRelation(source="Turing", target="Computer", type="invented"),  # dup post-merge
    ]
    merged, out_relations = merge_entities(entities, relations, threshold=0.85)
    assert len(merged) == 2  # Turing fuso con Alan Turing
    assert len(out_relations) == 1  # relazione duplicata collassata


def test_merge_keeps_distinct_below_threshold() -> None:
    entities = [_embedded("A", [1.0, 0.0, 0.0]), _embedded("B", [0.0, 1.0, 0.0])]
    merged, _ = merge_entities(entities, [], threshold=0.85)
    assert len(merged) == 2


def test_merge_drops_self_loops_and_unknown_endpoints() -> None:
    entities = [_embedded("A", [1.0, 0.0, 0.0]), _embedded("B", [0.0, 1.0, 0.0])]
    relations = [
        ExtractedRelation(source="A", target="A", type="self"),  # self-loop
        ExtractedRelation(source="A", target="ghost", type="x"),  # estremo sconosciuto
    ]
    _, out_relations = merge_entities(entities, relations, threshold=0.85)
    assert out_relations == []


def test_merge_empty_returns_empty() -> None:
    assert merge_entities([], [], threshold=0.85) == ([], [])


# =============================================================================
# detect_communities (Louvain)
# =============================================================================
def test_detect_communities_two_clusters() -> None:
    a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
    communities = detect_communities([a, b, c, d], [(a, b), (c, d)])
    assert communities[a] == communities[b]
    assert communities[c] == communities[d]
    assert communities[a] != communities[c]


def test_detect_communities_empty() -> None:
    assert detect_communities([], []) == {}


def test_detect_communities_isolated_node_gets_a_community() -> None:
    node = uuid4()
    communities = detect_communities([node], [])
    assert node in communities


# =============================================================================
# extract_knowledge (orchestrazione, con fake deterministici)
# =============================================================================
class _FakeExtractor:
    def __init__(self, graph: ChunkGraph) -> None:
        self._graph = graph
        self.languages: list[str] = []  # registra la lingua ricevuta a ogni chunk

    def extract(self, text: str, *, language: str) -> ChunkGraph:
        self.languages.append(language)
        return self._graph


class _FakeEmbedder:
    """'turing' --> (1,0,0); 'computer' --> (0,1,0); altro --> (0,0,1)."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            if "turing" in lowered:
                out.append([1.0, 0.0, 0.0])
            elif "computer" in lowered:
                out.append([0.0, 1.0, 0.0])
            else:
                out.append([0.0, 0.0, 1.0])
        return out


class _FakeSummarizer:
    def __init__(self) -> None:
        self.languages: list[str] = []  # registra la lingua ricevuta

    def summarize(self, chunks: Sequence[str], *, language: str) -> DocumentSummary:
        self.languages.append(language)
        return DocumentSummary(
            overview="panoramica", sections=[SummarySection(title="T", content="C")]
        )


class _RaisingExtractor:
    def extract(self, text: str, *, language: str) -> ChunkGraph:
        raise LLMError("estrazione fallita", retryable=False)


def test_extract_knowledge_end_to_end() -> None:
    graph = ChunkGraph(
        entities=[
            ExtractedEntity(name="Alan Turing", type="PERSON", description="matematico"),
            ExtractedEntity(name="Turing", type="PERSON"),
            ExtractedEntity(name="Computer", type="CONCEPT", description="macchina"),
        ],
        relations=[ExtractedRelation(source="Alan Turing", target="Computer", type="invented")],
    )
    result = extract_knowledge(
        text="testo su turing e computer " * 3,
        extractor=_FakeExtractor(graph),
        embedder=_FakeEmbedder(),
        summarizer=_FakeSummarizer(),
        max_chunk_chars=10_000,
        chunk_overlap_chars=0,
        dedup_threshold=0.85,
    )
    assert result.meta["node_count"] == 2
    assert result.meta["relationship_count"] == 1
    assert result.meta["community_count"] == 1
    assert len(result.embeddings) == 2
    assert result.summary.overview == "panoramica"
    # Gli id delle entita' e degli embeddings coincidono (stesso nodo).
    assert {entity.id for entity in result.entities} == {emb.entity_id for emb in result.embeddings}
    # Le community sono assegnate.
    assert all(entity.community is not None for entity in result.entities)


def test_extract_knowledge_passes_language_to_adapters() -> None:
    """La lingua di output scelta arriva a extractor.extract e summarizer.summarize."""
    graph = ChunkGraph(
        entities=[ExtractedEntity(name="Alan Turing", type="PERSON", description="matematico")],
        relations=[],
    )
    extractor = _FakeExtractor(graph)
    summarizer = _FakeSummarizer()

    extract_knowledge(
        text="testo su turing " * 3,
        extractor=extractor,
        embedder=_FakeEmbedder(),
        summarizer=summarizer,
        max_chunk_chars=10_000,
        chunk_overlap_chars=0,
        dedup_threshold=0.85,
        language="en",
    )

    assert extractor.languages and all(lang == "en" for lang in extractor.languages)
    assert summarizer.languages == ["en"]


def test_extract_knowledge_defaults_language_to_italian() -> None:
    """Senza language esplicito, la pipeline usa il default italiano."""
    graph = ChunkGraph(
        entities=[ExtractedEntity(name="X", type="CONCEPT")],
        relations=[],
    )
    extractor = _FakeExtractor(graph)
    summarizer = _FakeSummarizer()

    extract_knowledge(
        text="testo qualunque " * 3,
        extractor=extractor,
        embedder=_FakeEmbedder(),
        summarizer=summarizer,
        max_chunk_chars=10_000,
        chunk_overlap_chars=0,
        dedup_threshold=0.85,
    )

    assert summarizer.languages == ["it"]


def test_extract_knowledge_propagates_llm_error() -> None:
    with pytest.raises(LLMError):
        extract_knowledge(
            text="qualcosa",
            extractor=_RaisingExtractor(),
            embedder=_FakeEmbedder(),
            summarizer=_FakeSummarizer(),
            max_chunk_chars=100,
            chunk_overlap_chars=0,
            dedup_threshold=0.85,
        )
