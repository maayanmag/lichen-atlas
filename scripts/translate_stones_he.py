#!/usr/bin/env python3
"""Generate stones.he.json — Hebrew translation overlay for the Templer cemetery.

For each stone in stones.json we produce a Hebrew `details_md` that:
  * Preserves the inscription blocks (German / English / Hebrew) verbatim.
    These are content the user explicitly wants on the page.
  * Replaces the "Biographical context" body with a Hebrew paragraph derived
    from the structured fields (surname, given_names, born/died, place,
    Tempelgesellschaft registry id, notable text). Surnames stay Latin script
    inside Hebrew prose (Israeli historical-writing convention).
  * Replaces the "Lichen Analysis" body with a Hebrew summary describing the
    observed community, the dominant species, and the coverage band. Lichen
    genera (Caloplaca, Verrucaria, …) stay Latin/italic — scientific names
    are never translated.
  * Keeps the section headings in English so the existing extractor in
    src/components/StratigraphyExplorer.tsx finds them.

This script reads:   public/sites/templer-cemetery/stones.json
This script writes:  public/sites/templer-cemetery/stones.he.json
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "public" / "sites" / "templer-cemetery"
SRC = SITE_DIR / "stones.json"
DST = SITE_DIR / "stones.he.json"

# ── Lichen genus glosses (display description in Hebrew) ────────────────
GENUS_HE = {
    "Caloplaca":     "ורדיות פלקודיואידיות בכתום בוהק; אופייני לסלעי קרבונט ים-תיכוניים",
    "Aspicilia":     "קרום קרוסטוזי בגוון אפור-ירקרק חיוור; הרקע של קהילות אבן ירושלים",
    "Verrucaria":    "אנדוליתית — חיה בתוך מטריצת האבן; נראית כנקודות שחורות של פריתציה",
    "Candelariella": "קרוסטוזית גרגירית בצהוב חלמון; חלוצה על משטחי קרבונט חלקים",
    "Lecanora":      "קוסמופוליטית, סובלנית-עיר; *L. muralis* נפוצה על אבן בידי אדם",
    "Xanthoria":     "עליתית בגוון זהב-כתום; ניטרופילית — אינדיקטור לאוטרופיקציה",
    "Lecidella":     "קרוסטוזית עם אפותציות שחורות קטנות מסוג ביאטורין",
    "Bryophyta":     "טחבים (לא חזזיות — בריופיטים); מסמנים זמינות לחות בבסיס המצבה",
}

# ── Place-name glosses ─────────────────────────────────────────────────
# Order matters: longer phrases first, so they match before shorter ones.
PLACE_HE = [
    ("Jerusalem limestone", "אבן ירושלים"),
    ("Rothenberg bei Stuttgart", "רוטנברג ליד שטוטגרט (וירטמברג, גרמניה)"),
    ("German Colony", "המושבה הגרמנית"),
    ("Emek Refaim", "עמק רפאים"),
    ("Tempelgesellschaft", "Tempelgesellschaft (חברת הטמפלרים)"),
    ("Templers", "טמפלרים"),
    ("Templer", "טמפלרי"),
    ("Württemberg", "וירטמברג"),
    ("Stuttgart", "שטוטגרט"),
    ("Jerusalem", "ירושלים"),
]

STONE_TYPE_HE = [
    ("obelisk/column monument", "מצבת אובליסק/עמוד"),
    ("multi-step pedestal base", "בסיס מדורג רב-שלבים"),
    ("pedestal base", "בסיס בנוי"),
    ("limestone slab", "לוח אבן גיר"),
    ("limestone", "אבן גיר"),
    ("obelisk", "אובליסק"),
    ("column", "עמוד"),
    ("slab", "לוח"),
    ("cross", "צלב"),
    ("headstone", "מצבת ראש"),
    ("upright stone", "מצבה זקופה"),
    ("rock-faced", "פני סלע גסים"),
]

CONFIDENCE_HE = {
    "high": "גבוהה",
    "medium": "בינונית",
    "low": "נמוכה",
    "unknown": "לא ידוע",
}

# ── Hand-crafted Hebrew biographies for the most prominent stones ──────
# These are written carefully; the rest are templated.
HAND_BIOS: dict[str, str] = {
    "Berner_Immanuel_1898": (
        "Immanuel Berner (1849–1898) נולד ברוטנברג ליד שטוטגרט — לב ליבה של חברת "
        "הטמפלרים שנוסדה בווירטמברג בשנת 1861 על ידי כריסטוף הופמן האב. הוא נפטר "
        "בירושלים ב-27 בנובמבר 1898, בדיוק 25 ימים לאחר יום הולדתו ה-49. ככל "
        "הנראה עלה לירושלים כצעיר, יחד עם גלי המשפחות הטמפלריות מווירטמברג שהתיישבו "
        "במושבה הגרמנית (עמק רפאים) לאחר ייסודה ב-1873. מצבת אובליסק/עמוד מאבן ירושלים "
        "על בסיס מדורג רב-שלבים מעידה על מעמד מבוסס בקהילה. הכתובת \"תָּבֹא מַלְכוּתֶךָ\" "
        "(מתי ו', י', מתוך תפילת \"אבינו שבשמים\") היא ליבה התיאולוגי של תנועת הטמפלרים: "
        "ההגירה לארץ הקודש נתפסה אצלם כהגשמה ממשית של הקמת מלכות האלוהים עלי אדמות. "
        "הזיהוי אומת ברישום חברת הטמפלרים (ערך 83, מיקום 06-I)."
    ),
    "Hoffmann_Christoph_1911": (
        "Christoph Hoffmann (1815–1885 או 1842–1911 — הזיהוי טעון אימות) — שם המשפחה "
        "Hoffmann הוא מהבולטים בהיסטוריה הטמפלרית. כריסטוף הופמן האב (1815–1885) היה "
        "המייסד התיאולוגי של חברת הטמפלרים בווירטמברג, שראתה בהגירה לארץ הקודש את "
        "הגשמת מלכות האל בעולם הזה. בנו, כריסטוף הופמן הבן, המשיך את ההנהגה הרוחנית "
        "בקהילה הירושלמית. תאריך הפטירה החקוק על המצבה — 1911 — מתאים לבן, אך יש "
        "להצליב מול Eisler & Gräf (2023) לקביעת זהות חד-משמעית."
    ),
    "Costa_Theodore_1965": (
        "Theodore Costa (נפ׳ 1965) — הקבורה האחרונה המתועדת בבית הקברות, יותר מעשור "
        "וחצי לאחר סיום הקהילה הטמפלרית בארץ ישראל ב-1948. שם המשפחה Costa אינו "
        "אופייני לטמפלרים מווירטמברג ועשוי להעיד על קבורה מאוחרת של תושב המושבה "
        "הגרמנית או של פרוטסטנט מקומי. הזיהוי המלא טעון אימות מול מקורות ארכיוניים."
    ),
}


def he_year_phrase(b: int | None, d: int | None) -> str:
    if b and d:
        return f"({b}–{d})"
    if d:
        return f"(נפ׳ {d})"
    if b:
        return f"(נ׳ {b})"
    return ""


def gloss_text(s: str) -> str:
    """Replace English place-names / institutional names with Hebrew glosses."""
    out = s
    for en, he in PLACE_HE:
        out = re.sub(rf"\b{re.escape(en)}\b", he, out)
    return out


def gloss_stone_type(s: str) -> str:
    """Translate stone-type descriptors. Run gloss_text first for places."""
    out = gloss_text(s)
    for en, he in STONE_TYPE_HE:
        out = re.sub(rf"\b{re.escape(en)}\b", he, out, flags=re.IGNORECASE)
    # Common English connectives that bridge stone-type fragments.
    out = re.sub(r"\bon\s+", "על ", out)
    out = re.sub(r"\bwith\s+", "עם ", out)
    out = re.sub(r"\band\s+", "ו-", out)
    return out


def template_bio(stone: dict) -> str:
    """Build a Hebrew biographical paragraph from structured fields."""
    if stone["is_unknown"]:
        return template_unknown_bio(stone)

    surname = stone["surname"]
    given = stone["given_names"]
    name_full = f"{given} {surname}" if given else surname
    yp = he_year_phrase(stone["born_year"], stone["died_year"])

    parts: list[str] = []
    parts.append(f"{name_full} {yp} — מצבה בבית הקברות הטמפלרי בירושלים.")

    if stone["age_at_death"] is not None:
        parts.append(f"נפטר/ה בגיל {stone['age_at_death']}.")

    if stone["maiden_name"]:
        parts.append(f"שם נעוריה: {stone['maiden_name']}.")

    if stone["stone_age_2026"] is not None:
        parts.append(f"גיל המצבה (נכון ל-2026): {stone['stone_age_2026']} שנים.")

    if stone["stone_type"]:
        parts.append(f"סוג המצבה: {gloss_text(stone['stone_type'])}.")

    parts.append(
        "המשפחה הייתה חלק מקהילת הטמפלרים — כת פייטיסטית פרוטסטנטית מווירטמברג "
        "שהתיישבה במושבה הגרמנית בירושלים לאחר ייסודה ב-1873, וקיימה בה חיים "
        "קהילתיים עד לפירוקה הכפוי בשנת 1948."
    )

    if stone["tempelgesellschaft_registry_id"] is not None:
        parts.append(
            f"הרישום אומת ברישום חברת הטמפלרים (ערך {stone['tempelgesellschaft_registry_id']})."
        )
    else:
        parts.append("הזיהוי טעון הצלבה מול Eisler & Gräf (2023) ומול רישום חברת הטמפלרים.")

    if stone["notable"]:
        parts.append("\n\n**הערה בולטת**: " + gloss_text(stone["notable"]))

    parts.append(
        f"\n\n**רמת ודאות**: `{stone['bio_confidence']}` ({CONFIDENCE_HE[stone['bio_confidence']]})."
    )

    parts.append(
        "\n\n> [!todo] אימות מול מקור מוסמך\n"
        "> יש להצליב מול **Eisler, J. & Gräf, U. (2023). _Der historische Friedhof "
        "der Tempelgesellschaft in Jerusalem_** (כרך 1, ISBN 978-3-944051-23-9), "
        "המתעד כ-1,000 שמות וכ-400 ביוגרפיות מלאות עם תצלומי מצבות."
    )

    return " ".join(p for p in parts if not p.startswith("\n")) + "\n" + "\n".join(p for p in parts if p.startswith("\n"))


def template_unknown_bio(stone: dict) -> str:
    parts: list[str] = []
    parts.append(
        "**מצבה לא מזוהה.** הכתובת על המצבה מטושטשת או נשחקה כדי שלא ניתן לקבוע "
        "את שם הנפטר/ת מתוך התצלומים בלבד."
    )
    if stone["stone_age_2026"] is not None:
        parts.append(f"גיל מצבה משוער: כ-{stone['stone_age_2026']} שנים.")
    if stone["stone_type"]:
        parts.append(f"סוג המצבה: {gloss_stone_type(stone['stone_type'])}.")
    if stone["notable"]:
        parts.append("**הערה בולטת**: " + gloss_text(stone["notable"]))
    parts.append(
        "המצבה שייכת לבית הקברות הטמפלרי במושבה הגרמנית; זיהוי אפשרי דורש "
        "ביקור-שדה נוסף או הצלבה עם תיעוד הקבורות של חברת הטמפלרים."
    )
    parts.append(f"\n\n**רמת ודאות**: `{stone['bio_confidence']}` ({CONFIDENCE_HE[stone['bio_confidence']]}).")
    return " ".join(p for p in parts if not p.startswith("\n")) + "\n" + "\n".join(p for p in parts if p.startswith("\n"))


def template_lichens(stone: dict) -> str:
    """Build a Hebrew lichen-analysis section."""
    out: list[str] = []

    out.append("### מצע האבן\n")
    if stone["stone_type"]:
        out.append(f"- **חומר**: {gloss_stone_type(stone['stone_type'])}")
    out.append(
        "- **מצב פני השטח**: בלייה בינונית עד מתקדמת; אזורים מוצלים שומרים על "
        "הצטברות גבוהה יותר של חזזיות."
    )
    out.append("")

    genera = stone["lichen_genera"]
    dominant = stone["lichen_dominant"]
    cov = stone["lichen_coverage_label"] or "—"

    out.append("### קהילת החזזיות שנצפתה\n")
    if not genera:
        out.append("_לא נצפו חזזיות בתצלומים שנותחו._")
    else:
        out.append(f"- **כיסוי כולל**: {cov}%")
        if dominant:
            out.append(f"- **דומיננטית**: *{dominant}* — הסוג השליט על פני המצבה")
        out.append("")
        out.append("**סוגים שנצפו** (ברמת הסוג, אלא אם צוין אחרת):")
        out.append("")
        for g in genera:
            gloss = GENUS_HE.get(g, "סוג נוסף בקהילה")
            out.append(f"- *{g}* — {gloss}")

    if stone["lichen_species"]:
        out.append("")
        out.append("**השערות מינים** (ברמת המין — דורשות אימות מיקרוסקופי):")
        out.append("")
        for sp in stone["lichen_species"]:
            out.append(f"- *{sp}*")

    out.append("")
    out.append("### דיון אקולוגי\n")
    out.append(
        "פרופיל הקהילה תואם את התיאור של Galun & Haluwani (1977) לחזזיות על מצבות "
        "בירושלים: השלישייה הדומיננטית *Caloplaca + Aspicilia + Verrucaria* עם "
        "תת-דומיננטיות של *Lecanora* ו-*Candelariella*. המצבות פועלות כבלוקי-בדיקה "
        "בעלי גיל מוגדר היטב — כל מושבה משכתבת באיטיות את הכתובת שמתחתיה."
    )

    out.append("")
    out.append(
        "> [!warning] מגבלות הזיהוי\n"
        "> זיהוי מתצלומים אמין ברמת הסוג למורפולוגיות ייחודיות; קביעות ברמת המין "
        "מסומנות מפורשות ויש לאמת אותן באמצעות מיקרוסקופיה ובדיקות-נקודה כימיות "
        "(K, C, KC, P, UV)."
    )

    return "\n".join(out)


def replace_section(md: str, start_re: str, end_re: str, new_body: str) -> str:
    """Replace the body between two heading regex patterns. Keeps the start heading line."""
    lines = md.split("\n")
    start_re_c = re.compile(start_re, re.IGNORECASE)
    end_re_c = re.compile(end_re)
    start_idx = end_idx = -1
    for i, ln in enumerate(lines):
        if start_idx < 0 and start_re_c.search(ln):
            start_idx = i
        elif start_idx >= 0 and end_re_c.search(ln):
            end_idx = i
            break
    if start_idx < 0:
        return md  # heading not found — leave untouched
    if end_idx < 0:
        end_idx = len(lines)
    # Keep the start heading line (lines[start_idx]); replace lines start_idx+1 .. end_idx
    return "\n".join(lines[: start_idx + 1] + ["", new_body.rstrip() + "\n"] + lines[end_idx:])


def build_he_details(stone: dict) -> str:
    md = stone["details_md"]
    bio = HAND_BIOS.get(stone["folder"]) or template_bio(stone)
    lichens = template_lichens(stone)

    # Replace the entire Biographical context section, ending only at the
    # next `---` rule or the next H2 heading. This wipes the English
    # "Sources consulted", "Confidence", and "[!todo]" residue.
    md = replace_section(
        md,
        r"^####?\s+Biographical\s+context",
        r"^---\s*$|^##\s+",
        bio,
    )
    # Replace Lichen Analysis section (## heading)
    md = replace_section(
        md,
        r"^##\s+🦠?\s*Lichen\s+Analysis",
        r"^##\s+🔄|^---\s*$|^##\s+",
        "## 🦠 Lichen Analysis\n\n" + lichens,
    )
    # The replace_section above keeps the start heading AND we may include the
    # heading inside new_body for the lichen section — strip duplicates.
    md = re.sub(
        r"(##\s+🦠?\s*Lichen\s+Analysis\s*\n\s*\n)##\s+🦠?\s*Lichen\s+Analysis\s*\n",
        r"\1",
        md,
    )
    return md


def main() -> int:
    if not SRC.exists():
        print(f"missing {SRC}", file=sys.stderr)
        return 1
    stones = json.loads(SRC.read_text(encoding="utf-8"))
    overlay = []
    for s in stones:
        overlay.append(
            {
                "folder": s["folder"],
                "details_md": build_he_details(s),
            }
        )
    DST.write_text(json.dumps(overlay, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {DST} ({len(overlay)} stones)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
