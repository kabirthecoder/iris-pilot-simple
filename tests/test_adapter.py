"""The source adapter: one GeoJSON loader for every dataset and country."""

import json

from pilot import cli
from pilot.adapters import load_geojson
from pilot.db import ROOT, connect
from pilot.runner import run_pipeline

PARCELS = ROOT / "fixtures" / "de" / "parcel.geojson"


def delivery(tmp_path, name="delivery.geojson", **changes) -> "Path":
    """A copy of the DE parcel fixture with some file-level fields changed."""
    data = json.loads(PARCELS.read_text())
    data.update(changes)
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


def staged(ctx, sql: str, *args):
    with connect(ctx.db_url) as conn:
        return conn.execute(sql, args).fetchall()


def test_loading_the_same_file_twice_changes_nothing(ctx):
    assert load_geojson(ctx.db_url, PARCELS)["changed"] == 0     # already loaded by setup


def test_same_ids_in_another_country_stay_separate(ctx):
    """An NL delivery reuses the ids P001... - rows, keys and joins are country-scoped."""
    load_geojson(ctx.db_url, delivery(ctx.out_dir.parent, country_code="NL"))
    run = run_pipeline(ctx)

    assert run["status"] == "succeeded"
    rows = staged(ctx, "SELECT country_code, ok_grid FROM mart.bess_candidates WHERE parcel_id = 'P001'")
    assert {r["country_code"]: r["ok_grid"] for r in rows} == {"DE": True, "NL": False}  # no NL substations
    assert not list((ctx.out_dir / "dossiers" / "bess").glob("NL-*"))


def test_file_without_crs_is_loaded_but_never_promoted(ctx):
    load_geojson(ctx.db_url, delivery(ctx.out_dir.parent, country_code="AT", crs=None))
    rejected = run_pipeline(ctx)["stages"][1]["counts"]["rejected_rows"]
    assert "parcel P001: unknown CRS" in rejected             # the adapter did not assume WGS84


def test_changed_redelivery_waits_for_review_and_keeps_last_good_version(ctx):
    run_pipeline(ctx)
    data = json.loads(PARCELS.read_text())
    p001 = data["features"][0]
    p001["properties"] = {"land_use": "forest"}                # changed, and no review decision
    path = ctx.out_dir.parent / "redelivery.geojson"
    path.write_text(json.dumps(data))

    assert load_geojson(ctx.db_url, path)["changed"] == 1
    assert staged(ctx, "SELECT review_status FROM staging.feature WHERE feature_id = 'P001'")[0][
        "review_status"] == "pending"
    run_pipeline(ctx)
    assert staged(ctx, "SELECT land_use FROM core.parcel WHERE parcel_id = 'P001'")[0]["land_use"] == "arable"


def test_broken_file_is_not_loaded_at_all(ctx, monkeypatch, capsys):
    data = json.loads(PARCELS.read_text())
    data["features"][5]["geometry"] = {"type": "Polygon", "coordinates": "broken"}
    for f in data["features"]:
        f["id"] = "NEW-" + f["id"]
    path = ctx.out_dir.parent / "broken.geojson"
    path.write_text(json.dumps(data))
    monkeypatch.setenv("PILOT_DATABASE_URL", ctx.db_url)

    assert cli.main(["load", str(path)]) == 1
    assert "NOT loaded: broken.geojson, feature NEW-P006" in capsys.readouterr().out
    assert staged(ctx, "SELECT count(*) AS n FROM staging.feature WHERE feature_id LIKE 'NEW-%%'")[0]["n"] == 0
