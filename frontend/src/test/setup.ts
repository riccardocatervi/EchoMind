import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Pulisce il DOM dopo ogni test (con globals disattivati lo registriamo a mano).
afterEach(() => {
  cleanup();
});
