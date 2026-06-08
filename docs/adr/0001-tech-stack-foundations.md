# 0001 — Fondamenta tecnologiche di M0

- **Status**: Accepted
- **Date**: 2026-04-26
- **Deciders**: Riccardo Catervi

## Contesto e problema

EchoMind è in fase di scaffolding (Milestone M0 — Project Foundation). Prima di scrivere qualunque codice applicativo, dobbiamo decidere quattro questioni fondazionali che vincoleranno l'esperienza developer per l'intera vita del progetto:

1. **Package manager Python** per backend
2. **Strategia infrastruttura locale** (database, broker, cache)
3. **Tooling di monorepo** (orchestrazione di backend + frontend)
4. **Tempistica scaffolding frontend** (in M0 oppure rimandato a M6)

Stack tecnologica complessiva (FastAPI, Celery, Neo4j, React, ecc.) è già definita a livello di visione di progetto e fuori dallo scope di questo ADR.

## Driver decisionali

- **Velocità di feedback locale**: dev experience reattiva (sync/install <30s)
- **Riproducibilità**: clone fresco → ambiente funzionante con un comando
- **Curva di apprendimento minima**: progetto a singolo developer, niente overhead di tool sofisticati
- **Sicurezza in dev**: niente accesso accidentale a dati di staging/prod
- **Scope creep prevention**: M0 deve rimanere ~4 giorni, non espandersi

## Opzioni considerate (per ciascuna delle 4 questioni)

### Q1 — Package manager Python

1. **uv** (Astral) — Rust-based, installer + venv + lock + builder unificato
2. **Poetry** — Python-based, maturo, dependency resolver eccellente
3. **pip + pip-tools** — minimalista, manuale

### Q2 — Infrastruttura locale

1. **Tutto via docker-compose locale** (Postgres + RabbitMQ + Redis)
2. **Hybrid**: Supabase remoto in dev + RabbitMQ/Redis locali
3. **Tutto remoto**: Supabase + CloudAMQP + Upstash anche in dev

### Q3 — Monorepo orchestration

1. **Cartelle semplici + Makefile root**
2. **Turborepo** (pnpm workspaces, cache build incrementale)
3. **Nx** (mix Python+Node, plugin ricchi)

### Q4 — Frontend in M0

1. **Solo backend+infra ora**, scaffolding frontend in M6
2. **Anche scaffold frontend minimale** (Vite+React+Tailwind) già in M0

## Decisione

| # | Decisione |
|---|---|
| Q1 | **uv** |
| Q2 | **docker-compose locale** per tutti i servizi infrastrutturali |
| Q3 | **Cartelle semplici + Makefile** |
| Q4 | **Solo backend+infra ora** (frontend rimandato a M6) |

## Conseguenze

### Positive

- **Setup veloce**: `uv sync` ~10x più rapido di `poetry install`; sviluppo locale stops/starts senza attesa.
- **Isolamento totale**: docker-compose locale evita di toccare risorse cloud durante sperimentazione (schema breaking changes, query distruttive).
- **Niente costo di apprendimento aggiuntivo**: né Turborepo né Nx vanno studiati. Make è universale.
- **M0 resta nei tempi (~4 giorni)**: non gonfiato dallo scaffolding frontend.
- **Single source of truth per i comandi**: `make help` mostra tutto.

### Negative / Trade-off accettati

- **uv ecosistema più giovane**: meno tutorial vs Poetry. Mitigato: documentazione ufficiale Astral è eccellente, e uv supporta gli stessi standard PEP.
- **Drift dev↔prod**: Postgres locale non è esattamente Supabase. Rischio: RLS testato in dev potrebbe comportarsi diversamente in cloud. Mitigazione: in M1 si eseguiranno smoke test contro un Supabase staging prima del merge in main.
- **Niente cache build cross-progetti**: senza Turborepo, ogni build di backend/frontend parte da zero. Mitigazione: per due progetti il guadagno di una cache è marginale.
- **Frontend in ritardo**: chi vuole "vedere l'app" in M0 resta deluso. Mitigazione: documentato esplicitamente in `frontend/README.md`.

### Neutre

- **`uv.lock`** committato → conflict resolution su PR. Non è un problema, è normalità per qualunque lock file.

## Pro/contro delle opzioni scartate

### Q1 — Poetry (scartata)

- ✅ Maturità, lockfile robusto, dependency resolver di prim'ordine
- ❌ Lentezza percepibile (resolver ~10-30s su progetti medi)
- ❌ Tooling separato per ambienti, lock, build

### Q1 — pip + pip-tools (scartata)

- ✅ Massima semplicità, niente tool extra
- ❌ Niente venv mgmt automatico, niente lock unificato
- ❌ Più boilerplate manuale per il developer

### Q2 — Hybrid Supabase remoto + broker locali (scartata)

- ✅ RLS testato su Supabase reale
- ❌ Dipendenza dalla rete in dev quotidiano
- ❌ Rischio di toccare dati condivisi accidentalmente

### Q2 — Tutto remoto (scartata)

- ✅ Massima fedeltà al production
- ❌ Slowdown su ogni operazione (latenza)
- ❌ Costi (anche se piccoli) e free tier consumo
- ❌ Debugging più complesso (no `docker logs`)

### Q3 — Turborepo (scartata)

- ✅ Cache build incrementale, ottima per pacchetti condivisi futuri (es. tipi TS)
- ❌ Tooling JS-centric, non ideale per progetto a maggioranza Python
- ❌ Overhead di setup non giustificato per 2 progetti

### Q3 — Nx (scartata)

- ✅ Più potente, supporto plugin Python
- ❌ Curva di apprendimento ripida
- ❌ Overkill per MVP a singolo developer

### Q4 — Scaffold frontend in M0 (scartata)

- ✅ Quando arrivi a M6, parti da terra arata
- ❌ M0 si allunga di 1-2 giorni
- ❌ Setup frontend obsoleto al momento di M6 (deps vecchie)

## Riferimenti

- [uv documentation](https://docs.astral.sh/uv/)
- [PEP 735 — Dependency Groups](https://peps.python.org/pep-0735/)
- [src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [MADR template](https://adr.github.io/madr/)
