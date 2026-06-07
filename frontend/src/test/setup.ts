import "@testing-library/jest-dom/vitest";
// Inizializza i18next prima di ogni test: senza questo i componenti che usano
// useTranslation() restituiscono la chiave grezza invece del testo tradotto.
import "@/shared/i18n";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Pulisce il DOM dopo ogni test (con globals disattivati lo registriamo a mano).
afterEach(() => {
  cleanup();
});
