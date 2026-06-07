/**
 * useTheme — gestione del tema chiaro/scuro.
 *
 * Strategia:
 * - Persistenza: localStorage key "echomind_theme"
 * - Default: "dark" (il design system e' orientato al dark)
 * - Applicazione: aggiunge/rimuove class "dark" su <html>
 *   (i CSS token di shadcn/ui sono definiti per :root e .dark)
 * - Effetto collaterale al mount: applica subito il tema salvato
 *   per evitare il flash of wrong theme (FOWT).
 */
import { useCallback, useEffect, useState } from "react";

export type Theme = "dark" | "light";

const STORAGE_KEY = "echomind_theme";
const DEFAULT_THEME: Theme = "dark";

function readTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
    if (stored === "dark" || stored === "light") return stored;
  } catch {
    // localStorage non disponibile (SSR, incognito aggressivo)
  }
  return DEFAULT_THEME;
}

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(readTheme);

  // Applica il tema letto dal localStorage al mount (anti-FOWT).
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    applyTheme(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  return { theme, setTheme, toggleTheme, isDark: theme === "dark" };
}
