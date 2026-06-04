import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SummaryView } from "@/features/summary/components/SummaryView";
import type { SummaryRead } from "@/features/summary/schemas/summary";

const summary: SummaryRead = {
  id: "s1",
  document_id: "d1",
  owner_id: "o1",
  overview: "Panoramica di prova",
  sections: [{ title: "Sezione uno", content: "Contenuto della sezione" }],
  meta: { node_count: 9, relationship_count: 8, community_count: 1 },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("SummaryView", () => {
  it("rende overview e titolo della sezione", () => {
    render(<SummaryView summary={summary} />);
    expect(screen.getByText("Panoramica di prova")).toBeInTheDocument();
    expect(screen.getByText("Sezione uno")).toBeInTheDocument();
  });
});
