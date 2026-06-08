# 0009 -- GraphRAG Q&A: retrieval ibrido pgvector+Neo4j, structured output con citazioni, RAG sincrono in-API

- **Status**: Accepted
- **Date**: 2026-06-08
- **Deciders**: Riccardo Catervi
- **Milestone**: M8 -- GraphRAG / Q&A per-documento

## Contesto e problema

Dopo M5 il documento e' una **struttura interrogabile** (grafo Neo4j + riassunto + embeddings su pgvector) e dopo M6 e' **navigabile** nella SPA. Manca l'ultimo passo del valore: permettere all'utente di **fare domande in linguaggio naturale** su un documento e ricevere risposte **ancorate** al suo contenuto, con le fonti esplicite.

Il rischio principale del Q&A su LLM e' l'**allucinazione**: il modello, da solo, inventa fatti plausibili. M8 deve costruire un'architettura RAG che (a) recuperi il contesto giusto dal documento, (b) vincoli la risposta a quel contesto, (c) citi le fonti, e (d) lo faccia riusando -- non duplicando -- le fondamenta di M5 (embeddings pgvector, grafo Neo4j, riassunto) e di M6 (SPA feature-based).

Sette decisioni determinano qualita' delle risposte, costo, sicurezza e UX:

1. **Strategia di retrieval** (cosa diamo in pasto al modello)
2. **Grounding e formato della risposta** (anti-allucinazione + citazioni)
3. **Dove gira il RAG** (path API sincrono vs worker asincrono)
4. **Barriera di sicurezza e semantica degli errori HTTP**
5. **Lingua della risposta**
6. **Performance delle chiamate Gemini** (estrazione e Q&A)
7. **Integrazione frontend** del Q&A

## Driver decisionali

- **Risposte ancorate, non creative**: la priorita' e' la **fedelta'** al documento; meglio "non lo so" che un'allucinazione.
- **Riuso delle fondamenta M5/M6**: gli embeddings sono gia' su pgvector, il grafo gia' su Neo4j, il riassunto gia' su Postgres; il RAG li compone, non li ricrea.
- **Costo sotto controllo**: stesso provider (Gemini free tier) di M5, una sola credenziale.
- **Sicurezza multi-tenant**: una domanda su un documento altrui non deve rivelare nulla -- stessa serieta' della doppia barriera di M5.
- **Interattivita'**: il Q&A e' on-demand e l'utente attende la risposta; non e' un job batch.
- **Testabilita' offline**: come l'estrazione, il RAG deve essere testabile senza rete (LLM e grafo dietro Protocol + fake).
- **UX nel contesto del grafo**: la risposta dev'essere esplorabile, non un testo isolato.

## Opzioni considerate (per ciascuna decisione)

### Q1 -- Strategia di retrieval

1. **GraphRAG ibrido**: pgvector trova le entita'-seme piu' vicine alla domanda, poi Neo4j **espande** al vicinato (relazioni + vicini)
2. **RAG vettoriale puro**: solo top-K da pgvector, nessuna espansione sul grafo
3. **Solo grafo**: traversamento Neo4j senza retrieval semantico

### Q2 -- Grounding e formato risposta

1. **Structured output** (`RagAnswer` Pydantic: testo + citazioni) + system prompt che vincola al contesto e dichiara l'assenza di informazioni
2. Testo libero, citazioni parse-ate a posteriori

### Q3 -- Dove gira il RAG

1. **Sincrono nel path API** (`asyncio.to_thread` sul client Gemini), componenti costruiti nel lifespan e tenuti in `app.state`
2. Task Celery asincrono (come estrazione/trascrizione)

### Q4 -- Barriera di sicurezza + errori

1. **Doppia barriera** (RLS Postgres sul documento **+** check esplicito `status == COMPLETED`) con 404 indistinguibile, 503 se il backend RAG non e' configurato, 422 su domanda/LLM invalidi
2. Solo RLS, errori generici

### Q5 -- Lingua della risposta

1. **Lingua dell'interfaccia** dall'header `Accept-Language` (it/en)
2. Lingua del documento

### Q6 -- Performance delle chiamate Gemini

1. **Estrazione chunk in parallelo** (thread pool, ordine preservato) + **retry per-chiamata** con backoff sui 429; **thinking lasciato ABILITATO** di default
2. Tutto sequenziale; thinking disattivato per ridurre la latenza

### Q7 -- Integrazione frontend del Q&A

1. **Pannello overlay** dentro la feature `graph` esistente, con citazioni cliccabili che selezionano il nodo
2. Pagina/feature dedicata separata

## Decisione

| # | Decisione |
|---|---|
| Q1 | **GraphRAG ibrido**: pgvector (coseno, top-K, scoped per documento) per le entita'-seme, poi `GraphStore.get_neighborhood` (Neo4j, `rag_neighbor_hops`) per il vicinato semantico |
| Q2 | **Structured output `RagAnswer`** (testo + `Citation[]`) via `response_schema`, con system prompt di grounding anti-allucinazione |
| Q3 | **RAG sincrono on-demand nel path API**: client Gemini in `asyncio.to_thread`, `rag_embedder`/`rag_answerer` costruiti nel lifespan e in `app.state`; nessun task Celery |
| Q4 | **Doppia barriera** (RLS Postgres + `status == COMPLETED`) --> `RagNotReadyError` = **404** indistinguibile; `RagUnavailableError` = **503**; `LLMError` retryable --> 503, non-retryable --> **422** |
| Q5 | **Lingua = `Accept-Language`** (UI, clampata a it/en), non la lingua del documento |
| Q6 | **Estrazione parallela + retry/backoff** sui 429; **thinking ABILITATO di default** (`GEMINI_THINKING_BUDGET=-1`): qualita' > latenza |
| Q7 | **Pannello overlay nella feature `graph`** (`GraphQaPanel`), citazioni cliccabili --> selezione del nodo nel viewer |

### Pattern emergenti

#### GraphRAG: il grafo come moltiplicatore del retrieval

Il RAG vettoriale puro recupera frammenti **isolati**; il grafo aggiunge la **struttura relazionale**. `RagService.ask` usa pgvector solo per **innescare** (le entita'-seme piu' vicine alla domanda), poi Neo4j espande al vicinato (`get_neighborhood`): vicini diretti + archi tra loro. Il modello vede non solo "le entita' rilevanti" ma "come sono collegate", che e' esattamente cio' che il knowledge graph di M5 codifica. Se nessuna entita' e' simile, il contesto e' vuoto e il prompt impone al modello di dichiararlo.

#### Anti-allucinazione per costruzione

Due leve combinate: (1) il **system prompt** (`rag/prompt.py`) ancora la risposta al solo contesto fornito e impone di ammettere l'assenza di informazioni; (2) lo **structured output** (`RagAnswer`) costringe il modello a restituire le **citazioni** (entita' del grafo usate come fonte), rendendo la risposta verificabile. La temperatura bassa (0.1) completa il quadro: task fattuale, non creativo.

#### Pipeline pura + Protocol iniettato (come M5)

`RagAnswerer` e' un **Protocol**: `RagService` non dipende da Gemini ma dall'interfaccia. I test usano un answerer fake e un `FakeGraphStore`, senza rete ne' API key -- stesso confine astratto di `GraphExtractor`/`Embedder`/`Summarizer` in M5. L'implementazione reale (`GeminiRagAnswerer`) e' sostituibile senza toccare il service.

#### RAG nel path API, non nel worker

A differenza di trascrizione ed estrazione (job batch, Celery), il Q&A e' **interattivo**: l'utente invia la domanda e attende. Quindi gira **sincrono** nella richiesta HTTP, col client Gemini incapsulato in `asyncio.to_thread` (stesso pattern sync-in-thread di M2/M4/M5). I componenti RAG vivono in `app.state` (costruiti nel lifespan): se `GEMINI_API_KEY` manca, il dep `get_rag_service` solleva `RagUnavailableError` --> 503, senza far cadere l'intera app.

#### Doppia barriera riusata

Identica a M5: prima `RagService` verifica via **RLS Postgres** che il documento sia dell'utente **e** che sia `COMPLETED`; solo allora interroga pgvector e Neo4j (entrambi filtrati per `owner_id`). Un documento inesistente, altrui o non pronto da' lo **stesso** 404: non si rivela l'esistenza di risorse altrui.

#### Performance senza sacrificare la qualita'

I chunk dell'estrazione sono indipendenti: vengono estratti **in parallelo** (`ThreadPoolExecutor`, `executor.map` -> ordine preservato e risultato deterministico), idem la fase *map* del riassunto. Ogni chiamata Gemini ha **retry con backoff** sui 429 (`GEMINI_MAX_RETRIES`): un rate-limit isolato non fa ripartire l'intero documento -- particolarmente utile con la concorrenza. Il **thinking** di Gemini 2.5 resta **abilitato di default** (`GEMINI_THINKING_BUDGET=-1`): si privilegia la qualita' del ragionamento, accettando piu' latenza; e' una leva di config se si vuole invertire il compromesso.

#### Q&A nel contesto del grafo

Il Q&A non e' una pagina isolata: e' un `GraphQaPanel` reso **dentro** il `GraphViewer` (overlay), in linea con gli altri pannelli (controlli, dettagli nodo). Le **citazioni sono cliccabili** e selezionano il nodo corrispondente nel grafo: la risposta testuale e l'esplorazione visiva sono lo stesso flusso. Lato dati: schema zod `AskResponse`, mutation `useAskDocument`, request che eredita l'`Accept-Language` dall'interceptor axios.

## Conseguenze

### Positive

- **Risposte ancorate e verificabili**: grounding + citazioni + temperatura bassa; il contesto vuoto produce un onesto "non ho informazioni".
- **Retrieval piu' ricco del vettoriale puro**: il vicinato del grafo aggiunge le relazioni che i frammenti isolati perdono.
- **Riuso totale di M5/M6**: pgvector, Neo4j e il riassunto sono gia' li'; M8 li compone.
- **Testabile offline**: `RagAnswerer` e `GraphStore` dietro Protocol + fake; nessuna chiamata Gemini/Neo4j in CI.
- **Isolamento robusto**: doppia barriera; il 404 non distingue "non tuo" da "non pronto".
- **Degradazione pulita**: senza `GEMINI_API_KEY` l'endpoint da' 503 e il resto dell'app funziona.
- **UX integrata**: citazioni --> nodi; risposta ed esplorazione nello stesso schermo.

### Negative / Trade-off accettati

- **Latenza interattiva**: il Q&A e' sincrono e fa due round-trip Gemini (embed domanda + risposta) piu' le query a pgvector/Neo4j; il thinking abilitato aggiunge latenza (scelta deliberata, qualita' > velocita').
- **Costo per-domanda**: ogni Q&A consuma token (embedding + generazione); sul free tier vale il rate limit (mitigato dai retry).
- **Qualita' legata al retrieval**: se `rag_top_k`/`rag_neighbor_hops` sono troppo bassi il contesto e' povero, se troppo alti il prompt cresce e con esso latenza e costo. Default bilanciati (8 / 1), tunabili.
- **Nessuna cache delle risposte**: domande identiche ricomputano tutto (caching rimandato, M9).

### Neutre

- **Sincrono nel path API**: nessun task/stato da pollare per il Q&A (a differenza di estrazione/trascrizione); la richiesta vive quanto la risposta.
- **`thinking_budget=-1` = default del modello**: non inviamo il parametro, quindi vale il comportamento nativo (thinking dinamico su 2.5 Flash). Su un modello che non accetta l'override esplicito, resta comunque innocuo.
- **Q&A dentro la feature `graph`** invece che in una feature dedicata: coerente con l'UX (citazioni --> nodi), rivedibile se il Q&A crescesse (storico conversazione, ecc.).

## Pro/contro delle opzioni scartate

### Q1 -- RAG vettoriale puro / solo grafo (scartate)

- ✅ Vettoriale puro: piu' semplice, una sola query
- ❌ Perde le relazioni: frammenti isolati, niente "come sono collegate le cose"
- ✅ Solo grafo: struttura ricca
- ❌ Senza retrieval semantico non sa **da dove** partire data una domanda in linguaggio naturale

### Q2 -- Testo libero + parsing citazioni (scartata)

- ✅ Prompt piu' semplice
- ❌ Parsing fragile delle fonti, formato non garantito; lo structured output elimina un'intera classe di bug (come in M5)

### Q3 -- Q&A come task Celery (scartata)

- ✅ Riuso del motore async, util per domande "lunghe"
- ❌ Aggiunge polling/stato a un'interazione che e' intrinsecamente request/response; latenza percepita peggiore per l'utente

### Q5 -- Risposta nella lingua del documento (scartata)

- ✅ Coerente col contenuto citato
- ❌ Un utente IT che legge un documento EN vuole la risposta in IT; la lingua dell'**interfaccia** e' la scelta giusta per la UX

### Q6 -- Thinking disattivato per default (scartata)

- ✅ Risposte ed estrazione piu' rapide
- ❌ Possibile calo di qualita' sul ragionamento multi-step (estrazione di relazioni implicite, Q&A multi-hop); si e' scelto di privilegiare la **qualita'**, lasciando la disattivazione come leva opt-in

### Q7 -- Feature/pagina Q&A dedicata (scartata)

- ✅ Piu' spazio per evoluzioni future (storico chat)
- ❌ Spezza il legame risposta<->grafo; l'overlay nel viewer tiene insieme testo ed esplorazione

## Riferimenti

- [`docs/adr/0007-knowledge-extraction.md`](0007-knowledge-extraction.md) -- embeddings pgvector, grafo Neo4j e riassunto che M8 consuma
- [`docs/adr/0008-frontend-visualization.md`](0008-frontend-visualization.md) -- SPA feature-based in cui si innesta il `GraphQaPanel`
- [pgvector](https://github.com/pgvector/pgvector) -- similarita' coseno per il retrieval delle entita'-seme
- [Google Gen AI SDK (`google-genai`)](https://googleapis.github.io/python-genai/) -- structured output, embeddings, `ThinkingConfig`
- `backend/src/echomind/services/rag.py` -- orchestrazione `RagService.ask` (retrieval ibrido + grounding)
- `backend/src/echomind/rag/` -- `RagAnswerer` Protocol, `GeminiRagAnswerer`, prompt di grounding, schema `RagAnswer`
- `backend/src/echomind/schemas/rag.py` -- `AskRequest`/`AskResponse`/`CitationRead` (boundary HTTP)
- `backend/src/echomind/api/v1/documents.py` -- `POST /documents/{id}/ask`
- `frontend/src/features/graph/components/GraphQaPanel.tsx` -- UI Q&A overlay con citazioni cliccabili
