# 🪦 Lichen Atlas

**🌐 Live demo: <https://maayanmag.github.io/lichen-atlas/>**

> **🚧 Work in progress** — this is an early prototype of the explorer for an ongoing field-research project. Data, taxonomy IDs, and biographies are AI-assisted and subject to verification (see *Methodology & Limits*). Don't cite anything from here without cross-referencing the printed sources.

A multi-site web atlas of lichens colonizing historical cemeteries — Bezalel Bio-Design / Maayan Magenheim.

The Lichen Atlas is a static web app that turns the AI-assisted documentation pipeline output (per-stone DETAILS.md + photos + metadata) into a beautiful, modern, browsable interface.

## Aesthetic — "Memory Stratigraphy"

A two-pane explorer:

- **Left pane** — a vertical "soil-core" timeline. Every stone is a stratum, ordered chronologically by death year. Each stratum's coloured bar is sized by lichen coverage (so you can _literally see_ the colonization-vs-time pattern across the cemetery) and tinted by the stone's dominant lichen genus.
- **Right pane** — clean photograph carousel + tri-lingual inscription (German / English / Hebrew toggle) + biography with confidence label + lichen taxonomy chips with the same canonical genus-colors as the strata, so you can move your eye between data and image without re-orienting.
- **Bottom** — a small biodiversity bar that updates with the current filter, doubling as a legend.

Built with **Astro 4 + Tailwind + React** (islands architecture — only the explorer hydrates). Static output, deployable to GitHub Pages, Netlify, Vercel, or any static host.

## Multi-site by design

Each cemetery is a "site" with its own data folder under `public/sites/<slug>/`. Adding a new field site is a one-command operation:

```bash
python3 scripts/ingest_site.py --site har-hamenuchot --source /path/to/_organized
```

This produces:
```
public/sites/har-hamenuchot/
  site.json            cemetery-level metadata
  stones.json          per-stone normalized array
  photos/{thumb,medium,large}/   3 image sizes for fast loads
```

The Astro site picks up new sites at next build.

## File structure

```
lichen_atlas/
├── README.md
├── package.json
├── astro.config.mjs
├── tailwind.config.js
├── tsconfig.json
├── public/
│   ├── favicon.svg
│   └── sites/
│       └── templer-cemetery/        ← built by ingest_site.py
│           ├── site.json
│           ├── stones.json
│           └── photos/{thumb,medium,large}/
├── scripts/
│   └── ingest_site.py               ← Python: workspace → public/sites/<slug>/
└── src/
    ├── styles/global.css
    ├── lib/
    │   ├── data.ts                  ← build-time data loaders
    │   ├── lichens.ts               ← canonical genus palette
    │   ├── markdown.ts              ← inline markdown → HTML for DETAILS bodies
    │   └── types.ts                 ← TypeScript types mirroring JSON shapes
    ├── components/
    │   ├── Header.astro
    │   ├── Footer.astro
    │   └── StratigraphyExplorer.tsx ← the React island doing the heavy lifting
    ├── layouts/
    │   └── BaseLayout.astro
    └── pages/
        ├── index.astro              /  (site picker)
        ├── about.astro              /about
        ├── lichens.astro            /lichens (cross-site genus reference)
        └── sites/
            └── [slug]/
                ├── index.astro      /sites/<slug>/  (the explorer)
                └── stone/
                    └── [stone].astro /sites/<slug>/stone/<folder>/  (deep-link)
```

## Develop

```bash
# Install dependencies (one time)
npm install --legacy-peer-deps

# Ingest the Templer site (or a new one)
npm run ingest:templer
# or:  python3 scripts/ingest_site.py --site templer-cemetery

# Local dev server with hot reload
npm run dev
# → http://localhost:4321/lichen-atlas/

# Production build
npm run build
# → dist/ (static, deploy anywhere)

# Preview the production build locally
npm run preview
```

## Adding a new cemetery site

The easiest way is the **local editor** (see below) — but you can also do it by hand:

1. Run the upstream documentation pipeline on the new cemetery's photos to produce a `_organized/` folder (with per-stone subfolders containing DETAILS.md + _meta.json + photos)
2. Run the ingest:
   ```bash
   python3 scripts/ingest_site.py --site my-new-site --source /path/to/_organized
   ```
3. Register the cemetery's name, location, founded year, history paragraph, and tagline — either in `scripts/sites_registry.json` (data-driven, preferred) or by extending `SITE_PROFILES` in `scripts/ingest_site.py`
4. Rebuild: `npm run build`

The site picker on `/` will automatically include the new site.

## ✏️ Adding graves with the local Editor (private, not deployed)

The public atlas is a **static** site, so the published URL is inherently
**view-only** — there is no backend in production that could accept edits. To add
content there is a small **local editor** that runs only on your machine and is
never deployed:

```bash
npm run admin
# → opens the editor at:
#   http://localhost:4455/
```

Open that URL in your browser. The editor lets you:

- **Add a grave** to any existing site (inscriptions, biography, lichen analysis,
  dates, and full-stone + close-up photo uploads), and
- **Create a new cemetery on the fly** — if the grave belongs to a site that isn't
  in the atlas yet, switch to *➕ New site* and fill in its name, location, history,
  etc. (English, with optional Hebrew fields).

On **Save**, the editor:

1. writes the canonical source files (`_organized/<Stone>/_meta.json` + `DETAILS.md` + the photos),
2. registers any new site in [`scripts/sites_registry.json`](scripts/sites_registry.json) (so `ingest_site.py` finds it without code changes),
3. runs `ingest_site.py` to regenerate `public/sites/<slug>/`, and
4. writes optional Hebrew overlays (`site.he.json` / `stones.he.json`).

Then review on the dev server (`npm run dev`) and **commit + push** to publish. The
GitHub Pages site updates — and stays view-only, because the editor never ships
with it.

> **Security model:** the editor binds to `127.0.0.1` only, so it is reachable
> from your own machine and is never deployed with the static site. A brand-new
> site may need a dev-server restart before its page appears (Astro caches
> `getStaticPaths` in dev).

## Visual language

| Element | Specification |
|---|---|
| Background | Deep slate `#0F1115` with a subtle SVG noise grain |
| Headings / inscriptions | *Newsreader* (editorial serif) |
| UI / chrome | *Inter Tight* |
| Hebrew text | *Frank Ruhl Libre* (RTL) |
| German Fraktur | *UnifrakturMaguntia* (used sparingly for original inscriptions) |
| Accent | Ember `#E07A2E` (canonical *Caloplaca* color) |
| Lichen genus colors | Canonical palette in `src/lib/lichens.ts` — same color used in chips, dots, strata, charts |

## Deploy to GitHub Pages

The `astro.config.mjs` is set up for `https://maayanmag.github.io/lichen-atlas/`. To deploy:

1. Confirm with the project owner before pushing
2. Create a GitHub repo `maayanmag/lichen-atlas` (private or public)
3. Add a `.github/workflows/deploy.yml` that runs `npm install --legacy-peer-deps && npm run ingest:templer && npm run build` and publishes `dist/` to `gh-pages`
4. Enable GitHub Pages → source: `gh-pages` branch

## Credits

- Field photography & research direction — **Maayan Magenheim**
- Bezalel M.Des Industrial Design (Bio-Design course)
- AI-assisted documentation pipeline — built as part of the Bio-Design lichen-tombstone research thread
- Reference: Galun & Haluwani (1977) *Lichens on tombstones in Jerusalem*, The Lichenologist 9(2)
- Reference: Eisler & Gräf (2023) *Der historische Friedhof der Tempelgesellschaft in Jerusalem*

## License

Code: MIT. Photographs and biographical content: © Maayan Magenheim, all rights reserved unless otherwise noted.
