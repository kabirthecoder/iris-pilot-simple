"""Tests for the four acceptance criteria, plus the data contract."""

import json

import pytest

from pilot import cli
from pilot.db import connect
from pilot.manifest import output_states
from pilot.runner import STAGES, Stage, run_pipeline


def statuses(run: dict) -> dict:
    return {s["name"]: s["status"] for s in run["stages"]}


def states(ctx) -> dict:
    return {o["name"]: o for o in output_states(ctx)}


def candidates(ctx, view: str) -> set:
    with connect(ctx.db_url) as conn:
        return {r["parcel_id"] for r in conn.execute(f"SELECT parcel_id FROM {view} WHERE is_candidate")}


def with_stage(name: str, fn) -> list:
    """The normal pipeline, with one stage's code replaced (to simulate a failure)."""
    return [Stage(s.name, fn, s.produces) if s.name == name else s for s in STAGES]


def boom(ctx):
    raise RuntimeError("simulated failure")


# 1. One command produces both vertical outputs -------------------------------------------

def test_success_produces_both_verticals(ctx):
    run = run_pipeline(ctx)

    assert run["status"] == "succeeded"
    assert set(statuses(run).values()) == {"succeeded"}
    assert candidates(ctx, "mart.bess_candidates") == {"P001", "P005", "P008"}
    assert candidates(ctx, "mart.peat_candidates") == {"P009", "P013"}
    assert sorted(p.name for p in (ctx.out_dir / "dossiers" / "bess").glob("*.md")) == \
        ["DE-P001.md", "DE-P005.md", "DE-P008.md"]
    assert sorted(p.name for p in (ctx.out_dir / "dossiers" / "peat").glob("*.md")) == ["DE-P009.md", "DE-P013.md"]
    manifest = json.loads((ctx.out_dir / "last_run.json").read_text())
    assert manifest["status"] == "succeeded" and manifest["started_at"] and manifest["finished_at"]
    assert all(o["state"] == "fresh" for o in manifest["outputs"])


# 2. A failed critical stage cannot be reported as success -------------------------------

def test_failing_stage_fails_the_run(ctx):
    run = run_pipeline(ctx, with_stage("refresh_peat_view", boom))

    assert run["status"] == "failed"
    assert statuses(run) == {
        "check_prerequisites": "succeeded",
        "promote_accepted_data": "succeeded",
        "refresh_bess_view": "succeeded",
        "refresh_peat_view": "failed",
        "export_dossiers": "skipped",
    }
    failed = next(s for s in run["stages"] if s["name"] == "refresh_peat_view")
    assert failed["error"] == "RuntimeError: simulated failure"
    assert json.loads((ctx.out_dir / "last_run.json").read_text())["status"] == "failed"


def test_missing_input_fails_prerequisites_and_cli_exits_1(ctx, monkeypatch):
    with connect(ctx.db_url) as conn:
        conn.execute("DELETE FROM staging.feature WHERE dataset = 'protected_area'")
    monkeypatch.setenv("PILOT_DATABASE_URL", ctx.db_url)
    monkeypatch.setenv("PILOT_OUT_DIR", str(ctx.out_dir))

    assert cli.main(["run"]) == 1
    run = json.loads((ctx.out_dir / "last_run.json").read_text())
    assert run["stages"][0]["error"] == "no accepted data for: protected_area"
    assert {s["status"] for s in run["stages"][1:]} == {"skipped"}


# 3. Stale view/export state is visible ----------------------------------------------------

def test_stale_outputs_are_visible(ctx, monkeypatch):
    assert run_pipeline(ctx)["status"] == "succeeded"
    with connect(ctx.db_url) as conn:            # new data arrives: P006 is no longer forest
        conn.execute("UPDATE staging.feature SET attrs = '{\"land_use\": \"brownfield\"}'"
                     " WHERE dataset = 'parcel' AND feature_id = 'P006'")

    run = run_pipeline(ctx, with_stage("refresh_bess_view", boom))
    s = states(ctx)
    assert run["status"] == "failed"
    assert s["bess_view"]["state"] == "STALE" and "last attempt failed" in s["bess_view"]["reason"]
    assert s["peat_view"]["state"] == "STALE" and "data version 1, data is now at 2" in s["peat_view"]["reason"]
    assert s["bess_dossiers"]["state"] == s["peat_dossiers"]["state"] == "STALE"

    monkeypatch.setenv("PILOT_DATABASE_URL", ctx.db_url)
    assert cli.main(["status"]) == 1                # visible from the command line too

    assert run_pipeline(ctx)["status"] == "succeeded"   # a good run makes everything fresh again
    assert all(o["state"] == "fresh" for o in output_states(ctx))
    assert "P006" in candidates(ctx, "mart.bess_candidates")


# 4. Rerun is safe --------------------------------------------------------------------------

def test_rerun_changes_nothing(ctx):
    run_pipeline(ctx)
    files = {p.name: p.read_text() for p in (ctx.out_dir / "dossiers").rglob("*.md")}
    with connect(ctx.db_url) as conn:
        before = conn.execute("SELECT (SELECT count(*) FROM core.parcel) AS parcels,"
                              " (SELECT value FROM ops.state WHERE key = 'data_version') AS version").fetchone()

    second = run_pipeline(ctx)

    assert second["status"] == "succeeded"
    assert second["stages"][1]["counts"]["changed"] == 0
    with connect(ctx.db_url) as conn:
        after = conn.execute("SELECT (SELECT count(*) FROM core.parcel) AS parcels,"
                             " (SELECT value FROM ops.state WHERE key = 'data_version') AS version").fetchone()
    assert after == before
    assert {p.name: p.read_text() for p in (ctx.out_dir / "dossiers").rglob("*.md")} == files


# Data contract: only accepted, valid rows are promoted -----------------------------------

@pytest.mark.parametrize("row, reason", [
    ("parcel P900", "invalid geometry: Self-intersection"),
    ("parcel P901", "missing country_code"),
    ("substation S5", "missing or invalid voltage_kv"),
])
def test_invalid_rows_are_rejected_with_a_reason(ctx, row, reason):
    promote = run_pipeline(ctx)["stages"][1]["counts"]
    assert any(r.startswith(f"{row}: {reason}") for r in promote["rejected_rows"])


def test_rows_not_accepted_are_never_promoted(ctx):
    run_pipeline(ctx)
    with connect(ctx.db_url) as conn:
        assert conn.execute("SELECT count(*) AS n FROM core.parcel WHERE parcel_id = 'P902'").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM core.parcel WHERE country_code IS NULL").fetchone()["n"] == 0


def test_wrong_unit_is_rejected(ctx):
    with connect(ctx.db_url) as conn:
        conn.execute("UPDATE staging.feature SET units = '{\"voltage_kv\": \"V\"}' WHERE feature_id = 'S1'")
    promote = run_pipeline(ctx)["stages"][1]["counts"]
    assert "substation S1: voltage_kv must be given in kV" in promote["rejected_rows"]
