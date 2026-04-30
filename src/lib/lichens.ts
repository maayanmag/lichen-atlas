// Lichen palette + small helpers.
// Each genus has ONE canonical color used everywhere (chips, dots, strata, charts).
// Descriptions are bilingual (English + Hebrew). Genus names are scientific
// Latin and never translated.

import type { Locale } from './i18n';

export interface LichenGenusInfo {
  genus: string;
  color: string;        // canonical color (used for dots, fills)
  textColor: string;    // legible text color when over the canonical color
  description: string;  // localized description (resolved by genusInfo)
}

interface LichenGenusEntry {
  genus: string;
  color: string;
  textColor: string;
  description_en: string;
  description_he: string;
}

export const LICHEN_PALETTE: Record<string, LichenGenusEntry> = {
  Caloplaca: {
    genus: 'Caloplaca',
    color: '#E07A2E',
    textColor: '#1A0E04',
    description_en: 'Bright orange placodioid rosettes — Mediterranean calcareous-rock specialist.',
    description_he: 'ורדיות פלקודיואידיות בכתום בוהק — מתמחה בסלעי קרבונט ים-תיכוניים.',
  },
  Aspicilia: {
    genus: 'Aspicilia',
    color: '#9DA67E',
    textColor: '#0E0F08',
    description_en: 'Pale grey-green crustose film — the background substrate of Jerusalem-limestone communities.',
    description_he: 'קרום קרוסטוזי בגוון אפור-ירקרק חיוור — הרקע של קהילות החזזיות על אבן ירושלים.',
  },
  Verrucaria: {
    genus: 'Verrucaria',
    color: '#3A3A3A',
    textColor: '#F0F0F0',
    description_en: 'Endolithic — lives inside the stone matrix; visible only as black perithecial dots on the surface.',
    description_he: 'אנדוליתית — חיה בתוך מטריצת האבן עצמה; נראית רק כנקודות שחורות של פריתציה על פני השטח.',
  },
  Candelariella: {
    genus: 'Candelariella',
    color: '#D9C04A',
    textColor: '#1A1402',
    description_en: 'Egg-yolk-yellow granular crustose — pioneer on smooth carbonate.',
    description_he: 'קרוסטוזית גרגירית בצבע צהוב חלמון — חלוצה על משטחי קרבונט חלקים.',
  },
  Lecanora: {
    genus: 'Lecanora',
    color: '#C5C2B5',
    textColor: '#1A1A14',
    description_en: 'Cosmopolitan urban-tolerant; *L. muralis* common on man-made stone.',
    description_he: 'קוסמופוליטית, סובלנית לסביבה עירונית; *L. muralis* נפוצה על אבן בידי אדם.',
  },
  Xanthoria: {
    genus: 'Xanthoria',
    color: '#E8B547',
    textColor: '#1A1004',
    description_en: 'Foliose, gold-orange; nitrophilous (eutrophication indicator).',
    description_he: 'עליתית בצבע זהב-כתום; ניטרופילית (אינדיקטור לאוטרופיקציה).',
  },
  Lecidella: {
    genus: 'Lecidella',
    color: '#5C5147',
    textColor: '#F0F0F0',
    description_en: 'Crustose with small black biatorine apothecia.',
    description_he: 'קרוסטוזית עם אפותציות שחורות קטנות מטיפוס ביאטורין.',
  },
  Bryophyta: {
    genus: 'Bryophyta',
    color: '#4A6B3F',
    textColor: '#F0F0F0',
    description_en: 'Mosses (not lichen — bryophyte). Often signals moisture availability at stone base.',
    description_he: 'טחבים (אינם חזזיות — בריופיטים). פעמים רבות מסמנים זמינות לחות בבסיס המצבה.',
  },
};

const FALLBACK_COLOR = '#6E6E6E';
const FALLBACK_DESC_EN = 'Genus not in canonical palette — see source.';
const FALLBACK_DESC_HE = 'הסוג אינו בפלטה הקנונית — ראו מקור.';

export function genusInfo(genus: string, locale: Locale = 'en'): LichenGenusInfo {
  const e = LICHEN_PALETTE[genus];
  if (!e) {
    return {
      genus,
      color: FALLBACK_COLOR,
      textColor: '#F0F0F0',
      description: locale === 'he' ? FALLBACK_DESC_HE : FALLBACK_DESC_EN,
    };
  }
  return {
    genus: e.genus,
    color: e.color,
    textColor: e.textColor,
    description: locale === 'he' ? e.description_he : e.description_en,
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
