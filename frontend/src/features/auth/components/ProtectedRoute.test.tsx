import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { ProtectedRoute } from "@/features/auth/components/ProtectedRoute";
import { useAuthStore } from "@/features/auth/store/authStore";

function renderProtected() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<div>Area protetta</div>} />
        </Route>
        <Route path="/login" element={<div>Pagina login</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    useAuthStore.setState({ session: null, status: "unauthenticated" });
  });

  it("reindirizza al login se non autenticato", () => {
    renderProtected();
    expect(screen.getByText("Pagina login")).toBeInTheDocument();
  });

  it("rende l'area protetta se autenticato", () => {
    useAuthStore.setState({ status: "authenticated" });
    renderProtected();
    expect(screen.getByText("Area protetta")).toBeInTheDocument();
  });
});
