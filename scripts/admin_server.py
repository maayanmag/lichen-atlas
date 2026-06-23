"""admin_server.py — the Lichen Atlas local EDITOR.

A private, localhost-only web tool for **adding a new grave** to the atlas — and,
if the grave belongs to a cemetery that isn't in the atlas yet, **adding the new
site** at the same time.

Why a separate local server?
----------------------------
The public atlas is a *static* site (Astro → GitHub Pages). A static site has no
backend, so the deployed/public URL is inherently **view-only** — nothing there
can write data. Editing therefore happens here, locally, behind a private,
non-guessable token URL that is never deployed:

    http://127.0.0.1:4455/<token>/

The editor writes into the project's source-of-truth (`_organized/` folders +
`sites_registry.json`) and then runs the existing `ingest_site.py` to regenerate
`public/sites/<slug>/`. Review the result on the dev server, commit, push — and
the public site updates, still view-only.

Run it:
    npm run admin
    # or:  python3 scripts/admin_server.py [--port 4455]

The full private URL (with the token) is printed to the console on startup.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import subprocess
import sys
import unicodedata
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageOps

# ----------------------------------------------------------------------------
# Paths & constants
# ----------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
PUBLIC = REPO_ROOT / "public"
SITES_PUBLIC = PUBLIC / "sites"
INGEST = SCRIPTS_DIR / "ingest_site.py"
REGISTRY_PATH = SCRIPTS_DIR / "sites_registry.json"
STAGING = SCRIPTS_DIR / ".admin_staging"

# Default base folder where each site's _organized/ source tree lives.
PICS_BASE = Path(
    "~/Documents/bezalel_projects/bio_design/linches_graves_pics"
).expanduser()

# Where the dev server serves the atlas (for clickable review links).
DEV_ORIGIN = "http://localhost:4321/lichen-atlas"

# Neutral verify-source defaults so a new site never inherits another site's
# citation. (The explorer falls back to the Templer citation when a site has no
# verify_source_*, so we always write something sensible here.)
DEFAULT_VERIFY_EN = (
    "No dedicated printed source — cross-reference against the cemetery / "
    "municipal registry and family records."
)
DEFAULT_VERIFY_HE = (
    "אין מקור מודפס ייעודי — יש להצליב מול רישומי בית הקברות / העירייה "
    "ומול רשומות משפחה."
)

# Make ingest_site importable so we can reuse its resolved site tables.
sys.path.insert(0, str(SCRIPTS_DIR))
import ingest_site  # noqa: E402

ALLOWED_IMAGE_FORMATS = {"JPEG", "JPG", "MPO", "PNG", "WEBP", "TIFF", "BMP", "GIF"}


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------
def _ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def slugify_site(name: str) -> str:
    s = _ascii_fold(name or "")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "site"


def sanitize_folder(name: str) -> str:
    """URL-safe ASCII folder name for a stone (becomes the page slug)."""
    s = _ascii_fold(name or "")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s or "Stone"


def safe_dirname(name: str) -> str:
    """Human-readable, path-safe folder name for a new site's source tree."""
    s = (name or "").replace("/", " ").replace("\\", " ").strip()
    s = re.sub(r"[\x00-\x1f]", "", s)
    return s or "New Site"


def _clean(v):
    """Empty string -> None; trim strings."""
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def _parse_int(v):
    try:
        if v in (None, "", []):
            return None
        return int(str(v).strip()[:4]) if re.match(r"^\s*\d", str(v)) else None
    except (ValueError, TypeError):
        return None


def _as_list(v):
    if v in (None, ""):
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    # comma / newline separated string
    return [p.strip() for p in re.split(r"[,\n;]+", str(v)) if p.strip()]


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"sites": {}}
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    data.setdefault("sites", {})
    return data


def save_registry(data: dict) -> None:
    REGISTRY_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def known_sites() -> list[dict]:
    """All sites the editor can target: hard-coded + registry + already-built."""
    sources = dict(ingest_site.DEFAULT_SOURCES)
    profiles = dict(ingest_site.SITE_PROFILES)
    reg = load_registry()
    for slug, entry in reg.get("sites", {}).items():
        if isinstance(entry, dict):
            if entry.get("source"):
                sources[slug] = Path(entry["source"]).expanduser()
            if isinstance(entry.get("profile"), dict):
                profiles[slug] = entry["profile"]
    # Include any built sites even if they lack a source mapping.
    if SITES_PUBLIC.exists():
        for d in SITES_PUBLIC.iterdir():
            if (d / "site.json").exists():
                sources.setdefault(d.name, None)
    out = []
    for slug in sorted(sources):
        name = (profiles.get(slug) or {}).get("name") or slug.replace("-", " ").title()
        out.append(
            {
                "slug": slug,
                "name": name,
                "has_source": bool(sources.get(slug)),
            }
        )
    return out


def resolve_source(slug: str) -> Path | None:
    sources = dict(ingest_site.DEFAULT_SOURCES)
    reg = load_registry()
    for sl, entry in reg.get("sites", {}).items():
        if isinstance(entry, dict) and entry.get("source"):
            sources[sl] = Path(entry["source"]).expanduser()
    src = sources.get(slug)
    return Path(src).expanduser() if src else None


# ----------------------------------------------------------------------------
# Source-file builders (_meta.json + DETAILS.md + HE overlay)
# ----------------------------------------------------------------------------
def _person_dict(p: dict) -> dict:
    return {
        "given_names": _clean(p.get("given_names")),
        "maiden_name": _clean(p.get("maiden_name")),
        "born": _clean(p.get("born")),
        "died": _clean(p.get("died")),
        "age_at_death": _clean(p.get("age_at_death")),
        "born_place": _clean(p.get("born_place")),
        "died_place": _clean(p.get("died_place")),
        "occupation": _clean(p.get("occupation")),
    }


def build_meta(stone: dict, full_list: list[str], closeup_list: list[str]) -> dict:
    persons = [_person_dict(p) for p in (stone.get("persons") or []) if any(p.values())]
    surname = _clean(stone.get("surname")) or ""
    if not persons:
        persons = [
            _person_dict(
                {
                    "given_names": stone.get("given_names"),
                    "maiden_name": stone.get("maiden_name"),
                    "born": stone.get("born"),
                    "died": stone.get("died"),
                }
            )
        ]
    primary_given = persons[0].get("given_names") or _clean(stone.get("given_names")) or ""
    primary = (f"{primary_given} {surname}").strip() or None

    died_year = None
    for p in persons:
        died_year = _parse_int(p.get("died"))
        if died_year:
            break
    death_year_used = _parse_int(stone.get("death_year_used_for_age")) or died_year
    stone_age = _parse_int(stone.get("stone_age_years_2026"))
    if stone_age is None and death_year_used:
        stone_age = 2026 - death_year_used

    return {
        "folder_name": stone["folder"],
        "surname": surname,
        "interred_persons": persons,
        "primary_person": primary,
        "folder_year": _parse_int(stone.get("folder_year")) or died_year,
        "community": _clean(stone.get("community")),
        "stone_type": _clean(stone.get("stone_type")),
        "inscription_language": _clean(stone.get("inscription_language")),
        "photo_count": len(full_list) + len(closeup_list),
        "full_stone_photos": full_list,
        "lichen_closeup_photos": closeup_list,
        "lichen_genera_observed": _as_list(stone.get("lichen_genera_observed")),
        "lichen_species_guesses": _as_list(stone.get("lichen_species_guesses")),
        "lichen_dominant": _clean(stone.get("lichen_dominant")),
        "lichen_coverage_estimate_pct": _clean(stone.get("lichen_coverage_estimate_pct")),
        "lichen_note": _clean(stone.get("lichen_note")),
        "biographical_confidence": _clean(stone.get("biographical_confidence")) or "low",
        "notes": _clean(stone.get("notes")),
        "stone_age_years_2026": stone_age,
        "death_year_used_for_age": death_year_used,
        "added_via": "admin_server",
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def _fence(text: str) -> str:
    return "```\n" + (text or "").strip("\n") + "\n```"


def build_details_md(stone: dict, site_name: str, lang: str = "en") -> str:
    """Render a DETAILS.md that satisfies StratigraphyExplorer's heading contract.

    Headings stay in English in both languages (the explorer parses them); only
    the prose (biography, lichen notes) is swapped for the Hebrew variant when
    lang == 'he' and a Hebrew value is present.
    """
    folder = stone["folder"]
    surname = _clean(stone.get("surname")) or ""
    persons = [p for p in (stone.get("persons") or []) if any(p.values())]
    orig_lang = _clean(stone.get("inscription_original_lang")) or _clean(
        stone.get("inscription_language")
    ) or "Original"
    insc_orig = _clean(stone.get("inscription_original"))
    insc_en = _clean(stone.get("inscription_english"))
    insc_he = _clean(stone.get("inscription_hebrew"))

    bio_en = _clean(stone.get("biographical_context"))
    bio_he = _clean(stone.get("biographical_context_he"))
    bio = (bio_he or bio_en) if lang == "he" else bio_en

    lichen_en = _clean(stone.get("lichen_note"))
    lichen_he = _clean(stone.get("lichen_note_he"))
    lichen_note = (lichen_he or lichen_en) if lang == "he" else lichen_en

    confidence = _clean(stone.get("biographical_confidence")) or "low"
    n_photos = len(stone.get("_full_list", [])) + len(stone.get("_closeup_list", []))

    L: list[str] = []
    L.append(f"# {folder}")
    L.append("")
    L.append(f"> 📷 **Photos in this folder**: {n_photos}")
    L.append(f"> 📍 **Site**: {site_name}")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 🪦 Gravestone Identification")
    L.append("")

    if insc_orig:
        L.append(f"### Original Inscription ({orig_lang})")
        L.append(_fence(insc_orig))
        L.append("")
    if insc_en:
        L.append("### English Translation")
        L.append(_fence(insc_en))
        L.append("")
    if insc_he:
        L.append("### Hebrew Translation")
        L.append(_fence(insc_he))
        L.append("")

    # Identification table (source-readability only; not rendered by the UI)
    L.append("### Identification")
    L.append("")
    L.append("| Field | Value |")
    L.append("|---|---|")
    if surname:
        L.append(f"| **Surname** | {surname} |")
    for i, p in enumerate(persons, 1):
        nm = " ".join(x for x in [p.get("given_names"), surname] if x).strip()
        dd = p.get("died") or "—"
        L.append(f"| **Interred ({i})** | {nm} — d. {dd} |")
    if stone.get("stone_type"):
        L.append(f"| **Structure** | {stone['stone_type']} |")
    if stone.get("inscription_language"):
        L.append(f"| **Inscription language** | {stone['inscription_language']} |")
    L.append("")

    if bio:
        L.append("#### Biographical context")
        L.append(bio)
        L.append("")
        L.append(f"**Confidence**: `{confidence}`")
        L.append("")

    L.append("---")
    L.append("")
    L.append("## 🦠 Lichen Analysis")
    L.append("")
    substrate = _clean(stone.get("stone_type"))
    if substrate:
        L.append("### Stone substrate")
        L.append(f"- **Material / structure**: {substrate}")
        L.append("")
    L.append("### Lichen community observed")
    if stone.get("lichen_dominant"):
        L.append(f"- **Dominant genus**: {stone['lichen_dominant']}")
    genera = _as_list(stone.get("lichen_genera_observed"))
    if genera:
        L.append(f"- **Genera observed**: {', '.join(genera)}")
    species = _as_list(stone.get("lichen_species_guesses"))
    if species:
        L.append(f"- **Species (tentative)**: {', '.join(species)}")
    if stone.get("lichen_coverage_estimate_pct"):
        L.append(f"- **Coverage estimate**: {stone['lichen_coverage_estimate_pct']}%")
    L.append("")
    if lichen_note:
        L.append(lichen_note)
        L.append("")

    L.append("---")
    L.append("")
    L.append("## 🔄 Cross-references")
    L.append(f"- Site: {site_name}")
    L.append("")
    return "\n".join(L)


def upsert_he_stone_overlay(slug: str, folder: str, details_md_he: str) -> None:
    path = SITES_PUBLIC / slug / "stones.he.json"
    arr = []
    if path.exists():
        try:
            arr = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            arr = []
    arr = [e for e in arr if e.get("folder") != folder]
    arr.append({"folder": folder, "details_md": details_md_he})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(arr, ensure_ascii=False, indent=2), encoding="utf-8")


def write_he_site_overlay(slug: str, he: dict) -> None:
    fields = {
        k: _clean(v)
        for k, v in {
            "name": he.get("name_he"),
            "subtitle": he.get("subtitle_he"),
            "location": he.get("location_he"),
            "community": he.get("community_he"),
            "tagline": he.get("tagline_he"),
            "history_md": he.get("history_he"),
        }.items()
        if _clean(v)
    }
    if not fields:
        return
    path = SITES_PUBLIC / slug / "site.he.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fields, ensure_ascii=False, indent=2), encoding="utf-8")


# ----------------------------------------------------------------------------
# Core: handle a submission
# ----------------------------------------------------------------------------
class SubmitError(Exception):
    pass


def stage_path(staged_name: str) -> Path:
    # only allow our generated names
    if not re.fullmatch(r"[0-9a-f]{32}\.jpeg", staged_name or ""):
        raise SubmitError(f"bad staged file reference: {staged_name!r}")
    p = STAGING / staged_name
    if not p.exists():
        raise SubmitError(f"staged file missing (re-upload): {staged_name}")
    return p


def handle_submit(payload: dict) -> dict:
    stone = payload.get("stone") or {}
    folder = sanitize_folder(stone.get("folder") or stone.get("surname") or "Stone")
    stone["folder"] = folder

    # ---- resolve / create the site ----
    site_mode = payload.get("site_mode") or "existing"
    new_site = payload.get("new_site") or {}

    if site_mode == "new":
        name = _clean(new_site.get("name"))
        if not name:
            raise SubmitError("new site needs a name")
        slug = slugify_site(new_site.get("slug") or name)
        dirname = safe_dirname(new_site.get("source_dirname") or name)
        source = PICS_BASE / dirname / "_organized"
        source.mkdir(parents=True, exist_ok=True)
        profile = {
            "name": name,
            "subtitle": _clean(new_site.get("subtitle")),
            "location": _clean(new_site.get("location")),
            "founded": _parse_int(new_site.get("founded")),
            "community": _clean(new_site.get("community")),
            "tagline": _clean(new_site.get("tagline")),
            "history_md": _clean(new_site.get("history_md")),
        }
        profile = {k: v for k, v in profile.items() if v is not None}
        # Always populate both verify sources so the HE/EN pages never fall back
        # to another cemetery's citation. Mirror whichever one was supplied.
        v_en = _clean(new_site.get("verify_source_en"))
        v_he = _clean(new_site.get("verify_source_he"))
        if not v_en and not v_he:
            v_en, v_he = DEFAULT_VERIFY_EN, DEFAULT_VERIFY_HE
        else:
            v_en = v_en or v_he
            v_he = v_he or v_en
        profile["verify_source_en"] = v_en
        profile["verify_source_he"] = v_he
        reg = load_registry()
        reg["sites"][slug] = {"source": str(source), "profile": profile}
        save_registry(reg)
        site_name = name
    else:
        slug = _clean(payload.get("site_slug"))
        if not slug:
            raise SubmitError("pick an existing site or create a new one")
        source = resolve_source(slug)
        if not source:
            raise SubmitError(f"no source folder known for site '{slug}'")
        source.mkdir(parents=True, exist_ok=True)
        site_name = next(
            (s["name"] for s in known_sites() if s["slug"] == slug), slug
        )

    # ---- move staged photos into the stone folder ----
    stone_dir = source / folder
    if stone_dir.exists() and any(stone_dir.iterdir()):
        raise SubmitError(
            f"a stone folder named '{folder}' already exists at this site — "
            "choose a different folder name"
        )
    stone_dir.mkdir(parents=True, exist_ok=True)

    base = sanitize_folder(folder).lower()
    photos = stone.get("photos") or {}
    full_list, closeup_list = [], []
    for idx, staged in enumerate(photos.get("full") or [], 1):
        fname = f"{base}_full{idx}.jpeg"
        shutil.move(str(stage_path(staged)), str(stone_dir / fname))
        full_list.append(fname)
    for idx, staged in enumerate(photos.get("closeups") or [], 1):
        fname = f"{base}_lichen{idx}.jpeg"
        shutil.move(str(stage_path(staged)), str(stone_dir / fname))
        closeup_list.append(fname)

    if not full_list and not closeup_list:
        # roll back the empty folder so we don't leave junk
        shutil.rmtree(stone_dir, ignore_errors=True)
        raise SubmitError("add at least one photo")

    # ---- write _meta.json + DETAILS.md ----
    stone["_full_list"] = full_list
    stone["_closeup_list"] = closeup_list
    meta = build_meta(stone, full_list, closeup_list)
    (stone_dir / "_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (stone_dir / "DETAILS.md").write_text(
        build_details_md(stone, site_name, "en"), encoding="utf-8"
    )

    # ---- run the existing ingest pipeline ----
    proc = subprocess.run(
        [sys.executable, str(INGEST), "--site", slug, "--source", str(source)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SubmitError(f"ingest failed:\n{proc.stdout}\n{proc.stderr}")

    # ---- Hebrew overlays (optional) ----
    has_he_stone = any(
        _clean(stone.get(k))
        for k in ("biographical_context_he", "lichen_note_he", "inscription_hebrew")
    )
    if has_he_stone:
        upsert_he_stone_overlay(
            slug, folder, build_details_md(stone, site_name, "he")
        )
    if site_mode == "new":
        write_he_site_overlay(slug, new_site)

    return {
        "ok": True,
        "slug": slug,
        "folder": folder,
        "site_name": site_name,
        "site_created": site_mode == "new",
        "photos": {"full": full_list, "closeups": closeup_list},
        "ingest_output": proc.stdout.strip(),
        "links": {
            "en_site": f"{DEV_ORIGIN}/sites/{slug}/",
            "he_site": f"{DEV_ORIGIN}/he/sites/{slug}/",
            "en_stone": f"{DEV_ORIGIN}/sites/{slug}/stone/{folder}/",
        },
    }


def handle_upload(raw: bytes, display_name: str) -> dict:
    if not raw:
        raise SubmitError("empty upload")
    try:
        im = Image.open(io.BytesIO(raw))
        fmt = (im.format or "").upper()
    except Exception:  # noqa: BLE001
        raise SubmitError("unsupported image — please use JPEG or PNG")
    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise SubmitError(f"unsupported image format: {fmt}")
    STAGING.mkdir(parents=True, exist_ok=True)
    staged_name = uuid.uuid4().hex + ".jpeg"
    dst = STAGING / staged_name
    if fmt in {"JPEG", "JPG", "MPO"}:
        dst.write_bytes(raw)  # keep original bytes (EXIF preserved for ingest)
    else:
        rgb = ImageOps.exif_transpose(im).convert("RGB")
        rgb.save(dst, "JPEG", quality=92, optimize=True)
    return {"staged": staged_name, "name": display_name}


# ----------------------------------------------------------------------------
# HTTP server
# ----------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "LichenAtlasEditor/1.0"

    # ---- helpers ----
    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _route(self):
        """Map any request path to a route. API endpoints are matched by suffix
        so the page works whether it's served from `/` or from a legacy
        `/<anything>/` path (the JS calls relative `./api/...`)."""
        path = urlparse(self.path).path
        if path.endswith("/api/sites"):
            return "sites"
        if path.endswith("/api/upload"):
            return "upload"
        if path.endswith("/api/submit"):
            return "submit"
        return "index"

    def log_message(self, fmt, *args):  # quieter logging
        sys.stderr.write("  [editor] " + (fmt % args) + "\n")

    # ---- routes ----
    def do_GET(self):
        route = self._route()
        if route == "sites":
            self._json({"sites": known_sites()})
            return
        # everything else (root, etc.) serves the editor page
        self._html(INDEX_HTML)

    def do_POST(self):
        route = self._route()
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length else b""

        try:
            if route == "upload":
                qs = parse_qs(urlparse(self.path).query)
                name = (qs.get("name") or ["photo"])[0]
                self._json(handle_upload(raw, name))
                return
            if route == "submit":
                payload = json.loads(raw.decode("utf-8"))
                self._json(handle_submit(payload))
                return
            self._json({"ok": False, "error": "unknown endpoint"}, 404)
        except SubmitError as e:
            self._json({"ok": False, "error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            import traceback

            traceback.print_exc()
            self._json({"ok": False, "error": f"server error: {e}"}, 500)


# ----------------------------------------------------------------------------
# Front-end (single page, vanilla JS — minimal/clean dark theme)
# ----------------------------------------------------------------------------
INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lichen Atlas — Editor</title>
<style>
  :root{ --bg:#0F1115; --panel:#171a21; --line:#262b35; --ink:#e6e7ea;
         --mut:#9aa0aa; --accent:#E07A2E; --ok:#4caf7d; --bad:#e0564e; }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font-family:"Inter Tight",ui-sans-serif,system-ui,Arial;line-height:1.5}
  header{padding:22px 28px;border-bottom:1px solid var(--line);
         display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
  header h1{font-size:20px;margin:0;font-weight:600}
  header .pill{font-size:12px;color:var(--accent);border:1px solid var(--accent);
       border-radius:999px;padding:2px 10px}
  header .mut{color:var(--mut);font-size:13px}
  main{max-width:860px;margin:0 auto;padding:26px 22px 80px}
  fieldset{border:1px solid var(--line);border-radius:12px;margin:0 0 22px;
           padding:18px 20px;background:var(--panel)}
  legend{padding:0 8px;color:var(--accent);font-size:13px;letter-spacing:.04em;
         text-transform:uppercase}
  label{display:block;font-size:13px;color:var(--mut);margin:12px 0 4px}
  input,select,textarea{width:100%;background:#0e1014;border:1px solid var(--line);
       color:var(--ink);border-radius:8px;padding:9px 11px;font-size:14px;
       font-family:inherit}
  textarea{min-height:76px;resize:vertical}
  input:focus,select:focus,textarea:focus{outline:none;border-color:var(--accent)}
  .row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  .row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
  .hint{font-size:12px;color:#6b7280;margin-top:4px}
  .person{border:1px dashed var(--line);border-radius:10px;padding:12px 14px;margin-top:12px}
  button{cursor:pointer;font-family:inherit}
  .btn{background:var(--accent);color:#1a1206;border:none;border-radius:9px;
       padding:11px 20px;font-size:15px;font-weight:600}
  .btn:disabled{opacity:.5;cursor:default}
  .btn-ghost{background:transparent;color:var(--mut);border:1px solid var(--line);
       border-radius:8px;padding:7px 12px;font-size:13px}
  .seg{display:inline-flex;border:1px solid var(--line);border-radius:9px;overflow:hidden}
  .seg button{background:transparent;color:var(--mut);border:none;padding:8px 16px;font-size:14px}
  .seg button.on{background:var(--accent);color:#1a1206;font-weight:600}
  .he{direction:rtl;text-align:right;font-family:"Frank Ruhl Libre",serif}
  #result{white-space:pre-wrap;border-radius:10px;padding:0}
  #result.show{padding:16px 18px;margin-top:8px}
  #result.ok{border:1px solid #2c5e43;background:#10221a;color:#bfe8cf}
  #result.err{border:1px solid #5e2c2c;background:#221010;color:#e8bfbf}
  #result a{color:var(--accent)}
  .filelist{font-size:12px;color:var(--mut);margin-top:6px}
  details summary{cursor:pointer;color:var(--mut);font-size:13px;margin-top:6px}
  .note{font-size:12.5px;color:var(--mut);border-left:2px solid var(--accent);
        padding-left:12px;margin:0 0 18px}
</style>
</head>
<body>
<header>
  <h1>🪦 Lichen Atlas — Editor</h1>
  <span class="pill">runs on your machine</span>
  <span class="mut">writes source files &amp; runs the ingest · the public site stays view-only</span>
</header>
<main>
  <p class="note">Add a grave to an existing cemetery, or create a brand-new
  cemetery on the fly. On save, this writes the <code>_organized/</code> source
  files and regenerates <code>public/sites/&lt;slug&gt;/</code>. Review it on the
  dev server, then commit &amp; push to publish.</p>

  <!-- SITE -->
  <fieldset>
    <legend>1 · Cemetery / site</legend>
    <div class="seg" id="siteseg">
      <button type="button" data-mode="existing" class="on">Existing site</button>
      <button type="button" data-mode="new">➕ New site</button>
    </div>

    <div id="existingBox" style="margin-top:14px">
      <label>Choose a site</label>
      <select id="site_slug"></select>
    </div>

    <div id="newBox" style="display:none;margin-top:8px">
      <div class="row">
        <div><label>Site name (English)</label><input id="ns_name" placeholder="e.g. Highgate Cemetery"></div>
        <div><label>Slug <span class="hint">(URL id; auto if blank)</span></label><input id="ns_slug" placeholder="highgate"></div>
      </div>
      <label>Subtitle</label><input id="ns_subtitle" placeholder="short one-line description">
      <div class="row">
        <div><label>Location</label><input id="ns_location" placeholder="city, country"></div>
        <div><label>Founded <span class="hint">(year, optional)</span></label><input id="ns_founded" placeholder="1839"></div>
      </div>
      <label>Community</label><input id="ns_community" placeholder="who is buried here / who runs it">
      <label>Tagline</label><textarea id="ns_tagline"></textarea>
      <label>History (markdown)</label><textarea id="ns_history"></textarea>
      <div class="row">
        <div><label>Verify source (EN)</label><input id="ns_verify_en"></div>
        <div><label>Source folder name <span class="hint">(under linches_graves_pics/)</span></label><input id="ns_dirname" placeholder="defaults to site name"></div>
      </div>
      <details>
        <summary>Hebrew site fields (optional)</summary>
        <label class="he">שם האתר</label><input class="he" id="ns_name_he">
        <label class="he">כותרת משנה</label><input class="he" id="ns_subtitle_he">
        <label class="he">מיקום</label><input class="he" id="ns_location_he">
        <label class="he">קהילה</label><input class="he" id="ns_community_he">
        <label class="he">תקציר (tagline)</label><textarea class="he" id="ns_tagline_he"></textarea>
        <label class="he">היסטוריה</label><textarea class="he" id="ns_history_he"></textarea>
        <label class="he">מקור לאימות (verify)</label><input class="he" id="ns_verify_he">
      </details>
    </div>
  </fieldset>

  <!-- STONE -->
  <fieldset>
    <legend>2 · Grave / stone</legend>
    <div class="row3">
      <div><label>Surname</label><input id="surname" placeholder="de Carvalho"></div>
      <div><label>Folder / slug <span class="hint">(auto if blank)</span></label><input id="folder" placeholder="Carvalho_Family_Chapel_1921"></div>
      <div><label>Year <span class="hint">(for ordering)</span></label><input id="folder_year" placeholder="1921"></div>
    </div>
    <div class="row">
      <div><label>Stone type / structure</label><input id="stone_type" placeholder="limestone headstone / chapel-tomb…"></div>
      <div><label>Inscription language</label><input id="inscription_language" placeholder="Portuguese"></div>
    </div>
    <div class="row3">
      <div><label>Confidence</label>
        <select id="biographical_confidence">
          <option>low</option><option selected>medium</option><option>high</option><option>unknown</option>
        </select></div>
      <div><label>Stone age in 2026 <span class="hint">(auto from death year)</span></label><input id="stone_age_years_2026" placeholder="105"></div>
      <div><label>Death year used for age</label><input id="death_year_used_for_age" placeholder="1921"></div>
    </div>

    <div id="persons"></div>
    <button type="button" class="btn-ghost" id="addPerson" style="margin-top:12px">+ add interred person</button>
  </fieldset>

  <!-- INSCRIPTIONS -->
  <fieldset>
    <legend>3 · Inscriptions</legend>
    <label>Original inscription language</label>
    <input id="inscription_original_lang" placeholder="Portuguese / Hebrew / German / English / Latin">
    <label>Original inscription (verbatim)</label>
    <textarea id="inscription_original"></textarea>
    <label>English translation</label>
    <textarea id="inscription_english"></textarea>
    <label class="he">תרגום / מקור עברי (אופציונלי)</label>
    <textarea class="he" id="inscription_hebrew"></textarea>
  </fieldset>

  <!-- LICHEN -->
  <fieldset>
    <legend>4 · Lichen analysis</legend>
    <div class="row">
      <div><label>Genera observed <span class="hint">(comma-separated)</span></label><input id="lichen_genera_observed" placeholder="Candelariella, Aspicilia, Verrucaria"></div>
      <div><label>Species guesses <span class="hint">(comma-separated)</span></label><input id="lichen_species_guesses" placeholder="Aspicilia calcarea, Verrucaria nigrescens"></div>
    </div>
    <div class="row">
      <div><label>Dominant genus</label><input id="lichen_dominant" placeholder="Candelariella"></div>
      <div><label>Coverage estimate %</label><input id="lichen_coverage_estimate_pct" placeholder="40-60"></div>
    </div>
    <label>Lichen note / analysis (English prose)</label>
    <textarea id="lichen_note"></textarea>
    <label class="he">ניתוח החזזיות בעברית (אופציונלי)</label>
    <textarea class="he" id="lichen_note_he"></textarea>
  </fieldset>

  <!-- BIO + NOTES -->
  <fieldset>
    <legend>5 · Biography &amp; notes</legend>
    <label>Biographical context (English)</label>
    <textarea id="biographical_context" style="min-height:120px"></textarea>
    <label class="he">הקשר ביוגרפי בעברית (אופציונלי)</label>
    <textarea class="he" id="biographical_context_he" style="min-height:120px"></textarea>
    <label>Field notes (English)</label>
    <textarea id="notes"></textarea>
  </fieldset>

  <!-- PHOTOS -->
  <fieldset>
    <legend>6 · Photos</legend>
    <label>Full-stone photo(s) <span class="hint">— the whole grave</span></label>
    <input type="file" id="full_photos" accept="image/*" multiple>
    <div class="filelist" id="full_list"></div>
    <label style="margin-top:14px">Lichen close-up photo(s)</label>
    <input type="file" id="closeup_photos" accept="image/*" multiple>
    <div class="filelist" id="closeup_list"></div>
    <p class="hint">JPEG or PNG. Photos are downscaled into thumb/medium/large by the ingest step.</p>
  </fieldset>

  <button class="btn" id="submit">Add to atlas</button>
  <div id="result"></div>
</main>

<script>
const $ = s => document.querySelector(s);
let mode = "existing";

// --- site mode toggle ---
document.querySelectorAll("#siteseg button").forEach(b=>{
  b.onclick = ()=>{
    mode = b.dataset.mode;
    document.querySelectorAll("#siteseg button").forEach(x=>x.classList.toggle("on", x===b));
    $("#existingBox").style.display = mode==="existing" ? "" : "none";
    $("#newBox").style.display = mode==="new" ? "" : "none";
  };
});

// --- load existing sites ---
fetch("./api/sites").then(r=>r.json()).then(d=>{
  const sel = $("#site_slug");
  sel.innerHTML = "";
  (d.sites||[]).forEach(s=>{
    const o = document.createElement("option");
    o.value = s.slug; o.textContent = s.name + "  (" + s.slug + ")";
    sel.appendChild(o);
  });
}).catch(()=>{});

// --- dynamic persons ---
function personRow(i){
  const div = document.createElement("div");
  div.className = "person";
  div.innerHTML = `
    <div class="row3">
      <div><label>Given names</label><input data-f="given_names"></div>
      <div><label>Born</label><input data-f="born" placeholder="1888 / 1888-04-02"></div>
      <div><label>Died</label><input data-f="died" placeholder="1948 / 1948-07-08"></div>
    </div>
    <div class="row3">
      <div><label>Age at death</label><input data-f="age_at_death"></div>
      <div><label>Maiden name</label><input data-f="maiden_name"></div>
      <div><label>Occupation</label><input data-f="occupation"></div>
    </div>`;
  return div;
}
$("#addPerson").onclick = ()=> $("#persons").appendChild(personRow());
$("#persons").appendChild(personRow()); // one by default

function collectPersons(){
  return [...document.querySelectorAll("#persons .person")].map(p=>{
    const o = {};
    p.querySelectorAll("[data-f]").forEach(i=> o[i.dataset.f]= i.value.trim());
    return o;
  }).filter(o=> Object.values(o).some(v=>v));
}

// --- file lists ---
function showFiles(input, target){
  input.onchange = ()=>{
    target.textContent = [...input.files].map(f=>f.name).join(", ") || "";
  };
}
showFiles($("#full_photos"), $("#full_list"));
showFiles($("#closeup_photos"), $("#closeup_list"));

async function uploadFiles(input){
  const out = [];
  for(const f of input.files){
    const buf = await f.arrayBuffer();
    const r = await fetch("./api/upload?name="+encodeURIComponent(f.name),
      {method:"POST", body:buf});
    const j = await r.json();
    if(!r.ok || j.error) throw new Error("upload failed for "+f.name+": "+(j.error||r.status));
    out.push(j.staged);
  }
  return out;
}

const val = id => ($("#"+id)?.value || "").trim();

$("#submit").onclick = async ()=>{
  const btn = $("#submit"); const res = $("#result");
  btn.disabled = true; res.className = "show"; res.textContent = "Uploading photos…";
  try{
    const full = await uploadFiles($("#full_photos"));
    const closeups = await uploadFiles($("#closeup_photos"));
    res.textContent = "Saving & ingesting…";

    const payload = {
      site_mode: mode,
      site_slug: val("site_slug"),
      new_site: {
        name: val("ns_name"), slug: val("ns_slug"), subtitle: val("ns_subtitle"),
        location: val("ns_location"), founded: val("ns_founded"),
        community: val("ns_community"), tagline: val("ns_tagline"),
        history_md: val("ns_history"), verify_source_en: val("ns_verify_en"),
        verify_source_he: val("ns_verify_he"),
        source_dirname: val("ns_dirname"),
        name_he: val("ns_name_he"), subtitle_he: val("ns_subtitle_he"),
        location_he: val("ns_location_he"), community_he: val("ns_community_he"),
        tagline_he: val("ns_tagline_he"), history_he: val("ns_history_he"),
      },
      stone: {
        folder: val("folder"), surname: val("surname"),
        folder_year: val("folder_year"),
        stone_type: val("stone_type"), inscription_language: val("inscription_language"),
        biographical_confidence: val("biographical_confidence"),
        stone_age_years_2026: val("stone_age_years_2026"),
        death_year_used_for_age: val("death_year_used_for_age"),
        persons: collectPersons(),
        inscription_original_lang: val("inscription_original_lang"),
        inscription_original: val("inscription_original"),
        inscription_english: val("inscription_english"),
        inscription_hebrew: val("inscription_hebrew"),
        lichen_genera_observed: val("lichen_genera_observed"),
        lichen_species_guesses: val("lichen_species_guesses"),
        lichen_dominant: val("lichen_dominant"),
        lichen_coverage_estimate_pct: val("lichen_coverage_estimate_pct"),
        lichen_note: val("lichen_note"), lichen_note_he: val("lichen_note_he"),
        biographical_context: val("biographical_context"),
        biographical_context_he: val("biographical_context_he"),
        notes: val("notes"),
        photos: { full, closeups },
      },
    };

    const r = await fetch("./api/submit", {method:"POST",
      headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)});
    const j = await r.json();
    if(!r.ok || !j.ok) throw new Error(j.error || ("HTTP "+r.status));

    res.className = "show ok";
    res.innerHTML =
      "✅ Added <b>"+j.folder+"</b> to <b>"+j.site_name+"</b>"+
      (j.site_created ? " (new site created)" : "")+".\n\n"+
      "Review on the dev server:\n"+
      "• EN: <a href='"+j.links.en_site+"' target='_blank'>"+j.links.en_site+"</a>\n"+
      "• HE: <a href='"+j.links.he_site+"' target='_blank'>"+j.links.he_site+"</a>\n\n"+
      (j.site_created ? "⚠ New sites may need a dev-server restart to appear.\n\n" : "")+
      "Ingest:\n"+j.ingest_output;
  }catch(e){
    res.className = "show err";
    res.textContent = "❌ "+e.message;
  }finally{
    btn.disabled = false;
  }
};
</script>
</body>
</html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Lichen Atlas local editor")
    ap.add_argument("--port", type=int, default=4455)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    STAGING.mkdir(parents=True, exist_ok=True)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    # 127.0.0.1 has no DNS name on some setups; show localhost, which always works.
    shown_host = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
    url = f"http://{shown_host}:{args.port}/"
    bar = "─" * 64
    print(f"\n{bar}")
    print("  🪦  Lichen Atlas — local EDITOR (runs on your machine only)")
    print(f"{bar}")
    print("  Open this URL in your browser:\n")
    print(f"      {url}\n")
    print("  • Add a grave to an existing site, or create a new site.")
    print("  • On save it writes _organized/ source files + runs the ingest.")
    print("  • It listens on your computer only — the public site stays view-only.")
    print("  • Stop it with Ctrl-C.")
    print(f"{bar}\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  editor stopped.")
        httpd.server_close()


if __name__ == "__main__":
    main()
