// Locale helpers for the bilingual (English / Hebrew) site.
//
// English is the default locale and lives at the root (`/lichen-atlas/...`).
// Hebrew lives under `/he/...` (i.e. `/lichen-atlas/he/...`).
//
// Pages that render in Hebrew set `locale='he'` explicitly; everything else
// defaults to `'en'`. The header switcher uses `pathInOtherLocale()` to
// produce a same-page link in the other language.

export type Locale = 'en' | 'he';

export const LOCALES: Locale[] = ['en', 'he'];
export const DEFAULT_LOCALE: Locale = 'en';

/** Strip a leading base prefix (e.g. `/lichen-atlas`) from a pathname. */
function stripBase(pathname: string, baseUrl: string): string {
  const base = baseUrl.replace(/\/$/, '');
  if (base && pathname.startsWith(base)) {
    return pathname.slice(base.length) || '/';
  }
  return pathname;
}

/** Detect locale from a URL pathname. Hebrew pages live under `/he/...`. */
export function getLocaleFromUrl(url: URL, baseUrl = ''): Locale {
  const p = stripBase(url.pathname, baseUrl);
  if (p === '/he' || p.startsWith('/he/')) return 'he';
  return 'en';
}

/** Opposite locale (only two for now — easy to extend later). */
export function oppositeLocale(locale: Locale): Locale {
  return locale === 'en' ? 'he' : 'en';
}

/**
 * Given a path inside the *English* site (e.g. `/about`, `/sites/foo/`),
 * return the path for the requested locale. English keeps the path as-is;
 * Hebrew prefixes with `/he`.
 */
export function localizedPath(path: string, locale: Locale): string {
  const clean = path.startsWith('/') ? path : `/${path}`;
  if (locale === 'he') return `/he${clean === '/' ? '' : clean}` || '/he';
  return clean;
}

/**
 * Compute the same-page path in the opposite locale.
 * Used by the header EN | עברית switcher.
 *
 *   /about                  ↔  /he/about
 *   /sites/x/stone/y/       ↔  /he/sites/x/stone/y/
 *   /he                     →  /
 */
export function pathInOtherLocale(url: URL, baseUrl = ''): string {
  const base = baseUrl.replace(/\/$/, '');
  const p = stripBase(url.pathname, baseUrl);
  const current = getLocaleFromUrl(url, baseUrl);
  const target = oppositeLocale(current);

  let englishPath: string;
  if (current === 'he') {
    englishPath = p === '/he' ? '/' : p.replace(/^\/he/, '') || '/';
  } else {
    englishPath = p;
  }

  const targetPath = target === 'en' ? englishPath : localizedPath(englishPath, 'he');
  // Re-apply hash and search if any were on the original URL.
  return `${base}${targetPath}${url.search}${url.hash}`;
}

/** HTML `dir` attribute for a locale. */
export function dirFor(locale: Locale): 'ltr' | 'rtl' {
  return locale === 'he' ? 'rtl' : 'ltr';
}

/** HTML `lang` attribute for a locale. */
export function htmlLangFor(locale: Locale): string {
  return locale === 'he' ? 'he' : 'en';
}
