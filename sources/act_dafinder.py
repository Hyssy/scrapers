"""ACT development applications from the ACT Government's DA Finder (ArcGIS).

Covers the whole ACT (single planning authority). Public feature service.
"""
from common import Store, arcgis_query, epoch_ms_to_date, since_date

LAYER = "https://services1.arcgis.com/E5n4f1VY84i0xSjy/arcgis/rest/services/ACTGOV_DAFINDER_LIST_VIEW/FeatureServer/0"
INFO_URL = "https://www.planning.act.gov.au/applications-and-assessments/development-applications/browse-das"


def main():
    s = Store("act_dafinder")
    where = f"LODGEMENT_DATE >= DATE '{since_date().isoformat()}'"
    for a, _ in arcgis_query(LAYER, where):
        da = str(a.get("DA_NUMBER") or "")
        if not da:
            continue
        version = a.get("AMENDMENT_VERSION")
        ref = f"{da}-{version}" if version else da
        addr = ", ".join(x for x in [a.get("STREET_ADDRESS"), a.get("SUBURB"), "ACT"] if x)
        s.save({
            "id": f"act:{ref}",
            "council_reference": ref,
            "authority_label": "ACT Planning & Land Authority",
            "address": addr,
            "suburb": a.get("SUBURB"),
            "description": a.get("PROPOSAL_TEXT"),
            "application_type": a.get("APPLICATION_SUB_TYPE") or a.get("APPLICATION_TYPE"),
            "status": a.get("DA_STAGE"),
            "date_received": epoch_ms_to_date(a.get("LODGEMENT_DATE")),
            "info_url": INFO_URL,
            "lat": a.get("CENTROID_LAT"),
            "lng": a.get("CENTROID_LONG"),
            "last_updated": epoch_ms_to_date(a.get("DATECREATED")),
            "raw": a,
        })
    s.done("ACT")


if __name__ == "__main__":
    main()
