// Palette categoriale per le community (colore stabile per indice).
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

const NO_COMMUNITY = "#64748B"; // slate-500

/** Colore associato a una community (ciclico sulla palette). */
export function communityColor(community: number | null): string {
  if (community === null || community < 0) return NO_COMMUNITY;
  return PALETTE[community % PALETTE.length];
}
