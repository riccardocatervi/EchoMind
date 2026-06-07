import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { profileKeys } from "@/features/profile/api/keys";
import { updateMyProfile } from "@/features/profile/api/requests";
import type { ProfileRead } from "@/features/profile/schemas/profile";
import { useAuthStore } from "@/features/auth/store/authStore";
import type { SupportedLang } from "@/shared/i18n";
import { SUPPORTED_LANGUAGES } from "@/shared/i18n";

/** Mappa lingua --> bandiera emoji + etichetta accessibile. */
const LANG_META: Record<SupportedLang, { flag: string; label: string }> = {
  it: { flag: "🇮🇹", label: "Italiano" },
  en: { flag: "🇬🇧", label: "English" },
};

/**
 * Switcher compatto: mostra la bandiera della lingua ATTIVA e al click
 * passa alla lingua opposta (ciclo su 2 lingue).
 *
 * Comportamento:
 *  - Cambia la lingua locale immediatamente (i18n.changeLanguage).
 *  - Se l'utente e' autenticato, persiste la scelta via PATCH /profiles/me
 *    (fire-and-forget: nessun feedback visivo, il cambio locale e' gia' immediato).
 *    In caso di errore di rete, la preferenza viene recuperata al prossimo login
 *    grazie alla sync dal profilo in AppShell.
 *
 * Con piu' lingue si potrebbe usare un Dropdown; per 2 un semplice toggle
 * e' piu' immediato per l'utente.
 */
export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const current = i18n.language as SupportedLang;
  const next = SUPPORTED_LANGUAGES.find((l) => l !== current) ?? "it";
  const meta = LANG_META[current];
  const isAuthenticated = useAuthStore((state) => state.status === "authenticated");
  const queryClient = useQueryClient();

  function handleClick() {
    // 1. Cambia subito la lingua locale.
    void i18n.changeLanguage(next);

    if (isAuthenticated) {
      // 2. Aggiorna ottimisticamente la cache del profilo: cosi' l'effect di sync
      //    in AppShell vede gia' la nuova lingua e non la sovrascrive al prossimo
      //    caricamento del profilo.
      const cached = queryClient.getQueryData<ProfileRead>(profileKeys.me);
      if (cached) {
        queryClient.setQueryData<ProfileRead>(profileKeys.me, {
          ...cached,
          preferred_language: next,
        });
      }

      // 3. Persiste la preferenza sul server (fire-and-forget).
      //    In caso di successo la cache viene aggiornata con il dato reale.
      //    In caso di errore la cache resta ottimistica: rimane coerente con la
      //    lingua locale e verra' corretta al prossimo fetch del profilo.
      void (async () => {
        try {
          const updated = await updateMyProfile({ preferred_language: next });
          queryClient.setQueryData<ProfileRead>(profileKeys.me, updated);
        } catch {
          // noop: la lingua e' gia' applicata localmente e in cache
        }
      })();
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label={`Lingua corrente: ${meta.label}. Clicca per cambiare.`}
      title={meta.label}
    >
      <span className="text-base leading-none" aria-hidden="true">
        {meta.flag}
      </span>
      <span className="hidden sm:inline">{meta.label}</span>
    </button>
  );
}
