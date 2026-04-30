// Shared types — mirror the JSON shape produced by scripts/ingest_site.py

export interface StonePhotos {
  full: string[];
  closeups: string[];
}

export type BioConfidence = 'high' | 'medium' | 'low' | 'unknown';

export interface Stone {
  folder: string;
  is_unknown: boolean;

  surname: string;
  given_names: string;
  maiden_name: string;
  born: string;
  born_year: number | null;
  died: string;
  died_year: number | null;
  age_at_death: number | null;
  stone_age_2026: number | null;

  bio_confidence: BioConfidence;
  stone_type: string;
  inscription_language: string;

  lichen_genera: string[];
  lichen_species: string[];
  lichen_dominant: string | null;
  lichen_coverage_low: number | null;
  lichen_coverage_high: number | null;
  lichen_coverage_label: string;

  photos: StonePhotos;
  photo_count: number;
  biblical_reference: string | null;
  details_md: string;
  notable: string | null;
  tempelgesellschaft_registry_id: number | null;
}

export interface SiteGenusEntry {
  genus: string;
  stone_count: number;
}

export interface SiteStoneAge {
  oldest: number | null;
  newest: number | null;
  median: number | null;
}

export interface Site {
  slug: string;
  name: string;
  subtitle?: string;
  location?: string;
  founded?: number;
  community?: string;
  tagline?: string;
  history_md?: string;

  stone_count: number;
  photo_count: number;
  identified_count: number;
  unknown_count: number;
  date_range: string;
  death_year_min: number | null;
  death_year_max: number | null;
  stone_age: SiteStoneAge;
  lichen_genera: SiteGenusEntry[];
  confidence_breakdown: Record<BioConfidence, number>;
  ingested_at: string;
}
