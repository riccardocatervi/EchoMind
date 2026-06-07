import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { useAuthStore } from "@/features/auth/store/authStore";
import { LanguageSwitcher } from "@/shared/components/LanguageSwitcher";

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
    render(<LanguageSwitcher />);
    expect(screen.getByTitle("Italiano")).toBeInTheDocument();
  });

  it("cambia lingua al click", async () => {
    useAuthStore.setState({ status: "unauthenticated" });
    render(<LanguageSwitcher />);

    fireEvent.click(screen.getByRole("button"));

    const { default: i18n } = await import("@/shared/i18n");
    expect(i18n.language).toBe("en");
  });

  it("persiste la preferenza via PATCH quando autenticato", async () => {
    useAuthStore.setState({ status: "authenticated" });
    const { updateMyProfile } = await import("@/features/profile/api/requests");
    vi.mocked(updateMyProfile).mockClear();

    render(<LanguageSwitcher />);
    fireEvent.click(screen.getByRole("button"));

    // updateMyProfile e' chiamata sincronicamente in handleClick (fire-and-forget)
    expect(vi.mocked(updateMyProfile)).toHaveBeenCalledWith({ preferred_language: "en" });
  });

  it("non chiama PATCH quando non autenticato", async () => {
    useAuthStore.setState({ status: "unauthenticated" });
    const { updateMyProfile } = await import("@/features/profile/api/requests");
    vi.mocked(updateMyProfile).mockClear();

    render(<LanguageSwitcher />);
    fireEvent.click(screen.getByRole("button"));

    expect(vi.mocked(updateMyProfile)).not.toHaveBeenCalled();
  });
});
