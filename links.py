"""Build a link to the council's own page for a DA.

council_links.json holds, per authority (as named by the source), a URL
template with {ref} (the council reference) or {raw.FIELD}, and how the
reference must be rewritten for that council's tracker:

  none          use as-is
  urlencode     URL-encode (DA/2026/1 -> DA%2F2026%2F1)
  slash_to_dash SP/225/2026 -> SP-225-2026
  masterview    MasterView trackers: 10.2026.567.1 / DA2026/567 -> 010.2026.00000567.001
                (_slash / _dash variants use that separator instead of '.')

kind = deep (opens that application), search (council's search page, filled
in where possible) or home (tracker home page only).
"""
import json
import os
import re
import urllib.parse

_CFG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "council_links.json")))


def masterview_ref(ref, sep="."):
    nums = re.findall(r"\d+", ref or "")
    years = [i for i, n in enumerate(nums) if len(n) == 4 and n.startswith("20")]
    if not years:
        return None
    y = years[0]
    after = nums[y + 1:]
    if after:                       # 10.2026.567.1, 2026/448/1, DA 16-2026-645-1
        typ = nums[y - 1] if y > 0 else "10"
        number, version = after[0], (after[1] if len(after) > 1 else "1")
    elif y > 0:                     # 214/2026, DA504/2026
        typ, number, version = "10", nums[y - 1], "1"
    else:
        return None
    return sep.join([typ.zfill(3), nums[y], number.zfill(8), version.zfill(3)])


def transform(ref, how):
    if how == "urlencode":
        return urllib.parse.quote(ref, safe="")
    if how == "slash_to_dash":
        return ref.replace("/", "-")
    if how.startswith("masterview"):
        return masterview_ref(ref, {"masterview": ".", "masterview_slash": "/", "masterview_dash": "-"}[how])
    return ref


def council_link(authority, ref, raw=None):
    """Return (url, kind) or (None, None) if we have nothing for this authority."""
    cfg = _CFG.get(authority)
    if not cfg:
        return None, None
    url = cfg["url"]
    if "{ref}" in url:
        r = transform(ref or "", cfg["ref"])
        if not r:  # couldn't rewrite the reference: fall back to the tracker's home page
            return url.split("/Application")[0].split("?")[0] + "/", "home"
        url = url.replace("{ref}", r)
    for field in re.findall(r"\{raw\.(\w+)\}", url):
        val = (raw or {}).get(field)
        if not val:
            return None, None
        url = url.replace("{raw.%s}" % field, str(val))
    return url, cfg["kind"]
