-- Deterministic pilot fixture: one synthetic region near Mannheim (DE).
-- Each row states its data contract explicitly: CRS (geometry SRID), units, source date,
-- positional uncertainty, and the data steward's review decision.
-- P900 (self-intersecting), P901 (no country_code) and S5 (no voltage) are deliberately invalid.
-- P902 is still 'pending' review, so it must never be promoted.

-- parcel: declared CRS EPSG:25832, source date 2026-06-30, uncertainty ±2.5 m, units n/a
INSERT INTO staging.feature (dataset, country_code, feature_id, attrs, geom, source_date, units, uncertainty_m, review_status) VALUES
  ('parcel', 'DE', 'P001', '{"land_use": "arable"}', ST_GeomFromText('POLYGON((471300 5481400,471600 5481400,471600 5481600,471300 5481600,471300 5481400))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', 'DE', 'P002', '{"land_use": "arable"}', ST_GeomFromText('POLYGON((470200 5481200,470350 5481200,470350 5481300,470200 5481300,470200 5481200))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', 'DE', 'P003', '{"land_use": "grassland"}', ST_GeomFromText('POLYGON((463000 5488000,463400 5488000,463400 5488300,463000 5488300,463000 5488000))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', 'DE', 'P004', '{"land_use": "arable"}', ST_GeomFromText('POLYGON((472000 5479000,472300 5479000,472300 5479300,472000 5479300,472000 5479000))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', 'DE', 'P005', '{"land_use": "brownfield"}', ST_GeomFromText('POLYGON((479000 5479000,479250 5479000,479250 5479160,479000 5479160,479000 5479000))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', 'DE', 'P006', '{"land_use": "forest"}', ST_GeomFromText('POLYGON((470500 5482000,470800 5482000,470800 5482300,470500 5482300,470500 5482000))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', 'DE', 'P007', '{"land_use": "arable"}', ST_GeomFromText('POLYGON((473500 5487000,473800 5487000,473800 5487200,473500 5487200,473500 5487000))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', 'DE', 'P008', '{"land_use": "grassland"}', ST_GeomFromText('POLYGON((480995 5480400,481295 5480400,481295 5480600,480995 5480600,480995 5480400))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', 'DE', 'P009', '{"land_use": "grassland"}', ST_GeomFromText('POLYGON((465000 5495000,465400 5495000,465400 5495300,465000 5495300,465000 5495000))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', 'DE', 'P010', '{"land_use": "grassland"}', ST_GeomFromText('POLYGON((466000 5495000,466300 5495000,466300 5495300,466000 5495300,466000 5495000))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', 'DE', 'P011', '{"land_use": "arable"}', ST_GeomFromText('POLYGON((467000 5495000,467300 5495000,467300 5495300,467000 5495300,467000 5495000))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', 'DE', 'P012', '{"land_use": "arable"}', ST_GeomFromText('POLYGON((468000 5495000,468300 5495000,468300 5495300,468000 5495300,468000 5495000))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', 'DE', 'P013', '{"land_use": "grassland"}', ST_GeomFromText('POLYGON((469000 5495000,469400 5495000,469400 5495400,469000 5495400,469000 5495000))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', 'DE', 'P900', '{"land_use": "arable"}', ST_GeomFromText('POLYGON((470000 5483000,470300 5483300,470300 5483000,470000 5483300,470000 5483000))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', NULL, 'P901', '{"land_use": "arable"}', ST_GeomFromText('POLYGON((470000 5484000,470300 5484000,470300 5484300,470000 5484300,470000 5484000))', 25832), DATE '2026-06-30', '{}', 2.5, 'accepted'),
  ('parcel', 'DE', 'P902', '{"land_use": "arable"}', ST_GeomFromText('POLYGON((471700 5481500,472000 5481500,472000 5481700,471700 5481700,471700 5481500))', 25832), DATE '2026-06-30', '{}', 2.5, 'pending')
ON CONFLICT DO NOTHING;

-- substation: declared CRS EPSG:4326, source date 2026-05-15, uncertainty ±5.0 m, units {'voltage_kv': 'kV'}
INSERT INTO staging.feature (dataset, country_code, feature_id, attrs, geom, source_date, units, uncertainty_m, review_status) VALUES
  ('substation', 'DE', 'S1', '{"voltage_kv": 110}', ST_GeomFromText('POINT(8.5996443 49.4809503)', 4326), DATE '2026-05-15', '{"voltage_kv": "kV"}', 5.0, 'accepted'),
  ('substation', 'DE', 'S2', '{"voltage_kv": 380}', ST_GeomFromText('POINT(8.6963081 49.476747)', 4326), DATE '2026-05-15', '{"voltage_kv": "kV"}', 5.0, 'accepted'),
  ('substation', 'DE', 'S3', '{"voltage_kv": 20}', ST_GeomFromText('POINT(8.6407304 49.5260594)', 4326), DATE '2026-05-15', '{"voltage_kv": "kV"}', 5.0, 'accepted'),
  ('substation', 'DE', 'S4', '{"voltage_kv": 110}', ST_GeomFromText('POINT(8.6680309 49.5756123)', 4326), DATE '2026-05-15', '{"voltage_kv": "kV"}', 5.0, 'accepted'),
  ('substation', 'DE', 'S5', '{}', ST_GeomFromText('POINT(8.6548014 49.4901229)', 4326), DATE '2026-05-15', '{"voltage_kv": "kV"}', 5.0, 'accepted'),
  ('substation', 'DE', 'S6', '{"voltage_kv": 220}', ST_GeomFromText('POINT(8.4764549 49.3815133)', 4326), DATE '2026-05-15', '{"voltage_kv": "kV"}', 5.0, 'accepted')
ON CONFLICT DO NOTHING;

-- protected_area: declared CRS EPSG:4326, source date 2026-01-31, uncertainty ±10.0 m, units n/a
INSERT INTO staging.feature (dataset, country_code, feature_id, attrs, geom, source_date, units, uncertainty_m, review_status) VALUES
  ('protected_area', 'DE', 'PA1', '{"name": "Naturschutzgebiet"}', ST_GeomFromText('POLYGON((8.615675 49.4612158,8.6225747 49.4612386,8.6225264 49.4675348,8.6156257 49.4675121,8.615675 49.4612158))', 4326), DATE '2026-01-31', '{}', 10.0, 'accepted'),
  ('protected_area', 'DE', 'PA2', '{"name": "FFH-Gebiet"}', ST_GeomFromText('POLYGON((8.570911 49.609293,8.5764475 49.6093134,8.5764319 49.6111123,8.5708952 49.6110919,8.570911 49.609293))', 4326), DATE '2026-01-31', '{}', 10.0, 'accepted')
ON CONFLICT DO NOTHING;

-- peat_soil: declared CRS EPSG:25832, source date 2025-11-01, uncertainty ±25.0 m, units {'depth_cm': 'cm'}
INSERT INTO staging.feature (dataset, country_code, feature_id, attrs, geom, source_date, units, uncertainty_m, review_status) VALUES
  ('peat_soil', 'DE', 'PS1', '{"depth_cm": 120, "drained": true}', ST_GeomFromText('POLYGON((465000 5495000,465320 5495000,465320 5495300,465000 5495300,465000 5495000))', 25832), DATE '2025-11-01', '{"depth_cm": "cm"}', 25.0, 'accepted'),
  ('peat_soil', 'DE', 'PS2', '{"depth_cm": 150, "drained": false}', ST_GeomFromText('POLYGON((466000 5495000,466300 5495000,466300 5495300,466000 5495300,466000 5495000))', 25832), DATE '2025-11-01', '{"depth_cm": "cm"}', 25.0, 'accepted'),
  ('peat_soil', 'DE', 'PS3', '{"depth_cm": 20, "drained": true}', ST_GeomFromText('POLYGON((467000 5495000,467300 5495000,467300 5495300,467000 5495300,467000 5495000))', 25832), DATE '2025-11-01', '{"depth_cm": "cm"}', 25.0, 'accepted'),
  ('peat_soil', 'DE', 'PS4', '{"depth_cm": 100, "drained": true}', ST_GeomFromText('POLYGON((468000 5495000,468030 5495000,468030 5495300,468000 5495300,468000 5495000))', 25832), DATE '2025-11-01', '{"depth_cm": "cm"}', 25.0, 'accepted'),
  ('peat_soil', 'DE', 'PS5', '{"depth_cm": 90, "drained": true}', ST_GeomFromText('POLYGON((469000 5495000,469400 5495000,469400 5495240,469000 5495240,469000 5495000))', 25832), DATE '2025-11-01', '{"depth_cm": "cm"}', 25.0, 'accepted')
ON CONFLICT DO NOTHING;
