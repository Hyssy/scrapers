"""NSW Planning Portal DA collector.

Uses the NSW Government's public ePlanning data APIs, which publish every
application lodged through the NSW Planning Portal (almost every NSW council):
  OnlineDA  - development applications (and modifications/reviews)
  OnlineCDC - complying development certificates
  OnlineCC  - construction certificates
No scraping of council websites is needed.

Output: data/das.sqlite (shared by all sources), table `data`, one row per application, using the same
core fields PlanningAlerts uses plus extra NSW fields. Each row has a `source` column so all states share one table.

Run:  python sources/nsw_planning_portal.py      (last DAYS_BACK days, default 14)
      DAYS_BACK=60 python sources/nsw_planning_portal.py
"""
import json
import os
import sqlite3
import time
import urllib.request
from datetime import date, datetime, timedelta

API_BASE = "https://api.apps1.nsw.gov.au/eplanning/data/v0/"
FEEDS = {"OnlineDA": "DA", "OnlineCDC": "CDC", "OnlineCC": "CC"}
PORTAL_URL = "https://www.planningportal.nsw.gov.au/"  # no public per-app page; council ref is the key
DB = os.environ.get("DB_PATH", "data/das.sqlite")
SOURCE = "nsw_planning_portal"
DAYS_BACK = int(os.environ.get("MORPH_DAYS_BACK", os.environ.get("DAYS_BACK", "14")))
PAGE_SIZE = 500

COLUMNS = [
    "id", "source", "council_reference", "authority_label", "address", "suburb", "postcode",
    "description", "application_type", "status", "date_received", "date_scraped",
    "info_url", "cost_of_development", "new_dwellings", "storeys", "lat", "lng",
    "last_updated", "raw",
]


def fetch_page(feed, page, date_from):
    req = urllib.request.Request(API_BASE + feed, headers={
        "PageSize": str(PAGE_SIZE),
        "PageNumber": str(page),
        "filters": json.dumps({"filters": {"LodgementDateFrom": date_from}}),
        "User-Agent": "da-collector/0.1",
    })
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))


def to_row(a, scraped, kind):
    loc = (a.get("Location") or [{}])[0]
    types = [t.get("DevelopmentType") for t in a.get("DevelopmentType") or [] if t.get("DevelopmentType")]
    uses = []
    if kind == "CC":  # CCs carry a short free-text building use, which helps keyword matching
        cur, new = a.get("CurrentBuildingUse"), a.get("ProposedBuildingUse")
        uses = [f"Use: {new}" + (f" (currently {cur})" if cur and cur != new else "")] if new else []
    council = (a.get("Council") or {}).get("CouncilName")
    pan = a.get("PlanningPortalApplicationNumber")
    ref = a.get("CouncilApplicationNumber") or a.get("CertifierApplicationNumber") or pan
    return {
        "id": f"nsw:{pan}",
        "source": SOURCE,
        "council_reference": ref,
        "authority_label": council,
        "address": loc.get("FullAddress"),
        "suburb": loc.get("Suburb"),
        "postcode": loc.get("Postcode"),
        "description": "; ".join(types + uses) or a.get("ApplicationType"),
        "application_type": a.get("ApplicationType") or "Construction Certificate",
        "status": a.get("ApplicationStatus"),
        "date_received": (a.get("LodgementDate") or "")[:10] or None,
        "date_scraped": scraped,
        "info_url": PORTAL_URL,
        "cost_of_development": a.get("CostOfDevelopment"),
        "new_dwellings": a.get("NumberOfNewDwellings") or a.get("UnitsProposed"),
        "storeys": a.get("NumberOfStoreys") or a.get("StoreysProposed"),
        "lat": loc.get("Y"),
        "lng": loc.get("X"),
        "last_updated": a.get("DateLastUpdated"),
        "raw": json.dumps(a, separators=(",", ":")),
    }


def main():
    date_from = (date.today() - timedelta(days=DAYS_BACK)).isoformat()
    scraped = datetime.now().date().isoformat()
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    db = sqlite3.connect(DB)
    db.execute(f"CREATE TABLE IF NOT EXISTS data ({', '.join(COLUMNS)}, PRIMARY KEY (id))")

    for feed, kind in FEEDS.items():
        page, total, new = 1, 0, 0
        while True:
            d = fetch_page(feed, page, date_from)
            for a in d.get("Application") or []:
                if not a.get("PlanningPortalApplicationNumber"):
                    continue
                row = to_row(a, scraped, kind)
                exists = db.execute("SELECT date_scraped FROM data WHERE id=?", (row["id"],)).fetchone()
                if exists:
                    row["date_scraped"] = exists[0]  # keep first-seen date so "new today" stays accurate
                else:
                    new += 1
                db.execute(
                    f"INSERT OR REPLACE INTO data ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
                    [row[c] for c in COLUMNS],
                )
                total += 1
            if page >= (d.get("TotalPages") or 1):
                break
            page += 1
            time.sleep(1)
        db.commit()
        print(f"{kind}: {total} applications lodged since {date_from}; {new} new")


if __name__ == "__main__":
    main()
