"""The five pipeline stages. Each one takes the Context and returns counts for the manifest.
A stage signals failure by raising; the runner records it and stops."""

from pathlib import Path

from pilot.db import Context, connect

MIN_POSTGRES = 160000      # PostgreSQL 16
MIN_POSTGIS = (3, 4)

# What each dataset must contain to be promoted (the data contract).
DATASETS = {
    "parcel": {
        "table": "core.parcel", "key": "parcel_id", "types": ("POLYGON", "MULTIPOLYGON"),
        "columns": {"land_use": "string"}, "units": {},
    },
    "substation": {
        "table": "core.substation", "key": "substation_id", "types": ("POINT",),
        "columns": {"voltage_kv": "number"}, "units": {"voltage_kv": "kV"}, "positive": ("voltage_kv",),
    },
    "protected_area": {
        "table": "core.protected_area", "key": "area_id", "types": ("POLYGON", "MULTIPOLYGON"),
        "columns": {"name": "string"}, "units": {},
    },
    "peat_soil": {
        "table": "core.peat_soil", "key": "peat_id", "types": ("POLYGON", "MULTIPOLYGON"),
        "columns": {"depth_cm": "number", "drained": "boolean"}, "units": {"depth_cm": "cm"},
        "positive": ("depth_cm",),
    },
}


class StageError(Exception):
    """An expected failure with a clear, human-readable reason."""


# --------------------------------------------------------------------------- 1. prerequisites

def check_prerequisites(ctx: Context) -> dict:
    try:
        conn = connect(ctx.db_url)
    except Exception as exc:
        raise StageError(f"database not reachable: {exc}") from exc
    with conn:
        pg = conn.execute("SELECT current_setting('server_version_num')::int AS v").fetchone()["v"]
        if pg < MIN_POSTGRES:
            raise StageError(f"PostgreSQL 16+ required, found {pg}")
        ext = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'postgis'").fetchone()
        if ext is None or tuple(int(x) for x in ext["extversion"].split(".")[:2]) < MIN_POSTGIS:
            raise StageError("PostGIS 3.4+ required (run `pilot setup`)")
        if conn.execute("SELECT to_regclass('mart.peat_candidates') AS t").fetchone()["t"] is None:
            raise StageError("tables missing (run `pilot setup`)")
        accepted = {r["dataset"]: r["n"] for r in conn.execute(
            "SELECT dataset, count(*) AS n FROM staging.feature WHERE review_status = 'accepted' GROUP BY dataset")}
        missing = [ds for ds in DATASETS if not accepted.get(ds)]
        if missing:
            # Never screen without an input: e.g. no protected areas would look like "0 % overlap".
            raise StageError(f"no accepted data for: {', '.join(missing)}")
    return {"postgres": pg, "postgis": ext["extversion"], "accepted_rows": sum(accepted.values())}


# --------------------------------------------------------------------------- 2. promotion

def _problem(spec: dict) -> str:
    """SQL expression: NULL when a staged row meets its data contract, otherwise the reason."""
    types = ", ".join(f"'{t}'" for t in spec["types"])
    checks = [
        "WHEN country_code IS NULL THEN 'missing country_code'",
        "WHEN country_code !~ '^[A-Z]{2}$' THEN 'country_code must be 2 capital letters, e.g. DE'",
        "WHEN feature_id !~ '^[A-Za-z0-9_.-]+$' THEN 'feature_id may only use letters, digits, _ . -'",
        "WHEN geom IS NULL OR ST_IsEmpty(geom) THEN 'missing geometry'",
        "WHEN ST_NDims(geom) <> 2 THEN 'geometry must be 2D (x, y)'",
        "WHEN ST_SRID(geom) NOT IN (SELECT srid FROM spatial_ref_sys) THEN 'unknown CRS'",
        f"WHEN GeometryType(geom) NOT IN ({types}) THEN 'wrong geometry type'",
        "WHEN NOT ST_IsValid(geom) THEN 'invalid geometry: ' || ST_IsValidReason(geom)",
        "WHEN source_date IS NULL OR source_date > current_date THEN 'missing or future source_date'",
        # NOT (x >= 0 AND x < 'Infinity') also rejects NaN and Infinity
        "WHEN uncertainty_m IS NULL OR NOT (uncertainty_m >= 0 AND uncertainty_m < 'Infinity')"
        " THEN 'missing or invalid uncertainty_m'",
    ]
    checks += [f"WHEN jsonb_typeof(attrs -> '{c}') IS DISTINCT FROM '{t}' THEN 'missing or invalid {c}'"
               for c, t in spec["columns"].items()]
    checks += [f"WHEN units ->> '{c}' IS DISTINCT FROM '{u}' THEN '{c} must be given in {u}'"
               for c, u in spec["units"].items()]
    checks += [f"WHEN NOT (attrs ->> '{c}')::numeric > 0 THEN '{c} must be greater than 0'"
               for c in spec.get("positive", ())]
    return "CASE " + " ".join(checks) + " END"


def _value(column: str, json_type: str) -> str:
    cast = {"string": "", "number": "::numeric", "boolean": "::boolean"}[json_type]
    return f"(attrs ->> '{column}'){cast}"


def promote(ctx: Context) -> dict:
    """Make core exactly match the staged rows that are accepted AND meet the data contract:
    insert or update those rows, delete rows that were withdrawn or became invalid.

    Rerun-safe: rows that are already identical are not touched, and data_version only goes up
    when something really changed. Everything happens in one transaction."""
    changed = valid = 0
    rejected: list[str] = []
    with connect(ctx.db_url) as conn:
        for dataset, spec in DATASETS.items():
            problem = _problem(spec)
            usable = 0
            for row in conn.execute(
                f"SELECT feature_id, {problem} AS problem FROM staging.feature"
                " WHERE dataset = %s AND review_status = 'accepted'", (dataset,)
            ):
                if row["problem"]:
                    rejected.append(f"{dataset} {row['feature_id']}: {row['problem']}")
                else:
                    usable += 1
            if usable == 0:  # never screen with an empty input (it would read as "0 % overlap")
                first = next((r for r in rejected if r.startswith(dataset)), "none accepted")
                raise StageError(f"no usable {dataset} data: all accepted rows break the data contract "
                                 f"(first: {first})")
            valid += usable

            cols = list(spec["columns"])
            geom = "ST_Transform(geom, 3035)" if spec["types"] == ("POINT",) else "ST_Multi(ST_Transform(geom, 3035))"
            all_cols = cols + ["geom", "source_date", "uncertainty_m"]
            changed += conn.execute(f"""
                INSERT INTO {spec['table']} AS t (country_code, {spec['key']}, {', '.join(all_cols)})
                SELECT country_code, feature_id, {', '.join(_value(c, t) for c, t in spec['columns'].items())},
                       {geom}, source_date, uncertainty_m
                FROM staging.feature
                WHERE dataset = %s AND review_status = 'accepted' AND ({problem}) IS NULL
                ON CONFLICT (country_code, {spec['key']}) DO UPDATE
                SET {', '.join(f'{c} = EXCLUDED.{c}' for c in all_cols)}
                WHERE ({', '.join(f't.{c}' for c in all_cols)})
                      IS DISTINCT FROM ({', '.join(f'EXCLUDED.{c}' for c in all_cols)})
            """, (dataset,)).rowcount
            # Withdrawn by the data steward: remove from core. (A row that is accepted but now
            # invalid keeps its last good version and is listed under LEFT OUT - a bad delivery
            # must never delete good data, e.g. a nature reserve.)
            changed += conn.execute(f"""
                DELETE FROM {spec['table']} t WHERE NOT EXISTS (
                    SELECT 1 FROM staging.feature
                    WHERE dataset = %s AND review_status = 'accepted'
                      AND country_code = t.country_code AND feature_id = t.{spec['key']})
            """, (dataset,)).rowcount

        if changed:
            conn.execute("UPDATE ops.state SET value = value + 1 WHERE key = 'data_version'")
            conn.execute("ANALYZE core.parcel, core.substation, core.protected_area, core.peat_soil")
        not_accepted = conn.execute(
            "SELECT count(*) AS n FROM staging.feature WHERE review_status <> 'accepted'").fetchone()["n"]
    return {"valid": valid, "changed": changed, "rejected": len(rejected),
            "not_accepted": not_accepted, "rejected_rows": rejected}


# --------------------------------------------------------------------------- 3 + 4. views

def mark_built(conn, artifact: str) -> None:
    conn.execute(
        "UPDATE ops.artifact SET status = 'ok', built_at = now(), error = NULL,"
        " data_version = (SELECT value FROM ops.state WHERE key = 'data_version') WHERE name = %s",
        (artifact,))


def _refresh(ctx: Context, view: str, artifact: str) -> dict:
    with connect(ctx.db_url) as conn:
        conn.execute(f"REFRESH MATERIALIZED VIEW {view}")
        stats = conn.execute(
            f"SELECT count(*) AS parcels, count(*) FILTER (WHERE is_candidate) AS candidates FROM {view}"
        ).fetchone()
        mark_built(conn, artifact)
    return stats


def refresh_bess(ctx: Context) -> dict:
    return _refresh(ctx, "mart.bess_candidates", "bess_view")


def refresh_peat(ctx: Context) -> dict:
    return _refresh(ctx, "mart.peat_candidates", "peat_view")


# --------------------------------------------------------------------------- 5. dossiers

SAMPLE_SIZE = 3


def _yes(ok: bool) -> str:
    return "yes" if ok else "NO"


def _bess_dossier(r: dict, version: int) -> str:
    return f"""# BESS dossier: {r['country_code']}-{r['parcel_id']}

Land use: {r['land_use']} | Area: {r['area_m2']:,} m²

| Rule | Value | Pass |
|---|---|---|
| Area at least 20,000 m² | {r['area_m2']:,} m² | {_yes(r['ok_area'])} |
| Land use arable, grassland or brownfield | {r['land_use']} | {_yes(r['ok_land_use'])} |
| Within 3,000 m of a substation of 110 kV or more | {r['substation_distance_m']} m ({r['substation_id']}, {r['voltage_kv']} kV) | {_yes(r['ok_grid'])} |
| At most 5 % inside protected areas | {float(r['protected_share']) * 100:.1f} % | {_yes(r['ok_protected'])} |

Source date: {r['source_date']} | Positional uncertainty: ±{r['uncertainty_m']} m | CRS: EPSG:3035 | Data version: {version} | Check READ_ME_FIRST.txt in the dossiers folder before use
"""


def _peat_dossier(r: dict, version: int) -> str:
    return f"""# Peatland dossier: {r['country_code']}-{r['parcel_id']}

Land use: {r['land_use']} | Area: {r['area_m2']:,} m²

| Rule | Value | Pass |
|---|---|---|
| At least 30 % of the parcel on peat | {float(r['peat_share']) * 100:.0f} % | {_yes(r['ok_peat'])} |
| At least 30 % on drained peat | {float(r['drained_share']) * 100:.0f} % | {_yes(r['ok_drained'])} |
| Peat at least 30 cm deep (area-weighted) | {r['mean_depth_cm']} cm | {_yes(r['ok_depth'])} |

Source date: {r['source_date']} | Positional uncertainty: ±{r['uncertainty_m']} m | CRS: EPSG:3035 | Data version: {version} | Check READ_ME_FIRST.txt in the dossiers folder before use
"""


VERTICALS = [
    # (folder, view, order: best first, renderer, artifact)
    ("bess", "mart.bess_candidates", "substation_distance_m, parcel_id", _bess_dossier, "bess_dossiers"),
    ("peat", "mart.peat_candidates", "peat_share DESC, parcel_id", _peat_dossier, "peat_dossiers"),
]


def write_atomic(path: Path, text: str) -> None:
    """Write via a temp file + rename, so a crash never leaves a half-written file."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def export_dossiers(ctx: Context) -> dict:
    counts = {}
    with connect(ctx.db_url) as conn:
        version = conn.execute("SELECT value FROM ops.state WHERE key = 'data_version'").fetchone()["value"]
        for folder, view, order, render, artifact in VERTICALS:
            rows = conn.execute(
                f"SELECT * FROM {view} WHERE is_candidate ORDER BY {order} LIMIT {SAMPLE_SIZE}").fetchall()
            target = ctx.out_dir / "dossiers" / folder
            target.mkdir(parents=True, exist_ok=True)
            names = {f"{r['country_code']}-{r['parcel_id']}.md" for r in rows}
            for r in rows:
                write_atomic(target / f"{r['country_code']}-{r['parcel_id']}.md", render(r, version))
            for old in target.glob("*.md"):          # rerun-safe: remove dossiers no longer selected
                if old.name not in names:
                    old.unlink()
            mark_built(conn, artifact)
            counts[folder] = len(rows)
    return counts
