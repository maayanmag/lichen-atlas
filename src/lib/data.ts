// Build-time data loaders. These read the JSON files materialized by ingest_site.py
// from the `public/sites/<slug>/` folder. Used by Astro pages (server-side build).
//
// Locale-aware: when called with `locale='he'`, an overlay file (e.g.
// `site.he.json`, `stones.he.json`) is merged on top of the English source.
// English remains the canonical data file so the Python ingest pipeline
// keeps working unchanged.

import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';
import type { Site, Stone } from './types';
import type { Locale } from './i18n';

const HERE = path.dirname(url.fileURLToPath(import.meta.url));
const SITES_ROOT = path.resolve(HERE, '../../public/sites');

export function listSiteSlugs(): string[] {
  if (!fs.existsSync(SITES_ROOT)) return [];
  return fs.readdirSync(SITES_ROOT)
    .filter(d => fs.existsSync(path.join(SITES_ROOT, d, 'site.json')))
    .sort();
}

function readJsonIfExists<T>(p: string): T | null {
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, 'utf-8')) as T;
  } catch {
    return null;
  }
}

/** Merge only defined string/number fields from overlay onto base. */
function mergeOverlay<T extends Record<string, any>>(base: T, overlay: Partial<T> | null): T {
  if (!overlay) return base;
  const out: Record<string, any> = { ...base };
  for (const k of Object.keys(overlay)) {
    const v = (overlay as any)[k];
    if (v === undefined || v === null || v === '') continue;
    out[k] = v;
  }
  return out as T;
}

export function loadSite(slug: string, locale: Locale = 'en'): Site {
  const base = JSON.parse(fs.readFileSync(path.join(SITES_ROOT, slug, 'site.json'), 'utf-8')) as Site;
  if (locale === 'en') return base;
  const overlay = readJsonIfExists<Partial<Site>>(path.join(SITES_ROOT, slug, `site.${locale}.json`));
  return mergeOverlay(base, overlay);
}

export function loadStones(slug: string, locale: Locale = 'en'): Stone[] {
  const stones = JSON.parse(fs.readFileSync(path.join(SITES_ROOT, slug, 'stones.json'), 'utf-8')) as Stone[];
  if (locale === 'en') return stones;
  const overlayList = readJsonIfExists<Array<Partial<Stone> & { folder: string }>>(
    path.join(SITES_ROOT, slug, `stones.${locale}.json`),
  );
  if (!overlayList) return stones;
  const byFolder = new Map<string, Partial<Stone>>();
  for (const o of overlayList) {
    if (o && o.folder) byFolder.set(o.folder, o);
  }
  return stones.map(s => {
    const ov = byFolder.get(s.folder);
    return ov ? mergeOverlay(s, ov) : s;
  });
}

export function listAllSites(locale: Locale = 'en'): Site[] {
  return listSiteSlugs().map(slug => loadSite(slug, locale));
}

/** Photo URL, given a site slug, photo filename and size */
export function photoUrl(slug: string, fname: string, size: 'thumb' | 'medium' | 'large', base = ''): string {
  return `${base.replace(/\/$/, '')}/sites/${slug}/photos/${size}/${fname}`;
}

