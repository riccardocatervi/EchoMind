# 0005 -- Infrastruttura di job asincroni: Celery, RabbitMQ, Redis e tabella tasks

- **Status**: Accepted
- **Date**: 2026-05-30
- **Deciders**: Riccardo Catervi

## Contesto e problema

M3 introduce la spina dorsale asincrona dell'applicazione. Il lavoro pesante del progetto -- trascrizione audio (M4) ed estrazione del knowledge graph (M5) -- richiede minuti, non può vivere nel ciclo richiesta/risposta HTTP. Serve un sistema di code che permetta a un client di accodare lavoro, ricevere subito una conferma, e consultare lo stato in un secondo momento.

RabbitMQ e Redis erano già presenti nel `docker-compose.dev.yml` da M0 ma inutilizzati. M3 li attiva con un task fittizio ("echo") che esercita l'intera pipeline end-to-end, così da costruire e validare il "motore" prima di attaccarci i worker reali in M4.

Quattro decisioni interconnesse vincolano tutta l'asincronia futura:

1. **Sorgente di verità dello stato** di un task (cosa legge l'endpoint di stato)
2. **Gestione dei fallimenti** (retry, dead-letter queue)
3. **Confine sync/async** (Celery è sincrono, il nostro stack DB è async)
4. **Strategia di test** (broker reale vs simulato)

## Driver decisionali

- **Isolamento per-utente**: lo stato di un task è un dato dell'utente, deve rispettare lo stesso modello RLS di profiles/documents.
- **Affidabilità**: nessun task "perso"; i fallimenti permanenti devono finire in un posto ispezionabile, non sparire.
- **Robustezza del confine sync/async**: il bug più insidioso in questo dominio è l'affinità connessione/event-loop; va eliminato a monte.
- **Velocità e determinismo dei test**: come per M2 (moto), i test girano offline e veloci; l'infrastruttura reale si valida con uno smoke test.
- **Skill trasferibili**: pattern Celery + broker + DLQ validi in qualunque sistema a code.

## Opzioni considerate (per ciascuna decisione)

### Q1 -- Sorgente di verità dello stato del task

1. **Tabella Postgres `tasks` (RLS)** + Redis come result backend interno di Celery
2. **Solo Redis** (l'endpoint interroga il result backend di Celery)

### Q2 -- Dead-letter queue

1. **App-level (stato terminale `failed`) + DLX RabbitMQ reale** sulla coda di lavoro
2. **Full broker DLQ** con un consumer dedicato che processa i messaggi morti
3. **Minimale**: solo retry, niente DLX (rimandata alla produzione)

### Q3 -- Confine sync/async nel worker

1. **`NullPool` + `asyncio.run()` per task**, engine creato lazy post-fork
2. **Event loop persistente per processo** con pool normale

### Q4 -- Test della pipeline

1. **`run_echo` testato direttamente** + enqueue Celery patchato; broker reale solo nello smoke test
2. **`task_always_eager`** (Celery esegue i task in-process nei test)

## Decisione

| # | Decisione |
|---|---|
| Q1 | **Tabella Postgres `tasks` (RLS)** come verità di dominio + Redis result backend interno |
| Q2 | **App-level `failed` + dead-letter exchange/queue RabbitMQ reale** |
| Q3 | **`NullPool` + `asyncio.run()`**, engine lazy post-fork |
| Q4 | **`run_echo` diretto + enqueue patchato**; smoke test reale a fine milestone |

### Pattern emergenti

#### Due tracce di stato

Celery scrive l'esito dei task nel suo **result backend** (Redis): è meccanica interna (SUCCESS/FAILURE, retvalue), volatile, senza concetto di proprietà. Se l'endpoint di stato leggesse da lì, chiunque conoscesse un `task_id` ne vedrebbe lo stato -- violando il modello di sicurezza dell'app.

La **verità di dominio** vive quindi nella tabella `tasks` (Postgres, RLS owner-based): persistente, paginabile, isolata per-utente. L'API legge solo da qui. Le due tracce coesistono: Redis serve a Celery (e tornerà utile per le chain di M4), la tabella serve all'applicazione.

#### Correlazione id senza tabella di mapping

L'id della riga `tasks` (UUID generato a INSERT sotto RLS) viene passato a Celery come `task_id` (`apply_async(task_id=str(row.id))`). DB id e Celery id coincidono: nessuna struttura di mapping, il worker correla la riga via `self.request.id` (o, come qui, via argomento esplicito).

#### Worker come componente di sistema

Le transizioni di stato (`running`, `succeeded`, `failed`) le scrive il worker tramite una sessione di **sistema** (ruolo `echomind`, superuser, che bypassa RLS), perché il worker non agisce "per conto" di un utente. Conseguenza di design: sulla tabella `tasks` esistono solo le policy RLS **SELECT** e **INSERT** per gli utenti, **nessuna UPDATE**. L'assenza della policy UPDATE è essa stessa una garanzia: nessun utente può falsificare lo stato dei propri task via API.

#### Dual write (DB + broker) e ordine delle operazioni

Accodare significa scrivere su due sistemi: la riga in Postgres e il messaggio su RabbitMQ. Non è atomico. La scelta: INSERT (flush, non commit -- il commit lo fa la dependency a fine request) e poi enqueue. Se l'enqueue fallisce, sollevo `TaskEnqueueError`: l'eccezione risale fuori dalla transazione della request, che fa **rollback** -- nessuna riga orfana `queued`. Niente codice di cleanup, niente policy UPDATE.

Resta una finestra teorica (l'`apply_async` pubblica prima del commit): un worker fulmineo potrebbe leggere la riga prima che sia committata. In pratica la latenza di rete (publish + dispatch al worker) è molto maggiore del commit in-process; e se accadesse, la guardia "riga assente" in `run_echo` la gestisce come no-op. La soluzione robusta (transactional outbox) è rimandata a M9.

#### Idempotenza per at-least-once delivery

Con `task_acks_late=True` il messaggio è ack-ato dopo il completamento: se il worker muore a metà, RabbitMQ riconsegna. Garanzia at-least-once -- quindi un task può girare più volte. `run_echo` è idempotente: su una riga già in stato terminale ritorna un no-op.

## Conseguenze

### Positive

- **Isolamento per-utente nativo**: lo stato dei task passa per RLS come ogni altra risorsa; l'endpoint `GET /tasks/{id}` ritorna 404 per i task altrui, indistinguibile da "non esiste".
- **Nessun task perso e fallimenti tracciabili**: at-least-once + dead-letter queue reale. I task che esauriscono i retry sono `failed` in DB e il messaggio finisce nella coda `echomind.dead`, ispezionabile dalla management UI.
- **Confine sync/async a prova di bug**: NullPool elimina l'affinità connessione/loop; l'engine creato post-fork evita la corruzione delle risorse ereditate dal padre.
- **Test deterministici e offline**: `run_echo` testato direttamente con DB reale; l'enqueue è patchato. CI non richiede né RabbitMQ né Redis.
- **Un solo identificatore** per task (DB id == Celery id): meno stato da mantenere coerente.
- **Indice composito sfruttato**: `(owner_id, created_at DESC)` risolve la lista paginata interamente in B-tree, come per documents.

### Negative / Trade-off accettati

- **Dual write non atomico**: finestra teorica enqueue-prima-di-commit, mitigata dalla guardia "riga assente" e rimandata all'outbox in M9. Trade-off accettato per non introdurre un relay in M3.
- **Una connessione DB nuova per task** (NullPool): leggero overhead rispetto a un pool, irrilevante al nostro volume e ripagato dalla robustezza. Rivedibile in M4 con un event loop persistente se il throughput lo richiederà.
- **`task_type` come TEXT** (non ENUM): perde il type-check del DB sul tipo, ma evita una migration `ALTER TYPE` a ogni nuovo tipo di task. La validazione è applicativa (StrEnum).
- **Eager mode non usata nei test**: `asyncio.run()` dentro l'event loop di pytest-asyncio solleverebbe RuntimeError, quindi testiamo il core async direttamente. Significa che il wiring Celery (retry/Reject/DLX) non è coperto dagli unit test ma solo dallo smoke test reale.
- **URL broker/backend come `str`** e non `AmqpDsn`/`RedisDsn`: i validator URL di Pydantic normalizzano il path, e per AMQP lo slash finale codifica il virtual host -- normalizzarlo cambierebbe il vhost per sbaglio. La stringa resta intatta; kombu valida e fallisce in chiaro.

### Neutre

- **Nessun servizio worker in docker-compose**: in dev il worker gira come processo host (`make worker`), come l'API (`make serve`). Un container worker arriverà in M9.
- **Niente Celery beat / task periodici / canvas (chain, chord)**: fuori scope M3; la chain transcribe --> extract arriverà in M4/M5.

## Pro/contro delle opzioni scartate

### Q1 -- Solo Redis (scartato)

- Più rapido da costruire (nessuna tabella, model, migration)
- Nessun isolamento per-utente: il result backend non conosce la proprietà
- Stato volatile (TTL), niente audit né paginazione
- Incoerente col modello RLS del resto dell'app

### Q2 -- Full broker DLQ con consumer dedicato (scartato per ora)

- Più fedele a un sistema di produzione (gestione esplicita dei "morti")
- Più codice e più superficie di test per un task fittizio
- Il valore (azioni automatiche sui messaggi morti) non serve finché i task sono fake; rivedibile in M9

### Q3 -- Event loop persistente per processo (scartato per ora)

- Più efficiente (riusa il pool tra i task)
- Più codice e più insidie (gestione del ciclo di vita del loop nei segnali Celery)
- Per il volume di M3, NullPool + `asyncio.run()` è più semplice e altrettanto corretto

### Q4 -- `task_always_eager` nei test (scartato)

- Esercita il path Celery completo in-process
- Confligge con l'event loop di pytest-asyncio (il task fa `asyncio.run()` dentro un loop già attivo --> RuntimeError)
- Testare `run_echo` direttamente è più pulito, veloce e deterministico

## Riferimenti

- [Celery -- Tasks, retry, acks_late](https://docs.celeryq.dev/en/stable/userguide/tasks.html)
- [RabbitMQ -- Dead Letter Exchanges](https://www.rabbitmq.com/dlx.html)
- [SQLAlchemy -- Using asyncio with NullPool](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [`docs/adr/0002-m1-auth-and-persistence.md`](0002-m1-auth-and-persistence.md) -- pattern RLS + doppio ruolo riusato per tasks
- [`docs/adr/0004-content-ingestion.md`](0004-content-ingestion.md) -- just-in-time profile provisioning e indice composito riusati
- `backend/src/echomind/worker/` -- Celery app, runtime, echo task
- `backend/alembic/versions/0003_tasks_table.py` -- schema + RLS + indice composito
