# EchoMind -- Frontend

SPA React che consuma l'API EchoMind: autenticazione, upload di documenti/audio,
avanzamento dell'elaborazione, riassunto multilivello e visualizzazione
interattiva del grafo di conoscenza.

## Stack

- **React 18** + **Vite** + **TypeScript**
- **Tailwind CSS** + **shadcn/ui** (primitivi Radix, copiati nel repo)
- **React Router v6** (rotte + route protette)
- **TanStack Query** (server state) + **Zustand** (UI state)
- **Supabase Auth** (`@supabase/supabase-js`) per il login lato client
- **axios** (client HTTP) + **zod** (schemi + validazione runtime)
- **React Flow v12** + **Elk.js** (rendering e layout del grafo)
- **date-fns** (date), **sonner** (toast), **lucide-react** (icone)

## Prerequisiti

- Node >= 20
- pnpm (vedi campo `packageManager` in `package.json`)

## Setup

```bash
cd frontend
cp .env.example .env        # popola i valori (vedi sotto)
pnpm install
pnpm dev                    # http://localhost:5173
```

Variabili (`.env`, mai committato -- solo valori PUBBLICI nel bundle):

| Variabile | Descrizione |
|---|---|
| `VITE_API_BASE_URL` | Base URL del backend (dev: `http://localhost:8000`) |
| `VITE_SUPABASE_URL` | URL del progetto Supabase |
| `VITE_SUPABASE_ANON_KEY` | Anon key Supabase (pubblica per design) |

> L'upload va **diretto a B2** (presigned URL): per la prova end-to-end il bucket
> B2 deve avere una regola CORS che consenta `PUT` dall'origin del frontend.
> Il backend deve essere in esecuzione con l'origin del frontend in
> `CORS_ALLOW_ORIGINS`.

## Script

```bash
pnpm dev            # dev server (HMR)
pnpm build          # tsc --noEmit && vite build
pnpm preview        # serve la build
pnpm lint           # eslint
pnpm typecheck      # tsc --noEmit
pnpm format         # prettier --write
pnpm format:check   # prettier --check
pnpm test           # vitest run
```

## Architettura (feature-based)

```
src/
  app/        composition root: main, App, router, AppShell
  shared/     cross-cutting: api/ (axios, queryClient), lib/, schemas/, components/ui/
  features/<dominio>/   api/  components/  hooks/  store/  schemas/  lib/
              auth · documents · tasks · transcripts · summary · graph · profile
```

Regola di dipendenza: `shared` non importa da `features`; le `features` importano
da `shared`; `app` compone entrambi.

- **Tipi e validazione**: ogni DTO e' uno **schema zod**; il tipo TS e' `z.infer`;
  le funzioni di request validano la risposta con `.parse()` (un drift del
  contratto diventa un errore esplicito).
- **Server vs client state**: TanStack Query possiede i dati del server (cache,
  polling); Zustand tiene solo lo stato di UI (sessione, selezione nel grafo).
- **Auth**: Supabase emette il JWT lato client; l'`axios` lo allega come `Bearer`;
  il backend lo verifica (RLS). Su 401 il client effettua logout e redirige.
- **Stato pipeline**: dedotto dal polling di transcript/summary/graph (404 = in
  corso, 200 = pronto). Il push real-time arriva con M7 (WebSocket).
- **Grafo**: React Flow renderizza, Elk posiziona. La rotta del grafo e'
  **code-split** (`React.lazy`): React Flow + Elk si scaricano solo all'apertura.

## Test

Vitest + Testing Library (jsdom). Test colocati (`*.test.ts(x)`) su logica pura
(format, zod, palette), layout Elk, e componenti (StatusBadge, SummaryView,
ProtectedRoute). I servizi esterni (Supabase, backend) non sono richiesti: la
verifica end-to-end e' manuale (vedi Setup).
