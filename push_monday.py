"""Send matching DAs to the monday.com "DA Tracking" board.

    MONDAY_API_TOKEN=... python push_monday.py              # matches lodged in the last 7 days
    MONDAY_API_TOKEN=... python push_monday.py 2026-10-16   # matches lodged since a date
    python push_monday.py 2026-10-16 --dry-run               # show what would be sent

Duplicates are skipped: a DA is only created if no item with the same name
(council reference) and council already exists on the board, and every DA we
send is remembered in the `pushed` table so it is never sent twice.
"""
import json
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import date, timedelta

from filters import matches

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
    if row.get("info_url"):
        columns["link"] = {"url": row["info_url"], "text": "Council Link"}
    return {
        "key": row["id"],
        "name": (row["council_reference"] or row["id"])[:255],
        "council": council,
        "group": GROUP_VET if tags[0] == "veterinary" else GROUP_CHILDCARE_MEDICAL,
        "columns": columns,
    }


def pending_items(since, db):
    db.execute("CREATE TABLE IF NOT EXISTS pushed (id PRIMARY KEY, monday_item_id, pushed_at)")
    done = {r[0] for r in db.execute("SELECT id FROM pushed")}
    items = []
    for row, tags in matches(DB, since=since):
        # vets first so a "vet hospital" lands in the vet group
        tags = sorted(tags, key=lambda t: t != "veterinary")
        if row["id"] not in done:
            items.append(build_item(row, tags))
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


def already_on_board(name, council):
    q = """query($b:ID!,$v:[String]!){items_page_by_column_values(board_id:$b,limit:50,
           columns:[{column_id:"name",column_values:$v}]){items{id column_values(ids:["council"]){text}}}}"""
    items = gql(q, {"b": BOARD_ID, "v": [name]})["items_page_by_column_values"]["items"]
    return any((i["column_values"][0]["text"] or "").strip() == council for i in items)


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
    for item in items:
        if already_on_board(item["name"], item["council"]):
            mid = "existing"
            skipped += 1
        else:
            mid = create(item)
            created += 1
            time.sleep(0.5)
        db.execute("INSERT OR REPLACE INTO pushed VALUES (?,?,?)", (item["key"], mid, date.today().isoformat()))
        db.commit()
    print(f"monday.com: {created} created, {skipped} already on board")


if __name__ == "__main__":
    main()
