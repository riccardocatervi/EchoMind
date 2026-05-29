# 0004 — Content Ingestion: presigned URL, S3-compatible storage e validazione MIME

- **Status**: Accepted
- **Date**: 2026-05-28
- **Deciders**: Riccardo Catervi

## Contesto e problema

M2 introduce la prima risorsa "di valore" dell'app: i documenti caricati dagli utenti. Senza questa milestone non c'è trascrizione (M4) né estrazione di knowledge graph (M5). Quattro decisioni interconnesse vincolano l'esperienza upload per il resto del progetto:

1. **SDK** per parlare con object storage (Backblaze B2 in prod)
2. **Pattern di upload** (client→backend→storage vs client→storage diretto)
3. **Validazione MIME** (trust del client vs verifica server-side)
4. **Test strategy** (storage reale vs mock)

Tutte queste decisioni si influenzano. La scelta di un SDK vincola le opzioni di mocking; il pattern di upload vincola la validazione; il pattern di test influenza la velocità di sviluppo per tutta M2-M9.

## Driver decisionali

- **Vendor independence**: B2 oggi, ma poter migrare a S3/MinIO/R2 senza riscrivere il codice
- **Scalabilità banda**: il backend non deve "passare attraverso" i file dell'utente (sprecato traffic + bottleneck)
- **Sicurezza by design**: il client può mentire su qualunque metadata, dobbiamo verificare ciò che importa
- **Velocità di sviluppo**: test deterministici, offline-friendly, senza credenziali in CI
- **Skill trasferibili**: pattern usati in qualunque progetto serio di file upload

## Opzioni considerate (per ciascuna decisione)

### Q1 — SDK per object storage

1. **boto3** (S3-compatible) — client AWS S3 ufficiale; B2 implementa l'API S3 al 100%
2. **b2sdk** (SDK nativo Backblaze) — features specifiche B2

### Q2 — Pattern di upload

1. **Presigned URL** verso storage direttamente — client invia bytes a storage, niente banda backend
2. **Multipart streaming via backend** — backend riceve il PUT, fa proxy al storage

### Q3 — Validazione MIME

1. **Server-side post-upload con magic bytes** — il backend scarica i primi byte, li passa a `python-magic`
2. **Solo Content-Type dichiarato dal client** — trust

### Q4 — Test storage

1. **`moto` (mock S3 in-memory)** — boto3 calls intercettati in memoria
2. **Bucket B2 di test reale** — credenziali reali in CI, network real-time

## Decisione

| # | Decisione |
|---|---|
| Q1 | **boto3 (S3-compatible)** |
| Q2 | **Presigned URL PUT** verso storage direttamente |
| Q3 | **Validazione server-side post-upload via magic bytes** |
| Q4 | **moto** per test; smoke test reale contro B2 a fine milestone |

### Pattern emergenti

#### Just-in-time profile provisioning come dependency

`documents.owner_id` ha FK a `profiles(id)`. Il profile è creato lazy alla prima richiesta autenticata (M1). Quindi prima di un INSERT su documents serve garantire l'esistenza del profile.

Implementato come **side effect del dependency** `get_document_service`: prima di costruire il service, chiama `profile_service.get_or_create(user_id)`. Pattern riusabile a tutte le risorse owned-by-user future.

#### Storage opzionale con 503 graceful

In dev senza credenziali B2, il `lifespan` cattura `StorageError` da `B2StorageService.from_settings(...)` e setta `app.state.storage = None`. Gli endpoint `/documents` ritornano 503 (`storage_unavailable`); il resto dell'app (`/health`, `/users/me`, `/profiles/me`) continua a funzionare. Pattern di **graceful degradation**.

#### MIME equivalence map

Magic non sempre rileva il "MIME canonical" del client. Esempi noti:
- DOCX → `application/zip` (DOCX è un ZIP con XML dentro)
- WAV → `audio/wav` vs `audio/x-wav` vs `audio/vnd.wave`
- M4A → `audio/mp4` vs `video/mp4` (container condiviso)

`MIME_EQUIVALENCES` mappa ogni MIME dichiarato → `frozenset` di MIME rilevabili accettabili. Tutto fuori dal set → mismatch, mark `failed`.

## Conseguenze

### Positive

- **Vendor-neutral**: il codice non sa che il backend è B2. Migrare a MinIO/R2 = cambiare endpoint nel `.env`.
- **Zero banda backend** per i file: il client uploada direttamente a B2. Il nostro server gestisce solo i ~2KB di metadata.
- **Sicurezza MIME genuina**: anche se il client dichiara `application/pdf` ma carica un EXE, magic bytes rileva il mismatch → `status=failed`, niente trascrizione/estrazione su file malevoli.
- **Test deterministici e offline**: `moto` simula B2 in memoria. CI senza credenziali, test in microsecondi.
- **Presigned URL con `Content-Length` constraint**: il client non può "lying" sulla size — B2 verifica al ricevimento del PUT.
- **Indice composito sfruttato**: query "lista mia paginata" risolta interamente in B-tree, zero sort.
- **Hard delete idempotente**: order B2 → DB, ogni step retriable safely. Eventually consistent senza orchestrazione complicata.

### Negative / Trade-off accettati

- **Storage interface meno idiomatica per B2**: alcuni feature specifici Backblaze (es. file info metadata) sono inaccessibili. Trade-off vs vendor independence. Vinta.
- **Magic bytes su 256 byte**: alcuni formati (es. WAV header lungo) potrebbero essere identificati genericamente. Mitigazione: MIME equivalence map gestisce i casi noti.
- **DOCX = ZIP nella detection**: significa che anche uno ZIP non-DOCX uploadato come DOCX passa il check. Trade-off accettato: validazione semantica DOCX richiederebbe parser zip + check manifest, costoso.
- **Presigned URL leak**: TTL breve (15 min), Content-Length pinned, Content-Type pinned. Anche se l'URL viene leakato, attacker non può uploadare file con dimensione/tipo diverso. Storage-key è UUID server-generated, niente collision.
- **`moto` può divergere dal vero B2**: alcune feature S3 non sono implementate, errori non identici. Mitigazione: smoke test reale contro B2 prima del deploy.
- **values_callable per Enum**: SQLAlchemy di default serializza il NOME del Python Enum, Postgres accetta solo i VALORI. Workaround applicato in `Document.status`. Da ricordare per ogni futuro Enum.
- **Just-in-time profile in tutti gli endpoint owned-by-user**: aggiunge un `SELECT 1 FROM profiles` ad ogni request. Mitigazione: indice PK lookup è O(log n) trascurabile.

### Neutre

- **Niente multipart upload** per file > 50MB. La milestone limita esplicitamente a 50MB. Quando servirà (M4 con audio lunghi), introdurremo multipart S3.
- **Storage_key NON esposto in `DocumentRead`**: dettaglio implementativo, in download (futuro) genereremo un altro presigned URL GET.

## Pro/contro delle opzioni scartate

### Q1 — b2sdk (scartato)

- ✅ Features B2-specific (snapshot, lifecycle nativo)
- ❌ Skill non-trasferibile, vendor lock-in
- ❌ Costringe a riscrivere tutta la storage layer se cambiamo provider
- ❌ API divergente dalla S3 standard (devi rilearnerlo per ogni progetto)

### Q2 — Streaming via backend (scartato)

- ✅ Validazione MIME può avvenire **durante** il PUT (streaming magic)
- ❌ Banda backend = file size × N upload concurrent. Bottleneck immediato.
- ❌ Latency 2x (client→backend, backend→storage)
- ❌ Memoria/disk per buffer
- ❌ Limite dimensione file da architettura della rete del backend, non da storage

### Q3 — Trust Content-Type (scartato)

- ✅ Più semplice (10 righe vs 50)
- ❌ Sicurezza fittizia: il client può dichiarare qualunque cosa
- ❌ Un attaccante che voglia "iniettare" malware mascherato da PDF passa indisturbato
- ❌ In M4 (trascrizione) processeremmo file inutili o pericolosi senza accorgercene

### Q4 — Test contro B2 reale (scartato)

- ✅ Massima fedeltà
- ❌ Credenziali in CI = rischio leak
- ❌ Tempi: 1-2s per test vs microsecondi
- ❌ Risorse B2 da pulire dopo test (cron job o test fragili)
- ❌ Test fallibili per problemi di rete CI

## Riferimenti

- [boto3 docs — generate_presigned_url](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html)
- [Backblaze B2 — S3 Compatibility](https://www.backblaze.com/b2/docs/s3_compatible_api.html)
- [moto — mock_aws decorator (v5)](https://docs.getmoto.org/)
- [python-magic (libmagic bindings)](https://github.com/ahupp/python-magic)
- [`docs/adr/0002-m1-auth-and-persistence.md`](0002-m1-auth-and-persistence.md) — RLS pattern riutilizzato per documents
- [`docs/adr/0003-jwt-es256-support.md`](0003-jwt-es256-support.md) — JWT validation che protegge anche /documents
- `backend/src/echomind/services/storage.py` — wrapper boto3
- `backend/src/echomind/services/document.py` — MIME equivalence + lifecycle
- `backend/alembic/versions/0002_documents_table.py` — schema + RLS + indice composito
