"""Two-page prospecting dossiers (Markdown).

Page 1: the result, key facts and the screening rules with pass/fail.
Page 2: the evidence, i.e. which features the result is based on, their source date and
positional uncertainty, the datasets used, the method and the project's uncertainty wording.

Nothing is estimated here: every value comes from the screening views or from core.
"""

# The project's reference uncertainty wording (IRIS-CAND-22), printed on every dossier.
DISCLAIMER = (
    "Preliminary prospecting material. Figures, eco-point estimates and site suitability are indicative and "
    "based on available source data and commercial screening assumptions. The 8 eco-points/m2 factor is the "
    "current commercial baseline, not certified compensation. Ownership, planning, grid capacity, environmental "
    "eligibility and transferability remain subject to project-specific verification. No permit, reservation or "
    "construction readiness is represented."
)
ECO_POINTS_PER_M2 = 8          # commercial baseline from the wording above, not certified compensation
GRID_LIMIT_M = 3000
PAGE_BREAK = '<div style="page-break-after: always"></div>'   # two pages when printed / exported to PDF


def _yes(ok: bool) -> str:
    return "yes" if ok else "NO"


def _date(d) -> str:
    return str(d) if d else "–"


def _pm(u) -> str:
    return f"±{u} m" if u is not None else "–"


def _table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return "\n".join(lines + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows])


def _datasets(datasets: list[dict]) -> str:
    return _table(["Dataset", "Features", "Source dates", "Max. uncertainty"],
                  [[d["dataset"], d["n"], _date(d["oldest"]) + ("" if d["oldest"] == d["newest"] else f" to {d['newest']}"),
                    _pm(d["max_u"])] for d in datasets])


def _page2(title: str, inputs: list[list], datasets: list[dict], method: list[str]) -> str:
    return f"""{PAGE_BREAK}

# {title}: evidence and sources

**Page 2 of 2**

## Inputs this result is based on

{_table(["Input", "Feature(s) used", "Source date", "Positional uncertainty"], inputs)}

## Datasets used ({datasets[0]['country_code'] if datasets else '–'})

{_datasets(datasets)}

## Method

""" + "\n".join(f"- {m}" for m in method + [
        "All geometry is compared in EPSG:3035 (equal-area, metres); each source was delivered in its own CRS "
        "and transformed once, on promotion.",
        "Only data the data steward accepted and that meets the data contract (CRS, units, source date, "
        "uncertainty) is used; nothing missing is filled in.",
    ]) + f"""

## Limitations

> {DISCLAIMER}
"""


def _page1_footer(version: int) -> str:
    return (f"Data version {version} · CRS EPSG:3035 · "
            "Check READ_ME_FIRST.txt in the dossiers folder before use")


def bess(r: dict, version: int, datasets: list[dict]) -> str:
    title = f"BESS dossier {r['country_code']}-{r['parcel_id']}"
    margin_ok = r["substation_distance_m"] is not None and \
        abs(r["substation_distance_m"] - GRID_LIMIT_M) <= r["uncertainty_m"] + (r["substation_uncertainty_m"] or 0)
    borderline = (f"Borderline: the substation distance ({r['substation_distance_m']:,} m) is within the combined "
                  f"positional uncertainty (±{r['uncertainty_m'] + r['substation_uncertainty_m']} m) of the "
                  f"{GRID_LIMIT_M:,} m limit; verify with surveyed data.") if margin_ok else ""
    result = "candidate (passes all 4 screening rules)" + (", borderline: see below" if borderline else "")
    substation = (f"{r['substation_id']}, {r['voltage_kv']} kV, {r['substation_distance_m']:,} m"
                  if r["substation_id"] else "none of 110 kV or more in the data")
    page1 = f"""# {title}

**Page 1 of 2 · Summary**

**Result: {result}.**

{_table(["Key facts", ""], [
        ["Location (point inside the parcel, WGS84)", f"{r['lat']}, {r['lon']}"],
        ["Area", f"{r['area_m2'] / 10000:.2f} ha ({r['area_m2']:,} m²)"],
        ["Land use", r["land_use"]],
        ["Nearest substation of 110 kV or more", substation],
        ["Share inside protected areas", f"{float(r['protected_share']) * 100:.1f} %"],
    ])}

## Screening rules

{_table(["Rule", "Value", "Pass"], [
        ["Area at least 20,000 m²", f"{r['area_m2']:,} m²", _yes(r["ok_area"])],
        ["Land use arable, grassland or brownfield", r["land_use"], _yes(r["ok_land_use"])],
        ["Within 3,000 m of a substation of 110 kV or more", substation, _yes(r["ok_grid"])],
        ["At most 5 % inside protected areas", f"{float(r['protected_share']) * 100:.1f} %", _yes(r["ok_protected"])],
    ])}
{chr(10) + borderline + chr(10) if borderline else ""}
{_page1_footer(version)}

"""
    inputs = [
        ["Parcel", r["parcel_id"], _date(r["source_date"]), _pm(r["uncertainty_m"])],
        ["Nearest substation of 110 kV or more", f"{r['substation_id']} ({r['voltage_kv']} kV)" if r["substation_id"] else "none",
         _date(r["substation_source_date"]), _pm(r["substation_uncertainty_m"])],
        ["Protected areas overlapping the parcel", r["protected_areas"] or "none",
         _date(r["protected_source_date"]), _pm(r["protected_uncertainty_m"])],
    ]
    method = ["Grid distance: shortest distance from the parcel to the nearest substation of 110 kV or more.",
              "Protected share: overlapping protected areas are merged first, so no area is counted twice."]
    if borderline:
        method.append(borderline)
    return page1 + _page2(title, inputs, datasets, method)


def peat(r: dict, version: int, datasets: list[dict]) -> str:
    title = f"Peatland dossier {r['country_code']}-{r['parcel_id']}"
    eco_points = int(r["drained_area_m2"]) * ECO_POINTS_PER_M2
    page1 = f"""# {title}

**Page 1 of 2 · Summary**

**Result: candidate (passes all 3 screening rules).**

{_table(["Key facts", ""], [
        ["Location (point inside the parcel, WGS84)", f"{r['lat']}, {r['lon']}"],
        ["Area", f"{r['area_m2'] / 10000:.2f} ha ({r['area_m2']:,} m²)"],
        ["Land use", r["land_use"]],
        ["Drained peat on the parcel", f"{r['drained_area_m2']:,} m²"],
        ["Indicative eco-points", f"{eco_points:,} (drained peat area × {ECO_POINTS_PER_M2} eco-points/m², "
                                  "commercial baseline, not certified)"],
    ])}

## Screening rules

{_table(["Rule", "Value", "Pass"], [
        ["At least 30 % of the parcel on peat", f"{float(r['peat_share']) * 100:.0f} %", _yes(r["ok_peat"])],
        ["At least 30 % on drained peat", f"{float(r['drained_share']) * 100:.0f} %", _yes(r["ok_drained"])],
        ["Peat at least 30 cm deep (area-weighted)", f"{r['mean_depth_cm']} cm", _yes(r["ok_depth"])],
    ])}

{_page1_footer(version)}

"""
    inputs = [
        ["Parcel", r["parcel_id"], _date(r["source_date"]), _pm(r["uncertainty_m"])],
        ["Peat soil polygons overlapping the parcel", r["peat_features"] or "none",
         _date(r["peat_source_date"]), _pm(r["peat_uncertainty_m"])],
    ]
    method = ["Peat and drained shares: overlapping peat polygons are merged first, so no area is counted twice.",
              "Depth: mean of the peat depths, weighted by the area each polygon covers on the parcel.",
              f"Eco-points: drained peat area × {ECO_POINTS_PER_M2}, an indicative commercial figure only."]
    return page1 + _page2(title, inputs, datasets, method)
