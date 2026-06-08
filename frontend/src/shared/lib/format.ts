import { format } from "date-fns";
import { it } from "date-fns/locale";

/** Formatta una dimensione in byte in modo leggibile (B, KB, MB, GB). */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}

/** Formatta un timestamp ISO in italiano (es. "4 giu 2026, 14:30"). */
export function formatDateTime(iso: string): string {
  return format(new Date(iso), "d MMM yyyy, HH:mm", { locale: it });
}
