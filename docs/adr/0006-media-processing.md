# 0006 -- Media processing: pipeline pura, Transcriber Protocol, errori retryable, trigger su confirm

- **Status**: Accepted
- **Date**: 2026-06-01
- **Deciders**: Riccardo Catervi

## Contesto e problema

M4 e' il **primo worker reale** agganciato al motore asincrono di M3: trasforma i file caricati in M2 (PDF, DOCX, TXT, audio) in **testo normalizzato**, persistito come risorsa `transcripts`. E' il prerequisito di M5, che costruira' il knowledge graph a partire da questo testo.

Il flusso end-to-end: il worker scarica il file da B2, lo estrae (parsing dei documenti) o lo trascrive (audio via Whisper), normalizza il risultato e lo salva. L'utente, dopo aver confermato l'upload, fa polling su un endpoint finche' il transcript non e' pronto.

Cinque decisioni vincolano la pipeline e ne determinano testabilita', robustezza e costo:

1. **Architettura della pipeline** (accoppiata al provider di trascrizione o no)
2. **Gestione degli errori** (cosa ritentare, cosa no)
3. **Segmentazione audio** (il limite di dimensione di Whisper)
4. **Innesco della trascrizione** (chi e quando accoda il task)
5. **Persistenza dell'output** (dove vive il testo derivato)

## Driver decisionali

- **Testabilita' offline e deterministica**: come per M2 (moto) e M3 (enqueue patchato), la pipeline deve essere testabile senza rete (niente chiamate OpenAI reali) e con coperture significative anche dove manca ffmpeg in CI.
- **Sostituibilita' del provider**: Whisper non deve essere cablato nel cuore della pipeline; domani potremmo voler usare un modello locale.
- **Affidabilita' dei task**: un file corrotto non deve consumare retry inutili; un blip di rete sí. La distinzione va modellata esplicitamente.
- **Riuso del motore M3**: niente nuova infrastruttura di code; M4 attacca un worker vero al pattern gia' validato (two-layer task, idempotenza, dead-letter).
- **Coerenza col modello RLS**: il transcript e' un dato dell'utente; deve rispettare lo stesso isolamento di profiles/documents/tasks.
- **Skill trasferibili**: dependency inversion, error taxonomy, chunking di media, trigger di dominio.

## Opzioni considerate (per ciascuna decisione)

### Q1 -- Architettura della pipeline

1. **Pipeline pura e sincrona + `Transcriber` come Protocol** iniettato
2. **Pipeline accoppiata** al client OpenAI (chiamata diretta dentro l'orchestratore)

### Q2 -- Gestione degli errori

1. **Tassonomia `retryable`**: `ProcessingError` distingue errori permanenti (no retry) da transienti (retry)
2. **Retry indifferenziato**: ogni eccezione ritenta fino al tetto, poi dead-letter

### Q3 -- Segmentazione audio (limite 25 MB di Whisper)

1. **Fast-path + split per tempo**: file sotto soglia inviati as-is; sopra soglia, divisi per durata e ri-esportati in MP3
2. **Ricodifica sempre** in un formato compatto prima dell'invio
3. **Split per byte** del file grezzo

### Q4 -- Innesco della trascrizione

1. **Service-level**, dentro `confirm_upload`, sulla transizione `pending --> uploaded`
2. **Endpoint-level**: l'handler del confirm chiama il servizio task dopo il confirm
3. **Event-driven**: un evento `document.uploaded` consumato da un dispatcher

### Q5 -- Persistenza dell'output

1. **Tabella `transcripts` dedicata** (1:1 con documents, RLS SELECT-only)
2. **Colonne sul record `documents`** (es. `transcript_text`, `transcript_meta`)

## Decisione

| # | Decisione |
|---|---|
| Q1 | **Pipeline pura e sincrona** con `Transcriber` Protocol iniettato (dependency inversion) |
| Q2 | **`ProcessingError.retryable`**: permanente --> `failed` subito; transiente --> retry con backoff |
| Q3 | **Fast-path** (nessuna ricodifica sotto soglia) **+ split per tempo in MP3** sopra soglia |
| Q4 | **Trigger service-level** in `confirm_upload`, sulla sola transizione a `uploaded` |
| Q5 | **Tabella `transcripts` dedicata**, 1:1 con documents, RLS SELECT-only, upsert ON CONFLICT |

### Pattern emergenti

#### Confine astratto sulla trascrizione (dependency inversion)

`process_media` (l'orchestratore) dipende da un **Protocol** `Transcriber`, non dal client OpenAI concreto. Vantaggi: i test iniettano un transcriber finto (niente API key, niente rete); l'implementazione reale (`OpenAIWhisperTranscriber`) e' sostituibile con un modello locale senza toccare la pipeline. Il transcriber viene costruito (via factory nel worker) **solo per gli input audio**: processare un PDF non richiede alcuna API key OpenAI.

#### Errori permanenti vs transienti

E' l'analogo, per i task reali, del flag `fail` dell'echo in M3: lí era un input a decidere il percorso retry/DLQ, qui e' la **natura dell'errore**. `ProcessingError` porta un flag `retryable`. File corrotto, tipo non supportato, contenuto vuoto, oggetto storage assente (404): **permanenti** -- la stessa esecuzione fallirebbe identica, quindi si va dritti a `failed` (--> dead-letter) senza sprecare retry. Blip di rete verso B2, 5xx / rate-limit di Whisper: **transienti** -- retry con backoff esponenziale; esauriti, diventano `failed`. Il worker legge `err.retryable` e traduce nell'azione Celery (`self.retry` o `Reject`).

#### Chunking che rispetta i frame

Whisper rifiuta file oltre 25 MB; la soglia operativa e' 24 MB con margine. Due rami: un file gia' sotto soglia (la quasi totalita') viene inviato **as-is**, senza ricodifica -- zero perdita di qualita', zero lavoro di ffmpeg. Un file oltre soglia viene caricato, **diviso per tempo** in `ceil(dimensione / soglia)` pezzi e ri-esportato in MP3 (compatto e ben gestito da Whisper). Si divide per tempo e non per byte perche' tagliare i byte grezzi spezzerebbe un frame audio a meta', producendo chunk illeggibili.

#### Trigger al punto esatto di transizione

`confirm_upload` accoda la trascrizione **subito dopo** aver marcato il documento `uploaded`. Gli early-return in cima al metodo (documento gia' `uploaded` o `failed`) escludono i casi non-transizione: l'enqueue scatta quindi **una sola volta**, esattamente quando il documento entra in `uploaded`. L'enqueue vive nella **stessa transazione della request**: se fallisce (broker irraggiungibile --> `TaskEnqueueError`), il rollback annulla anche il `mark_uploaded`, il confirm risponde 503 e il client puo' ritentare. E' lo stesso dual-write di M3 (insert-then-enqueue, rollback-on-failure). Il `TaskService` e' iniettato in `DocumentService` come dipendenza **opzionale**: un `DocumentService` senza trigger resta legittimo (flussi senza processing), il wiring reale lo fornisce sempre.

#### Lavoro sincrono lungo fuori dall'event loop

Parsing, ffmpeg e Whisper sono operazioni **sincrone** e potenzialmente lunghe (minuti, per un audio chunked). Il core async del worker le esegue via `asyncio.to_thread`, cosi' da non bloccare il proprio event loop mentre intorno fa I/O su DB. I commit di stato separati (`running` prima del lavoro, `succeeded`/`failed` dopo) fanno sí che l'API osservi lo stato `running` durante l'elaborazione.

#### Output di sistema, 1:1 col documento

La tabella `transcripts` ha `document_id` **UNIQUE** (relazione 1:1; abilita l'upsert `ON CONFLICT` che rende idempotente il ri-processing) e `owner_id` **denormalizzato** dal documento, cosi' la policy RLS lo confronta col claim JWT senza join. Esiste solo la policy **SELECT**: il transcript lo scrive il worker (sessione di sistema, bypassa RLS), l'utente lo legge soltanto -- l'assenza di policy INSERT/UPDATE garantisce che un utente non possa fabbricarne o alterarne uno.

## Conseguenze

### Positive

- **Pipeline testabile offline**: `process_media` e' una funzione pura testata con input "golden" generati in memoria (PDF spec-valido, DOCX, TXT); il transcriber e' un fake. Nessuna chiamata OpenAI nei test.
- **Provider sostituibile**: cambiare motore di trascrizione tocca solo l'implementazione del Protocol, non la pipeline.
- **Retry mirati**: gli errori permanenti non sprecano tentativi; i transienti sopravvivono ai blip. La distinzione e' esplicita e testata.
- **Trigger affidabile e idempotente**: parte una sola volta per transizione, nella transazione del confirm; un broker giu' non lascia documenti "uploaded ma mai accodati" (rollback).
- **Ri-processing sicuro**: l'upsert su `document_id` sostituisce il transcript invece di violare il vincolo UNIQUE.
- **Isolamento per-utente nativo**: il transcript passa per RLS come ogni risorsa; `GET /documents/{id}/transcript` ritorna 404 per i transcript altrui (indistinguibile da "non pronto").
- **Riuso del motore M3**: stessa struttura two-layer (core async testabile + wrapper sincrono), stessa idempotenza, stessa dead-letter.

### Negative / Trade-off accettati

- **ffmpeg come dipendenza di sistema**: il chunking audio (pydub) richiede ffmpeg installato (come `libmagic` per M2). In CI -- dove ffmpeg non e' presente -- i test che decodificano audio reale si auto-saltano (`skipif`); l'orchestrazione del ramo audio resta coperta mockando il chunking, e la pipeline audio completa si valida nello smoke test locale.
- **L'API importa il pacchetto `processing`**: avendo scelto di accodare importando il task (`transcribe_task.apply_async`, coerente con l'echo di M3), il processo API trascina `processing` (e quindi pydub/openai) all'avvio. E' innocuo (l'import dei warning di pydub e' silenziato; ffmpeg serve solo a runtime). L'alternativa piu' disaccoppiata -- accodare per nome con `celery_app.send_task("echomind.transcribe", ...)`, senza importare il task -- e' annotata come possibile evoluzione quando API e worker saranno deployati separatamente (M9).
- **Trascrizione lossy per i file grandi**: i chunk oltre soglia vengono ri-esportati in MP3. Accettabile per la trascrizione (Whisper gestisce bene l'MP3); i file sotto soglia restano intatti.
- **Nessun OCR**: un PDF scansionato senza layer di testo produce contenuto vuoto --> `EmptyContentError` (permanente). L'OCR e' fuori scope M4.
- **`source_type` come TEXT** (non ENUM): coerente con `task_type` di M3 -- niente type-check del DB sul valore, validazione applicativa via `StrEnum`.

### Neutre

- **Polling per lo stato**: l'endpoint del transcript ritorna 404 finche' non e' pronto; il client fa polling (o consulta `GET /tasks/{id}`). Lo streaming del progresso (WebSocket) e' rimandato a M7.
- **Nessuna chain transcribe --> extract**: l'orchestrazione multi-task verra' in M5; per ora il transcribe e' un task singolo.

## Pro/contro delle opzioni scartate

### Q1 -- Pipeline accoppiata a OpenAI (scartata)

- Meno codice, nessun Protocol da definire
- Non testabile offline senza mockare in profondita' il client OpenAI
- Provider cablato: sostituirlo richiederebbe di riscrivere l'orchestratore

### Q2 -- Retry indifferenziato (scartato)

- Piu' semplice (un solo percorso d'errore)
- Spreca i 3 retry su input che falliranno identici (PDF corrotto, audio muto)
- Ritarda lo stato `failed` finale e intasa la coda

### Q3 -- Ricodifica sempre / split per byte (scartati)

- Ricodifica sempre: lavoro di ffmpeg e perdita di qualita' inutili per la maggioranza dei file (gia' sotto soglia)
- Split per byte: semplice da calcolare ma taglia i frame audio --> chunk corrotti, trascrizione spazzatura

### Q4 -- Trigger nell'endpoint / event-driven (scartati)

- Endpoint-level: l'handler non distingue "appena confermato" da "riconfermato" (confirm e' idempotente) --> doppio enqueue su re-confirm
- Event-driven: piu' disaccoppiato ma introduce un event bus/dispatcher non necessario in M4; rivedibile quando i trigger si moltiplicheranno

### Q5 -- Colonne su `documents` (scartata)

- Nessuna tabella nuova
- Mescola il lifecycle dell'upload con quello del processing
- Niente relazione 1:1 esplicita ne' upsert pulito; un record `documents` si gonfia di campi di un'altra responsabilita'

## Riferimenti

- [OpenAI -- Speech to Text (Whisper)](https://platform.openai.com/docs/guides/speech-to-text)
- [pypdf -- Extract text](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)
- [python-docx](https://python-docx.readthedocs.io/)
- [ffmpeg](https://ffmpeg.org/) -- richiesto da pydub per il chunking audio
- [`docs/adr/0005-async-job-infrastructure.md`](0005-async-job-infrastructure.md) -- motore async (Celery, DLQ, two-layer task, idempotenza) riusato da M4
- [`docs/adr/0004-content-ingestion.md`](0004-content-ingestion.md) -- documents, storage B2 e RLS su cui M4 si innesta
- `backend/src/echomind/processing/` -- pipeline pura (parsers, normalize, audio, transcription, errori)
- `backend/src/echomind/worker/tasks/transcribe.py` -- worker reale (core async + wrapper Celery)
- `backend/alembic/versions/0004_transcripts_table.py` -- schema transcripts + RLS + indice composito
