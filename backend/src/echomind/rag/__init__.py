"""Pacchetto RAG (Retrieval-Augmented Generation) -- M8.

Flusso per-documento:
  1. L'utente pone una domanda su un documento (API POST /documents/{id}/ask).
  2. `RagService` (CP7) coordina il retrieval:
     a. Embedding della domanda (`GeminiEmbedder`).
     b. Ricerca vettoriale delle entita' piu' rilevanti (`EmbeddingRepository.search_similar`).
     c. Espansione al vicinato nel grafo Neo4j (`Neo4jGraphStore.get_neighborhood`).
     d. Opzionale: aggiunta del `summary_overview` dal `SummaryRepository`.
  3. Il contesto assembla un `RetrievedContext` e lo passa a `RagAnswerer.answer`.
  4. `GeminiRagAnswerer` costruisce il prompt (contesto strutturato + system instruction)
     e chiama Gemini con structured output `RagAnswer` (risposta + citazioni).

Isolamento multi-tenant: `RagService` verifica ownership del documento sotto RLS
prima di qualsiasi retrieval (come `GraphService`). Il `get_neighborhood` filtra per
`owner_id` + `document_id` anche lato Neo4j.
"""
