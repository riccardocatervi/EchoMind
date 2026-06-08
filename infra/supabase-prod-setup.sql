-- =============================================================================
-- EchoMind — Setup ruolo runtime su SUPABASE (produzione). Eseguire UNA VOLTA
-- nel SQL Editor di Supabase, dopo aver applicato le migration Alembic.
--
-- Perché serve: l'app, a ogni richiesta autenticata, esegue
--   SET LOCAL ROLE app_runtime
-- per "scendere" a un ruolo NON privilegiato soggetto a RLS (i superuser la
-- bypassano). In locale il ruolo `app_runtime` è creato da
-- infra/postgres-init/01_dev_role_setup.sql; su Supabase va creato qui.
--
-- Questo script è IDEMPOTENTE: si può rieseguire senza errori.
-- =============================================================================

-- 1. Ruolo runtime: nessun login, non-superuser, soggetto a RLS.
--    Assumibile solo via SET ROLE da chi ne è membro.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_runtime') THEN
    CREATE ROLE app_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS;
  END IF;
END
$$;

-- 2. Il ruolo di connessione dell'app (postgres) deve poter assumere app_runtime.
GRANT app_runtime TO postgres;

-- 3. Visibilità dello schema public.
GRANT USAGE ON SCHEMA public TO app_runtime;

-- 4. Privilegi sulle tabelle/sequenze GIÀ create dalle migration.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_runtime;

-- 5. Privilegi di default per le tabelle/sequenze FUTURE create da postgres
--    (le prossime migration), così non si dovrà ripetere il punto 4.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO app_runtime;

-- 6. search_path con `extensions`.
--    Su Supabase l'estensione `vector` (pgvector) è installata nello schema
--    `extensions`, quindi l'operatore di distanza `<=>` vive lì. Le query del
--    RAG (embedding <=> :q) altrimenti falliscono con
--    "operator does not exist: extensions.vector <=> unknown" perché il
--    search_path di default non include `extensions`.
--    Lo impostiamo sul ruolo di login dell'app (postgres): viene applicato a
--    ogni nuova connessione e resta valido anche dopo `SET LOCAL ROLE app_runtime`.
ALTER ROLE postgres SET search_path TO "$user", public, extensions;

-- 7. USAGE/EXECUTE sullo schema `extensions` per app_runtime.
--    Anche con `extensions` nel search_path, un ruolo che NON ha USAGE sullo
--    schema non "vede" gli oggetti che contiene: Postgres riporta l'operatore
--    come "does not exist" (non "permission denied") durante la risoluzione.
--    Senza questo, le query RAG (pgvector `<=>`) eseguite come app_runtime
--    falliscono. EXECUTE sulle funzioni copre l'operatore di distanza.
GRANT USAGE ON SCHEMA extensions TO app_runtime;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA extensions TO app_runtime;
