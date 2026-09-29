-- Screening views. One row per parcel with a yes/no per rule, so every result is explainable.
-- All geometry is EPSG:3035, so ST_Area is in m² and ST_Distance in metres.

-- BESS (battery storage): big enough, allowed land use, close to a high-voltage substation,
-- (almost) no overlap with protected areas.
CREATE MATERIALIZED VIEW IF NOT EXISTS mart.bess_candidates AS
SELECT
    p.country_code,
    p.parcel_id,
    p.land_use,
    round(ST_Area(p.geom)::numeric)                            AS area_m2,
    s.substation_id,
    s.voltage_kv,
    round(s.distance_m::numeric)                               AS substation_distance_m,
    round(coalesce(pa.share, 0)::numeric, 3)                   AS protected_share,
    ST_Area(p.geom) >= 20000                                   AS ok_area,          -- ≥ 2 ha
    p.land_use IN ('arable', 'grassland', 'brownfield')        AS ok_land_use,
    coalesce(s.distance_m <= 3000, false)                      AS ok_grid,          -- ≤ 3 km to ≥ 110 kV
    coalesce(pa.share, 0) <= 0.05                              AS ok_protected,     -- ≤ 5 % protected
    ST_Area(p.geom) >= 20000
      AND p.land_use IN ('arable', 'grassland', 'brownfield')
      AND coalesce(s.distance_m <= 3000, false)
      AND coalesce(pa.share, 0) <= 0.05                        AS is_candidate,
    p.source_date,
    p.uncertainty_m
FROM core.parcel p
LEFT JOIN LATERAL (                      -- nearest substation of at least 110 kV (uses the GiST index)
    SELECT s.substation_id, s.voltage_kv, ST_Distance(s.geom, p.geom) AS distance_m
    FROM core.substation s
    WHERE s.country_code = p.country_code AND s.voltage_kv >= 110
    ORDER BY s.geom <-> p.geom
    LIMIT 1
) s ON true
LEFT JOIN LATERAL (                      -- share of the parcel inside protected areas (union: no double counting)
    SELECT ST_Area(ST_Intersection(p.geom, ST_Union(a.geom))) / ST_Area(p.geom) AS share
    FROM core.protected_area a
    WHERE a.country_code = p.country_code AND ST_Intersects(a.geom, p.geom)
) pa ON true
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS bess_candidates_key ON mart.bess_candidates (country_code, parcel_id);

-- Peatland (rewetting): mostly on peat, that peat is drained, and it is deep enough.
CREATE MATERIALIZED VIEW IF NOT EXISTS mart.peat_candidates AS
SELECT
    p.country_code,
    p.parcel_id,
    p.land_use,
    round(ST_Area(p.geom)::numeric)                            AS area_m2,
    round(coalesce(pk.peat_share, 0)::numeric, 3)              AS peat_share,
    round(coalesce(pk.drained_share, 0)::numeric, 3)           AS drained_share,
    round(pk.mean_depth_cm::numeric)                           AS mean_depth_cm,
    coalesce(pk.peat_share, 0) >= 0.30                         AS ok_peat,          -- ≥ 30 % peat
    coalesce(pk.drained_share, 0) >= 0.30                      AS ok_drained,       -- ≥ 30 % drained peat
    coalesce(pk.mean_depth_cm >= 30, false)                    AS ok_depth,         -- ≥ 30 cm deep
    coalesce(pk.peat_share, 0) >= 0.30
      AND coalesce(pk.drained_share, 0) >= 0.30
      AND coalesce(pk.mean_depth_cm >= 30, false)              AS is_candidate,
    p.source_date,
    p.uncertainty_m
FROM core.parcel p
LEFT JOIN LATERAL (
    SELECT ST_Area(ST_Union(x.part)) / ST_Area(p.geom)                                  AS peat_share,
           coalesce(ST_Area(ST_Union(x.part) FILTER (WHERE x.drained)), 0) / ST_Area(p.geom) AS drained_share,
           sum(x.depth_cm * ST_Area(x.part)) / nullif(sum(ST_Area(x.part)), 0)          AS mean_depth_cm
    FROM (
        SELECT ps.depth_cm, ps.drained, ST_Intersection(ps.geom, p.geom) AS part
        FROM core.peat_soil ps
        WHERE ps.country_code = p.country_code AND ST_Intersects(ps.geom, p.geom)
    ) x
) pk ON true
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS peat_candidates_key ON mart.peat_candidates (country_code, parcel_id);
