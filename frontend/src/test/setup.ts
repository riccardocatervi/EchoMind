import "@testing-library/jest-dom/vitest";
// Inizializza i18next prima di ogni test: senza questo i componenti che usano
// useTranslation() restituiscono la chiave grezza invece del testo tradotto.
import i18n from "@/shared/i18n";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeAll } from "vitest";

// Forza sempre l'italiano nei test: evita dipendenze dalla locale del runner CI
// (es. GitHub Actions usa "en-US" --> i18n si inizializzerebbe in inglese).
beforeAll(async () => {
  await i18n.changeLanguage("it");
});

// Pulisce il DOM dopo ogni test (con globals disattivati lo registriamo a mano).
afterEach(() => {
  cleanup();
});
