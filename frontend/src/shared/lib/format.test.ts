import { describe, expect, it } from "vitest";

import { formatBytes } from "@/shared/lib/format";

describe("formatBytes", () => {
  it("formatta byte, KB e MB", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1024)).toBe("1.0 KB");
    expect(formatBytes(1024 * 1024)).toBe("1.0 MB");
  });
});
