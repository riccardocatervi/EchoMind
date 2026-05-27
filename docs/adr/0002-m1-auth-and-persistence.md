# 0002 — Auth, persistenza e RLS per M1

- **Status**: Accepted
- **Date**: 2026-04-26
- **Deciders**: Riccardo Catervi

## Contesto e problema

M1 deve introdurre il **primo codice applicativo** del progetto: configurazione, persistenza, autenticazione, autorizzazione e i primi endpoint. Sei decisioni interconnesse vincolano l'esperienza di sviluppo per tutto il backend:

1. **Identity Provider**: gestire signup/login direttamente o delegare a un IdP esterno?
2. **DB access**: ORM completo o SDK più leggero?
3. **Migrazioni schema**: quale tool?
4. **Schema iniziale**: cosa modellare in M1 senza fare scope creep?
5. **Ambiente dev**: DB locale, remoto, o ibrido?
6. **Sicurezza dei dati**: solo controlli applicativi o anche database-level?

Tutte queste decisioni sono prese **insieme** perché si influenzano a vicenda: la scelta dell'IdP determina la struttura dei JWT che dobbiamo validare, la scelta del DB access determina come implementiamo RLS, ecc.

## Driver decisionali

- **Tempo di implementazione M1**: 7 giorni di lavoro netto, niente di più
- **Curva di apprendimento**: progetto formativo, valore didattico cumulativo
- **Sicurezza by-design**: i dati utente devono essere isolati, anche di fronte a bug applicativi futuri
- **Fedeltà dev↔prod**: minimizzare il drift tra come gira in locale e come girerà in Supabase produzione
- **Riusabilità della conoscenza**: pattern e skill trasferibili a futuri progetti
- **Manutenibilità a lungo termine**: codice che resta leggibile e modificabile a 6-12 mesi

## Opzioni considerate

### Q1 — Identity Provider

1. **Supabase Auth (IdP esterno)** — Supabase gestisce signup/login/password reset/OAuth, ci dà JWT firmati
2. **JWT custom self-hosted** — Implementiamo signup/login/hashing/refresh token
3. **Auth0/Clerk** — IdP commerciali, simili a Supabase ma indipendenti dal DB

### Q2 — DB access

1. **SQLAlchemy 2.0 async + asyncpg** — ORM Python più maturo
2. **Supabase Python SDK** — API REST-like (PostgREST sotto)
3. **psycopg + raw SQL** — Massima trasparenza, niente ORM

### Q3 — Migrazioni schema

1. **Alembic** — Standard SQLAlchemy
2. **SQL plain files numerati** — Massima trasparenza
3. **Supabase Migrations CLI** — Tool proprietario integrato

### Q4 — Schema iniziale di M1

1. **Solo `profiles` (FK 1:1 a `auth.users`)** — Minimal, testabile, focus
2. **`profiles` + `documents`** — Anticipa M2
3. **`profiles` + `documents` + `tasks`** — Anticipa M3

### Q5 — Ambiente DB di sviluppo

1. **Postgres locale + schema `auth.users` fittizio** — Container Docker, FK risolta in locale
2. **Supabase reale anche in dev** — Niente container locale
3. **Ibrido**: locale + smoke staging Supabase prima del merge

### Q6 — Approccio sicurezza dei dati

1. **RLS database-level + filtri applicativi**
2. **Solo filtri applicativi** (`WHERE user_id = ?`)
3. **RLS rimandata a milestone separata dopo M2**

## Decisione

| # | Decisione |
|---|---|
| Q1 | **Supabase Auth** |
| Q2 | **SQLAlchemy 2.0 async + asyncpg** |
| Q3 | **Alembic** |
| Q4 | **Solo `profiles` (FK 1:1 a `auth.users`)** |
| Q5 | **Postgres locale + schema `auth.users` fittizio** |
| Q6 | **RLS database-level inclusa in M1 (minimal)** |

### Pattern emergente: doppio ruolo `echomind` / `app_runtime`

Una conseguenza non-ovvia delle scelte sopra: per testare RLS in modo realistico in dev locale, abbiamo dovuto creare **due ruoli PostgreSQL**:

- **`echomind`** — superuser, owner del DB. Usato per migration Alembic e provisioning iniziale. Equivalente di `service_role` in Supabase.
- **`app_runtime`** — `NOLOGIN`, non-superuser, soggetto a RLS. L'app si connette comunque come `echomind`, ma esegue `SET LOCAL ROLE app_runtime` dentro ogni transazione autenticata per "scendere" al livello di privilegi corretto. Equivalente di `authenticated` in Supabase.

Setup gestito da `infra/postgres-init/01_dev_role_setup.sql`, eseguito automaticamente dall'immagine Postgres al primo avvio del container.

## Conseguenze

### Positive

- **Sicurezza database-level**: anche se un bug applicativo in futuro dimentica un `WHERE user_id = ...`, PostgreSQL blocca categoricamente le righe non autorizzate. Test esplicito in `tests/test_rls.py` lo dimostra.
- **Niente codice crypto custom**: il signup/password reset/OAuth è production-grade gratis. Riduce drasticamente la superficie di attacco e il debito di sicurezza.
- **Skill trasferibili**: SQLAlchemy + Alembic + RLS + JWT validation sono pattern usati in qualunque app Python+Postgres seria. Nessun lock-in proprietario nel codice (solo in `.env`).
- **Dev offline-friendly**: niente dipendenza dalla rete per sviluppo quotidiano. CI deterministica.
- **Fedeltà dev↔prod alta**: la stessa RLS che gira in locale è quella che girerà in Supabase prod. Stessa logica, stesso pattern di `SET LOCAL ROLE`.
- **Scope M1 contenuto**: solo `profiles`, niente upload/queue/grafo. M1 finita in 7 giorni come pianificato.

### Negative / Trade-off accettati

- **Complessità del doppio ruolo**: il pattern `echomind`/`app_runtime` aggiunge un layer concettuale che un junior developer potrebbe trovare opaco. Mitigazione: spiegato in `docs/adr/0002` e nei commenti di `infra/postgres-init/01_dev_role_setup.sql`.
- **INSERT di profile richiede sessione di sistema**: il just-in-time provisioning ha bisogno di una seconda sessione `echomind` perché in M1 NON abbiamo una policy `INSERT WITH CHECK (id = sub_claim)`. Più complessità nel `ProfileService` ma più sicurezza (un utente compromesso non può creare profile per id arbitrari). Documentato in `services/profile.py`.
- **Drift potenziale Postgres locale ↔ Supabase**: il nostro `auth.users` mock ha solo `id`, mentre Supabase ne ha decine di colonne. Mitigazione: la FK punta solo `id`, niente coupling sugli altri campi. Verifica end-to-end su Supabase staging prevista a fine M1.
- **Alembic genera SQL diverso da quello che useremmo a mano**: i nomi dei constraint sono determinati dalla naming convention dichiarata in `db/base.py`. Mitigazione: naming convention esplicita evita confusione e rende il DDL prevedibile.
- **Settings con campi vuoti in dev**: variabili come `SUPABASE_URL`, `NEO4J_URI` restano vuote finché non servono. Pydantic Settings con default-vuoto-permesso le ignora ma non protegge da "ho dimenticato di popolarle in produzione". Mitigazione: futura validazione condizionale per app_env=production.

### Neutre

- **Niente policy INSERT su `profiles`** in M1. Aggiunta a M2 quando avremo bisogno di pattern "user-driven create".
- **Niente refresh token logic** — Supabase gestisce lifecycle dei token lato suo, noi solo validiamo.

## Pro/contro delle opzioni scartate

### Q1 — JWT custom (scartato)

- ✅ Controllo totale, nessuna dipendenza esterna
- ❌ Crypto fatta a mano = altissimo rischio di CVE
- ❌ Tempo: signup/login/reset/refresh prendono settimane se fatti bene
- ❌ Niente OAuth/magic link senza ulteriore lavoro

### Q1 — Auth0/Clerk (scartato)

- ✅ Production-grade come Supabase
- ❌ Vendor lock-in più forte (Supabase ce l'abbiamo già per il DB)
- ❌ Costo: pricing tier "free" più stretto rispetto a Supabase

### Q2 — Supabase SDK (scartato)

- ✅ Più semplice per CRUD basic
- ❌ Skill non-trasferibili
- ❌ Limitato per query complesse (join, aggregazioni, subquery): in M5 ci serve SQL serio
- ❌ Non-async-native idiomatico in Python

### Q2 — psycopg + raw SQL (scartato)

- ✅ Massima trasparenza, performance
- ❌ Boilerplate enorme: mapping manuale row → oggetto Python
- ❌ Type safety zero: ogni `row["display_nme"]` (typo) è KeyError a runtime
- ❌ Refactor distrutti: cambia il nome di una colonna = grep su tutto il codebase

### Q3 — SQL plain (scartato)

- ✅ Trasparenza assoluta
- ❌ Niente autogenerate da modelli SQLAlchemy
- ❌ Niente rollback automatico, niente verifica dello stato corrente del DB
- ❌ Reinventare la ruota

### Q3 — Supabase Migrations CLI (scartato)

- ✅ Integrato col loro ecosistema
- ❌ Skill non-trasferibili
- ❌ Più difficile testare/validare in locale

### Q4 — Anticipare `documents`/`tasks` (scartato)

- ✅ M2/M3 partirebbero più veloci
- ❌ M1 si allunga, rischio scope creep
- ❌ Test/migration più complessi senza valore immediato
- ❌ Modellare prematuramente porta a refactor pesanti dopo

### Q5 — Supabase reale anche in dev (scartato)

- ✅ Massima fedeltà al production
- ❌ Niente dev offline
- ❌ Rischio di toccare dati condivisi accidentalmente
- ❌ Ogni reset schema impatta il cloud

### Q6 — Solo filtri applicativi (scartato)

- ✅ Più semplice da scrivere
- ❌ Una dimenticanza = data leak silenzioso
- ❌ Niente difesa in profondità

### Q6 — Rimandare RLS a milestone successiva (scartato)

- ✅ M1 più snella
- ❌ Costruire feature senza RLS poi retrofittarle è doloroso (UI flow, test, ecc.)
- ❌ Posticipare una competenza chiave (= il pattern Supabase)

## Riferimenti

- [Supabase Auth concepts](https://supabase.com/docs/guides/auth)
- [PostgreSQL Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [SQLAlchemy 2.0 migration guide](https://docs.sqlalchemy.org/en/20/changelog/migration_20.html)
- [Alembic naming conventions](https://alembic.sqlalchemy.org/en/latest/naming.html)
- [PostgREST → Supabase pattern: authenticator + authenticated](https://postgrest.org/en/stable/explanations/auth.html)
- `docs/architecture-phase0.md` — roadmap milestone
- `docs/adr/0001-tech-stack-foundations.md` — decisioni di M0
- `infra/postgres-init/01_dev_role_setup.sql` — implementazione doppio ruolo
- `backend/alembic/versions/0001_initial_schema.py` — schema + RLS policies
