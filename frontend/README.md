# EchoMind — Frontend

> ⚠️ **Stato: placeholder**
> Lo scaffolding del frontend (Vite + React + Tailwind + React Flow + Elk.js) è pianificato per la **Milestone M6**. Vedi [`/docs/architecture-phase0.md`](../docs/architecture-phase0.md#m6--frontend-visualization).

## Perché non è ancora qui

La decisione di rimandare il frontend è documentata nell'[ADR-0001](../docs/adr/0001-tech-stack-foundations.md#q4--frontend-in-m0). In sintesi: M0 si concentra su fondamenta backend e infrastruttura. Iniziare il frontend ora significherebbe deps obsolete al momento dell'effettivo sviluppo (M6).

## Stack previsto (M6)

- **Framework**: React 18 + Vite
- **Styling**: Tailwind CSS
- **State management**: Zustand
- **Graph rendering**: React Flow v12 + Elk.js (layout engine)
- **Data fetching**: TanStack Query
- **Real-time**: WebSocket (con fallback polling)

## Quick start (futuro)

Quando arriveremo a M6:

```bash
cd frontend
pnpm install
pnpm dev
```
