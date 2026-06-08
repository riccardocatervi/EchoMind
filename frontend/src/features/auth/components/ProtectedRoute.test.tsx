import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { ProtectedRoute } from "@/features/auth/components/ProtectedRoute";
import { useAuthStore } from "@/features/auth/store/authStore";

/**
 * Il router di test parte da /protected (rotta autenticata).
 * - "/" e' la landing page (destinazione del redirect quando non autenticato)
 * - "/protected" e' dentro ProtectedRoute
 *
 * Questa struttura rispecchia il router reale dell'app, dove ProtectedRoute
 * redirige a "/" (non a "/login") cosi' il logout torna alla home.
 */
function renderProtected() {
  return render(
    <MemoryRouter initialEntries={["/protected"]}>
      <Routes>
        <Route path="/" element={<div>Landing page</div>} />
        <Route element={<ProtectedRoute />}>
          <Route path="/protected" element={<div>Area protetta</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    useAuthStore.setState({ session: null, status: "unauthenticated" });
  });

  it("reindirizza alla home se non autenticato", () => {
    renderProtected();
    expect(screen.getByText("Landing page")).toBeInTheDocument();
  });

  it("rende l'area protetta se autenticato", () => {
    useAuthStore.setState({ status: "authenticated" });
    renderProtected();
    expect(screen.getByText("Area protetta")).toBeInTheDocument();
  });
});
