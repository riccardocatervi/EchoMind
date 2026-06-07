import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "@/features/documents/components/StatusBadge";

describe("StatusBadge", () => {
  it("mostra l'etichetta dello stato", () => {
    render(<StatusBadge status="uploaded" />);
    expect(screen.getByText("Caricato")).toBeInTheDocument();
  });

  it("mostra l'etichetta per lo stato fallito", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText("Fallito")).toBeInTheDocument();
  });
});
