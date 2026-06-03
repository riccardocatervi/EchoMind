import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Combina classi Tailwind in modo sicuro: `clsx` gestisce condizioni/array,
 * `tailwind-merge` risolve i conflitti (es. "px-2 px-4" -> "px-4"). E' l'helper
 * standard di shadcn/ui, usato da tutti i componenti.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
