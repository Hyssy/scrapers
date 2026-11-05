# DA scrapers

Collects new development applications (DAs) from Australian planning authorities
into one SQLite database, ready to push into monday.com.

## Sources

| Source | File | Coverage | Method |
|---|---|---|---|
| NSW Planning Portal | `sources/nsw_planning_portal.py` | ~122 NSW councils: DAs, CDCs and construction certificates | Official public APIs (no scraping) |

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

## Filtering

`filters.py` tags each DA as `childcare`, `medical`, `veterinary` and/or
`hospital` using keyword patterns (with exclusions such as pool
"child-resistant barriers"). Only tagged DAs get pushed on. Edit the lists at
the top of the file to change what counts.

```bash
python filters.py 30     # show matches from the last 30 days
```

## monday.com

`push_monday.py` sends matching DAs to the **DA Tracking** board
(childcare/medical/hospital → "New Leads - Childcare & Medical", vet →
"New Leads - Vet & Animal"). It skips anything whose name + council is already
on the board. The daily workflow runs it when the `MONDAY_API_TOKEN` repo secret
is set.

```bash
python push_monday.py 2026-10-16 --dry-run   # preview
MONDAY_API_TOKEN=... python push_monday.py    # last 7 days
```
