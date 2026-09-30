# Peatland dossier DE-P009

**Page 1 of 2 · Summary**

**Result: candidate (passes all 3 screening rules).**

| Key facts |  |
|---|---|
| Location (point inside the parcel, WGS84) | 49.60792, 8.51833 |
| Area | 12.01 ha (120,092 m²) |
| Land use | grassland |
| Drained peat on the parcel | 96,074 m² |
| Indicative eco-points | 768,592 (drained peat area × 8 eco-points/m², commercial baseline, not certified) |

## Screening rules

| Rule | Value | Pass |
|---|---|---|
| At least 30 % of the parcel on peat | 80 % | yes |
| At least 30 % on drained peat | 80 % | yes |
| Peat at least 30 cm deep (area-weighted) | 120 cm | yes |

Data version 1 · CRS EPSG:3035 · Check READ_ME_FIRST.txt in the dossiers folder before use

<div style="page-break-after: always"></div>

# Peatland dossier DE-P009: evidence and sources

**Page 2 of 2**

## Inputs this result is based on

| Input | Feature(s) used | Source date | Positional uncertainty |
|---|---|---|---|
| Parcel | P009 | 2026-06-30 | ±2.5 m |
| Peat soil polygons overlapping the parcel | PS1 (120 cm, drained) | 2025-11-01 | ±25 m |

## Datasets used (DE)

| Dataset | Features | Source dates | Max. uncertainty |
|---|---|---|---|
| parcel | 13 | 2026-06-30 | ±2.5 m |
| peat_soil | 5 | 2025-11-01 | ±25 m |

## Method

- Peat and drained shares: overlapping peat polygons are merged first, so no area is counted twice.
- Depth: mean of the peat depths, weighted by the area each polygon covers on the parcel.
- Eco-points: drained peat area × 8, an indicative commercial figure only.
- All geometry is compared in EPSG:3035 (equal-area, metres); each source was delivered in its own CRS and transformed once, on promotion.
- Only data the data steward accepted and that meets the data contract (CRS, units, source date, uncertainty) is used; nothing missing is filled in.

## Limitations

> Preliminary prospecting material. Figures, eco-point estimates and site suitability are indicative and based on available source data and commercial screening assumptions. The 8 eco-points/m2 factor is the current commercial baseline, not certified compensation. Ownership, planning, grid capacity, environmental eligibility and transferability remain subject to project-specific verification. No permit, reservation or construction readiness is represented.
