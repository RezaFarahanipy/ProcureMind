"""Standardisation of free text into canonical values (province, unit, bank, ...), the in-memory model of the planned
`lookup_values` + `lookup_aliases` tables (decision 11, 12). Input stays free text; the stored value is canonical.

Seeds below are a starting point and must be reviewed by the owner before they go into the database.
A value is never silently invented: exact/alias match -> canonical; close match -> suggestions; otherwise -> "new" (needs confirmation).
"""
import difflib

from backend.validators import normalize_text

PROVINCES = ["آذربایجان شرقی", "آذربایجان غربی", "اردبیل", "اصفهان", "البرز", "ایلام", "بوشهر", "تهران", "چهارمحال و بختیاری",
             "خراسان جنوبی", "خراسان رضوی", "خراسان شمالی", "خوزستان", "زنجان", "سمنان", "سیستان و بلوچستان", "فارس", "قزوین",
             "قم", "کردستان", "کرمان", "کرمانشاه", "کهگیلویه و بویراحمد", "گلستان", "گیلان", "لرستان", "مازندران", "مرکزی",
             "هرمزگان", "همدان", "یزد"]

SEEDS = {
    "province": {p: [] for p in PROVINCES} | {"تهران": ["طهران", "tehran"], "اصفهان": ["isfahan", "esfahan"], "فارس": ["fars"]},
    "unit": {"کیلوگرم": ["کیلو", "kg", "کگ"], "تن": ["ton", "tonne"], "متر": ["m", "mtr"], "متر مربع": ["مترمربع", "m2", "m²"],
             "عدد": ["دانه", "pcs"], "شاخه": [], "بسته": ["پک", "pack"], "رول": ["roll"], "لیتر": ["lit", "liter"]},
}


def fold_loose(s: str) -> str:
    """Matching key: letter variants (آ/ا، ة/ه، ي/ی، ك/ک), spaces, half-spaces and case are ignored."""
    t = normalize_text(s).replace("\u200c", "").replace(" ", "").casefold()
    return t.translate(str.maketrans({"آ": "ا", "أ": "ا", "إ": "ا", "ة": "ه", "ؤ": "و"}))


def canonicalize(list_key: str, value: str, extra: dict | None = None) -> dict:
    """Return {"status": "exact"|"suggest"|"new"|"empty", "value", "suggestions"}.
    `extra` = {canonical: [aliases]} extra entries (e.g. from the database) merged over the seeds."""
    if not value or not str(value).strip():
        return {"status": "empty", "value": None, "suggestions": []}
    entries = {**SEEDS.get(list_key, {}), **(extra or {})}
    keys = {}
    for canon, aliases in entries.items():
        for form in [canon, *aliases]:
            keys.setdefault(fold_loose(form), canon)
    k = fold_loose(value)
    if k in keys:
        return {"status": "exact", "value": keys[k], "suggestions": []}
    close = difflib.get_close_matches(k, list(keys), n=6, cutoff=0.78)
    sugg = list(dict.fromkeys(keys[c] for c in close))[:3]
    return {"status": "suggest" if sugg else "new", "value": None, "suggestions": sugg}
