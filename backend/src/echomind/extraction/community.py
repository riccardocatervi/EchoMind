"""Community detection con l'algoritmo di Louvain (networkx, in-process).

Perche' in-process e non GDS Neo4j: networkx gira su qualsiasi installazione e non
richiede il plugin GDS (spesso assente su AuraDB free tier -- rischio R3 della
roadmap). Per il volume MVP e' piu' che sufficiente. Le community raggruppano nodi
densamente connessi: diventano i "temi" per il drill-down della UI (M6).

Puro e deterministico (seed fisso).
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import networkx as nx

_LOUVAIN_SEED = 42


def detect_communities(
    entity_ids: Sequence[UUID],
    edges: Sequence[tuple[UUID, UUID]],
) -> dict[UUID, int]:
    """Assegna a ogni entita' un indice di community (0-based).

    I nodi isolati (senza archi) finiscono ciascuno in una community singoletto.
    Ritorna `{}` se non ci sono entita'.
    """
    if not entity_ids:
        return {}

    graph = nx.Graph()
    graph.add_nodes_from(entity_ids)
    graph.add_edges_from(edges)

    communities = nx.community.louvain_communities(graph, seed=_LOUVAIN_SEED)

    assignment: dict[UUID, int] = {}
    for index, community in enumerate(communities):
        for node in community:
            assignment[node] = index
    return assignment
