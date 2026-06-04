import { describe, expect, it } from "vitest";

import { credentialsSchema } from "@/features/auth/schemas/authSchema";

describe("credentialsSchema", () => {
  it("accetta credenziali valide", () => {
    expect(credentialsSchema.safeParse({ email: "a@b.com", password: "secret1" }).success).toBe(
      true,
    );
  });

  it("rifiuta email malformata e password corta", () => {
    expect(credentialsSchema.safeParse({ email: "nope", password: "secret1" }).success).toBe(false);
    expect(credentialsSchema.safeParse({ email: "a@b.com", password: "123" }).success).toBe(false);
  });
});
