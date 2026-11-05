"""Send matching DAs to the monday.com "DA Tracking" board.

    MONDAY_API_TOKEN=... python push_monday.py              # matches lodged in the last 7 days
    MONDAY_API_TOKEN=... python push_monday.py 2026-10-16   # matches lodged since a date
    python push_monday.py 2026-10-16 --dry-run               # show what would be sent

Duplicates are skipped: a DA is not created if the board already has an item
for the same council with the same reference number OR the same street address
(so a site that comes through again as a new application isn't added twice).
NSW CDCs, construction certificates, modifications and reviews are never sent.
"""
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from datetime import date, timedelta

from filters import matches
from links import council_link

BOARD_ID = 5589886642
DB = os.environ.get("DB_PATH", "data/das.sqlite")

# Board groups
GROUP_VET = "topics"                 # New Leads - Vet & Animal
GROUP_CHILDCARE_MEDICAL = "new_group71055"  # New Leads - Childcare & Medical

# filters.py tag -> "Industry" status label
INDUSTRY = {"childcare": "Childcare", "medical": "Medical", "veterinary": "Vet", "hospital": "Hospital"}

STATE_LABEL = {
    "nsw_planning_portal": "NSW & ACT",
    "act_dafinder": "NSW & ACT",
    "qld_councils": "QLD & NT",
    "sa_plansa": "WA & SA",
}

# NSW Planning Portal council names -> existing "Council" dropdown labels on the board
COUNCIL_ALIASES = {
    "City of Parramatta Council": "Parramatta City Council",
    "Council of the City of Sydney": "City of Sydney",
    "Lismore City Council": "City of Lismore",
    "Wagga Wagga City Council": "City of Wagga Wagga",
}


# Application types we never send (too late in the process, or a repeat of an
# earlier application for the same project).
SKIP_TYPES = {
    "Complying Development Certificate Application",
    "Construction Certificate",
    "Modification Application",
    "Review of determination",
}

_ABBREV = {"ROAD": "RD", "STREET": "ST", "AVENUE": "AV", "AVE": "AV", "DRIVE": "DR", "PLACE": "PL",
           "COURT": "CT", "CRESCENT": "CRES", "HIGHWAY": "HWY", "PARADE": "PDE", "TERRACE": "TCE",
           "CLOSE": "CL", "CIRCUIT": "CCT", "BOULEVARD": "BVD", "LANE": "LN", "GROVE": "GR"}
_STATES = {"NSW", "ACT", "QLD", "SA", "VIC", "WA", "TAS", "NT", "AUSTRALIA"}


def norm_address(addr):
    """'142 Old Pitt Town Road, Box Hill NSW 2765' and '142 OLD PITT TOWN RD BOX HILL 2765'
    both become '142 OLD PITT TOWN RD BOX HILL'."""
    if not addr:
        return ""
    words = re.sub(r"[^A-Z0-9 ]", " ", addr.upper().replace(" -", "-")).split()
    words = [_ABBREV.get(w, w) for w in words if w not in _STATES and not re.fullmatch(r"\d{4}", w)]
    return " ".join(words)


def norm_ref(ref):
    return re.sub(r"[^A-Z0-9]", "", (ref or "").upper())


def money(v):
    if not v:
        return ""
    v = float(v)
    return f"${v/1e6:.1f}m" if v >= 1e6 else f"${v:,.0f}"


def build_item(row, tags):
    council = COUNCIL_ALIASES.get(row["authority_label"], row["authority_label"])
    parts = [row["description"] or ""]
    extra = [row["application_type"], money(row["cost_of_development"])]
    if row["new_dwellings"]:
        extra.append(f"{row['new_dwellings']} dwellings")
    extra.append(row["id"].split(":", 1)[-1])  # Planning Portal number, e.g. PAN-123456
    description = f"{parts[0]} | " + " | ".join(e for e in extra if e)
    columns = {
        "text0": row["address"] or "",
        "text4": description[:2000],
        "council": {"labels": [council]},
        "status_16": {"label": STATE_LABEL.get(row["source"], "NSW & ACT")},
        "status_1": {"label": INDUSTRY[tags[0]]},
        "date4": {"date": row["date_received"]},
        "date": {"date": date.today().isoformat()},
    }
    try:
        raw = json.loads(row["raw"] or "{}")
    except ValueError:
        raw = {}
    url, kind = council_link(row["authority_label"], row["council_reference"], raw)
    url = url or row.get("info_url")
    if url:
        text = {"deep": "Open DA on council site", "search": "Council DA search"}.get(kind, "Council tracker")
        columns["link"] = {"url": url, "text": text}
    return {
        "key": row["id"],
        "name": (row["council_reference"] or row["id"])[:255],
        "council": council,
        "address_key": norm_address(row["address"]),
        "group": GROUP_VET if tags[0] == "veterinary" else GROUP_CHILDCARE_MEDICAL,
        "columns": columns,
    }


def pending_items(since, db):
    db.execute("CREATE TABLE IF NOT EXISTS pushed (id PRIMARY KEY, monday_item_id, pushed_at)")
    done = {r[0] for r in db.execute("SELECT id FROM pushed")}
    items = []
    seen = set()
    for row, tags in matches(DB, since=since):
        if row["id"] in done or row["application_type"] in SKIP_TYPES:
            continue
        # vets first so a "vet hospital" lands in the vet group
        tags = sorted(tags, key=lambda t: t != "veterinary")
        item = build_item(row, tags)
        # one item per site: e.g. Toowoomba lodges MCU, RAL and OWS for the same address
        akey = (item["council"], item["address_key"]) if item["address_key"] else None
        if akey and akey in seen:
            continue
        if akey:
            seen.add(akey)
        items.append(item)
    return items


# ---- monday API -------------------------------------------------------------

def gql(query, variables=None):
    req = urllib.request.Request(
        "https://api.monday.com/v2",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": os.environ["MONDAY_API_TOKEN"], "Content-Type": "application/json",
                 "API-Version": "2024-10"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    if out.get("errors"):
        raise RuntimeError(out["errors"])
    return out["data"]


def board_index():
    """Reference numbers and addresses already on the board (any group, any status)."""
    refs, addrs = set(), set()
    q = """query($b:ID!,$c:String){boards(ids:[$b]){items_page(limit:500,cursor:$c){cursor
           items{name column_values(ids:["text0","council"]){id text}}}}}"""
    cursor = None
    while True:
        page = gql(q, {"b": BOARD_ID, "c": cursor})["boards"][0]["items_page"]
        for it in page["items"]:
            cv = {c["id"]: (c["text"] or "").strip() for c in it["column_values"]}
            refs.add((cv.get("council"), norm_ref(it["name"])))
            if cv.get("text0"):
                addrs.add((cv.get("council"), norm_address(cv["text0"])))
        cursor = page["cursor"]
        if not cursor:
            return refs, addrs


def already_on_board(item, index):
    refs, addrs = index
    if (item["council"], norm_ref(item["name"])) in refs:
        return True
    return bool(item["address_key"]) and (item["council"], item["address_key"]) in addrs


def create(item):
    q = """mutation($b:ID!,$g:String!,$n:String!,$c:JSON!){create_item(board_id:$b,group_id:$g,
           item_name:$n,column_values:$c,create_labels_if_missing:true){id}}"""
    return gql(q, {"b": BOARD_ID, "g": item["group"], "n": item["name"],
                   "c": json.dumps(item["columns"])})["create_item"]["id"]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    since = args[0] if args else (date.today() - timedelta(days=7)).isoformat()
    db = sqlite3.connect(DB)
    items = pending_items(since, db)
    if "--dry-run" in sys.argv or "--json" in sys.argv:
        if "--json" in sys.argv:
            print(json.dumps(items, indent=1))
        else:
            for i in items:
                print(i["name"], "|", i["council"], "|", i["columns"]["text0"], "|", i["columns"]["text4"][:80])
            print(f"{len(items)} items would be sent")
        return
    created = skipped = 0
    index = board_index() if items else (set(), set())
    for item in items:
        if already_on_board(item, index):
            mid = "existing"
            skipped += 1
        else:
            mid = create(item)
            created += 1
            time.sleep(0.5)
        db.execute("INSERT OR REPLACE INTO pushed VALUES (?,?,?)", (item["key"], mid, date.today().isoformat()))
        db.commit()
    print(f"monday.com: {created} created, {skipped} skipped (same reference or address already on board)")


if __name__ == "__main__":
    main()
