"""Orchestratore PURO dell'estrazione: testo --> grafo + riassunto + embeddings.

`extract_knowledge` mette in fila chunking, estrazione per-chunk, embedding, dedup,
community detection e riassunto, prendendo `GraphExtractor`, `Embedder`, `Summarizer`
come Protocol INIETTATI. Niente Gemini, niente Neo4j, niente DB: i test la chiamano
con fake deterministici (come `process_media` di M4). Il worker (CP7) la invoca in
UN solo `asyncio.to_thread`, poi persiste il risultato.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from echomind.extraction.chunking import chunk_text
from echomind.extraction.community import detect_communities
from echomind.extraction.dedup import (
    EmbeddedEntity,
    collapse_exact_duplicates,
    merge_entities,
    normalize_name,
)
from echomind.extraction.embedder import Embedder
from echomind.extraction.extractor import GraphExtractor
from echomind.extraction.schema import (
    DocumentSummary,
    Entity,
    EntityVector,
    ExtractedEntity,
    ExtractedRelation,
    Relation,
)
from echomind.extraction.summarize import Summarizer


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Output completo dell'estrazione, pronto per la persistenza."""

    entities: list[Entity]
    relations: list[Relation]
    summary: DocumentSummary
    embeddings: list[EntityVector]
    meta: dict[str, Any]


def _embedding_text(entity: ExtractedEntity) -> str:
    """Testo da embeddare per un'entita': nome + descrizione, se presente."""
    if entity.description.strip():
        return f"{entity.name}: {entity.description}"
    return entity.name


def extract_knowledge(
    *,
    text: str,
    extractor: GraphExtractor,
    embedder: Embedder,
    summarizer: Summarizer,
    max_chunk_chars: int,
    chunk_overlap_chars: int,
    dedup_threshold: float,
) -> ExtractionResult:
    """Trasforma un testo (transcript) in grafo + riassunto + embeddings.

    Deterministico a parita' di input + adapter. Tollerante al vuoto: testo o
    estrazione vuoti producono un risultato vuoto coerente (0 nodi/archi), non un
    errore -- la decisione su cosa farne spetta al worker.
    """
    chunks = chunk_text(text, max_chars=max_chunk_chars, overlap=chunk_overlap_chars)

    # 1. Estrazione per-chunk: accumula entita' e relazioni grezze.
    raw_entities: list[ExtractedEntity] = []
    raw_relations: list[ExtractedRelation] = []
    for chunk in chunks:
        graph = extractor.extract(chunk)
        raw_entities.extend(graph.entities)
        raw_relations.extend(graph.relations)

    # 2. Dedup esatta --> embed --> dedup semantica.
    collapsed = collapse_exact_duplicates(raw_entities)
    if collapsed:
        vectors = embedder.embed([_embedding_text(entity) for entity in collapsed])
        embedded = [
            EmbeddedEntity(
                name=entity.name,
                type=entity.type,
                description=entity.description,
                embedding=vector,
            )
            for entity, vector in zip(collapsed, vectors, strict=True)
        ]
    else:
        embedded = []
    merged, merged_relations = merge_entities(embedded, raw_relations, threshold=dedup_threshold)

    # 3. Id stabile per ogni entita' canonica.
    merged_ids: list[UUID] = [uuid4() for _ in merged]
    name_to_id: dict[str, UUID] = {
        normalize_name(entity.name): eid for entity, eid in zip(merged, merged_ids, strict=True)
    }

    # 4. Relazioni canoniche --> archi per id (con guardia su estremi/self-loop).
    relations: list[Relation] = []
    edges: list[tuple[UUID, UUID]] = []
    for relation in merged_relations:
        source_id = name_to_id.get(normalize_name(relation.source))
        target_id = name_to_id.get(normalize_name(relation.target))
        if source_id is None or target_id is None or source_id == target_id:
            continue
        relations.append(
            Relation(
                source_id=source_id,
                target_id=target_id,
                type=relation.type,
                description=relation.description,
            )
        )
        edges.append((source_id, target_id))

    # 5. Community detection sul grafo per id.
    communities = detect_communities(merged_ids, edges)

    # 6. Assembla entita' finali + embeddings da persistere.
    entities: list[Entity] = []
    embeddings: list[EntityVector] = []
    for entity, eid in zip(merged, merged_ids, strict=True):
        entities.append(
            Entity(
                id=eid,
                name=entity.name,
                type=entity.type,
                description=entity.description,
                community=communities.get(eid),
            )
        )
        embeddings.append(EntityVector(entity_id=eid, name=entity.name, vector=entity.embedding))

    # 7. Riassunto multilivello.
    summary = summarizer.summarize(chunks)

    meta: dict[str, Any] = {
        "chunk_count": len(chunks),
        "raw_entity_count": len(raw_entities),
        "node_count": len(entities),
        "relationship_count": len(relations),
        "community_count": len(set(communities.values())),
    }
    return ExtractionResult(
        entities=entities,
        relations=relations,
        summary=summary,
        embeddings=embeddings,
        meta=meta,
    )
