// Lichen palette + small helpers.
// Each genus has ONE canonical color used everywhere (chips, dots, strata, charts).

export interface LichenGenusInfo {
  genus: string;
  color: string;        // canonical color (used for dots, fills)
  textColor: string;    // legible text color when over the canonical color
  description: string;  // 1-line for tooltips / legends
}

export const LICHEN_PALETTE: Record<string, LichenGenusInfo> = {
  Caloplaca: {
    genus: 'Caloplaca',
    color: '#E07A2E',
    textColor: '#1A0E04',
    description: 'Bright orange placodioid rosettes — Mediterranean calcareous-rock specialist.',
  },
  Aspicilia: {
    genus: 'Aspicilia',
    color: '#9DA67E',
    textColor: '#0E0F08',
    description: 'Pale grey-green crustose film — the background substrate of Jerusalem-limestone communities.',
  },
  Verrucaria: {
    genus: 'Verrucaria',
    color: '#3A3A3A',
    textColor: '#F0F0F0',
    description: 'Endolithic — lives inside the stone matrix; visible only as black perithecial dots on the surface.',
  },
  Candelariella: {
    genus: 'Candelariella',
    color: '#D9C04A',
    textColor: '#1A1402',
    description: 'Egg-yolk-yellow granular crustose — pioneer on smooth carbonate.',
  },
  Lecanora: {
    genus: 'Lecanora',
    color: '#C5C2B5',
    textColor: '#1A1A14',
    description: 'Cosmopolitan urban-tolerant; *L. muralis* common on man-made stone.',
  },
  Xanthoria: {
    genus: 'Xanthoria',
    color: '#E8B547',
    textColor: '#1A1004',
    description: 'Foliose, gold-orange; nitrophilous (eutrophication indicator).',
  },
  Lecidella: {
    genus: 'Lecidella',
    color: '#5C5147',
    textColor: '#F0F0F0',
    description: 'Crustose with small black biatorine apothecia.',
  },
  Bryophyta: {
    genus: 'Bryophyta',
    color: '#4A6B3F',
    textColor: '#F0F0F0',
    description: 'Mosses (not lichen — bryophyte). Often signals moisture availability at stone base.',
  },
};

const FALLBACK_COLOR = '#6E6E6E';

export function genusInfo(genus: string): LichenGenusInfo {
  return LICHEN_PALETTE[genus] ?? {
    genus,
    color: FALLBACK_COLOR,
    textColor: '#F0F0F0',
    description: 'Genus not in canonical palette — see source.',
  };
}

export function genusColor(genus: string): string {
  return LICHEN_PALETTE[genus]?.color ?? FALLBACK_COLOR;
}

/** Coverage → row width fraction for stratigraphy bars */
export function coverageFraction(low: number | null, high: number | null): number {
  if (low == null && high == null) return 0.10; // small default for "no data"
  const v = high ?? low ?? 0;
  return Math.min(1, Math.max(0.05, v / 100));
}
