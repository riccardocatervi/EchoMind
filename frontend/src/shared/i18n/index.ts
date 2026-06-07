/**
 * Configurazione i18next.
 *
 * Strategia:
 * - Default: "it" (italiano)
 * - Fallback: "it" (nessuna stringa mancante in IT)
 * - Persistenza: localStorage key "echomind_lang"
 * - Rilevamento automatico: non usato (scelta esplicita dell'utente)
 *
 * Uso nei componenti:
 *   const { t, i18n } = useTranslation();
 *   t("docs.title")   --> "I tuoi documenti" (it) | "Your documents" (en)
 *   i18n.changeLanguage("en")
 */
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "@/shared/i18n/locales/en";
import it from "@/shared/i18n/locales/it";

export const SUPPORTED_LANGUAGES = ["it", "en"] as const;
export type SupportedLang = (typeof SUPPORTED_LANGUAGES)[number];

const STORAGE_KEY = "echomind_lang";

function getInitialLanguage(): SupportedLang {
  const stored = localStorage.getItem(STORAGE_KEY) as SupportedLang | null;
  if (stored && SUPPORTED_LANGUAGES.includes(stored)) return stored;
  // Rilevamento browser: navigator.language e' tipo "it-IT" o "en-US"
  const browserLang = navigator.language.split("-")[0] as SupportedLang;
  return SUPPORTED_LANGUAGES.includes(browserLang) ? browserLang : "it";
}

void i18n.use(initReactI18next).init({
  resources: {
    it: { translation: it },
    en: { translation: en },
  },
  lng: getInitialLanguage(),
  fallbackLng: "it",
  interpolation: {
    escapeValue: false, // React gia' escapa l'HTML
  },
});

// Persisti la lingua scelta nel localStorage ogni volta che cambia
i18n.on("languageChanged", (lang: string) => {
  localStorage.setItem(STORAGE_KEY, lang);
});

export default i18n;
