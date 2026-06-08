# 0003 — Supporto JWT ES256 in aggiunta a HS256

- **Status**: Accepted
- **Date**: 2026-05-27
- **Deciders**: Riccardo Catervi

## Contesto e problema

[ADR-0002](0002-m1-auth-and-persistence.md) decideva di validare i JWT Supabase con **HS256** (HMAC simmetrico, secret condiviso). Quella scelta riflette la realtà storica di Supabase, che usava HS256 di default sui progetti creati fino a inizio 2026.

Al momento di chiudere M1 (verifica end-to-end contro un progetto Supabase reale appena creato), abbiamo scoperto che **Supabase ha cambiato il default per i nuovi progetti**: la chiave di firma è ora **ECC P-256 con algoritmo ES256** (firma asimmetrica). La chiave HS256 resta disponibile come "Legacy" per i progetti vecchi.

Validare un JWT firmato ES256 con un secret HMAC è **impossibile**: i due algoritmi usano matematica diversa (HMAC vs ECDSA). Senza il supporto ES256, il backend rifiuterebbe ogni token reale di un nuovo progetto Supabase.

## Driver decisionali

- **Compatibilità con Supabase corrente**: la maggioranza dei nuovi progetti usa ES256, non possiamo restare bloccati su HS256
- **Sicurezza superiore di ES256**: chiave privata su Supabase non condivisa; anche se il nostro backend è compromesso, gli attaccanti possono solo *validare* token, mai *forgiarli*
- **Conservare i test esistenti**: 53 test passano con HS256 + secret fittizio, non vogliamo riscriverli
- **Tempo**: ~1-2 ore di lavoro netto per estendere il codice
- **Onestà didattica**: scoprire e adattarsi a un cambio di default upstream è una situazione realistica che insegna pattern professionali

## Opzioni considerate

1. **Tornare a HS256** cambiando l'algoritmo lato Supabase (legacy)
   - Pro: zero codice da cambiare
   - Contro: usiamo un sistema che Supabase ha deprecato come default. Tra 6 mesi questo problema riapparirà
2. **Aggiornare il backend per supportare ES256 in aggiunta a HS256**
   - Pro: pattern moderno, sicurezza migliorata, retro-compat con i test HS256
   - Contro: ~1-2 ore di lavoro, aggiorna gli ADR
3. **Sostituire HS256 con ES256 in toto** (rimuove HS256)
   - Pro: codice più snello
   - Contro: i test che firmano JWT con HMAC (più semplici da scrivere) andrebbero riscritti con ECDSA; tempo maggiore

## Decisione

**Scegliamo l'Opzione 2: supportare entrambi gli algoritmi**.

Aggiornamenti al codice:

### `Settings` (`backend/src/echomind/core/config.py`)
- `supabase_jwt_algorithm: Literal["HS256", "ES256"]` (default `HS256` per retro-compat dei test)
- `supabase_jwt_secret: SecretStr | None` (obbligatorio se `HS256`)
- `supabase_jwt_public_key: SecretStr | None` (obbligatorio se `ES256`; accetta PEM o JWK come stringa JSON)
- `@model_validator` cross-field: l'app non parte se la credential corrispondente all'algoritmo è mancante

### `security.py` (`backend/src/echomind/core/security.py`)
- Nuova funzione interna `_resolve_verification_key(settings)` che restituisce secret HMAC o chiave pubblica PEM/JWK in base a `algorithm`
- `decode_and_validate` resta invariata nella firma pubblica, ma usa la chiave risolta

### Test (`backend/tests/test_security_es256.py`)
- Nuovo file con 5 test:
  - Generazione coppia chiavi P-256 ad-hoc per ogni test
  - Happy path: firma con privata → validazione con pubblica
  - Rejection: token firmato con altra chiave privata
  - Supporto formato JWK (oltre a PEM)
  - Validation cross-field di Settings (HS256 senza secret / ES256 senza public_key → ValidationError)

### `.env.example` e `.env`
- Documentati i due percorsi alternativi (HS256 secret vs ES256 public_key)
- In `.env` reale: configurato ES256 con la JWK letta dalla dashboard Supabase

## Conseguenze

### Positive

- **Allineamento al pattern corrente Supabase**: nuovi progetti girano out-of-the-box
- **Sicurezza migliorata**: la chiave privata non lascia mai Supabase; anche un compromise del nostro backend non permette di forgiare token
- **Retro-compat con i test**: i 53 test che usano HS256 + secret fittizio continuano a passare senza modifiche
- **Validazione fail-fast**: `@model_validator` rifiuta config incoerenti al boot, non a runtime
- **Pattern professionale documentato**: supporto multi-algoritmo con scelta esplicita è il pattern standard delle librerie JWT mature
- **Verifica end-to-end completata**: smoke test reale contro Supabase con utente vero e JWT vero ha avuto successo (GET/PATCH `/profiles/me` ritornano i dati corretti)

### Negative / Trade-off accettati

- **Doppio percorso di configurazione**: l'utente deve sapere quale algoritmo usa il suo Supabase e popolare la variabile giusta. Mitigazione: `.env.example` documenta entrambi con commenti chiari; il validator dà errore esplicito se la combinazione è inconsistente
- **Test asimmetrici più complessi**: i test ES256 generano coppie di chiavi al volo con `cryptography` (più dipendenze, più righe). Limitato a un singolo file `test_security_es256.py`
- **Chiave pubblica in `.env`**: il JWK su singola riga è ingombrante e l'editor lo evidenzia in rosso (syntax highlighting `.env` non capisce JSON). Cosmetico, nessun impatto funzionale. In M9 potremo migrare a JWKS endpoint fetch dinamico (vedi sotto)

### Neutre

- **Niente JWKS fetch dinamico**: per ora la chiave pubblica è statica in `.env`. Funziona ma richiede aggiornamento manuale se Supabase ruota la chiave. Pattern moderno (OAuth 2.0 / OpenID Connect) sarebbe scaricare le chiavi da `https://<project>.supabase.co/auth/v1/.well-known/jwks.json` al boot con cache. Rimandato a M9 (production readiness)

## Pro/contro delle opzioni scartate

### Opzione 1 — Switch a HS256 legacy

- ✅ Zero codice da cambiare
- ❌ Posticipa il problema: tra qualche mese Supabase potrebbe rimuovere HS256 anche per i vecchi progetti
- ❌ Sicurezza inferiore (chiave condivisa)
- ❌ Non insegna il pattern asimmetrico, che è quello standard moderno

### Opzione 3 — ES256 only (rimuove HS256)

- ✅ Codice più snello
- ❌ I test esistenti che firmano JWT con HMAC dovrebbero essere riscritti con ECDSA (più complesso da gestire nei test)
- ❌ Niente fallback per progetti Supabase legacy
- ❌ Nessun vantaggio reale di sicurezza (HS256 viene usato solo nei test, mai in produzione)

## Verifica end-to-end (smoke test reale)

Sequenza eseguita per chiudere M1:

1. Creato utente di test su Supabase (dashboard Auth)
2. Login via `POST /auth/v1/token?grant_type=password` → JWT ES256 reale
3. Pre-seed dell'UUID Supabase in `auth.users` locale (necessario per la FK)
4. `make serve` avvia uvicorn con `.env` configurato ES256
5. `GET /api/v1/users/me` con header `Authorization: Bearer <JWT>` → **200**, claim decodificati correttamente (sub, aud, email, iat, exp, iss, role, ...)
6. `GET /api/v1/profiles/me` → **200**, profile creato just-in-time (display_name=null, timestamp DB)
7. `PATCH /api/v1/profiles/me` con `{"display_name":"Riccardo"}` → **200**, valore persistito
8. `GET /api/v1/profiles/me` di nuovo → **200**, `display_name="Riccardo"`, `updated_at` aggiornato dal trigger SQL

## Riferimenti

- [`docs/adr/0002-m1-auth-and-persistence.md`](0002-m1-auth-and-persistence.md) — decisione iniziale che assumeva HS256
- [RFC 7518 — JSON Web Algorithms (JWA)](https://datatracker.ietf.org/doc/html/rfc7518) — definisce ES256 e HS256
- [RFC 7517 — JSON Web Key (JWK)](https://datatracker.ietf.org/doc/html/rfc7517) — formato JWK
- [python-jose multi-algorithm support](https://python-jose.readthedocs.io/)
- [Supabase JWT signing keys (corrente)](https://supabase.com/docs/guides/auth/signing-keys)
- `backend/src/echomind/core/config.py` — implementazione validator
- `backend/src/echomind/core/security.py` — implementazione `_resolve_verification_key`
- `backend/tests/test_security_es256.py` — test suite ES256
