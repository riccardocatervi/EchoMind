import { useTranslation } from "react-i18next";

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
 * Controllo SOLO la lingua dell'interfaccia (i18n).
 * La lingua di output (riassunti, grafo, risposte RAG) e' indipendente
 * e viene gestita dalla sezione "Lingua di output" nella pagina Profilo,
 * dove viene salvata su profiles.preferred_language senza toccare i18n.
 */
export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const current = i18n.language as SupportedLang;
  const next = SUPPORTED_LANGUAGES.find((l) => l !== current) ?? "it";
  const meta = LANG_META[current] ?? LANG_META["it"];

  function handleClick() {
    void i18n.changeLanguage(next);
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
