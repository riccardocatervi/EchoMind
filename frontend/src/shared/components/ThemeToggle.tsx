import { Moon, Sun } from "lucide-react";

import { Button } from "@/shared/components/ui/button";
import { useTheme } from "@/shared/hooks/useTheme";

/** Pulsante che alterna tema scuro / chiaro. */
export function ThemeToggle() {
  const { isDark, toggleTheme } = useTheme();

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
      aria-label={isDark ? "Attiva tema chiaro" : "Attiva tema scuro"}
    >
      {isDark ? (
        <Sun className="size-4" aria-hidden="true" />
      ) : (
        <Moon className="size-4" aria-hidden="true" />
      )}
    </Button>
  );
}
