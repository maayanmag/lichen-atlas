// Build-time data loaders. These read the JSON files materialized by ingest_site.py
// from the `public/sites/<slug>/` folder. Used by Astro pages (server-side build).

import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';
import type { Site, Stone } from './types';

const HERE = path.dirname(url.fileURLToPath(import.meta.url));
const SITES_ROOT = path.resolve(HERE, '../../public/sites');

export function listSiteSlugs(): string[] {
  if (!fs.existsSync(SITES_ROOT)) return [];
  return fs.readdirSync(SITES_ROOT)
    .filter(d => fs.existsSync(path.join(SITES_ROOT, d, 'site.json')))
    .sort();
}

export function loadSite(slug: string): Site {
  const p = path.join(SITES_ROOT, slug, 'site.json');
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

export function loadStones(slug: string): Stone[] {
  const p = path.join(SITES_ROOT, slug, 'stones.json');
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

export function listAllSites(): Site[] {
  return listSiteSlugs().map(loadSite);
}

/** Photo URL, given a site slug, photo filename and size */
export function photoUrl(slug: string, fname: string, size: 'thumb' | 'medium' | 'large', base = ''): string {
  return `${base.replace(/\/$/, '')}/sites/${slug}/photos/${size}/${fname}`;
}
