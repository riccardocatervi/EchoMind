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
 * Con piu' lingue si potrebbe usare un Dropdown; per 2 un semplice toggle
 * e' piu' immediato per l'utente.
 */
export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const current = i18n.language as SupportedLang;
  const next = SUPPORTED_LANGUAGES.find((l) => l !== current) ?? "it";
  const meta = LANG_META[current];

  return (
    <button
      type="button"
      onClick={() => void i18n.changeLanguage(next)}
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
