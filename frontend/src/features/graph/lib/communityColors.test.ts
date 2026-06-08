import { describe, expect, it } from "vitest";

import { communityColor } from "@/features/graph/lib/communityColors";

describe("communityColor", () => {
  it("e' stabile per community e differenzia community diverse", () => {
    expect(communityColor(0)).toBe(communityColor(0));
    expect(communityColor(0)).not.toBe(communityColor(1));
  });

  it("ritorna un colore di fallback per community null", () => {
    expect(communityColor(null)).toMatch(/^#[0-9A-Fa-f]{6}$/);
  });
});
