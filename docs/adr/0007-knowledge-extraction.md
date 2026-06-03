# 0007 -- Knowledge extraction: GraphExtractor Protocol, Gemini, Neo4j multi-tenant, Louvain in-process, embeddings pgvector

- **Status**: Accepted
- **Date**: 2026-06-02
- **Deciders**: Riccardo Catervi

## Contesto e problema

M5 e' il **cuore del prodotto**: il secondo worker reale agganciato al motore asincrono di M3. Legge un `transcript` (output di M4), ne estrae via LLM **entita'** (concetti, persone, organizzazioni, ...) e **relazioni**, le persiste come **grafo** su Neo4j, raggruppa i nodi in **community tematiche** e genera un **riassunto multilivello**. Per deduplicare le entita' in modo semantico calcola **embeddings**, salvati su Postgres (pgvector) -- fondamenta del RAG ibrido di M8.

Il testo, da solo, non e' conoscenza navigabile: un transcript di migliaia di parole non si esplora. Il grafo + il riassunto trasformano quel testo in una struttura interrogabile.

Sei decisioni determinano testabilita', costo, robustezza e portabilita':

1. **Motore di estrazione** (libreria pronta vs interfaccia propria)
2. **Provider LLM** (estrazione + riassunto + embeddings)
3. **Persistenza del grafo** (e isolamento per-utente senza RLS)
4. **Community detection** (plugin del DB vs in-process)
5. **Embeddings e deduplicazione** delle entita'
6. **Innesco dell'estrazione** (chi e quando accoda il task)

## Driver decisionali

- **Testabilita' offline e deterministica**: come M2 (moto), M3 (enqueue patchato), M4 (Transcriber fake), la pipeline deve girare nei test senza rete -- niente chiamate LLM, niente Neo4j.
- **Costo sotto controllo**: l'estrazione e' la fase piu' costosa in token (rischio R1 della roadmap). Il provider e la strategia di chunking devono tenerlo basso.
- **Portabilita' del datastore grafo**: il free tier di Neo4j AuraDB e' il target di produzione; non possiamo dipendere da plugin server non garantiti (es. GDS).
- **Isolamento per-utente**: il grafo e' un dato dell'utente, ma Neo4j non ha Row-Level Security. L'isolamento va garantito a livello applicativo, con la stessa serieta' delle policy RLS di Postgres.
- **Sostituibilita' del provider**: l'LLM non deve essere cablato nel cuore della pipeline.
- **Riuso del motore M3/M4**: stessa struttura two-layer, stessa idempotenza, stessa dead-letter; nessuna nuova infrastruttura di code.
- **Skill trasferibili**: structured output, prompt engineering, embeddings & similarita', graph DB, community detection.

## Opzioni considerate (per ciascuna decisione)

### Q1 -- Motore di estrazione

1. **`GraphExtractor` come Protocol** + structured output dell'LLM (schema Pydantic)
2. **LangChain `LLMGraphTransformer`** (transformer pronto)

### Q2 -- Provider LLM

1. **Gemini** via `google-genai` (Google AI Studio, free tier) per estrazione + riassunto + embeddings
2. **OpenAI** (riuso della key di Whisper)
3. **Anthropic Claude**

### Q3 -- Persistenza del grafo + isolamento

1. **Neo4j** con **multi-tenancy applicativa** (`owner_id` + `document_id` su ogni nodo/arco, filtro su ogni query)
2. Grafo modellato su Postgres (tabelle nodi/archi)

### Q4 -- Community detection

1. **Louvain in-process** con `networkx` (poi le community scritte come property sui nodi)
2. **Louvain via GDS** (Graph Data Science plugin di Neo4j)

### Q5 -- Embeddings e deduplicazione entita'

1. **Embeddings + dedup semantica** (coseno) + persistenza su **pgvector**
2. Dedup solo per nome esatto (niente embeddings)

### Q6 -- Innesco dell'estrazione

1. **Auto-concatenazione** sul successo del transcribe (seam `transcript.ready`) **+** endpoint manuale di trigger/re-run
2. Solo trigger manuale
3. Solo auto-chain (nessun recupero manuale)

## Decisione

| # | Decisione |
|---|---|
| Q1 | **`GraphExtractor`/`Embedder`/`Summarizer` come Protocol**, structured output via `response_schema` Pydantic. Niente LangChain |
| Q2 | **Gemini** (`google-genai`, AI Studio free tier) per estrazione, riassunto **ed** embeddings: una sola credenziale |
| Q3 | **Neo4j** + **multi-tenancy applicativa**: ogni nodo/arco porta `owner_id` + `document_id`, ogni query filtra per owner |
| Q4 | **Louvain in-process** con `networkx` (nessun plugin GDS) |
| Q5 | **Embeddings Gemini + dedup coseno** + persistenza su `pgvector` (vector(768)) |
| Q6 | **Auto-chain best-effort** su transcribe riuscito **+** `POST /documents/{id}/extract` per trigger/re-run |

### Pattern emergenti

#### Structured output: niente parsing fragile

Gli schemi Pydantic (`ChunkGraph`, `DocumentSummary`) vengono passati a Gemini come `response_schema`: il modello e' vincolato a restituire **JSON valido e tipizzato**, deserializzato direttamente in oggetti Pydantic. Sparisce un'intera classe di bug (parsing di testo libero, JSON malformato, campi mancanti). L'output malformato resta un caso d'errore esplicito, non un crash silenzioso.

#### Pipeline pura + tre adapter iniettati

`extract_knowledge` (l'orchestratore in `extraction/pipeline.py`) e' **puro e sincrono**: dipende da tre Protocol -- `GraphExtractor`, `Embedder`, `Summarizer` -- non dal client Gemini concreto. I test lo chiamano con fake deterministici (niente rete, niente API key). Le implementazioni reali (`Gemini*` in `extraction/gemini.py`) sono sostituibili senza toccare la pipeline. E' lo stesso confine astratto del `Transcriber` di M4, esteso a tre servizi esterni.

#### Multi-tenancy senza RLS

Neo4j non ha Row-Level Security: l'isolamento e' **applicativo ed esplicito**. Ogni nodo `:Entity` e ogni arco `:RELATES` portano `owner_id` + `document_id`, e **ogni** query del `GraphStore` filtra per `owner_id`. L'API aggiunge una **seconda barriera**: prima di interrogare Neo4j, `GraphService` verifica via RLS su Postgres che il documento appartenga all'utente (altrimenti 404, indistinguibile da "non pronto"). Doppia difesa: RLS su Postgres + filtro owner su Neo4j.

#### Deduplicazione in due fasi

L'LLM, estraendo chunk per chunk, nomina la stessa entita' in modi diversi ("Alan Turing", "Turing", "A. Turing"): senza fusione il grafo si frammenta. La dedup ha due fasi pure (solo `numpy`): **esatta** (nomi normalizzati identici) e **semantica** (clustering greedy per similarita' **coseno** degli embeddings sopra una soglia). Le relazioni vengono rimappate sui nomi canonici, scartando self-loop, estremi sconosciuti e duplicati.

#### Community detection portabile

Le community (cluster densi = "temi" per il drill-down della UI in M6) si calcolano con l'algoritmo di **Louvain in-process** (`networkx`), poi scritte come property `community` sui nodi. Si evita di proposito il plugin **GDS** di Neo4j: spesso assente sul free tier di AuraDB (rischio R3 della roadmap). networkx gira su qualsiasi installazione ed e' piu' che sufficiente al volume MVP.

#### Idempotenza cross-store

Re-eseguire l'estrazione **sostituisce**, non duplica: il sottografo Neo4j del documento viene rimpiazzato (`DETACH DELETE` + create), il riassunto e' un upsert `ON CONFLICT (document_id)`, gli embeddings sono delete-by-document + insert. Un retry o una ri-estrazione lasciano lo stato coerente. La cancellazione di un documento pulisce anche il sottografo Neo4j (best-effort); summary ed embeddings spariscono via FK `ON DELETE CASCADE` su Postgres.

#### Chaining event-driven best-effort

Sul successo del transcribe, il worker accoda l'estrazione (seam `transcript.ready --> extract`). L'enqueue e' **best-effort**: una trascrizione gia' riuscita -- e costosa (Whisper) -- non deve fallire ne' essere rifatta se l'enqueue va male. In quel caso si logga soltanto, e l'utente recupera con `POST /documents/{id}/extract`. I due worker restano disaccoppiati.

#### Client sincroni in un thread

Come boto3 (M2) e OpenAI/Whisper (M4): i client Gemini e il driver Neo4j sono usati in modalita' **sincrona**, incapsulati dietro chiamate `asyncio.to_thread`. Evita il footgun dell'affinita' loop<->client tra i task del worker (ogni task gira in un nuovo event loop via `asyncio.run`). Il driver Neo4j sync e' thread-based: un singleton di processo riusabile su tutti i loop.

#### Hardening della key vuota

`require_secret` (in `core/config.py`) tratta una API key **vuota** (placeholder `=` nel `.env`) come **assente**, non solo `None`: errore di configurazione chiaro all'uso, invece di un 4xx criptico dall'API esterna a runtime. Applicato a Gemini e, retroattivamente, a OpenAI/Whisper.

## Conseguenze

### Positive

- **Pipeline testabile offline**: `extract_knowledge`, chunking, dedup e Louvain sono puri; i test usano fake di `GraphExtractor`/`Embedder`/`Summarizer` e un `FakeGraphStore`. Nessuna chiamata Gemini/Neo4j in CI.
- **Costo nullo in sviluppo**: Gemini free tier + embeddings free tier + Neo4j locale + Louvain in-process. Il rischio costi (R1) e' neutralizzato; resta da gestire il **rate limit** del free tier (i 429 sono transienti --> retry).
- **Portabile su AuraDB free**: niente dipendenza dal plugin GDS.
- **Isolamento robusto**: doppia barriera (RLS Postgres + filtro owner Neo4j); `GET /graph`/`summary` ritornano 404 per i dati altrui.
- **Provider sostituibile**: cambiare LLM tocca solo gli adapter, non la pipeline.
- **Ri-estrazione sicura**: idempotenza cross-store; nessun nodo/arco/embedding duplicato.
- **Fondamenta RAG (M8)**: gli embeddings sono gia' persistiti su pgvector.
- **Riuso del motore M3/M4**: stessa struttura two-layer, idempotenza, dead-letter.

### Negative / Trade-off accettati

- **Neo4j come nuova dipendenza d'infrastruttura**: un servizio in piu' nel compose di sviluppo (come Postgres/RabbitMQ/Redis) e un'istanza AuraDB in produzione.
- **Postgres con pgvector**: l'immagine dev passa a `pgvector/pgvector:pg16` (e altrettanto il service Postgres in CI), perche' la migration crea l'estensione `vector`.
- **Rate limit del free tier**: documenti lunghi = molte chiamate. Mitigato con chunk ampi e retry sui 429; per volumi alti servira' un tier a pagamento (o batching/caching, M9).
- **Qualita' dell'estrazione dipende dal prompt**: l'estrazione hand-rolled mette il prompt sotto il nostro controllo (vantaggio per il tuning), ma la qualita' va validata su documenti reali (smoke test + golden set).
- **Community detection in-process**: per grafi enormi sarebbe meno efficiente di GDS; irrilevante al volume MVP (free tier AuraDB: 50k nodi).
- **`POST /extract` richiede lo storage configurato**: l'endpoint riusa `DocumentService` (che impacchetta B2), quindi un B2 non disponibile da' 503 anche se l'estrazione non usa B2. Innocuo in produzione (B2 sempre configurato).

### Neutre

- **Polling per lo stato**: `GET /documents/{id}/graph` e `/summary` ritornano 404 finche' l'estrazione non e' pronta; il client fa polling (o consulta `GET /tasks/{id}`). Lo streaming (WebSocket) e' rimandato a M7.
- **Relazione `:RELATES` generica** con il tipo come property: evita APOC per i tipi dinamici. Un'eventuale tipizzazione nativa delle relazioni e' rivedibile.
- **`source_type`/`task_type` come TEXT**: coerente con le milestone precedenti; validazione applicativa via `StrEnum`.

## Pro/contro delle opzioni scartate

### Q1 -- LangChain `LLMGraphTransformer` (scartata)

- Meno codice di estrazione da scrivere
- Dipendenza pesante e in rapida evoluzione (il transformer vive in un pacchetto "experimental"); prompt opaco, difficile da tunare; test in CI piu' difficili da isolare. L'interfaccia propria e' coerente con la filosofia della codebase (Protocol + fake)

### Q2 -- OpenAI / Anthropic (scartate)

- OpenAI: riuso della key di Whisper, structured output nativi -- ma pay-per-use sull'estrazione (la fase piu' costosa)
- Anthropic: ottima qualita' -- ma nuova credenziale e pay-per-use
- Gemini free tier copre estrazione + riassunto + embeddings a costo zero in sviluppo, con structured output ed embeddings nativi

### Q3 -- Grafo su Postgres (scartata)

- Nessun datastore nuovo
- Le query di traversamento (cammini, vicinato, community) sono naturali in Cypher e goffe in SQL ricorsivo; il grafo e' il modello giusto per il dominio, e Neo4j e' gia' nello stack pianificato

### Q4 -- Louvain via GDS (scartata)

- Piu' efficiente su grafi molto grandi, calcolo lato DB
- Plugin spesso non disponibile sul free tier di AuraDB --> non portabile; aggiunge una dipendenza server fragile

### Q5 -- Dedup solo per nome esatto (scartata)

- Piu' semplice, nessun embedding
- Lascia il grafo frammentato (varianti dello stesso nome restano nodi distinti); inoltre niente fondamenta per il RAG di M8

### Q6 -- Solo manuale / solo auto-chain (scartate)

- Solo manuale: l'utente dovrebbe innescare ogni estrazione a mano (non event-driven)
- Solo auto-chain: nessun modo di recuperare se l'enqueue automatico fallisce, ne' di ri-estrarre. La combinazione auto + manuale copre entrambi

## Riferimenti

- [Google Gen AI SDK (`google-genai`)](https://googleapis.github.io/python-genai/) -- structured output ed embeddings
- [Neo4j Python Driver](https://neo4j.com/docs/api/python-driver/current/) -- Bolt, transazioni gestite
- [pgvector](https://github.com/pgvector/pgvector) -- tipo `vector` e similarita' su Postgres
- [networkx -- Louvain communities](https://networkx.org/documentation/stable/reference/algorithms/community.html)
- [`docs/adr/0006-media-processing.md`](0006-media-processing.md) -- i `transcripts` che M5 consuma in input
- [`docs/adr/0005-async-job-infrastructure.md`](0005-async-job-infrastructure.md) -- motore async (two-layer task, idempotenza, DLQ) riusato da M5
- `backend/src/echomind/extraction/` -- pipeline pura (chunking, dedup, community, schema) + adapter Gemini
- `backend/src/echomind/services/graph_store.py` -- `GraphStore` Protocol + `Neo4jGraphStore` (multi-tenancy)
- `backend/src/echomind/worker/tasks/extract.py` -- worker reale (core async + wrapper Celery)
- `backend/alembic/versions/0005_summaries_embeddings.py` -- schema summaries + entity_embeddings + RLS + estensione vector
