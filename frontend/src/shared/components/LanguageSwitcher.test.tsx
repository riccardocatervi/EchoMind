import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { useAuthStore } from "@/features/auth/store/authStore";
import { LanguageSwitcher } from "@/shared/components/LanguageSwitcher";

// QueryClientProvider necessario perche' LanguageSwitcher usa useQueryClient()
// per l'update ottimistico della cache profilo.
function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// Simula updateMyProfile: intercetta la chiamata PATCH senza toccare la rete.
vi.mock("@/features/profile/api/requests", () => ({
  updateMyProfile: vi.fn().mockResolvedValue({ preferred_language: "en" }),
}));

describe("LanguageSwitcher", () => {
  beforeEach(async () => {
    // Forza la lingua a italiano prima di ogni test
    const { default: i18n } = await import("@/shared/i18n");
    await i18n.changeLanguage("it");
  });

  it("mostra la lingua corrente (italiano)", () => {
    useAuthStore.setState({ status: "unauthenticated" });
    render(<LanguageSwitcher />, { wrapper: makeWrapper() });
    expect(screen.getByTitle("Italiano")).toBeInTheDocument();
  });

  it("cambia lingua al click", async () => {
    useAuthStore.setState({ status: "unauthenticated" });
    render(<LanguageSwitcher />, { wrapper: makeWrapper() });

    fireEvent.click(screen.getByRole("button"));

    const { default: i18n } = await import("@/shared/i18n");
    expect(i18n.language).toBe("en");
  });

  it("persiste la preferenza via PATCH quando autenticato", async () => {
    useAuthStore.setState({ status: "authenticated" });
    const { updateMyProfile } = await import("@/features/profile/api/requests");
    vi.mocked(updateMyProfile).mockClear();

    render(<LanguageSwitcher />, { wrapper: makeWrapper() });
    fireEvent.click(screen.getByRole("button"));

    // updateMyProfile e' chiamata all'interno di un async IIFE (fire-and-forget):
    // il mock viene invocato sincronicamente prima del primo await.
    expect(vi.mocked(updateMyProfile)).toHaveBeenCalledWith({ preferred_language: "en" });
  });

  it("non chiama PATCH quando non autenticato", async () => {
    useAuthStore.setState({ status: "unauthenticated" });
    const { updateMyProfile } = await import("@/features/profile/api/requests");
    vi.mocked(updateMyProfile).mockClear();

    render(<LanguageSwitcher />, { wrapper: makeWrapper() });
    fireEvent.click(screen.getByRole("button"));

    expect(vi.mocked(updateMyProfile)).not.toHaveBeenCalled();
  });
});
