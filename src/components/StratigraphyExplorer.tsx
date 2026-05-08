import React, { useEffect, useMemo, useState } from 'react';
import type { Site, Stone, BioConfidence } from '@/lib/types';
import { coverageFraction, genusColor, genusInfo } from '@/lib/lichens';
import { renderDetails } from '@/lib/markdown';

type Locale = 'en' | 'he';

interface Props {
  site: Site;
  stones: Stone[];
  baseUrl: string;
  /** Stone folder to pre-select (from URL) */
  initialStone?: string | null;
  /** UI locale */
  locale?: Locale;
  /** Pre-resolved string bag from src/lib/strings.ts */
  t: Record<string, string>;
}

type SortKey = 'chronological' | 'coverage' | 'surname' | 'age';

function photoSrc(slug: string, fname: string, size: 'thumb' | 'medium' | 'large', base: string): string {
  return `${base}/sites/${slug}/photos/${size}/${fname}`;
}

export default function StratigraphyExplorer({ site, stones, baseUrl, initialStone = null, locale = 'en', t }: Props) {
  const isHe = locale === 'he';
  const [selected, setSelected] = useState<string | null>(initialStone ?? stones[0]?.folder ?? null);
  const [sortBy, setSortBy] = useState<SortKey>('chronological');
  const [filterGenus, setFilterGenus] = useState<string | null>(null);
  const [confidenceFilter, setConfidenceFilter] = useState<Set<BioConfidence>>(new Set(['high','medium','low','unknown']));
  const [photoIdx, setPhotoIdx] = useState(0);
  const [tab, setTab] = useState<'inscription' | 'biography' | 'lichens' | 'photos'>('inscription');
  const [lang, setLang] = useState<InscriptionLang>(isHe ? 'he' : 'en');

  // Hash-driven deep linking
  useEffect(() => {
    const h = window.location.hash;
    const m = h.match(/stone=([^&]+)/);
    if (m && stones.find(s => s.folder === m[1])) {
      setSelected(m[1]);
    }
    const onHash = () => {
      const m2 = window.location.hash.match(/stone=([^&]+)/);
      if (m2 && stones.find(s => s.folder === m2[1])) setSelected(m2[1]);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  // When selection changes, push to URL and reset detail tabs
  useEffect(() => {
    if (selected) {
      const h = `#stone=${selected}`;
      if (window.location.hash !== h) {
        history.replaceState(null, '', h);
      }
      setPhotoIdx(0);
      setTab('inscription');
    }
  }, [selected]);

  const selectedStone = useMemo(
    () => stones.find(s => s.folder === selected) ?? stones[0] ?? null,
    [selected, stones]
  );

  // Sorting
  const sortedStones = useMemo(() => {
    const arr = [...stones];
    if (sortBy === 'chronological') {
      arr.sort((a, b) => (a.died_year ?? 9999) - (b.died_year ?? 9999) || a.folder.localeCompare(b.folder));
    } else if (sortBy === 'coverage') {
      arr.sort((a, b) => (b.lichen_coverage_high ?? 0) - (a.lichen_coverage_high ?? 0));
    } else if (sortBy === 'surname') {
      arr.sort((a, b) => a.folder.localeCompare(b.folder));
    } else if (sortBy === 'age') {
      arr.sort((a, b) => (b.stone_age_2026 ?? 0) - (a.stone_age_2026 ?? 0));
    }
    return arr;
  }, [stones, sortBy]);

  // Filtering — affects strata DIM state, not visibility (so layout doesn't shift)
  const isDimmed = (s: Stone) => {
    if (filterGenus && !s.lichen_genera.includes(filterGenus)) return true;
    if (!confidenceFilter.has(s.bio_confidence as BioConfidence)) return true;
    return false;
  };

  // Bottom biodiversity bar — reflects current filter visible set
  const visibleStones = sortedStones.filter(s => !isDimmed(s));
  const genusBreakdown = useMemo(() => {
    const counts: Record<string, number> = {};
    visibleStones.forEach(s => s.lichen_genera.forEach(g => { counts[g] = (counts[g] ?? 0) + 1; }));
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [visibleStones]);

  // Keyboard navigation
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!selectedStone) return;
      if (e.target && (e.target as HTMLElement).tagName === 'INPUT') return;
      const idx = sortedStones.findIndex(s => s.folder === selectedStone.folder);
      if (e.key === 'ArrowDown' || e.key === 'j') {
        e.preventDefault();
        setSelected(sortedStones[Math.min(sortedStones.length - 1, idx + 1)]?.folder ?? null);
      } else if (e.key === 'ArrowUp' || e.key === 'k') {
        e.preventDefault();
        setSelected(sortedStones[Math.max(0, idx - 1)]?.folder ?? null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [sortedStones, selectedStone]);

  // Confidence labels (translated)
  const confLabel: Record<BioConfidence, string> = {
    high: t['explorer.confidence.high'],
    medium: t['explorer.confidence.medium'],
    low: t['explorer.confidence.low'],
    unknown: t['explorer.confidence.unknown'],
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[minmax(380px,440px)_1fr] gap-0 min-h-[calc(100vh-4rem)]">
      {/* ============= LEFT: Stratigraphy ============= */}
      <aside className={`${isHe ? 'border-l border-r-0' : 'border-r'} border-slate-700/40 bg-slate-850/60`}>
        {/* Sort + filter chips */}
        <div className="sticky top-16 z-30 bg-slate-850/95 backdrop-blur border-b border-slate-700/40 p-4">
          {/* Sort */}
          <div className="flex items-center gap-1 text-xs mb-3">
            <span className="text-slate-600 me-2 uppercase tracking-wider">{t['explorer.sort.label']}</span>
            {([
              ['chronological', t['explorer.sort.chronological']],
              ['coverage',      t['explorer.sort.coverage']],
              ['age',           t['explorer.sort.age']],
              ['surname',       t['explorer.sort.surname']],
            ] as const).map(([k, label]) => (
              <button
                key={k}
                onClick={() => setSortBy(k as SortKey)}
                className={`px-2 py-1 rounded transition-colors ${sortBy === k ? 'bg-ember/15 text-ember' : 'text-bone-200 hover:bg-slate-700/40'}`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Genus filter chips */}
          <div className="flex items-center gap-1.5 flex-wrap text-xs">
            <span className="text-slate-600 me-1 uppercase tracking-wider">{t['explorer.filter.lichen']}</span>
            <button
              onClick={() => setFilterGenus(null)}
              className={`px-2 py-1 rounded transition-colors ${filterGenus == null ? 'bg-slate-700/60 text-bone-100' : 'text-bone-300 hover:bg-slate-700/40'}`}
            >
              {t['explorer.filter.all']}
            </button>
            {site.lichen_genera.slice(0, 6).map(({ genus }) => (
              <button
                key={genus}
                onClick={() => setFilterGenus(filterGenus === genus ? null : genus)}
                className={`flex items-center gap-1 px-2 py-1 rounded transition-all ${filterGenus === genus ? 'bg-slate-700/60 ring-1 ring-bone-300/30' : 'hover:bg-slate-700/30'}`}
                title={genusInfo(genus, locale).description}
              >
                <span className="lichen-dot" style={{ background: genusColor(genus) }} />
                <span className="text-bone-200 italic">{genus}</span>
              </button>
            ))}
          </div>

          {/* Confidence filter */}
          <div className="flex items-center gap-1.5 flex-wrap text-[11px] mt-2">
            <span className="text-slate-600 me-1 uppercase tracking-wider">{t['explorer.confidence.label']}</span>
            {(['high','medium','low','unknown'] as const).map(level => (
              <button
                key={level}
                onClick={() => {
                  const next = new Set(confidenceFilter);
                  if (next.has(level)) next.delete(level); else next.add(level);
                  if (next.size === 0) next.add(level); // never empty
                  setConfidenceFilter(next);
                }}
                className={`px-1.5 py-0.5 rounded transition-colors ${confidenceFilter.has(level) ? 'bg-slate-700/60 text-bone-100' : 'text-slate-600 line-through'}`}
              >
                {confLabel[level]}
              </button>
            ))}
          </div>
        </div>

        {/* The stratigraphy itself */}
        <div className="py-3">
          {sortedStones.map((stone) => {
            const isActive = selectedStone?.folder === stone.folder;
            const dim = isDimmed(stone);
            const fillFrac = coverageFraction(stone.lichen_coverage_low, stone.lichen_coverage_high);
            const dominant = stone.lichen_dominant?.split(' ')[0] ?? stone.lichen_genera[0];
            const tintColor = dominant ? genusColor(dominant) : '#444';
            const gradientDir = isHe ? 'to left' : 'to right';
            const borderSide = isHe
              ? { borderRight: `2px solid ${tintColor}`, borderLeft: 'none' }
              : { borderLeft:  `2px solid ${tintColor}`, borderRight: 'none' };
            return (
              <button
                key={stone.folder}
                onClick={() => setSelected(stone.folder)}
                className={`stratum w-full text-start px-4 py-2.5 group relative ${isActive ? 'is-active' : ''} ${dim ? 'opacity-30' : ''}`}
              >
                {/* Coverage bar (background) — anchors to the start edge in both LTR and RTL */}
                <div
                  className={`absolute inset-y-1.5 ${isHe ? 'right-4 rounded-l-sm' : 'left-4 rounded-r-sm'} transition-all`}
                  style={{
                    width: `calc(${fillFrac * 100}% - 1rem)`,
                    background: `linear-gradient(${gradientDir}, ${tintColor}55 0%, ${tintColor}15 80%, transparent 100%)`,
                    ...borderSide,
                  }}
                  aria-hidden="true"
                />
                {/* Row content */}
                <div className="relative flex items-center justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs tabular-nums ${isActive ? 'text-ember' : 'text-slate-600'} w-12 shrink-0`}>
                        {stone.died_year ?? '—'}
                      </span>
                      <span className={`text-sm font-medium truncate ${isActive ? 'text-bone-50' : 'text-bone-200'}`}>
                        {stone.is_unknown
                          ? <span className="italic text-bone-300">{t['explorer.unknownStone']}</span>
                          : (stone.surname ? `${stone.surname}, ${stone.given_names || ''}`.replace(/, $/, '') : stone.folder)}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 ps-14 text-[11px] text-slate-600">
                      <span>{stone.stone_age_2026 != null ? `${stone.stone_age_2026}${isHe ? ' ' + t['site.dl.years.suffix'] : 'y'}` : '—'}</span>
                      <span className="text-slate-700">·</span>
                      <span>{stone.lichen_coverage_label || '—'}</span>
                      <span className="text-slate-700">·</span>
                      <div className="flex items-center gap-0.5">
                        {stone.lichen_genera.slice(0, 4).map(g => (
                          <span key={g} className="lichen-dot" style={{ background: genusColor(g) }} title={g} />
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Bottom biodiversity bar */}
        <div className="sticky bottom-0 bg-slate-850/95 backdrop-blur border-t border-slate-700/40 px-4 py-3 z-30">
          <div className="text-[10px] uppercase tracking-wider text-slate-600 mb-1.5">
            {t['explorer.biodiversity.label']} ({visibleStones.length} {t['explorer.biodiversity.stones']})
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
            {genusBreakdown.length === 0 && <span className="text-slate-600">{t['explorer.biodiversity.none']}</span>}
            {genusBreakdown.map(([g, n]) => (
              <span key={g} className="inline-flex items-center gap-1.5">
                <span className="lichen-dot" style={{ background: genusColor(g) }} />
                <span className="text-bone-200 italic">{g}</span>
                <span className="text-slate-600 tabular-nums">{n}</span>
              </span>
            ))}
          </div>
        </div>
      </aside>

      {/* ============= RIGHT: Detail pane ============= */}
      <section className="overflow-y-auto">
        {selectedStone
          ? <DetailPane stone={selectedStone} site={site} baseUrl={baseUrl} photoIdx={photoIdx} setPhotoIdx={setPhotoIdx} tab={tab} setTab={setTab} lang={lang} setLang={setLang} locale={locale} t={t} />
          : <EmptyState text={t['explorer.empty']} />}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------- DetailPane

interface DetailProps {
  stone: Stone;
  site: Site;
  baseUrl: string;
  photoIdx: number;
  setPhotoIdx: (n: number) => void;
  tab: 'inscription' | 'biography' | 'lichens' | 'photos';
  setTab: (t: 'inscription' | 'biography' | 'lichens' | 'photos') => void;
  lang: InscriptionLang;
  setLang: (l: InscriptionLang) => void;
  locale: Locale;
  t: Record<string, string>;
}

type InscriptionLang = 'en' | 'he' | 'de' | 'pt' | 'latin';

/** Display priority for the language tabs. Originals first (he, de, pt),
 *  then translations/aids (en, latin). */
const LANG_PRIORITY: readonly InscriptionLang[] = ['he', 'de', 'pt', 'en', 'latin'] as const;
const RTL_LANGS: ReadonlySet<InscriptionLang> = new Set<InscriptionLang>(['he']);

function DetailPane({ stone, site, baseUrl, photoIdx, setPhotoIdx, tab, setTab, lang, setLang, locale, t }: DetailProps) {
  const isHe = locale === 'he';
  const allPhotos = [...stone.photos.full, ...stone.photos.closeups];
  const safeIdx = Math.min(photoIdx, allPhotos.length - 1);
  const currentPhoto = allPhotos[safeIdx];

  // Extract specific sections from the DETAILS.md for the tabbed views
  const sections = useMemo(() => extractSections(stone.details_md), [stone.details_md]);

  // Tab labels (translated; internal keys stay English)
  const tabLabels: Record<DetailProps['tab'], string> = {
    inscription: t['detail.tab.inscription'],
    biography:   t['detail.tab.biography'],
    lichens:     t['detail.tab.lichens'],
    photos:      t['detail.tab.photos'],
  };
  const langLabels: Record<InscriptionLang, string> = {
    en:    t['detail.lang.en'],
    de:    t['detail.lang.de'],
    he:    t['detail.lang.he'],
    pt:    t['detail.lang.pt'],
    latin: t['detail.lang.latin'],
  };

  // Compute which language tabs actually have content for THIS stone.
  const sectionByLang: Record<InscriptionLang, string> = {
    en:    sections.inscription_en,
    de:    sections.inscription_de,
    he:    sections.inscription_he,
    pt:    sections.inscription_pt,
    latin: sections.inscription_latin,
  };
  const availableLangs = LANG_PRIORITY.filter(l => sectionByLang[l]?.trim());

  // Clamp `lang` to an available choice when the stone changes — pick the
  // UI-locale's language if available, otherwise the first original.
  useEffect(() => {
    if (availableLangs.length === 0) return;
    if (!availableLangs.includes(lang)) {
      const preferred: InscriptionLang | undefined =
        availableLangs.includes(locale === 'he' ? 'he' : 'en')
          ? (locale === 'he' ? 'he' : 'en')
          : availableLangs[0];
      if (preferred) setLang(preferred);
    }
  }, [stone.folder, availableLangs.join(',')]);

  return (
    <div className="max-w-3xl mx-auto px-6 md:px-10 py-8">
      {/* Header */}
      <header className="mb-6">
        <p className="text-[10px] uppercase tracking-[0.2em] text-slate-600 mb-2">
          {site.name}{stone.died_year ? ` · ${stone.died_year}` : ''}
        </p>
        <h1 className="text-3xl md:text-4xl">
          {stone.is_unknown
            ? <span className="text-bone-200 italic">{t['explorer.unknownStone']}</span>
            : (
              <>
                <span className="text-bone-50">{stone.surname}</span>
                {stone.given_names && <span className="text-bone-300">, {stone.given_names}</span>}
              </>
            )
          }
        </h1>
        {stone.maiden_name && <p className="text-sm text-slate-600 mt-1">{t['detail.nee']} {stone.maiden_name}</p>}
        <div className="flex items-center gap-2 mt-3 text-xs flex-wrap">
          {stone.born && <span className="text-bone-300">{t['detail.born.short']} {stone.born}</span>}
          {stone.born && stone.died && <span className="text-slate-700">·</span>}
          {stone.died && <span className="text-bone-300">{t['detail.died.short']} {stone.died}</span>}
          {stone.age_at_death != null && <span className="text-slate-600">{t['detail.age.prefix']} {stone.age_at_death}</span>}
          {stone.stone_age_2026 != null && (
            <>
              <span className="text-slate-700">·</span>
              <span className="text-ember">{t['detail.stoneAge.prefix']} {stone.stone_age_2026} {t['detail.stoneAge.suffix']}</span>
            </>
          )}
          <span className={`confidence-pill confidence-${stone.bio_confidence}`}>
            {(({high:t['explorer.confidence.high'],medium:t['explorer.confidence.medium'],low:t['explorer.confidence.low'],unknown:t['explorer.confidence.unknown']}) as Record<string,string>)[stone.bio_confidence]}
          </span>
        </div>
      </header>

      {/* Photo carousel */}
      {currentPhoto && (
        <div className="relative panel overflow-hidden mb-6 group">
          <img
            src={photoSrc(site.slug, currentPhoto, 'medium', baseUrl)}
            alt={
              stone.photos.full.includes(currentPhoto)
                ? `${stone.is_unknown ? t['explorer.unknownStone'] : (stone.surname + ' ' + stone.given_names).trim()}${stone.died_year ? ' (' + stone.died_year + ')' : ''}`
                : `${stone.is_unknown ? t['explorer.unknownStone'] : stone.surname} — ${stone.lichen_genera.join(', ')}`
            }
            className="w-full max-h-[60vh] object-contain bg-slate-900"
            loading="eager"
          />
          {allPhotos.length > 1 && (
            <>
              <button onClick={() => setPhotoIdx((safeIdx - 1 + allPhotos.length) % allPhotos.length)}
                      className="absolute start-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-slate-900/60 backdrop-blur text-bone-100 hover:bg-slate-900/90 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">‹</button>
              <button onClick={() => setPhotoIdx((safeIdx + 1) % allPhotos.length)}
                      className="absolute end-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-slate-900/60 backdrop-blur text-bone-100 hover:bg-slate-900/90 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">›</button>
              <div className="absolute bottom-3 start-3 text-[10px] uppercase tracking-wider text-bone-200 bg-slate-900/70 backdrop-blur px-2 py-1 rounded">
                {safeIdx + 1} / {allPhotos.length} · {stone.photos.full.includes(currentPhoto) ? t['detail.photo.full'] : t['detail.photo.closeup']}
              </div>
            </>
          )}
        </div>
      )}

      {/* Photo strip */}
      {allPhotos.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-3 mb-6 -mx-2 px-2">
          {allPhotos.map((p, i) => (
            <button key={p} onClick={() => setPhotoIdx(i)}
                    aria-label={`${i+1} / ${allPhotos.length} — ${stone.photos.full.includes(p) ? t['detail.photo.full'] : t['detail.photo.closeup']}`}
                    className={`shrink-0 w-20 h-20 rounded overflow-hidden border ${i === safeIdx ? 'border-ember' : 'border-slate-700/40 opacity-60 hover:opacity-100'}`}>
              <img src={photoSrc(site.slug, p, 'thumb', baseUrl)} alt="" className="w-full h-full object-cover" loading="lazy" />
            </button>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-slate-700/40 mb-4 text-sm">
        {(['inscription','biography','lichens','photos'] as const).map(tk => (
          <button key={tk} onClick={() => setTab(tk)}
                  className={`px-4 py-2 -mb-px border-b-2 transition-colors ${tab === tk ? 'border-ember text-ember' : 'border-transparent text-bone-300 hover:text-bone-100'}`}>
            {tabLabels[tk]}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div>
        {tab === 'inscription' && (
          <div>
            {/* Language toggle (inscription language — independent of UI locale)
                Only languages with actual content for this stone are shown. */}
            {availableLangs.length > 1 && (
              <div className="flex items-center gap-1 mb-4 text-xs flex-wrap">
                <span className="text-slate-600 me-1 uppercase tracking-wider">{t['detail.readIn']}</span>
                {availableLangs.map(l => (
                  <button key={l} onClick={() => setLang(l)}
                          className={`px-2 py-0.5 rounded ${lang === l ? 'bg-ember/15 text-ember' : 'text-bone-300 hover:bg-slate-700/40'}`}>
                    {langLabels[l]}
                  </button>
                ))}
              </div>
            )}

            <div className={`whitespace-pre-line ${RTL_LANGS.has(lang) ? 'font-hebrew text-right text-lg' : (lang === 'latin' ? 'font-mono text-base text-bone-200 italic' : 'font-serif text-lg')} text-bone-100 leading-snug`} dir={RTL_LANGS.has(lang) ? 'rtl' : 'ltr'}>
              {sectionByLang[lang] || <span className="text-slate-600 italic">{t['detail.inscription.empty']}</span>}
            </div>
            {stone.biblical_reference && (
              <p className="text-xs text-slate-600 italic mt-4">— {stone.biblical_reference}</p>
            )}
          </div>
        )}

        {tab === 'biography' && (
          <div className="prose-invert max-w-none">
            <div dangerouslySetInnerHTML={{ __html: renderDetails(sections.biography || t['detail.biography.empty']) }} />
            {stone.tempelgesellschaft_registry_id != null && (
              <a href={`https://www.tempelgesellschaft.de/de/geschichte/historische-friedhoefe/verzeichnis-grabstaetten.php?id=${stone.tempelgesellschaft_registry_id}&detail=1`}
                 target="_blank" rel="noopener"
                 className="inline-block mt-4 text-xs text-ember underline-offset-2 underline decoration-ember/30">
                {t['detail.registry.entry']} #{stone.tempelgesellschaft_registry_id} ↗
              </a>
            )}
          </div>
        )}

        {tab === 'lichens' && (
          <div>
            <div className="flex flex-wrap gap-2 mb-4">
              {stone.lichen_genera.map(g => {
                const info = genusInfo(g, locale);
                return (
                  <span key={g} className="lichen-chip" title={info.description}>
                    <span className="lichen-dot" style={{ background: info.color }} />
                    <span className="italic">{g}</span>
                  </span>
                );
              })}
              {stone.lichen_genera.length === 0 && <span className="text-slate-600 text-sm italic">{t['detail.lichens.empty']}</span>}
            </div>
            {stone.lichen_dominant && (
              <p className="text-sm text-bone-300 mb-3">
                {t['detail.dominant']} <span className="text-bone-100 italic">{stone.lichen_dominant}</span>
                {stone.lichen_coverage_label && <span className="text-slate-600"> {t['detail.coverage.prefix']} {stone.lichen_coverage_label}</span>}
              </p>
            )}
            <div className="prose-invert max-w-none" dangerouslySetInnerHTML={{ __html: renderDetails(sections.lichens || '') }} />
          </div>
        )}

        {tab === 'photos' && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {allPhotos.map((p, i) => (
              <button key={p} onClick={() => { setTab('inscription'); setPhotoIdx(i); }} className="aspect-square rounded overflow-hidden border border-slate-700/40 hover:border-ember/40 transition-colors">
                <img src={photoSrc(site.slug, p, 'thumb', baseUrl)} alt="" className="w-full h-full object-cover" loading="lazy" />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Notable callout */}
      {stone.notable && (
        <div className="mt-8 border-s-2 border-ember/40 ps-4 py-2 text-sm text-bone-200 bg-ember/5 rounded-e-md">
          <div className="text-[10px] uppercase tracking-wider text-ember mb-1">{t['detail.notable.label']}</div>
          {stone.notable}
        </div>
      )}

      {/* Stone-type / verify footer */}
      <footer className="mt-8 pt-6 border-t border-slate-700/40 text-xs text-slate-600 space-y-2">
        {stone.stone_type && <p><span className="text-bone-300">{t['detail.stone.label']}</span> {stone.stone_type}</p>}
        {(() => {
          const verifyBody = (isHe ? site.verify_source_he : site.verify_source_en) || t['detail.verify.body'];
          return verifyBody ? (
            <p><span className="text-bone-300">{t['detail.verify.label']}</span> {verifyBody}</p>
          ) : null;
        })()}
        <p className="font-mono">{stone.folder}</p>
      </footer>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="flex items-center justify-center h-full text-slate-600">{text}</div>;
}

// ---------------------------------------------------------------- helpers

interface Sections {
  inscription_de: string;
  inscription_en: string;
  inscription_he: string;
  inscription_pt: string;
  inscription_latin: string;
  biography: string;
  lichens: string;
}

/** Pattern for matching inscription section headings to a language bucket.
 *  Order matters — more specific patterns must come first.
 *  - Bare "### Original Inscription" (no language hint) falls back to German
 *    for backward compatibility with the Templer DETAILS.md template, where
 *    the original was always German. New per-site templates should always
 *    declare the language explicitly: e.g. "### Original Inscription (Hebrew)". */
const INSCRIPTION_HEADING_PATTERNS: ReadonlyArray<readonly [RegExp, InscriptionLang]> = [
  [/^####?\s+Original\s+Inscription\s*\(.*Hebrew.*\)/i,                                'he'],
  [/^####?\s+Original\s+Inscription\s*\(.*German.*\)/i,                                'de'],
  [/^####?\s+Original\s+Inscription\s*\(.*Portuguese.*\)/i,                            'pt'],
  [/^####?\s+Original\s+Inscription\s*\(.*(Latin|English).*\)/i,                       'en'],
  [/^####?\s+Hebrew\s+Translation/i,                                                   'he'],
  [/^####?\s+English\s+Translation/i,                                                  'en'],
  [/^####?\s+Portuguese\s+Translation/i,                                               'pt'],
  [/^####?\s+German\s+Translation/i,                                                   'de'],
  [/^####?\s+Latin\s+Transliteration/i,                                                'latin'],
  [/^####?\s+Transliteration/i,                                                        'latin'],
  [/^####?\s+Original\s+Inscription(?!\s*\()/i,                                        'de'],
];

const SEPARATOR = '\n\n— — —\n\n';

/** Extract themed sections out of a DETAILS.md body. The DETAILS.md template
 *  has fairly stable headings — but agents wrote slight variations.
 *  Multiple inscription sections in the same language (e.g. headstone +
 *  grave-bed, or left + right panel) are concatenated with a SEPARATOR. */
function extractSections(md: string): Sections {
  const out: Sections = {
    inscription_de: '', inscription_en: '', inscription_he: '',
    inscription_pt: '', inscription_latin: '',
    biography: '', lichens: '',
  };
  if (!md) return out;
  const lines = md.split('\n');

  // Helper: extract content between two heading patterns (single-shot — first match).
  const extractBetween = (startRe: RegExp, endRes: RegExp[]): string => {
    let i = 0;
    for (; i < lines.length; i++) if (startRe.test(lines[i])) break;
    if (i >= lines.length) return '';
    const start = i + 1;
    let end = lines.length;
    for (let j = start; j < lines.length; j++) {
      if (endRes.some(r => r.test(lines[j]))) { end = j; break; }
    }
    return lines.slice(start, end).join('\n').trim();
  };

  // Extract all fenced code blocks from a substring, joined with the separator.
  const extractAllFencedBlocks = (src: string): string => {
    const matches = [...src.matchAll(/```[^\n]*\n([\s\S]*?)```/g)];
    if (matches.length === 0) return src.trim();
    return matches.map(m => m[1].trim()).join(SEPARATOR);
  };

  const sectionEndRe = /^#{2,4}\s+/;

  const langBuckets: Record<InscriptionLang, string[]> = {
    en: [], de: [], he: [], pt: [], latin: [],
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    let matchedLang: InscriptionLang | null = null;
    for (const [re, lang] of INSCRIPTION_HEADING_PATTERNS) {
      if (re.test(line)) { matchedLang = lang; break; }
    }
    if (!matchedLang) continue;

    let end = lines.length;
    for (let j = i + 1; j < lines.length; j++) {
      if (sectionEndRe.test(lines[j])) { end = j; break; }
    }
    const body = lines.slice(i + 1, end).join('\n');
    const block = extractAllFencedBlocks(body);
    if (block) langBuckets[matchedLang].push(block);
    i = end - 1;
  }

  out.inscription_en    = langBuckets.en.join(SEPARATOR);
  out.inscription_de    = langBuckets.de.join(SEPARATOR);
  out.inscription_he    = langBuckets.he.join(SEPARATOR);
  out.inscription_pt    = langBuckets.pt.join(SEPARATOR);
  out.inscription_latin = langBuckets.latin.join(SEPARATOR);

  out.biography = extractBetween(/^####?\s+Biographical\s+context/i, [sectionEndRe, /^---/]);
  out.lichens = extractBetween(/^##\s+🦠?\s*Lichen\s+Analysis/i, [/^##\s+🔄/, /^##\s+/, /^---/]);

  return out;
}
