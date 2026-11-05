# DA scrapers

Collects new development applications (DAs) from Australian planning authorities
into one SQLite database, ready to push into monday.com.

## Sources

| Source | File | Coverage | Method |
|---|---|---|---|
| NSW Planning Portal | `sources/nsw_planning_portal.py` | ~122 NSW councils | Official public API (no scraping) |

More states to come — preference order: official API/open data → shared tracker
platform (one scraper, many councils) → one-off council scraper.

## Run locally

```bash
python sources/nsw_planning_portal.py          # last 14 days
DAYS_BACK=60 python sources/nsw_planning_portal.py
```

Output goes to `data/das.sqlite`, table `data`. Key columns: `source`,
`authority_label` (council), `council_reference`, `address`, `description`,
`date_received`, `date_scraped` (first time we saw it), plus extras where the
source provides them (cost, dwellings, storeys, lat/lng).

## Schedule

`.github/workflows/daily.yml` runs every morning on GitHub Actions (free for
public repos) and stores the database on the `data` branch so we know which
DAs are new.

Note: GitHub's runners are in the US. Some council websites block overseas
traffic, so scrapers for those will need an Australian host.

## Etiquette

One run per day, at most ~1 request/second, generic `User-Agent`. Never try to
get around CAPTCHAs or bot blocking.
