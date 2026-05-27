# Architectural Decision Records (ADR)

Questa cartella raccoglie le **decisioni architetturali** del progetto EchoMind.

## Cos'è un ADR

Un ADR documenta una decisione tecnica significativa **nel momento in cui viene presa**, includendo il contesto, le alternative valutate e le conseguenze attese. Serve a rispondere alla domanda "perché abbiamo fatto X?" sei mesi dopo, quando nessuno se lo ricorda più.

Riferimento di stile: [MADR (Markdown Architectural Decision Records)](https://adr.github.io/madr/).

## Quando scrivere un ADR

Scrivilo quando:

- la decisione è **difficile da invertire** (es. scelta di un database, framework principale);
- coinvolge **trade-off non ovvi** (es. async vs sync, monolite vs microservizi);
- la giustificazione **non sopravviverà nel solo codice** (il codice mostra il *cosa*, non il *perché*).

**NON** serve un ADR per scelte triviali (es. "uso `pytest` invece di `unittest`" se il team già usa pytest ovunque).

## Convenzioni

- File: `NNNN-titolo-in-kebab-case.md` (es. `0001-tech-stack-foundations.md`)
- Numerazione **progressiva e monotona**: una volta assegnato, un numero non si riusa nemmeno se l'ADR viene rifiutato.
- **Immutabili**: un ADR superato non si modifica. Si crea un nuovo ADR con `Status: Accepted` e si aggiorna lo status del vecchio a `Superseded by ADR-NNNN`.
- Linguaggio: italiano (consistente con tutta la documentazione del progetto).

## Workflow

1. Copia [`template.md`](template.md) in un nuovo file.
2. Scrivilo in **draft** (status `Proposed`).
3. Discutilo (con il team o riflettendoci a fondo da soli) — è il momento dei dubbi.
4. Imposta `Status: Accepted` e committalo insieme all'implementazione.

## Indice

| # | Titolo | Status |
|---|---|---|
| [0001](0001-tech-stack-foundations.md) | Fondamenta tecnologiche di M0 | Accepted |
| [0002](0002-m1-auth-and-persistence.md) | Auth, persistenza e RLS per M1 | Accepted |
| [0003](0003-jwt-es256-support.md) | Supporto JWT ES256 in aggiunta a HS256 | Accepted |
