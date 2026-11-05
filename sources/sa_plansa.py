"""South Australian development applications from the PlanSA register (ArcGIS).

Statewide (all SA councils + State Commission). Read-only queries only.
The service is public but undocumented, so it could change without notice.
"""
from common import Store, arcgis_query, epoch_ms_to_date, since_date

LAYER = ("https://location.sa.gov.au/server6/rest/services/GrowthManagementPublic/"
         "DevelopmentApplicationRegister_PRODUCTION/FeatureServer/0")
INFO_URL = "https://plan.sa.gov.au/development_application_register"


def main():
    s = Store("sa_plansa")
    where = f"lodgementdate >= DATE '{since_date().isoformat()}'"
    for a, g in arcgis_query(LAYER, where):
        appid = a.get("appid")
        if not appid:
            continue
        council = (a.get("locationcouncil") or "").strip()
        s.save({
            "id": f"sa:{appid}",
            "council_reference": str(appid),
            "authority_label": f"{council} (SA)" if council else "Plan SA",
            "address": a.get("address"),
            "suburb": a.get("suburb"),
            "description": (a.get("natureofdevelopment") or "").strip(),
            "application_type": a.get("assessmentpathway"),
            "status": a.get("applicationstatus"),
            "date_received": epoch_ms_to_date(a.get("lodgementdate")),
            "info_url": INFO_URL,
            "lat": g.get("y"),
            "lng": g.get("x"),
            "raw": a,
        })
    s.done("SA")


if __name__ == "__main__":
    main()
