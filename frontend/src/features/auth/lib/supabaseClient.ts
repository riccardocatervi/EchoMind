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
