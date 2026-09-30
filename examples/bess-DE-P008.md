# BESS dossier DE-P008

**Page 1 of 2 · Summary**

**Result: candidate (passes all 4 screening rules), borderline: see below.**

| Key facts |  |
|---|---|
| Location (point inside the parcel, WGS84) | 49.47685, 8.73972 |
| Area | 6.00 ha (60,048 m²) |
| Land use | grassland |
| Nearest substation of 110 kV or more | S2, 380 kV, 2,997 m |
| Share inside protected areas | 0.0 % |

## Screening rules

| Rule | Value | Pass |
|---|---|---|
| Area at least 20,000 m² | 60,048 m² | yes |
| Land use arable, grassland or brownfield | grassland | yes |
| Within 3,000 m of a substation of 110 kV or more | S2, 380 kV, 2,997 m | yes |
| At most 5 % inside protected areas | 0.0 % | yes |

Borderline: the substation distance (2,997 m) is within the combined positional uncertainty (±7.5 m) of the 3,000 m limit; verify with surveyed data.

Data version 1 · CRS EPSG:3035 · Check READ_ME_FIRST.txt in the dossiers folder before use

<div style="page-break-after: always"></div>

# BESS dossier DE-P008: evidence and sources

**Page 2 of 2**

## Inputs this result is based on

| Input | Feature(s) used | Source date | Positional uncertainty |
|---|---|---|---|
| Parcel | P008 | 2026-06-30 | ±2.5 m |
| Nearest substation of 110 kV or more | S2 (380 kV) | 2026-05-15 | ±5 m |
| Protected areas overlapping the parcel | none | – | – |

## Datasets used (DE)

| Dataset | Features | Source dates | Max. uncertainty |
|---|---|---|---|
| parcel | 13 | 2026-06-30 | ±2.5 m |
| substation | 5 | 2026-05-15 | ±5 m |
| protected_area | 2 | 2026-01-31 | ±10 m |

## Method

- Grid distance: shortest distance from the parcel to the nearest substation of 110 kV or more.
- Protected share: overlapping protected areas are merged first, so no area is counted twice.
- Borderline: the substation distance (2,997 m) is within the combined positional uncertainty (±7.5 m) of the 3,000 m limit; verify with surveyed data.
- All geometry is compared in EPSG:3035 (equal-area, metres); each source was delivered in its own CRS and transformed once, on promotion.
- Only data the data steward accepted and that meets the data contract (CRS, units, source date, uncertainty) is used; nothing missing is filled in.

## Limitations

> Preliminary prospecting material. Figures, eco-point estimates and site suitability are indicative and based on available source data and commercial screening assumptions. The 8 eco-points/m2 factor is the current commercial baseline, not certified compensation. Ownership, planning, grid capacity, environmental eligibility and transferability remain subject to project-specific verification. No permit, reservation or construction readiness is represented.
