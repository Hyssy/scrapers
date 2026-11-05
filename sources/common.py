"""Shared helpers for all sources: one SQLite table, same columns everywhere."""
import json
import os
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

DB = os.environ.get("DB_PATH", "data/das.sqlite")
DAYS_BACK = int(os.environ.get("DAYS_BACK", "14"))
UA = "da-collector/0.1"
AEST = timezone(timedelta(hours=10))

COLUMNS = [
    "id", "source", "council_reference", "authority_label", "address", "suburb", "postcode",
    "description", "application_type", "status", "date_received", "date_scraped",
    "info_url", "cost_of_development", "new_dwellings", "storeys", "lat", "lng",
    "last_updated", "raw",
]


def since_date():
    return date.today() - timedelta(days=DAYS_BACK)


def epoch_ms_to_date(ms):
    """ArcGIS / .NET dates are epoch milliseconds; read them in Australian time."""
    if ms in (None, "", "0", 0):
        return None
    return datetime.fromtimestamp(int(ms) / 1000, AEST).date().isoformat()


def http_json(url, params=None, body=None, retries=4):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    headers = {"User-Agent": UA}
    if data:
        headers["Content-Type"] = "application/json"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=120) as r:
                return json.load(r)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** (attempt + 1))


def arcgis_query(layer_url, where, page_size=1000):
    """Yield (attributes, geometry) for every feature matching `where`, paging politely."""
    offset = 0
    while True:
        d = http_json(layer_url + "/query", {
            "where": where, "outFields": "*", "returnGeometry": "true", "outSR": "4326",
            "orderByFields": "OBJECTID", "resultOffset": offset, "resultRecordCount": page_size, "f": "json",
        })
        if "error" in d:
            raise RuntimeError(d["error"])
        feats = d.get("features") or []
        for f in feats:
            yield f.get("attributes") or {}, f.get("geometry") or {}
        if not d.get("exceededTransferLimit") and len(feats) < page_size:
            break
        offset += len(feats)
        time.sleep(1)


class Store:
    def __init__(self, source):
        self.source = source
        os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
        self.db = sqlite3.connect(DB)
        self.db.execute(f"CREATE TABLE IF NOT EXISTS data ({', '.join(COLUMNS)}, PRIMARY KEY (id))")
        self.scraped = date.today().isoformat()
        self.total = self.new = 0

    def save(self, row):
        row = {c: row.get(c) for c in COLUMNS}
        row["source"] = self.source
        row["date_scraped"] = self.scraped
        if isinstance(row["raw"], (dict, list)):
            row["raw"] = json.dumps(row["raw"], separators=(",", ":"), default=str)
        old = self.db.execute("SELECT date_scraped FROM data WHERE id=?", (row["id"],)).fetchone()
        if old:
            row["date_scraped"] = old[0]
        else:
            self.new += 1
        self.db.execute(
            f"INSERT OR REPLACE INTO data ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
            [row[c] for c in COLUMNS],
        )
        self.total += 1

    def done(self, label=None):
        self.db.commit()
        print(f"{label or self.source}: {self.total} applications since {since_date()}; {self.new} new")
