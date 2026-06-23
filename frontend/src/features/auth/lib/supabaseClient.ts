/**
 * Client Supabase singleton — gateway verso Auth e (in futuro) Storage/Realtime.
 *
 * Perché singleton (modulo ES):
 *   Il modulo JavaScript è caricato una sola volta per sessione browser (module
 *   singleton). Esportare `supabase` come `const` a livello di modulo garantisce
 *   che tutta l'app usi la stessa istanza → una sola connessione WebSocket per i
 *   realtime (se usati), una sola cache di sessione, nessun conflitto di refresh.
 *
 * Perché la anon key è PUBBLICA (e sta nel bundle):
 *   Supabase Auth è progettato per avere la anon key nel client browser. La sicurezza
 *   non viene dalla segretezza della key, ma da:
 *     a) RLS (Row Level Security): il DB filtra i dati per utente in base al JWT.
 *     b) Policy Supabase: la anon key non ha accesso ad aree admin.
 *   In contrasto, la `service_role_key` (backend) NON deve MAI stare nel browser.
 *
 * Opzioni di configurazione auth:
 *
 *   persistSession: true
 *     Salva la sessione in localStorage. Sopravvive ai reload di pagina.
 *     Senza questo, ogni refresh richiede un login → UX pessima.
 *
 *   autoRefreshToken: true
 *     Rinnova l'access token PRIMA della scadenza (~1 minuto prima di `exp`).
 *     Gli access token Supabase durano 1 ora; senza refresh l'utente sarebbe
 *     disconnesso ogni ora. Il refresh è silenzioso (nessuna UI).
 *
 *   detectSessionInUrl: true
 *     Cattura i parametri `access_token`, `refresh_token` dal fragment URL (#) o
 *     dai query param. Necessario per i magic link email e per i redirect OAuth
 *     (es. Google Login): Supabase appende i token all'URL di callback e il client
 *     li interpreta qui.
 *
 * Fail-fast se le variabili mancano:
 *   Meglio un errore esplicito al caricamento che un comportamento silenziosamente
 *   rotto (fetch che falliscono tutte con 401, senza capire perché).
 */
import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  // Fail-fast con messaggio chiaro: senza queste due variabili l'auth non puo'
  // funzionare. La anon key e' PUBBLICA per design (vive nel browser).
  throw new Error(
    "Configurazione Supabase mancante: imposta VITE_SUPABASE_URL e " +
      "VITE_SUPABASE_ANON_KEY in frontend/.env (vedi .env.example).",
  );
}

/**
 * Client Supabase singleton. Gestisce la sessione lato browser:
 *  - persistSession: salva la sessione in localStorage (sopravvive al reload);
 *  - autoRefreshToken: rinnova l'access token prima della scadenza;
 *  - detectSessionInUrl: cattura i token dai redirect (es. conferma email).
 */
export const supabase = createClient(url, anonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});
