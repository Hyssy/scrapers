"""Queensland council DAs.

- Development.i councils (Brisbane, Ipswich, Redland, Sunshine Coast, Toowoomba,
  Western Downs): the JSON endpoint the public Development.i map uses. Not an
  official API, so it may change.
- Logan and Moreton Bay: official open-data ArcGIS layers (CC-BY).
"""
import re
import time
from datetime import datetime, timezone

from common import Store, arcgis_query, epoch_ms_to_date, http_json, since_date

DEVELOPMENTI = {
    "developmenti.brisbane.qld.gov.au": "Brisbane City Council",
    "developmenti.ipswich.qld.gov.au": "Ipswich City Council",
    "developmenti.redland.qld.gov.au": "Redland City Council",
    "developmenti.sunshinecoast.qld.gov.au": "Sunshine Coast Regional Council",
    "developmenti.tr.qld.gov.au": "Toowoomba Regional Council",
    "developmenti.wdrc.qld.gov.au": "Western Downs Regional Council",
}

LOGAN = ("https://services5.arcgis.com/ZUCWDRj8F77Xo351/arcgis/rest/services/"
         "Logan_City_Undecided_Development_Applications/FeatureServer/0")
MORETON_BAY = "https://services-ap1.arcgis.com/152ojN3Ts9H3cdtl/ArcGIS/rest/services/MyStreet/FeatureServer/0"


def developmenti_filter(start_ms, end_ms, offset, page):
    return {
        "Progress": "all", "StartDateUnixEpochNumber": start_ms, "EndDateUnixEpochNumber": end_ms,
        "DateRangeField": "submitted", "DateRangeDescriptor": None, "LotPlan": None, "LandNumber": None,
        "PropNumber": None, "DANumber": None, "BANumber": None, "PlumbNumber": None,
        "IncludeDA": True, "IncludeBA": False, "IncludePlumb": False, "LocalityId": None,
        "DivisionId": None, "ApplicationTypeId": None, "SubCategoryUseId": None, "AssessmentLevels": [],
        "ShowCode": True, "ShowImpact": True, "ShowIAGA": True, "ShowIAGI": True,
        "ShowNotifiableCode": True, "ShowReferralResponse": True, "ShowRequest": True,
        "PagingStartIndex": offset, "MaxRecords": page, "Boundary": None, "ViewPort": None,
        "IncludeAroundMe": False, "SortField": "submitted", "SortAscending": False,
        "BBox": None, "PixelWidth": 800, "PixelHeight": 800,
    }


def split_address(desc):
    """Pull the street address out of a Development.i description.

    Brisbane puts it first ('12 SMITH ST SUBURB QLD 4000 - details'); Toowoomba
    puts it last ('details - 12 Smith Street, SUBURB QLD 4350').
    """
    if not desc or " - " not in desc:
        return None, desc
    parts = desc.split(" - ")
    if re.search(r"\bQLD \d{4}\s*$", parts[0]):
        return parts[0].strip(), " - ".join(parts[1:]).strip()
    if re.search(r"^\s*\d.*\bQLD \d{4}\s*$", parts[-1]):
        return parts[-1].strip(), " - ".join(parts[:-1]).strip()
    return None, desc


def developmenti(store):
    start = datetime.combine(since_date(), datetime.min.time(), timezone.utc)
    start_ms, end_ms = int(start.timestamp() * 1000), int(time.time() * 1000)
    for host, council in DEVELOPMENTI.items():
        offset, page, n = 0, 200, 0
        try:
            while True:
                d = http_json(f"https://{host}/Home/ApplicationFilterCSVPaged",
                              body=developmenti_filter(start_ms, end_ms, offset, page))
                apps = d.get("applications") or []
                for a in apps:
                    ref = a.get("ramId")
                    if not ref:
                        continue
                    addr, details = split_address(a.get("description"))
                    uses = " ".join(x for x in [a.get("useLevel1"), a.get("useLevel2")] if x)
                    store.save({
                        "id": f"qld:{host.split('.')[1]}:{ref}",
                        "council_reference": ref,
                        "authority_label": council,
                        "address": addr,
                        "description": " | ".join(x for x in [details, a.get("applicationType"), uses] if x),
                        "application_type": a.get("applicationType"),
                        "status": a.get("stage") or a.get("progress"),
                        "date_received": epoch_ms_to_date(a.get("dateReceived")),
                        "info_url": f"https://{host}/",
                        "raw": a,
                    })
                    n += 1
                if len(apps) < page:
                    break
                offset += page
                time.sleep(1)
        except Exception as e:  # one council being down shouldn't stop the others
            print(f"  {council}: FAILED ({e})")
            continue
        print(f"  {council}: {n}")
        time.sleep(1)


def logan(store):
    where = f"Application_Lodgement_Date >= DATE '{since_date().isoformat()}'"
    for a, g in arcgis_query(LOGAN, where):
        ref = a.get("Application_Number")
        if not ref:
            continue
        store.save({
            "id": f"qld:logan:{ref}",
            "council_reference": ref,
            "authority_label": "Logan City Council",
            "address": (a.get("Application_Property_Address") or "").replace("  ", " "),
            "suburb": a.get("Application_Property_Suburb"),
            "description": " | ".join(x for x in [a.get("Application_Description"),
                                                   a.get("Application_Development_Type_De")] if x),
            "application_type": a.get("Application_Development_Type_De"),
            "status": a.get("Application_Status"),
            "date_received": epoch_ms_to_date(a.get("Application_Lodgement_Date")),
            "info_url": "https://pdonline.logan.qld.gov.au/",
            "lat": g.get("y"), "lng": g.get("x"),
            "raw": a,
        })


def moreton_bay(store):
    where = f"LODGED_DATE >= DATE '{since_date().isoformat()}'"
    for a, g in arcgis_query(MORETON_BAY, where):
        ref = a.get("FORMATTED_APPLICATION_NUMBER")
        if not ref:
            continue
        store.save({
            "id": f"qld:moretonbay:{ref}",
            "council_reference": ref,
            "authority_label": "Moreton Bay Regional Council",
            "address": None,  # layer has a map point but no street address
            "description": (a.get("DESCRIPTION") or "").replace("\n", " | "),
            "application_type": a.get("TYPE_DESCRIPTION"),
            "status": a.get("STATUS_DESCRIPTION"),
            "date_received": epoch_ms_to_date(a.get("LODGED_DATE")),
            "info_url": a.get("DA_TRACKER_URL"),
            "lat": g.get("y"), "lng": g.get("x"),
            "raw": a,
        })


def main():
    s = Store("qld_councils")
    developmenti(s)
    for fn in (logan, moreton_bay):
        try:
            fn(s)
        except Exception as e:
            print(f"  {fn.__name__}: FAILED ({e})")
    s.done("QLD")


if __name__ == "__main__":
    main()
