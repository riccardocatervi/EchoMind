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

/** Formatta una data ISO in formato italiano leggibile. */
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("it-IT", { dateStyle: "medium", timeStyle: "short" });
}
