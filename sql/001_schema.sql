-- Tables. Safe to run again (IF NOT EXISTS).
--   staging : data as delivered, with its data contract and the data steward's decision
--   core    : validated, promoted data (one CRS: EPSG:3035, metres, equal-area)
--   ops     : what the pipeline needs to show stale / failed outputs

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS ops;

-- One row per delivered feature. Nothing here is trusted until promotion checks it.
CREATE TABLE IF NOT EXISTS staging.feature (
    dataset        text    NOT NULL CHECK (dataset IN ('parcel', 'substation', 'protected_area', 'peat_soil')),
    country_code   text,                 -- checked on promotion (must be present)
    feature_id     text    NOT NULL,
    attrs          jsonb   NOT NULL DEFAULT '{}',
    geom           geometry,             -- in the delivered CRS; the SRID says which one
    source_date    date,                 -- data contract: when the source produced it
    units          jsonb   NOT NULL DEFAULT '{}',  -- data contract: e.g. {"voltage_kv": "kV"}
    uncertainty_m  numeric,              -- data contract: positional uncertainty in metres
    review_status  text    NOT NULL CHECK (review_status IN ('pending', 'accepted', 'rejected')),
    UNIQUE NULLS NOT DISTINCT (dataset, country_code, feature_id)
);

-- Promoted data. Every table: non-null country_code, country-scoped key, canonical `geom`.
CREATE TABLE IF NOT EXISTS core.parcel (
    country_code   char(2) NOT NULL,
    parcel_id      text    NOT NULL,
    land_use       text    NOT NULL,
    geom           geometry(MultiPolygon, 3035) NOT NULL,
    source_date    date    NOT NULL,
    uncertainty_m  numeric NOT NULL,
    PRIMARY KEY (country_code, parcel_id)
);

CREATE TABLE IF NOT EXISTS core.substation (
    country_code   char(2) NOT NULL,
    substation_id  text    NOT NULL,
    voltage_kv     numeric NOT NULL,     -- unit enforced on promotion: kV
    geom           geometry(Point, 3035) NOT NULL,
    source_date    date    NOT NULL,
    uncertainty_m  numeric NOT NULL,
    PRIMARY KEY (country_code, substation_id)
);

CREATE TABLE IF NOT EXISTS core.protected_area (
    country_code   char(2) NOT NULL,
    area_id        text    NOT NULL,
    name           text    NOT NULL,
    geom           geometry(MultiPolygon, 3035) NOT NULL,
    source_date    date    NOT NULL,
    uncertainty_m  numeric NOT NULL,
    PRIMARY KEY (country_code, area_id)
);

CREATE TABLE IF NOT EXISTS core.peat_soil (
    country_code   char(2) NOT NULL,
    peat_id        text    NOT NULL,
    depth_cm       numeric NOT NULL,     -- unit enforced on promotion: cm
    drained        boolean NOT NULL,
    geom           geometry(MultiPolygon, 3035) NOT NULL,
    source_date    date    NOT NULL,
    uncertainty_m  numeric NOT NULL,
    PRIMARY KEY (country_code, peat_id)
);

CREATE INDEX IF NOT EXISTS parcel_geom_idx         ON core.parcel         USING gist (geom);
CREATE INDEX IF NOT EXISTS substation_geom_idx     ON core.substation     USING gist (geom);
CREATE INDEX IF NOT EXISTS protected_area_geom_idx ON core.protected_area USING gist (geom);
CREATE INDEX IF NOT EXISTS peat_soil_geom_idx      ON core.peat_soil      USING gist (geom);

-- data_version goes up by 1 every time promotion actually changes core data.
CREATE TABLE IF NOT EXISTS ops.state (
    key    text PRIMARY KEY,
    value  bigint NOT NULL
);
INSERT INTO ops.state VALUES ('data_version', 0) ON CONFLICT DO NOTHING;

-- One row per output. An output is STALE if its last attempt failed, it was never built,
-- or it was built from an older data_version than the current one.
CREATE TABLE IF NOT EXISTS ops.artifact (
    name          text PRIMARY KEY,
    status        text NOT NULL DEFAULT 'never built' CHECK (status IN ('never built', 'ok', 'failed')),
    built_at      timestamptz,
    data_version  bigint,
    error         text
);
INSERT INTO ops.artifact (name) VALUES
    ('bess_view'), ('peat_view'), ('bess_dossiers'), ('peat_dossiers')
ON CONFLICT DO NOTHING;
