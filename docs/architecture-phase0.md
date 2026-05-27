# EchoMind — Documento di Architettura Strategica (Fase 0)

> **Ruolo**: Architect Senior
> **Versione**: 0.1 — Pianificazione iniziale
> **Stato codebase**: greenfield (solo `CLAUDE.md`)

---

## 1. Analisi del Dominio

### 1.1 Cosa farà EchoMind (sintesi)

1. **Ingestione multimodale**: l'utente carica un documento testuale (PDF, DOCX, TXT) o un file audio (MP3, WAV) tramite upload diretto verso object storage.
2. **Trascrizione automatica**: i file audio vengono convertiti in testo via Whisper API in modo asincrono.
3. **Estrazione semantica**: un pipeline LLM identifica entità (concetti) e relazioni (archi) e li struttura in un grafo.
4. **Riassunto multilivello**: vengono generati riassunti gerarchici (panoramica → sezioni → dettagli), ottenuti tramite *recursive summarization*.
5. **Community detection**: il grafo viene clusterizzato in "comunità" tematiche per consentire navigazione progressiva (drill-down).
6. **Visualizzazione interattiva**: l'utente vede una mappa concettuale navigabile (React Flow + layout Elk.js).
7. **Q&A in linguaggio naturale**: l'utente interroga il grafo ("Cosa dice il documento su X?") tramite RAG ibrido (vector + graph).
8. **Esportazione**: download del riassunto, del grafo (JSON/PNG/SVG) e di eventuali risposte.
9. **Multi-utente**: ogni utente ha la propria area privata, con isolamento dei dati garantito da Row-Level Security.
10. **Asincronia trasparente**: l'utente non aspetta sulla pagina; riceve aggiornamenti via WebSocket quando i job completano.

**Utenti target**: studenti, ricercatori, knowledge workers, professionisti che devono assimilare grandi volumi di contenuti.
**Valore generato**: trasformare ore di lettura/ascolto in pochi minuti di esplorazione visuale.

### 1.2 Bounded Contexts (DDD)

Identifico **6 bounded context** (più granulari dei 4 suggeriti, perché la separazione delle responsabilità qui è critica):

| Contesto | Responsabilità | Linguaggio ubiquitario |
|---|---|---|
| **IdentityAccess** | Autenticazione, autorizzazione, gestione utenti | User, Session, Token, Role |
| **ContentIngestion** | Upload, validazione, storage di documenti/audio | Document, MediaFile, UploadSession, PresignedURL |
| **MediaProcessing** | Trascrizione audio, parsing PDF/DOCX | Transcript, ParsedText, ProcessingJob |
| **KnowledgeExtraction** | LLM-based entity/relation extraction, summarization | Entity, Relation, Community, Summary, Embedding |
| **GraphQuery** | Q&A, ricerca semantica, navigazione grafo | Question, Answer, GraphTraversal, RAGContext |
| **Presentation** | UI rendering, layout grafo, real-time updates | View, Node, Edge, Layout, Subscription |

> **Perché 6 e non 4?** Perché *MediaProcessing* (trascrizione/parsing) ha un ciclo di vita e dipendenze diverse da *KnowledgeExtraction* (LLM, prompt). Mescolarli porta a worker Celery troppo grossi e prompt difficili da testare. *GraphQuery* è separato da *KnowledgeExtraction* perché la fase di interrogazione è read-mostly e richiede ottimizzazioni diverse (caching, indici).

### 1.3 Interazione tra contesti (diagramma testuale)

```
┌─────────────────┐
│  IdentityAccess │ ◄─── ogni richiesta autenticata
└────────┬────────┘
         │ user_id
         ▼
┌─────────────────┐    publish   ┌──────────────────┐
│ContentIngestion │──────────────▶│ MediaProcessing  │
└────────┬────────┘  (event:      └─────────┬────────┘
         │ document_id           transcribe)│ transcript_ready
         │                                  ▼
         │              ┌───────────────────────────┐
         └─────────────▶│  KnowledgeExtraction      │
                        │  (entities, relations,     │
                        │   summaries, communities)  │
                        └─────────────┬─────────────┘
                                      │ graph_ready
                                      ▼
                        ┌─────────────────────────┐
                        │      GraphQuery         │◄──── user questions
                        └─────────────┬───────────┘
                                      │
                                      ▼
                              ┌───────────────┐
                              │  Presentation │
                              └───────────────┘
```

**Pattern di comunicazione**: tra i contesti backend usiamo **eventi asincroni** (RabbitMQ), non chiamate sincrone. Questo è il principio "event-driven" del CLAUDE.md: ogni contesto pubblica un evento di completamento, il successivo lo consuma.

---

## 2. Architettura High-Level (C4 — Container Diagram)

```mermaid
graph TB
    subgraph Client
        U[User Browser<br/>React + React Flow]
    end

    subgraph Edge
        CDN[CDN / Static Hosting]
    end

    subgraph Backend["Backend (AWS)"]
        API[FastAPI<br/>REST + WebSocket]
        WORKER1[Celery Worker:<br/>Transcription]
        WORKER2[Celery Worker:<br/>Extraction]
        WORKER3[Celery Worker:<br/>Summarization]
        BROKER[(RabbitMQ<br/>Broker)]
        CACHE[(Redis<br/>Task State + Cache)]
    end

    subgraph DataLayer["Data Layer"]
        PG[(Supabase<br/>PostgreSQL + Auth)]
        NEO[(Neo4j AuraDB<br/>Knowledge Graph)]
        B2[(Backblaze B2<br/>Object Storage)]
    end

    subgraph External["External APIs"]
        WHISP[OpenAI Whisper]
        LLM[Claude / GPT<br/>via LangChain]
    end

    U -->|HTTPS| CDN
    CDN -->|JS bundle| U
    U <-->|REST + WS| API
    U -.->|direct upload<br/>presigned URL| B2

    API --> PG
    API --> CACHE
    API -->|enqueue| BROKER
    API --> NEO

    BROKER --> WORKER1
    BROKER --> WORKER2
    BROKER --> WORKER3

    WORKER1 --> B2
    WORKER1 --> WHISP
    WORKER1 --> CACHE
    WORKER1 -->|publish| BROKER

    WORKER2 --> LLM
    WORKER2 --> NEO
    WORKER2 --> CACHE
    WORKER2 -->|publish| BROKER

    WORKER3 --> LLM
    WORKER3 --> PG
    WORKER3 --> CACHE

    API -.->|notify| U
```

### Flussi principali

**Flusso 1: Upload documento**

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant PG as Supabase
    participant B2 as Backblaze B2
    participant MQ as RabbitMQ

    U->>API: POST /documents/init-upload (filename, size)
    API->>PG: INSERT document(status=pending)
    API->>B2: generate presigned URL
    API-->>U: {presigned_url, document_id}
    U->>B2: PUT file (direct upload)
    U->>API: POST /documents/{id}/confirm
    API->>PG: UPDATE status=uploaded
    API->>MQ: publish "document.uploaded"
    API-->>U: 202 Accepted (task_id)
```

**Flusso 2: Trascrizione + estrazione**

```mermaid
sequenceDiagram
    participant MQ as RabbitMQ
    participant W1 as Worker (Transcribe)
    participant W2 as Worker (Extract)
    participant B2 as Backblaze
    participant WH as Whisper
    participant LLM as LangChain+LLM
    participant NEO as Neo4j
    participant R as Redis

    MQ->>W1: consume document.uploaded
    W1->>R: state=transcribing
    W1->>B2: download file
    W1->>WH: transcribe(audio)
    WH-->>W1: transcript
    W1->>R: store transcript + state=transcribed
    W1->>MQ: publish transcript.ready
    MQ->>W2: consume transcript.ready
    W2->>LLM: extract entities + relations
    LLM-->>W2: structured graph
    W2->>NEO: MERGE nodes/edges (Cypher)
    W2->>MQ: publish graph.ready
```

### Connection points (dove i sistemi si incontrano)

| Connessione | Protocollo | Dove vive | Note di design |
|---|---|---|---|
| Browser ↔ FastAPI | HTTPS REST + WSS | Load balancer AWS | JWT in header `Authorization` |
| Browser ↔ B2 | HTTPS PUT (presigned) | Bypassa il backend | Validità URL: 15 min |
| FastAPI ↔ RabbitMQ | AMQP 0.9.1 | Stessa VPC | Producer side, ack persistente |
| Celery worker ↔ RabbitMQ | AMQP 0.9.1 | Stessa VPC | Consumer prefetch=1 per fairness |
| FastAPI ↔ Redis | RESP (TCP) | Stessa VPC | TTL su task state (24h) |
| Worker ↔ Neo4j | Bolt (TCP 7687) | Cloud-to-cloud | Connection pool, transazioni esplicite |
| Worker ↔ Whisper/LLM | HTTPS | Internet | Retry esponenziale, timeout 60s |
| FastAPI ↔ Supabase | PostgreSQL wire (TCP 5432) | Cloud-to-cloud | Connection pool (asyncpg) |

---

## 3. Analisi delle Dipendenze Esterne

### 3.1 Servizi cloud da configurare

| Servizio | Tipo | Free tier? | Criticità per testing |
|---|---|---|---|
| **Supabase** | PostgreSQL + Auth | Sì (500MB DB, 1GB storage) | Bloccante: senza DB non parte nulla |
| **Neo4j AuraDB** | Graph DB | Sì (50k nodi, 175k archi) | Bloccante per fase grafo |
| **Backblaze B2** | Object storage S3-compat | Sì (10GB) | Bloccante per upload |
| **OpenAI Whisper** | API trascrizione | No (pay-per-use, ~$0.006/min) | Bloccante per audio |
| **OpenAI / Anthropic LLM** | API generazione | No (pay-per-use) | Bloccante per estrazione |
| **RabbitMQ** | Message broker | Locale (Docker) o CloudAMQP free | Bloccante per async |
| **Redis** | Cache / state | Locale (Docker) o Upstash free | Bloccante per stato task |

### 3.2 Entry points per servizio

- **Supabase** → URL progetto + `anon_key` + `service_role_key` + connection string PostgreSQL
- **Neo4j AuraDB** → URI bolt+s://xxxxx.databases.neo4j.io + username/password
- **Backblaze B2** → `keyID`, `applicationKey`, bucket name, S3-compatible endpoint
- **OpenAI** → API key + organization ID
- **RabbitMQ** → URL AMQP (user:pass@host:5672/vhost)
- **Redis** → URL redis://user:pass@host:port/db

### 3.3 Ordine logico di setup

Il principio: **"non puoi configurare ciò che dipende da qualcosa che non esiste ancora"**.

```
1. Account cloud (registrazioni)
   ├─ Supabase project
   ├─ Neo4j AuraDB instance
   ├─ Backblaze B2 bucket
   └─ OpenAI API key

2. Sviluppo locale (Docker Compose)
   ├─ RabbitMQ container
   └─ Redis container

3. Schema & migrazioni
   ├─ Supabase: tabelle (users via auth, documents, tasks, chat_messages)
   ├─ Supabase: RLS policies
   └─ Neo4j: constraints (UNIQUE su :Concept(id)), indici

4. Configurazione applicativa
   ├─ .env con tutte le credenziali
   ├─ Pydantic Settings per validazione
   └─ Smoke test di connessione per ogni servizio
```

> **Errore comune da evitare**: applicare le RLS policies dopo aver scritto il codice. Vanno scritte **insieme** allo schema — altrimenti scopri buchi di sicurezza in produzione.

---

## 4. Milestone (alto livello)

Ho definito **9 milestone** (7 per MVP + 2 di arricchimento). Ogni milestone è completabile, testabile, di valore.

### M0 — Fondamenta del progetto
- **Scope**: struttura repo, tooling (ruff, mypy, pytest, pre-commit), Docker Compose locale, CLAUDE.md sub-files, ADR template
- **Figura**: Architect + Infra/SRE
- **Valore**: ambiente di sviluppo riproducibile

### M1 — Identity & Persistence Foundations
- **Scope**: FastAPI skeleton, Pydantic Settings, integrazione Supabase, modelli SQLAlchemy/asyncpg, autenticazione JWT, RLS, healthcheck, prima migrazione
- **Figura**: Backend Engineer
- **Valore**: utenti possono registrarsi/loggarsi, stato salvato

### M2 — Content Ingestion (Upload Scalabile)
- **Scope**: presigned URL Backblaze, endpoint init/confirm upload, validazione MIME/size, tabella `documents`, job placeholder
- **Figura**: Backend Engineer
- **Valore**: utenti caricano file in modo scalabile (no banda backend)

### M3 — Async Job Infrastructure
- **Scope**: Celery + RabbitMQ, primo worker (mock), tracking stato su Redis, endpoint `/tasks/{id}/status`, error handling, retry policy, dead-letter queue
- **Figura**: Backend Engineer
- **Valore**: pipeline asincrona testabile end-to-end con un task fittizio

### M4 — Media Processing Pipeline
- **Scope**: worker `Transcriber` (Whisper API), parser PDF/DOCX/TXT, normalizzazione testo, salvataggio transcript, gestione file lunghi (chunking)
- **Figura**: Backend Engineer + ML/AI Engineer
- **Valore**: input multimodale → testo strutturato

### M5 — Knowledge Extraction Engine (cuore del progetto)
- **Scope**: LangChain `LLMGraphTransformer`, prompt few-shot, Pydantic schema entità/relazioni, persistence Cypher su Neo4j, recursive summarization, community detection (algoritmo Louvain in Neo4j)
- **Figura**: ML/AI Engineer
- **Valore**: il grafo viene effettivamente costruito

### M6 — Frontend Visualization
- **Scope**: React + Vite skeleton, autenticazione client, upload UI, polling/WebSocket per stato, React Flow + Elk.js, custom node, drill-down su community, panel dettagli
- **Figura**: Frontend Engineer
- **Valore**: l'utente vede il proprio grafo

### M7 — End-to-End Integration & Real-time
- **Scope**: WebSocket per progress updates, gestione errori UI, ottimizzazioni rendering grafo grande, esportazione (JSON, PNG)
- **Figura**: Backend + Frontend Engineer
- **Valore**: prodotto MVP completo e fluido

### M8 — Q&A Interface (oltre MVP)
- **Scope**: chat UI, RAG ibrido (graph traversal + vector retrieval su Supabase pgvector), citazioni dei nodi, history conversazione
- **Figura**: ML/AI Engineer + Frontend Engineer
- **Valore**: vera interazione conversazionale col contenuto

### M9 — Production Readiness
- **Scope**: Dockerfile multi-stage, GitHub Actions (lint+test+build+deploy), deploy AWS (ECS/Fargate o EC2), monitoring (Sentry, structured logs), rate limiting, backup
- **Figura**: Infra/SRE + QA/Reviewer
- **Valore**: il sistema è in produzione e osservabile

---

## 5. Dipendenze tra Milestone

### 5.1 Matrice di dipendenze

| Milestone | Prerequisiti diretti |
|---|---|
| M0 | — |
| M1 | M0 |
| M2 | M1 (auth + utenti) |
| M3 | M0 (può iniziare in parallelo a M1/M2 sul lato infrastruttura) |
| M4 | M2 + M3 (servono file caricati + worker funzionante) |
| M5 | M4 (serve testo) |
| M6 | M1 (per autenticarsi); può iniziare scaffold dopo M0 |
| M7 | M5 + M6 |
| M8 | M5 + M6 |
| M9 | M7 |

### 5.2 Critical path

```
M0 → M1 → M2 → M4 → M5 → M7 → M9
```

È la strada più lunga di dipendenze sequenziali. **Ogni giorno di ritardo qui ritarda l'intero progetto.**

### 5.3 Lavori parallelizzabili

- M3 può procedere in parallelo a M1/M2 (è infrastruttura indipendente dall'auth, finché lavora su task fake)
- M6 (scaffolding frontend, design system, mock data) può partire in parallelo a M2 appena M1 espone l'auth
- M8 può iniziare in parallelo a M7 una volta che M5 espone i dati

### 5.4 Gantt (Mermaid)

```mermaid
gantt
    title EchoMind — Roadmap a 10 settimane
    dateFormat  YYYY-MM-DD
    axisFormat  S%V

    section Fondamenta
    M0 Project Foundation        :m0, 2026-04-27, 4d
    M1 Identity & Persistence    :m1, after m0, 7d

    section Backend Core
    M2 Content Ingestion         :m2, after m1, 5d
    M3 Async Infrastructure      :m3, after m0, 6d
    M4 Media Processing          :m4, after m2 m3, 7d
    M5 Knowledge Extraction      :crit, m5, after m4, 12d

    section Frontend
    M6 Frontend Skeleton         :m6, after m1, 10d

    section Integrazione
    M7 E2E Integration           :crit, m7, after m5 m6, 6d
    M8 Q&A Interface             :m8, after m7, 7d

    section Produzione
    M9 Production Readiness      :m9, after m7, 5d
```

---

## 6. Rischi e Vincoli

### 6.1 Risk Register

| # | Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|---|
| R1 | **Costi LLM fuori controllo** durante estrazione su documenti grandi | Alta | Alto | Chunking aggressivo, limite caratteri per request, prompt caching, monitoraggio token con counter, soft-cap per utente |
| R2 | **Recursive summarization** produce output incoerente o si perde in loop | Media | Alto | Schema Pydantic strict + validation, max-depth, deduplicazione semantica via embedding cosine, golden-set di test |
| R3 | **Neo4j AuraDB free tier saturazione** (50k nodi) | Media | Medio | Limite documenti per utente, soglia di archi prima del compact/merge, alert via query di counting |
| R4 | **Latenza Whisper su file lunghi** (>10 min audio) | Alta | Medio | Chunking audio con `pydub`/`ffmpeg`, parallelizzazione chunk, progress incrementale via WebSocket |
| R5 | **Sicurezza presigned URL** (URL leak, abuso) | Media | Alto | TTL breve (10-15 min), validation user_id nel path, logging accessi B2, max upload size |
| R6 | **Race condition** tra worker che scrivono sullo stesso documento | Bassa | Alto | Lock optimistico (version column), idempotency key, transazioni Cypher esplicite |
| R7 | **Frontend bloccato** su grafo molto grande (>500 nodi) | Alta | Medio | Progressive rendering, view-by-community prima, virtualizzazione, livelli di dettaglio |
| R8 | **Vendor lock-in** (Supabase, B2, OpenAI) | Media | Basso | Astrazioni dietro interfacce (repository pattern), variabili env, evitare feature proprietarie |
| R9 | **Curva di apprendimento** (Celery, Neo4j, Cypher, React Flow tutti nuovi) | Alta | Alto | Learning milestones espliciti, spike di 1 giorno per tecnologia prima di integrarla |
| R10 | **Scope creep** (M8 diventa "ChatGPT su grafo") | Alta | Medio | Definition of Done rigorosa, milestone non si chiude finché non passa il test di accettazione |

### 6.2 Vincoli del progetto

- **Token budget**: Sonnet incluso in Claude Pro (CLAUDE.md). Niente preoccupazioni qui, ma OpenAI è pay-per-use.
- **Free tier limits**: Supabase 500MB, Neo4j 50k/175k, B2 10GB → sufficienti per MVP, non per produzione reale.
- **Singolo developer + mentor**: niente parallelismo umano vero. Il "parallel work" è virtuale (alternare contesti).
- **Deadline implicita**: 10 settimane per arrivare a M7 (MVP funzionante).

---

## 7. Sequenza Dettagliata di Implementazione

### M0 — Project Foundation (4 giorni)

| Aspetto | Dettagli |
|---|---|
| **Componenti** | Monorepo structure, `pyproject.toml`, `package.json`, Docker Compose dev, pre-commit hooks, ADR folder, `.env.example` |
| **Teoria minima** | Monorepo vs polyrepo, dependency management Python (Poetry/uv), Docker Compose networking, Architecture Decision Records |
| **Tecnologie** | uv o Poetry, ruff, mypy, pytest, Docker, pnpm/npm |
| **Deliverable** | `docker compose up` avvia RabbitMQ + Redis + Postgres locale |
| **Tempo** | 4 giorni |
| **Done criteria** | `make dev` parte senza errori, lint passa, primo commit con CI green |
| **Next** | M1 |

### M1 — Identity & Persistence (7 giorni)

| Aspetto | Dettagli |
|---|---|
| **Componenti** | `app/main.py`, `app/core/config.py` (Pydantic Settings), `app/core/security.py` (JWT verification), modelli ORM, `app/api/v1/auth.py`, RLS policies, Alembic |
| **Teoria minima** | Dependency Injection in FastAPI, JWT lifecycle, RLS PostgreSQL, async vs sync SQLAlchemy, connection pooling |
| **Tecnologie** | FastAPI, SQLAlchemy 2.0 async, asyncpg, Alembic, Supabase client, python-jose |
| **Deliverable** | Endpoint `/auth/signup`, `/auth/login`, `/users/me`, healthcheck |
| **Tempo** | 7 giorni |
| **Done criteria** | Posso registrarmi, ricevere JWT, fare GET autenticata, vedere RLS bloccare un altro utente |
| **Next** | M2 + M3 in parallelo |

### M2 — Content Ingestion (5 giorni)

| Aspetto | Dettagli |
|---|---|
| **Componenti** | `app/services/storage.py` (B2 client), endpoint init/confirm upload, modello `Document`, validazione MIME, quota utente |
| **Teoria minima** | Presigned URL pattern, S3 API, content-type sniffing, idempotency in upload |
| **Tecnologie** | boto3 (S3-compatible per B2), python-magic |
| **Deliverable** | Posso ottenere URL, fare PUT da curl, vedere `documents` aggiornarsi |
| **Tempo** | 5 giorni |
| **Done criteria** | Test e2e: presigned URL → upload → confirm → record in DB con status=uploaded |
| **Next** | M4 |

### M3 — Async Infrastructure (6 giorni, parallelo a M1/M2)

| Aspetto | Dettagli |
|---|---|
| **Componenti** | `worker/celery_app.py`, `worker/tasks/`, signal handlers, retry policy, dead-letter exchange RabbitMQ, endpoint stato task, structured logging |
| **Teoria minima** | Message broker patterns (work queue, pub-sub), at-least-once vs exactly-once delivery, idempotency, task acknowledgment |
| **Tecnologie** | Celery 5+, RabbitMQ, Redis as result backend, structlog |
| **Deliverable** | Task fake "echo": API riceve richiesta → enqueue → worker logga → stato "completed" |
| **Tempo** | 6 giorni |
| **Done criteria** | Posso vedere il flusso end-to-end di un task asincrono e tracciarne lo stato |
| **Next** | M4 |

### M4 — Media Processing (7 giorni)

| Aspetto | Dettagli |
|---|---|
| **Componenti** | Worker `transcribe`, parser docs (`pypdf`, `python-docx`), chunking audio, normalizzazione testo, evento `transcript.ready` |
| **Teoria minima** | Whisper API limits (25MB), audio chunking, encoding/decoding multimediale, retry su API esterne |
| **Tecnologie** | OpenAI SDK, ffmpeg, pypdf, python-docx |
| **Deliverable** | Carico un PDF/MP3 → ottengo testo |
| **Tempo** | 7 giorni |
| **Done criteria** | Test su 3 input (PDF testo, PDF scansione [error path], MP3 30 min) tutti producono testo o errore gestito |
| **Next** | M5 |

### M5 — Knowledge Extraction (12 giorni — il più rischioso)

| Aspetto | Dettagli |
|---|---|
| **Componenti** | Prompt templates, `LLMGraphTransformer` config, schema Pydantic Entity/Relation, deduplicazione semantica, persistence Cypher, community detection, recursive summarization |
| **Teoria minima** | Prompt engineering, few-shot, structured output, embedding e cosine similarity, Louvain algorithm, Cypher MERGE pattern, vector indexing |
| **Tecnologie** | LangChain, OpenAI/Anthropic, Neo4j Python driver, GDS plugin (se disponibile in AuraDB free), pgvector (per embeddings) |
| **Deliverable** | Da un transcript ottengo un grafo Neo4j navigabile + summary multilivello |
| **Tempo** | 12 giorni |
| **Done criteria** | Su 3 documenti golden, l'estrazione produce nodi/relazioni "ragionevoli" (validazione manuale + test su entità note) |
| **Next** | M7 |

### M6 — Frontend (10 giorni, parte da fine M1)

| Aspetto | Dettagli |
|---|---|
| **Componenti** | Vite scaffold, routing (TanStack Router o React Router), auth context, upload UI, dashboard documenti, viewer grafo (React Flow + Elk), node/edge custom, drill-down |
| **Teoria minima** | React Flow API, Elk.js layout algorithms, Zustand patterns, suspense, optimistic UI |
| **Tecnologie** | React 18, Vite, Tailwind, Zustand, React Flow v12, Elk.js, TanStack Query |
| **Deliverable** | Posso loggarmi, caricare, vedere stato, esplorare grafo (con dati mock prima, reali dopo M5) |
| **Tempo** | 10 giorni |
| **Done criteria** | Lighthouse score >85, grafo di 200 nodi naviga fluido |
| **Next** | M7 |

### M7 — E2E Integration (6 giorni)

| Aspetto | Dettagli |
|---|---|
| **Componenti** | WebSocket gateway in FastAPI, broadcast su Redis pub-sub, gestione errori UI completa, esportazione |
| **Teoria minima** | WebSocket auth, Redis pub-sub vs RabbitMQ, error boundary React |
| **Deliverable** | Demo: upload → vedo progress live → grafo appare → esporto |
| **Tempo** | 6 giorni |
| **Done criteria** | 3 utenti diversi caricano in parallelo e vedono solo i propri dati aggiornati live |

### M8 — Q&A (7 giorni, opzionale per MVP)

| Aspetto | Dettagli |
|---|---|
| **Componenti** | Chat UI, endpoint `/chat`, retrieval ibrido (Cypher + vector), citation, history |
| **Teoria minima** | RAG, hybrid retrieval, prompt design per Q&A, citation patterns |
| **Tecnologie** | pgvector, LangChain RAG chains |
| **Done criteria** | Risposte citano nodi del grafo; latenza <5s; allucinazioni rare su test set |

### M9 — Production Readiness (5 giorni)

| Aspetto | Dettagli |
|---|---|
| **Componenti** | Dockerfile multi-stage, GitHub Actions, deploy AWS, Sentry, rate limiter, backup script |
| **Teoria minima** | Multi-stage builds, secrets management, observabilità, blue-green deploy basic |
| **Done criteria** | App live su URL pubblico, monitoraggio attivo, runbook scritto |

---

## 8. Setup Prerequisiti

### 8.1 Cosa fai TU manualmente (prima di tutto)

| # | Azione | Output atteso |
|---|---|---|
| 1 | Crea account Supabase + nuovo progetto | URL + anon key + service key + DB password |
| 2 | Crea istanza Neo4j AuraDB Free | bolt URI + username + password |
| 3 | Crea account Backblaze B2 + bucket privato + application key | keyID + appKey + bucket name + endpoint |
| 4 | Crea API key OpenAI con limiti spending | API key |
| 5 | Crea repo GitHub privato | URL repo |
| 6 | Installa: Docker Desktop, Python 3.11+, Node 20+, uv (o Poetry), pnpm | versioni verificate |
| 7 | Crea `.env` da `.env.example` con tutte le credenziali | file `.env` locale (NON committato) |

### 8.2 Cosa farò io (Claude) al primo prompt di implementazione

1. **Plan Mode**: proporrò la struttura repo dettagliata e l'aspettarò la tua conferma.
2. **Scaffolding M0**: creerò `pyproject.toml`, `docker-compose.yml`, struttura directory, pre-commit, README minimo.
3. **Smoke test**: creerò script `scripts/check_env.py` che verifica connessione a tutti i servizi cloud configurati.
4. **Spiegazione**: per ogni file, una sezione "Perché questo file è qui" e "Best practice applicata".

### 8.3 Test/validazioni per prerequisito

- Supabase: `psql $DATABASE_URL -c "SELECT 1"` → ritorna `1`
- Neo4j: query Cypher `RETURN 1` via `cypher-shell` → ritorna `1`
- B2: lista bucket via AWS CLI con endpoint custom → vedi il bucket
- OpenAI: `curl` su `/v1/models` con la key → status 200
- RabbitMQ locale: management UI su `localhost:15672` accessibile
- Redis locale: `redis-cli ping` → `PONG`

---

## 9. Learning Milestones

| Milestone | Concetti chiave da padroneggiare |
|---|---|
| M0 | Monorepo layout, dependency pinning, Docker Compose, ADR, pre-commit philosophy |
| M1 | **Dependency Injection in FastAPI**, JWT lifecycle, **Row-Level Security**, async Python, Pydantic Settings, connection pooling |
| M2 | **Presigned URL pattern**, S3 API, idempotency, content validation, separazione metadata vs binary |
| M3 | **Message broker patterns** (work queue, fanout, DLQ), Celery internals, at-least-once delivery, **idempotency** |
| M4 | OpenAI API design, retry exponential backoff, audio chunking, streaming vs batch processing |
| M5 | **Prompt engineering** strutturato, **structured output** con Pydantic, **embeddings & semantic similarity**, **Cypher MERGE**, community detection (Louvain), **recursive summarization** |
| M6 | **React Flow** (nodes, edges, handlers), **Elk.js** layout, Zustand vs Context, optimistic UI, suspense |
| M7 | **WebSocket auth**, Redis pub-sub, integration testing async flows, error boundaries |
| M8 | **RAG patterns**, hybrid retrieval (graph + vector), citation, hallucination control |
| M9 | Multi-stage Docker, **CI/CD pipelines**, secrets management, **observability** (logs, metrics, traces), blue-green deploy |

---

## 10. Piano di Validazione (Definition of Done per milestone)

| Milestone | Test minimo per dirla "completa" |
|---|---|
| **M0** | `make dev` su clone fresco funziona; CI green su commit vuoto; ADR-001 scritto |
| **M1** | Posso `signup` → `login` → `GET /users/me` con JWT; un secondo utente NON vede dati del primo (RLS test) |
| **M2** | Test e2e: ottengo presigned URL, faccio PUT con curl, confermo, vedo riga in `documents` |
| **M3** | Task "echo" → enqueue → worker consuma → status passa pending→running→completed; un task che fallisce 3 volte va in DLQ |
| **M4** | 3 input golden (PDF testuale, MP3 5 min, TXT) producono transcript salvato in DB |
| **M5** | Su 1 documento di riferimento: ≥10 nodi creati, ≥15 archi, summary multilivello generato; query di sanity: `MATCH (n) RETURN count(n)` ritorna numero atteso |
| **M6** | Login → upload → polling status → grafo renderizzato; navigazione drill-down funziona |
| **M7** | 2 utenti in parallelo: ognuno carica e vede solo i suoi update via WebSocket; export PNG funziona |
| **M8** | "Cosa dice il documento su X?" → risposta cita nodi reali del grafo |
| **M9** | URL pubblico raggiungibile; deploy automatico su push a `main`; alert Sentry su errore forzato |

---

## Tabella Riassuntiva

| Milestone | Durata | Prerequisiti | Learning Focus | Success Criteria |
|---|---|---|---|---|
| M0 | 4g | — | Monorepo, Docker, ADR | `make dev` works |
| M1 | 7g | M0 | DI, JWT, RLS, async ORM | Auth + RLS demo |
| M2 | 5g | M1 | Presigned URLs, S3 | Upload e2e |
| M3 | 6g | M0 | Message brokers, Celery, DLQ | Echo task + DLQ |
| M4 | 7g | M2+M3 | Whisper, parsing, chunking | 3 inputs → text |
| M5 | 12g | M4 | Prompt eng., LangChain, Cypher | Graph from doc |
| M6 | 10g | M1 | React Flow, Elk, Zustand | Interactive viewer |
| M7 | 6g | M5+M6 | WebSocket, integration | Live multi-user demo |
| M8 | 7g | M5+M6 | RAG, hybrid retrieval | Cited Q&A |
| M9 | 5g | M7 | Docker, CI/CD, observability | Live deploy |

**Totale critical path (M0→M1→M2→M4→M5→M7→M9)**: 4+7+5+7+12+6+5 = **46 giorni** = ~9.2 settimane → MVP in 10 settimane è **fattibile** con margine ~4 giorni per imprevisti, considerando che M3 e M6 sono parallelizzabili.

---

## Note finali del Senior Architect

**Tre cose su cui voglio richiamarti l'attenzione prima di partire:**

1. **M5 è il vero punto di rottura del progetto.** È la milestone più lunga, più rischiosa, e quella dove la qualità del prodotto si gioca davvero. Tutto il resto è "plumbing". Quando arriveremo lì, ti suggerirò di dedicare almeno un giorno solo a *spike* (prototipo throwaway) prima di scrivere codice "vero".

2. **Non saltare M0.** La tentazione del developer junior è iniziare subito da `app/main.py`. Quello porta a 2 settimane di "fix tooling" più tardi. Quattro giorni di setup ora ti risparmiano 2 settimane di dolore dopo.

3. **Il pattern "event-driven" del CLAUDE.md è una scelta forte.** Significa che ogni transizione di stato deve essere un evento RabbitMQ, non una chiamata sincrona. Questo è più complesso da debuggare ma è ciò che rende il sistema scalabile e resiliente. Lo discuteremo a M3.

**Prossimo passo suggerito**: confermami questo piano (o richiedimi modifiche), poi attiviamo Plan Mode per M0 e iniziamo lo scaffolding.

Suggerimento di branch quando saremo pronti a partire: `feature/m0-project-foundation`. (Ricorda: io non eseguo Git, sei tu a farlo.)
