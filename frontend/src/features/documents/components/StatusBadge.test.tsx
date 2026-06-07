import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "@/features/documents/components/StatusBadge";

describe("StatusBadge", () => {
  it("mostra 'In elaborazione' per lo stato uploaded", () => {
    render(<StatusBadge status="uploaded" />);
    expect(screen.getByText("In elaborazione")).toBeInTheDocument();
  });

  it("mostra 'Trascritto' per lo stato transcribed", () => {
    render(<StatusBadge status="transcribed" />);
    expect(screen.getByText("Trascritto")).toBeInTheDocument();
  });

  it("mostra 'Completato' per lo stato completed", () => {
    render(<StatusBadge status="completed" />);
    expect(screen.getByText("Completato")).toBeInTheDocument();
  });

  it("mostra l'etichetta per lo stato fallito", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText("Fallito")).toBeInTheDocument();
  });
});
