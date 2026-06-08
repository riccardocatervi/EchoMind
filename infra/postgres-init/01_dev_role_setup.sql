-- =============================================================================
-- EchoMind — Setup ruoli di dev (eseguito UNA VOLTA al primo avvio del container)
--
-- Replica il pattern Supabase di doppio ruolo:
--
--   `echomind`     — superuser, owner del DB. Usato per:
--                    - migration Alembic (DDL)
--                    - operazioni di sistema
--                    Equivalente Supabase: `service_role`
--
--   `app_runtime`  — NOLOGIN, non-superuser, soggetto a RLS. Usato dall'app
--                    via `SET LOCAL ROLE app_runtime` dentro ogni transazione
--                    autenticata. Equivalente Supabase: `authenticated`.
--
-- Perché due ruoli:
--   I superuser bypassano sempre RLS, anche con ALTER TABLE ... FORCE.
--   Per testare RLS in modo realistico (= come gira in Supabase produzione),
--   serve un ruolo non-superuser. L'app si connette comunque come `echomind`
--   (così le migration funzionano), ma "scende" a `app_runtime` per le query
--   utente con `SET LOCAL ROLE`.
--
-- Quando viene eseguito:
--   Solo al PRIMO avvio del container (volume dati vuoto). Per ri-eseguire:
--   `make infra-reset`.
-- =============================================================================

-- 1. Ruolo runtime non-superuser, NOLOGIN (può essere assunto solo via SET ROLE)
CREATE ROLE app_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS;

-- 2. Permetti a `echomind` di assumere `app_runtime` con `SET ROLE`.
--    Senza questo, SET ROLE fallirebbe per mancanza di membership.
GRANT app_runtime TO echomind;

-- 3. Schema `auth` (pre-creato qui per poter settare i privilegi).
--    La migration 0001 ha `CREATE SCHEMA IF NOT EXISTS auth` → idempotente.
CREATE SCHEMA IF NOT EXISTS auth;

-- 4. USAGE sui due schemi → app_runtime può "vedere" le tabelle.
GRANT USAGE ON SCHEMA public, auth TO app_runtime;

-- 5. Default privileges: tutte le tabelle future create da `echomind` (cioè le
--    migration) saranno selezionabili/scrivibili da app_runtime.
ALTER DEFAULT PRIVILEGES FOR ROLE echomind IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_runtime;

ALTER DEFAULT PRIVILEGES FOR ROLE echomind IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO app_runtime;

-- Per la schema `auth`: solo SELECT + REFERENCES (per verificare la FK).
-- Niente INSERT/UPDATE: gli utenti li gestisce Supabase Auth (in dev: solo
-- la migration / seed manuale).
ALTER DEFAULT PRIVILEGES FOR ROLE echomind IN SCHEMA auth
    GRANT SELECT, REFERENCES ON TABLES TO app_runtime;
