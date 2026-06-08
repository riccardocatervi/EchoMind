# ADR-0008: Frontend -- SPA feature-based, auth Supabase, grafo React Flow + Elk

- **Status**: Accepted
- **Data**: 2026-06
- **Milestone**: M6 -- Frontend Visualization

## Contesto

Dopo M5 il backend e' un sistema GraphRAG completo lato server (upload -->
trascrizione --> estrazione grafo + riassunto + embeddings), ma consumabile solo
via HTTP. M6 aggiunge "la faccia" del prodotto: una SPA che permette di
autenticarsi, caricare file, seguire l'elaborazione e -- soprattutto --
esplorare visivamente il grafo di conoscenza.

Vincoli ereditati dal backend:

- l'autenticazione e' delegata a **Supabase**: il backend *verifica* i JWT, non
  li emette. Il client deve quindi ottenere il token da Supabase.
- l'upload e' **diretto a object storage** (presigned URL B2): il browser carica
  il file bypassando la banda del backend.
- lo stato della pipeline e' esposto da un campo `status` sulla risorsa Document
  (`pending --> uploaded --> transcribed --> extracted --> completed`, oppure
  `failed`): e' la sorgente di verita' del lifecycle. I singoli artefatti
  (transcript, summary, graph) rispondono comunque 404 finche' non sono pronti.
- niente push real-time prima di M7 (WebSocket): l'aggiornamento e' via polling.

## Decisione

### 1. Stack

React 18 + Vite + TypeScript; Tailwind CSS + shadcn/ui; React Router v6; TanStack
Query (server state) + Zustand (UI state); axios; zod; React Flow v12 + Elk.js per
il grafo. Scelte confermate in Plan Mode con l'utente.

### 2. Architettura feature-based

Tre layer: `app/` (composition root), `shared/` (cross-cutting), `features/<dominio>/`
con sottocartelle `api/ components/ hooks/ store/ schemas/ lib/`. Regola di
dipendenza: `shared` non importa da `features`. Le feature sono allineate ai
bounded context del backend (auth, documents, tasks, transcripts, summary, graph,
profile).

### 3. zod come fonte unica di tipi + validazione

Ogni DTO e' uno schema zod; il tipo TS e' derivato con `z.infer`; le funzioni di
request validano la risposta con `.parse()`. Un cambio di contratto non riflesso
negli schemi diventa un errore (a compile-time via il tipo, a runtime via il
parse), invece di un bug silenzioso a valle.

### 4. Modello di autenticazione

`supabase-js` ottiene e rinnova la sessione; un interceptor axios allega il
`Bearer` leggendo il token **live** dallo store; su 401 il client effettua
`signOut` e ridirige al login. Il data layer non dipende da Supabase: l'auth
"riempie" uno slot (`setAccessTokenGetter`) esposto dal client. Inversione di
dipendenza, come i Protocol del backend.

### 5. Stato della pipeline dal campo `status` + polling

La fase viene letta dal campo `status` della risorsa Document (sorgente di
verita' del lifecycle), NON dedotta dai 404 dei singoli artefatti. Il client
fa polling di un **singolo** endpoint -- il documento -- con un `refetchInterval`
(3 s sul dettaglio, 10 s sulla lista) e abilita *condizionalmente* i componenti
figli (transcript, summary, graph) in base allo `status`. Il polling si autospegne
quando lo stato diventa terminale (`completed`/`failed`); una guardia lo ferma
anche se il documento resta bloccato in uno stato non terminale oltre 10 minuti
(es. estrazione esaurita per 429 Gemini), lasciando all'utente il re-run manuale.

### 6. Visualizzazione del grafo

React Flow renderizza nodi/archi; **Elk** ne calcola il layout (una volta, async).
Lo stato di presentazione (filtro per community, ricerca, evidenziazione dei
vicini) e' derivato dal layout base, senza ricalcolarlo. La rotta del grafo e'
**code-split** (`React.lazy`): React Flow + Elk vivono in un chunk on-demand,
fuori dal bundle iniziale.

## Conseguenze

**Positive**

- contratto API tipizzato e validato end-to-end (zod + tsc);
- separazione netta server/client state; cache e invalidazione gestite da TanStack
  Query;
- bundle iniziale snello: le dipendenze pesanti del grafo si caricano solo quando
  servono;
- struttura per-feature: una feature e' un'unica cartella, facile da estendere
  (M8 Q&A nascera' come nuova feature).

**Negative / debiti**

- il chunk del grafo resta grande (~500 kB gzip, quasi tutto Elk): mitigabile
  spostando Elk in un **web worker** (toglie il motore dal chunk e libera il main
  thread). Rimandato a una ottimizzazione mirata.
- l'aggiornamento dello stato e' via polling, non push: c'e' una latenza fino
  all'intervallo di poll e, per non interrogare all'infinito, una guardia ferma il
  polling se un documento resta bloccato oltre 10 minuti. Il push real-time
  (WebSocket) e' rimandato a M7.
- la validazione zod e' piu' rigida del semplice cast: uno schema disallineato
  rispetto al backend fa fallire la lettura (e' voluto, ma richiede disciplina).

## Alternative scartate

- **fetch a mano** invece di axios: meno ergonomico per interceptor (Bearer/errori)
  rispetto a un'istanza axios con interceptor centralizzati.
- **Tipi TS scritti a mano** invece di zod: nessuna validazione runtime; il drift
  di contratto resterebbe silenzioso.
- **Redux** per lo stato: sovradimensionato; TanStack Query copre il server state
  e Zustand basta per lo stato di UI.
- **TanStack Router**: ottimo type-safety, ma React Router v6 e' piu' diffuso e
  sufficiente per ~5 rotte (scelta dell'utente).
- **Tailwind senza shadcn/ui**: piu' controllo ma molto piu' lavoro e maggior
  rischio sull'accessibilita' (focus, dialog, ruoli ARIA).
- **GDS / layout server-side**: il layout e' una preoccupazione di presentazione,
  meglio sul client (Elk) e per-vista.
