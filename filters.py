"""Decide which DAs we care about.

Every source collects everything; this file decides what gets sent on (e.g. to
monday.com). Edit the keyword lists below and re-run to re-check old data.

    python filters.py              # show matches from the last 7 days
    python filters.py 30           # last 30 days
"""
import re
import sqlite3
import sys
from datetime import date, timedelta

# Each tag -> patterns (case-insensitive regex, \b = word boundary so "vet"
# does not match "velvet" and "hospital" does not match "hospitality").
TAGS = {
    "childcare": [
        r"\bchild ?care\b", r"\bchildcare\b", r"\bchild-care\b",
        r"\bearly (learning|education|childhood)\b", r"\bELC\b",
        r"\bkindergarten\b", r"\bkindy\b", r"\bpre-?school\b", r"\bnursery school\b",
        r"\bdaycare\b", r"\bday care\b", r"\bOSHC\b", r"\bout of school hours\b",
    ],
    "medical": [
        r"\bmedical\b", r"\bGPs?\b", r"\bgeneral practi(ce|tioner)\b",
        r"\bhealth\b", r"\bclinics?\b", r"\bdental\b", r"\bdentist\b",
        r"\bphysio(therapy)?\b", r"\bpathology\b", r"\bradiology\b", r"\bpharmacy\b",
        r"\bconsulting rooms?\b", r"\bsurgery\b", r"\bday procedure\b",
    ],
    "veterinary": [
        r"\bvets?\b", r"\bveterinar(y|ian)\b", r"\banimal (hospital|clinic|care)\b",
    ],
    "hospital": [
        # not "veterinary hospital" / "animal hospital" (those are tagged veterinary)
        r"(?<!veterinary )(?<!animal )(?<!vet )\bhospitals?\b",
    ],
}

# Text that looks like a match but isn't. Checked before tagging.
EXCLUDE = [
    r"child[- ]resistant",          # pool fencing
    r"\bswimming pool",
    r"\bhealth (and|&) safety\b",
    r"\banimal care premises\b.*\bboarding\b",  # kennels, not vets (remove if wanted)
]

_TAGS = {t: re.compile("|".join(p), re.I) for t, p in TAGS.items()}
_EXCLUDE = re.compile("|".join(EXCLUDE), re.I)
# The GP/ELC/OSHC abbreviations must be upper case to avoid false hits.
_CASE_SENSITIVE = re.compile(r"\b(GPs?|ELC|OSHC)\b")


def tags_for(text):
    """Return the list of tags that match this description (may be empty)."""
    if not text:
        return []
    cleaned = _EXCLUDE.sub(" ", text)
    found = []
    for tag, rx in _TAGS.items():
        for m in rx.finditer(cleaned):
            word = m.group(0)
            if word.upper() in ("GP", "GPS", "ELC", "OSHC") and not _CASE_SENSITIVE.fullmatch(word):
                continue
            found.append(tag)
            break
    # "vet clinic" / "vet surgery" shouldn't also count as human medical
    if "veterinary" in found and "medical" in found and not re.search(r"\b(medical|health|GPs?)\b", cleaned):
        found.remove("medical")
    return found


def matches(db_path="data/das.sqlite", since=None):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    q = "SELECT * FROM data"
    args = []
    if since:
        q += " WHERE date_received >= ?"
        args.append(since)
    for row in db.execute(q + " ORDER BY date_received DESC", args):
        t = tags_for(row["description"])
        if t:
            yield dict(row), t


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    since = (date.today() - timedelta(days=days)).isoformat()
    n = 0
    for row, t in matches(since=since):
        n += 1
        print(f"{row['date_received']}  {','.join(t):20s} {row['authority_label'][:28]:28s} "
              f"{(row['address'] or '')[:40]:40s} {(row['description'] or '')[:70]}")
    print(f"\n{n} matching DAs since {since}")
