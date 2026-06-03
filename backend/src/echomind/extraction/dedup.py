"""Deduplicazione delle entita': esatta (stesso nome) + semantica (coseno).

Pura (solo numpy). L'LLM, estraendo chunk per chunk, produce la stessa entita' con
nomi leggermente diversi ("Alan Turing", "Turing", "A. Turing"). Senza dedup il
grafo si frammenta. Qui:
1. `collapse_exact_duplicates`: fonde i nomi identici (normalizzati).
2. `merge_entities`: raggruppa per similarita' coseno degli embedding (>= soglia)
   e rimappa le relazioni sui nomi canonici, scartando self-loop, estremi
   sconosciuti e duplicati.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from echomind.extraction.schema import ExtractedEntity, ExtractedRelation


def normalize_name(name: str) -> str:
    """Chiave di matching: lowercase + whitespace collassato."""
    return " ".join(name.strip().lower().split())


@dataclass(frozen=True, slots=True)
class EmbeddedEntity:
    """Entita' unica (per nome esatto) con il suo embedding -- input di merge_entities."""

    name: str
    type: str
    description: str
    embedding: list[float]


@dataclass(frozen=True, slots=True)
class MergedEntity:
    """Entita' canonica dopo il merge semantico (rappresentante del cluster)."""

    name: str
    type: str
    description: str
    embedding: list[float]


def collapse_exact_duplicates(entities: Sequence[ExtractedEntity]) -> list[ExtractedEntity]:
    """Fonde le entita' con lo stesso nome normalizzato (tra chunk diversi).

    Tiene il primo nome/tipo incontrato e la descrizione piu' lunga (la piu'
    informativa). Scarta i nomi vuoti.
    """
    by_norm: dict[str, ExtractedEntity] = {}
    for entity in entities:
        key = normalize_name(entity.name)
        if not key:
            continue
        existing = by_norm.get(key)
        if existing is None:
            by_norm[key] = entity
        elif len(entity.description) > len(existing.description):
            by_norm[key] = ExtractedEntity(
                name=existing.name,
                type=existing.type or entity.type,
                description=entity.description,
            )
    return list(by_norm.values())


def merge_entities(
    entities: Sequence[EmbeddedEntity],
    relations: Sequence[ExtractedRelation],
    *,
    threshold: float,
) -> tuple[list[MergedEntity], list[ExtractedRelation]]:
    """Clusterizza le entita' per similarita' coseno e rimappa le relazioni.

    Clustering greedy a passo singolo: ogni entita' entra nel primo cluster il cui
    rappresentante ha coseno >= soglia, altrimenti ne apre uno nuovo (e ne diventa
    il rappresentante). Sufficiente al volume MVP. Le relazioni vengono riportate
    ai nomi canonici; self-loop, estremi sconosciuti e duplicati sono scartati.
    """
    if not entities:
        return [], []

    vectors = np.asarray([entity.embedding for entity in entities], dtype=float)
    norms = np.linalg.norm(vectors, axis=1)

    cluster_members: list[list[int]] = []
    rep_indices: list[int] = []
    norm_to_cluster: dict[str, int] = {}

    for i, entity in enumerate(entities):
        best_cluster = -1
        best_sim = threshold
        for cluster, rep_index in enumerate(rep_indices):
            denom = float(norms[i] * norms[rep_index])
            if denom == 0.0:
                continue
            sim = float(np.dot(vectors[i], vectors[rep_index])) / denom
            if sim >= best_sim:
                best_sim = sim
                best_cluster = cluster
        if best_cluster == -1:
            rep_indices.append(i)
            cluster_members.append([i])
            best_cluster = len(rep_indices) - 1
        else:
            cluster_members[best_cluster].append(i)
        norm_to_cluster[normalize_name(entity.name)] = best_cluster

    merged: list[MergedEntity] = []
    for members in cluster_members:
        rep = entities[members[0]]
        description = max((entities[m].description for m in members), key=len, default="")
        merged.append(
            MergedEntity(
                name=rep.name, type=rep.type, description=description, embedding=rep.embedding
            )
        )

    out_relations: list[ExtractedRelation] = []
    seen: set[tuple[int, int, str]] = set()
    for relation in relations:
        source_cluster = norm_to_cluster.get(normalize_name(relation.source))
        target_cluster = norm_to_cluster.get(normalize_name(relation.target))
        if source_cluster is None or target_cluster is None or source_cluster == target_cluster:
            continue
        key = (source_cluster, target_cluster, relation.type.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        out_relations.append(
            ExtractedRelation(
                source=merged[source_cluster].name,
                target=merged[target_cluster].name,
                type=relation.type,
                description=relation.description,
            )
        )
    return merged, out_relations
