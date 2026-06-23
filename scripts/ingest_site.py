"""ingest_site.py — package an _organized/ folder into public/sites/<slug>/

Usage:
  python3 scripts/ingest_site.py --site templer-cemetery
  python3 scripts/ingest_site.py --site har-hamenuchot --source /path/to/_organized

For the templer site the source path is hard-coded as a default; for new sites
you must pass --source.

Outputs (under public/sites/<slug>/):
  site.json            cemetery-level metadata
  stones.json          array of all stones (normalized for UI consumption)
  photos/thumb/        400px-wide JPEGs (grid + chips)
  photos/medium/       1024px-wide JPEGs (detail-pane carousel)
  photos/large/        1920px-wide JPEGs (fullscreen viewer)

Idempotent — re-running overwrites stale outputs.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC = REPO_ROOT / "public"

# Default source paths per known site slug
DEFAULT_SOURCES = {
    "templer-cemetery": Path("/Users/mmagenheim/Documents/bezalel_projects/bio_design/linches_graves_pics/templer_cemetery/_organized"),
    "pardes-hahaim": Path("/Users/mmagenheim/Documents/bezalel_projects/bio_design/linches_graves_pics/Pardes HaHaim/_organized"),
    "cascais": Path("/Users/mmagenheim/Documents/bezalel_projects/bio_design/linches_graves_pics/Cascais Portugal/_organized"),
}

# Default site-level descriptors (extend as more cemeteries come in)
SITE_PROFILES = {
    "templer-cemetery": {
        "name": "Templerfriedhof Jerusalem",
        "subtitle": "Historical Templer Cemetery, German Colony",
        "location": "Emek Refaim 37, Jerusalem",
        "founded": 1878,
        "community": "Tempelgesellschaft (Württemberg Pietist Protestants)",
        "tagline": "A small enclosed Templer burial ground in the German Colony — the first cemetery documented in this atlas.",
        "history_md": (
            "Founded by the Tempelgesellschaft in 1878, five years after the German Colony was "
            "established (1873). The Templers — a Württemberg Pietist Protestant sect — settled "
            "in Jerusalem under Christoph Hoffmann's leadership. The community ended in Palestine "
            "by 1948 after British wartime internment and deportation. The cemetery preserves "
            "approximately 1,000 burials over three generations."
        ),
        "verify_source_en": "Cross-reference against Eisler & Gräf (2023) Der historische Friedhof der Tempelgesellschaft in Jerusalem.",
        "verify_source_he": "יש להצליב מול Eisler & Gräf (2023) Der historische Friedhof der Tempelgesellschaft in Jerusalem.",
    },
    "pardes-hahaim": {
        "name": "Pardes HaHaim",
        "subtitle": "Municipal cemetery, Kfar Saba (founded 2006)",
        "location": "Ha'Pardes Street, Kfar Saba, Sharon region",
        "founded": 2006,
        "community": "Israeli Jewish (municipal — Kfar Saba Chevra Kadisha)",
        "tagline": "A young, green municipal cemetery — the colonisation-onset counterpoint to Jerusalem's century-old stones.",
        "history_md": (
            "Pardes HaHaim (פרדס החיים — \"Orchard of Life\") opened for burial in 2006 to "
            "relieve burial pressure across the Sharon region. Operated jointly by the Kfar "
            "Saba municipality and the local Chevra Kadisha, it is built as a deliberately "
            "modern, accessible, green burial ground — wide shaded paths, irrigated native "
            "vegetation, marble and granite headstones rather than weathered limestone. For "
            "this atlas it is the experimental short-time control: a substrate that has had "
            "less than two decades to be re-written by lichen, photographed alongside the "
            "Templer site whose stones have stood for a century and a half."
        ),
        "verify_source_en": "Cross-reference against the Kfar Saba Chevra Kadisha registry and family records — no academic publication exists for this site.",
        "verify_source_he": "יש להצליב מול רישומי החברא קדישא כפר סבא ורשומות משפחה — לא קיים מקור אקדמי לאתר זה.",
    },
    "cascais": {
        "name": "Cemitério da Guia, Cascais",
        "subtitle": "Municipal cemetery on the Atlantic coast, Cascais, Portugal",
        "location": "Rua da Torre, Guia, Cascais e Estoril, Portugal",
        "community": "Portuguese Catholic (municipal — Câmara Municipal de Cascais)",
        "tagline": "The atlas's first site outside Israel — an Atlantic-coast Portuguese cemetery whose 1920s–1960s limestone tombs are being re-written by a yellow Candelariella–Aspicilia community.",
        "history_md": (
            "The Cemitério Municipal da Guia is one of the municipal cemeteries of "
            "Cascais, on the Atlantic coast west of Lisbon, beside the Farol da Guia "
            "and the Boca do Inferno. It grew with the town across the nineteenth and "
            "twentieth centuries, as Cascais turned from a fishing village into the "
            "preferred seaside resort of the Portuguese royal family and elite. The "
            "stones photographed here date from 1921 to 1960 — pale limestone (lioz) "
            "family chapels and recumbent ledger slabs, several already declared "
            "ABANDONADO (abandoned) by the municipality. For this atlas Cascais is the "
            "first oceanic-climate, non-Israeli site: a maritime Atlantic counterpoint "
            "to the hot, dry Mediterranean limestone of the Jerusalem Templer cemetery "
            "and to the young, irrigated Kfar Saba ground — and the place where a "
            "yellow Candelariella community, rather than the orange Caloplaca of "
            "Jerusalem, leads the colonisation."
        ),
        "verify_source_en": "Cross-reference against the Câmara Municipal de Cascais cemetery registry (e.g. Edital 434/2021) and Find a Grave — Cemitério da Guia. No academic publication documents this cemetery.",
        "verify_source_he": "יש להצליב מול רישומי בית הקברות של עיריית קשקאיש (Câmara Municipal de Cascais; למשל Edital 434/2021) ומול Find a Grave — Cemitério da Guia. לא קיים מקור אקדמי המתעד את בית הקברות הזה.",
    },
}

# Data-driven registry (scripts/sites_registry.json). Lets the local editor
# (scripts/admin_server.py) add new cemeteries without editing this file.
SITES_REGISTRY_PATH = Path(__file__).resolve().parent / "sites_registry.json"


def _load_registry() -> None:
    """Merge site entries from sites_registry.json into the dicts above.

    Registry entries override the hard-coded defaults, so a site can be both
    bootstrapped here and later refined through the registry / editor tool.
    """
    if not SITES_REGISTRY_PATH.exists():
        return
    try:
        data = json.loads(SITES_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"!! could not read sites registry {SITES_REGISTRY_PATH}: {exc}")
        return
    for slug, entry in (data.get("sites") or {}).items():
        if not isinstance(entry, dict):
            continue
        src = entry.get("source")
        if src:
            DEFAULT_SOURCES[slug] = Path(src).expanduser()
        profile = entry.get("profile")
        if isinstance(profile, dict) and profile:
            SITE_PROFILES[slug] = profile


_load_registry()

IMAGE_SIZES = {
    "thumb": 400,
    "medium": 1024,
    "large": 1920,
}
JPEG_QUALITY = 84


# ----------------- utilities -----------------

def resize_to(src: Path, dst: Path, max_w: int) -> None:
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        img = img.convert("RGB")
        img = ImageOps.exif_transpose(img)
        w, h = img.size
        if w > max_w:
            new_h = int(h * max_w / w)
            img = img.resize((max_w, new_h), Image.LANCZOS)
        img.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)


def parse_year(s) -> int | None:
    if not s:
        return None
    if isinstance(s, int):
        return s
    if isinstance(s, str) and len(s) >= 4 and s[:4].isdigit():
        return int(s[:4])
    return None


COVERAGE_NUM_RE = re.compile(r"(\d{1,3})\s*(?:-|–|to)?\s*(\d{1,3})?\s*%?")


def normalize_coverage(raw) -> tuple[int | None, int | None, str]:
    """Return (low_pct, high_pct, human_label).

    Handles inputs like:
      "40-60"
      "moderate (~40-50%)"
      "heavy (~60-80%)"
      "<5"
      "70"
      None / int / float
    """
    if raw is None or raw == "":
        return (None, None, "—")
    if isinstance(raw, (int, float)):
        v = int(raw)
        return (v, v, f"{v}%")
    s = str(raw).strip()
    label = s
    s_lo = s.lower()
    if "<" in s:
        m = re.search(r"<\s*(\d+)", s)
        if m:
            v = int(m.group(1))
            return (0, v, label)
    m = COVERAGE_NUM_RE.search(s)
    if m:
        low = int(m.group(1))
        high = int(m.group(2)) if m.group(2) else low
        if high < low:
            low, high = high, low
        return (low, high, label)
    # qualitative buckets
    if "trace" in s_lo: return (1, 5, label)
    if "sparse" in s_lo or "low" in s_lo: return (5, 20, label)
    if "moderate" in s_lo: return (30, 50, label)
    if "heavy" in s_lo or "dense" in s_lo: return (60, 80, label)
    if "dominant" in s_lo: return (75, 95, label)
    return (None, None, label)


def normalize_genera(raw) -> tuple[list[str], list[str]]:
    """Returns (genera, species). Species are always 'Genus species' form."""
    if not raw:
        return ([], [])
    genera = set()
    species = set()
    for g in raw:
        if not isinstance(g, str):
            continue
        g = g.strip().rstrip(".").rstrip(",")
        parts = g.split()
        if len(parts) >= 2 and parts[0][0].isupper():
            genera.add(parts[0])
            species.add(g)
        else:
            genera.add(parts[0])
    return (sorted(genera), sorted(species))


def first_person_field(meta: dict, *keys: str):
    """Some _meta.json files put the bio data inside `interred_persons[0]`."""
    for k in keys:
        v = meta.get(k)
        if v not in (None, "", []):
            return v
    persons = meta.get("interred_persons") or []
    if persons and isinstance(persons[0], dict):
        for k in keys:
            v = persons[0].get(k)
            if v not in (None, "", []):
                return v
    return None


# ----------------- main pipeline -----------------

def ingest(slug: str, source: Path) -> None:
    if not source.exists():
        sys.exit(f"!! source folder does not exist: {source}")

    profile = SITE_PROFILES.get(slug, {"name": slug.replace("-", " ").title()})
    site_root = PUBLIC / "sites" / slug
    site_root.mkdir(parents=True, exist_ok=True)
    photos_root = site_root / "photos"

    stones: list[dict] = []
    coverage_low_vals = []
    coverage_high_vals = []
    death_years: list[int] = []
    birth_years: list[int] = []
    confidence_counts = Counter()
    genus_counter = Counter()
    n_photos_total = 0

    # Walk the cluster folders
    for d in sorted(source.iterdir()):
        if not d.is_dir():
            continue
        if d.name.startswith(("_", "00_")):
            continue
        meta_path = d / "_meta.json"
        details_path = d / "DETAILS.md"
        if not meta_path.exists():
            print(f"!! skip {d.name}: no _meta.json")
            continue

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        details_md = details_path.read_text(encoding="utf-8") if details_path.exists() else ""

        # ----- normalize per-stone fields -----
        is_unknown = d.name.startswith("Unknown_")

        surname = (meta.get("surname")
                   or first_person_field(meta, "surname")
                   or "")
        given = first_person_field(meta, "given_names", "given_name", "Given") or ""
        maiden = first_person_field(meta, "maiden_name") or ""
        born = first_person_field(meta, "born") or ""
        died = first_person_field(meta, "died") or ""
        born_y = parse_year(born)
        died_y = parse_year(died) or meta.get("death_year_used_for_age")
        if born_y: birth_years.append(born_y)
        if died_y: death_years.append(died_y)

        age_at_death = first_person_field(meta, "age_at_death")
        stone_age_2026 = meta.get("stone_age_years_2026")

        bio_conf = (meta.get("bio_confidence")
                    or meta.get("biographical_confidence")
                    or ("unknown" if is_unknown else "low"))
        confidence_counts[bio_conf] += 1

        stone_type = meta.get("stone_type") or meta.get("stone_material_guess") or ""
        inscription_lang = meta.get("inscription_language") or ""

        genera, species_set = normalize_genera(meta.get("lichen_genera_observed"))
        for g in genera:
            genus_counter[g] += 1
        species_set = set(species_set) | set(meta.get("lichen_species_guesses") or [])
        species = sorted(species_set)

        coverage_raw = (meta.get("lichen_coverage_estimate")
                        or meta.get("lichen_coverage_estimate_pct")
                        or "")
        cov_lo, cov_hi, cov_label = normalize_coverage(coverage_raw)
        if cov_lo is not None: coverage_low_vals.append(cov_lo)
        if cov_hi is not None: coverage_high_vals.append(cov_hi)

        # Photos: gather full + closeups from the folder itself
        # Some _meta files have 'full_stone_photos' / 'lichen_closeup_photos' or 'photos' dict,
        # and some agents serialized single-item lists as plain strings — normalize.
        def _ensure_list(v):
            if v is None:
                return []
            if isinstance(v, str):
                return [v]
            if isinstance(v, list):
                return v
            return []

        photos_field = meta.get("photos") if isinstance(meta.get("photos"), dict) else None
        if photos_field:
            full_list = _ensure_list(
                photos_field.get("full_stone")
                or photos_field.get("full")
            )
            closeup_list = _ensure_list(
                photos_field.get("closeups")
                or photos_field.get("close_ups")
                or photos_field.get("close-ups")
            )
        else:
            full_list = _ensure_list(meta.get("full_stone_photos"))
            closeup_list = _ensure_list(meta.get("lichen_closeup_photos"))

        # Fallback: list every JPEG in the folder
        if not full_list and not closeup_list:
            jpegs = sorted([p.name for p in d.glob("*.jpeg")])
            if jpegs:
                full_list = jpegs[:1]
                closeup_list = jpegs[1:]

        all_photos = list(full_list) + list(closeup_list)
        n_photos_total += len(all_photos)

        # Generate the 3 image sizes for every photo
        for fname in all_photos:
            src_img = d / fname
            if not src_img.exists():
                # fallback: original location
                alt = source.parent / fname
                if alt.exists():
                    src_img = alt
                else:
                    print(f"!! missing image: {d.name}/{fname}")
                    continue
            for size_name, max_w in IMAGE_SIZES.items():
                dst = photos_root / size_name / fname
                resize_to(src_img, dst, max_w)

        stone = {
            "folder": d.name,
            "is_unknown": is_unknown,
            "surname": surname,
            "given_names": given,
            "maiden_name": maiden,
            "born": born,
            "born_year": born_y,
            "died": died,
            "died_year": died_y,
            "age_at_death": age_at_death,
            "stone_age_2026": stone_age_2026,
            "bio_confidence": bio_conf,
            "stone_type": stone_type,
            "inscription_language": inscription_lang,
            "lichen_genera": genera,
            "lichen_species": species,
            "lichen_dominant": meta.get("lichen_dominant"),
            "lichen_coverage_low": cov_lo,
            "lichen_coverage_high": cov_hi,
            "lichen_coverage_label": cov_label,
            "photos": {
                "full": full_list,
                "closeups": closeup_list,
            },
            "photo_count": len(all_photos),
            "biblical_reference": meta.get("biblical_reference"),
            "details_md": details_md,
            "notable": meta.get("notable_observations") or meta.get("notes"),
            "tempelgesellschaft_registry_id": meta.get("tempelgesellschaft_registry_id"),
        }
        stones.append(stone)

    # --- site-level summary ---
    stone_ages = [s["stone_age_2026"] for s in stones if s["stone_age_2026"] is not None]
    site = {
        "slug": slug,
        **profile,
        "stone_count": len(stones),
        "photo_count": n_photos_total,
        "identified_count": sum(1 for s in stones if not s["is_unknown"]),
        "unknown_count": sum(1 for s in stones if s["is_unknown"]),
        "date_range": (f"{min(death_years)}–{max(death_years)}" if death_years else "—"),
        "death_year_min": (min(death_years) if death_years else None),
        "death_year_max": (max(death_years) if death_years else None),
        "stone_age": {
            "oldest": (max(stone_ages) if stone_ages else None),
            "newest": (min(stone_ages) if stone_ages else None),
            "median": (int(statistics.median(stone_ages)) if stone_ages else None),
        },
        "lichen_genera": [
            {"genus": g, "stone_count": n}
            for g, n in genus_counter.most_common()
        ],
        "confidence_breakdown": dict(confidence_counts),
        "ingested_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source_workspace": str(source),
    }

    (site_root / "site.json").write_text(json.dumps(site, ensure_ascii=False, indent=2), encoding="utf-8")
    (site_root / "stones.json").write_text(json.dumps(stones, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OK  site:  {slug}")
    print(f"  stones={len(stones)}  photos={n_photos_total}  identified={site['identified_count']}")
    print(f"  date_range={site['date_range']}  oldest={site['stone_age']['oldest']}y  newest={site['stone_age']['newest']}y")
    print(f"  -> {site_root}")
    n_imgs = sum(1 for _ in photos_root.rglob("*.jpeg"))
    print(f"  images materialized: {n_imgs} (across thumb/medium/large)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, help="Site slug (e.g. templer-cemetery)")
    ap.add_argument("--source", help="Path to the _organized/ folder for this site")
    args = ap.parse_args()

    source = Path(args.source) if args.source else DEFAULT_SOURCES.get(args.site)
    if source is None:
        sys.exit(f"!! no default source for site '{args.site}'. Pass --source.")

    ingest(args.site, source)


if __name__ == "__main__":
    main()
