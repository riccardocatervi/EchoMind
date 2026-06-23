/**
 * Palette di colori categoriale per le community Louvain.
 *
 * Perché colori fissi anziché generati dinamicamente:
 *   Una palette fissa garantisce che la community N abbia sempre lo stesso colore
 *   in tutte le sessioni e in tutti i componenti (nodo, minimap, legenda).
 *   Generare colori a runtime con `hsl(i * 360/n)` porta a colori che cambiano
 *   se il numero di community cambia tra sessioni (ri-estrazione → colori diversi).
 *
 * Cycling con modulo (`% PALETTE.length`):
 *   Se il numero di community supera la lunghezza della palette (10), i colori
 *   si ripetono. Accettabile: raramente un documento ha >10 community distinte.
 *
 * `NO_COMMUNITY = slate-500`:
 *   Grigio neutro per i nodi isolati (community=null). Non confondersi con la
 *   palette categoriale.
 */

const PALETTE = [
  "#3B82F6", // blue
  "#22C55E", // green
  "#F59E0B", // amber
  "#A855F7", // purple
  "#EC4899", // pink
  "#14B8A6", // teal
  "#EF4444", // red
  "#0EA5E9", // sky
  "#84CC16", // lime
  "#F97316", // orange
];

const NO_COMMUNITY = "#64748B"; // slate-500: nodi senza community assegnata

/** Colore associato a una community (ciclico sulla palette se > 10 community). */
export function communityColor(community: number | null): string {
  if (community === null || community < 0) return NO_COMMUNITY;
  return PALETTE[community % PALETTE.length];
}
