"""Source adapter: loads one delivery file (GeoJSON) into staging.

One adapter for every dataset and every country. The file itself says which dataset and which
country it is, plus its data contract: CRS, source date, positional uncertainty and units.
A feature may override any of these for itself (e.g. "country_code": null).

The adapter copies what the file says and never fills anything in. A missing value stays
missing, and promotion rejects that row with a reason. For example, a file without a CRS is
loaded with SRID 0 and rejected as "unknown CRS". GeoJSON (RFC 7946) would imply WGS84, but
the data contract needs the CRS to be stated.

Controlled promotion: a feature's review_status comes from the file if the file gives one.
Otherwise a new or changed feature is 'pending', so the data steward must look at it again,
and an unchanged feature keeps its current decision. Loading the same file twice changes
nothing, and one delivery is loaded in one transaction: all of it or nothing.
"""

import json
import re
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from pilot.db import connect
from pilot.stages import DATASETS, StageError

CONTRACT = ("country_code", "source_date", "uncertainty_m", "units")   # file-level, per-feature override

UPSERT = """
INSERT INTO staging.feature AS t
       (dataset, country_code, feature_id, attrs, geom, source_date, units, uncertainty_m, review_status)
VALUES (%(dataset)s, %(country_code)s, %(id)s, %(attrs)s, ST_SetSRID(ST_GeomFromGeoJSON(%(geom)s), %(srid)s),
        %(source_date)s, %(units)s, %(uncertainty_m)s, coalesce(%(status)s::text, 'pending'))
ON CONFLICT (dataset, country_code, feature_id) DO UPDATE
SET attrs = EXCLUDED.attrs, geom = EXCLUDED.geom, source_date = EXCLUDED.source_date,
    units = EXCLUDED.units, uncertainty_m = EXCLUDED.uncertainty_m,
    review_status = coalesce(%(status)s::text, 'pending')
WHERE (t.attrs, t.geom, t.source_date, t.units, t.uncertainty_m)
      IS DISTINCT FROM (EXCLUDED.attrs, EXCLUDED.geom, EXCLUDED.source_date, EXCLUDED.units, EXCLUDED.uncertainty_m)
   OR (%(status)s::text IS NOT NULL AND t.review_status IS DISTINCT FROM %(status)s::text)
"""


def declared_srid(collection: dict) -> int:
    """EPSG code from the file's "crs" member, e.g. "urn:ogc:def:crs:EPSG::25832" -> 25832. 0 = not stated."""
    name = ((collection.get("crs") or {}).get("properties") or {}).get("name") or ""
    match = re.search(r"EPSG:+(\d+)$", name)
    return int(match.group(1)) if match else 0


def load_geojson(db_url: str, path: Path) -> dict:
    path = Path(path)
    try:
        collection = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StageError(f"{path.name}: not a readable JSON file ({exc})") from exc
    if collection.get("type") != "FeatureCollection":
        raise StageError(f"{path.name}: must be a GeoJSON FeatureCollection")
    dataset = collection.get("dataset")
    if dataset not in DATASETS:
        raise StageError(f"{path.name}: 'dataset' must be one of {', '.join(DATASETS)}")
    srid = declared_srid(collection)

    changed = 0
    features = collection.get("features") or []
    with connect(db_url) as conn:                      # one delivery = one transaction
        for feature in features:
            props = dict(feature.get("properties") or {})
            fid = feature.get("id", props.pop("id", None))
            if fid is None:
                raise StageError(f"{path.name}: every feature needs an id")
            row = {key: props.pop(key) if key in props else collection.get(key) for key in CONTRACT}
            row.update(dataset=dataset, id=str(fid), srid=srid, status=props.pop("review_status", None),
                       units=Jsonb(row["units"] or {}), attrs=Jsonb(props),
                       geom=json.dumps(feature["geometry"]) if feature.get("geometry") else None)
            try:
                changed += conn.execute(UPSERT, row).rowcount
            except psycopg.Error as exc:
                raise StageError(f"{path.name}, feature {fid}: {exc.diag.message_primary}") from exc
    return {"file": path.name, "dataset": dataset, "country_code": collection.get("country_code"),
            "features": len(features), "changed": changed}
