import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { LanguageSwitcher } from "@/shared/components/LanguageSwitcher";

/**
 * Test per LanguageSwitcher.
 *
 * Comportamento atteso (lingua di output disaccoppiata):
 *  - Il switcher cambia SOLO la lingua dell'interfaccia (i18n).
 *  - Non chiama PATCH /profiles/me in nessuna circostanza.
 *    La lingua di output (riassunti/grafo/RAG) e' gestita separatamente
 *    nella pagina Profilo tramite LanguageSection.
 */
describe("LanguageSwitcher", () => {
  beforeEach(async () => {
    // Forza la lingua a italiano prima di ogni test.
    const { default: i18n } = await import("@/shared/i18n");
    await i18n.changeLanguage("it");
  });

  it("mostra la lingua corrente (italiano)", () => {
    render(<LanguageSwitcher />);
    expect(screen.getByTitle("Italiano")).toBeInTheDocument();
  });

  it("cambia la lingua dell'interfaccia al click", async () => {
    render(<LanguageSwitcher />);

    fireEvent.click(screen.getByRole("button"));

    const { default: i18n } = await import("@/shared/i18n");
    expect(i18n.language).toBe("en");
  });

  it("non chiama PATCH /profiles/me indipendentemente dallo stato di autenticazione", async () => {
    // Il LanguageSwitcher non importa piu' updateMyProfile: questa asserzione
    // verifica il contratto a livello di modulo (nessuna chiamata API).
    // Usiamo uno spy sul fetch globale per sicurezza.
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    render(<LanguageSwitcher />);
    fireEvent.click(screen.getByRole("button"));

    // Nessuna chiamata di rete deve essere effettuata dallo switcher UI.
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
});
