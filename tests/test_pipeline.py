"""Tests for the four acceptance criteria, plus the data contract."""

import json

import pytest

from pilot import cli
from pilot.db import connect, setup
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
    assert (ctx.out_dir / "dossiers" / "READ_ME_FIRST.txt").read_text().startswith("OK: all reports are up to date")
    assert "Preliminary prospecting material." in (ctx.out_dir / "dossiers" / "peat" / "DE-P009.md").read_text()


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


@pytest.mark.parametrize("change, reason", [
    ("SET geom = ST_Force3D(geom) WHERE feature_id = 'P002'", "parcel P002: geometry must be 2D"),
    ("SET uncertainty_m = 'NaN' WHERE feature_id = 'P002'", "parcel P002: missing or invalid uncertainty_m"),
    ("SET attrs = '{\"voltage_kv\": -110}' WHERE feature_id = 'S1'", "substation S1: voltage_kv must be greater than 0"),
    ("SET feature_id = '../evil' WHERE feature_id = 'P001'", "parcel ../evil: feature_id may only use"),
])
def test_bad_delivery_is_left_out_and_run_still_succeeds(ctx, change, reason):
    """Found in trials: each of these used to crash the run, be accepted, or break the export."""
    with connect(ctx.db_url) as conn:
        conn.execute(f"UPDATE staging.feature {change}")
    run = run_pipeline(ctx)
    assert run["status"] == "succeeded"
    assert any(r.startswith(reason) for r in run["stages"][1]["counts"]["rejected_rows"])


def test_long_left_out_list_is_shortened_on_screen_but_complete_in_manifest(ctx, monkeypatch, capsys):
    with connect(ctx.db_url) as conn:
        conn.execute("INSERT INTO staging.feature (dataset, country_code, feature_id, review_status)"
                     " SELECT 'parcel', 'DE', 'BAD' || i, 'accepted' FROM generate_series(1, 30) i")
    monkeypatch.setenv("PILOT_DATABASE_URL", ctx.db_url)
    monkeypatch.setenv("PILOT_OUT_DIR", str(ctx.out_dir))
    cli.main(["run"])
    assert "... and 13 more, all listed in the manifest" in capsys.readouterr().out   # 30 + 3 fixture rows
    assert len(json.loads((ctx.out_dir / "last_run.json").read_text())["stages"][1]["counts"]["rejected_rows"]) == 33


def test_dossiers_are_two_pages_with_the_evidence_behind_the_result(ctx):
    run_pipeline(ctx)
    bess = (ctx.out_dir / "dossiers" / "bess" / "DE-P008.md").read_text()
    peat = (ctx.out_dir / "dossiers" / "peat" / "DE-P009.md").read_text()
    for text in (bess, peat):
        assert "Page 1 of 2" in text and "page-break-after" in text and "Page 2 of 2" in text
        assert "Preliminary prospecting material." in text
    # page 2 names the features used, with their own source date and uncertainty
    assert "| Nearest substation of 110 kV or more | S2 (380 kV) | 2026-05-15 | ±5 m |" in bess
    assert "| Peat soil polygons overlapping the parcel | PS1 (120 cm, drained) | 2025-11-01 | ±25 m |" in peat
    # P008 passes at 2,997 m of 3,000 m, within ±7.5 m combined uncertainty: flagged, P001 (500 m) is not
    assert "borderline" in bess
    assert "borderline" not in (ctx.out_dir / "dossiers" / "bess" / "DE-P001.md").read_text()
    assert "768,592 (drained peat area × 8" in peat         # 96,074 m² drained peat × 8


def test_setup_rebuilds_views_and_marks_outputs_not_fresh(ctx):
    run_pipeline(ctx)
    setup(ctx.db_url)                              # e.g. after a new version of the view SQL
    assert {o["state"] for o in output_states(ctx)} == {"STALE"}
    assert run_pipeline(ctx)["status"] == "succeeded"
    assert {o["state"] for o in output_states(ctx)} == {"fresh"}


def test_wrong_unit_is_rejected(ctx):
    with connect(ctx.db_url) as conn:
        conn.execute("UPDATE staging.feature SET units = '{\"voltage_kv\": \"V\"}' WHERE feature_id = 'S1'")
    promote = run_pipeline(ctx)["stages"][1]["counts"]
    assert "substation S1: voltage_kv must be given in kV" in promote["rejected_rows"]


# Design-review findings (see README "Design review") --------------------------------------

def test_early_failure_marks_every_output_stale(ctx, monkeypatch):
    run_pipeline(ctx)
    run_pipeline(ctx, with_stage("check_prerequisites", boom))
    assert {o["state"] for o in output_states(ctx)} == {"STALE"}
    assert (ctx.out_dir / "dossiers" / "READ_ME_FIRST.txt").read_text().startswith("DO NOT USE")
    monkeypatch.setenv("PILOT_DATABASE_URL", ctx.db_url)
    assert cli.main(["status"]) == 1


def test_readers_are_warned_while_a_run_is_in_progress(ctx):
    seen = {}

    def look_at_verdict_file(c):
        seen["text"] = (c.out_dir / "dossiers" / "READ_ME_FIRST.txt").read_text()
        return {}

    run_pipeline(ctx, with_stage("check_prerequisites", look_at_verdict_file))
    assert seen["text"].startswith("DO NOT USE YET: an update started")   # written before any stage runs


def test_dataset_with_no_valid_rows_fails_and_keeps_last_good_data(ctx):
    run_pipeline(ctx)
    with connect(ctx.db_url) as conn:
        conn.execute("UPDATE staging.feature SET source_date = NULL WHERE dataset = 'protected_area'")
    run = run_pipeline(ctx)
    assert statuses(run)["promote_accepted_data"] == "failed"
    assert run["stages"][1]["error"].startswith("no usable protected_area data")
    with connect(ctx.db_url) as conn:
        assert conn.execute("SELECT count(*) AS n FROM core.protected_area").fetchone()["n"] == 2


def test_withdrawn_row_is_removed_and_bad_country_code_is_rejected(ctx):
    run_pipeline(ctx)
    with connect(ctx.db_url) as conn:
        conn.execute("UPDATE staging.feature SET review_status = 'rejected' WHERE feature_id = 'P001'")
        conn.execute("UPDATE staging.feature SET country_code = 'DEU' WHERE feature_id = 'P002'")
        conn.execute("UPDATE staging.feature SET source_date = NULL WHERE feature_id = 'PA1'")  # bad re-delivery
    run = run_pipeline(ctx)
    assert run["status"] == "succeeded" and run["stages"][1]["counts"]["changed"] >= 2
    assert "parcel P002: country_code must be 2 capital letters, e.g. DE" in run["stages"][1]["counts"]["rejected_rows"]
    assert "P001" not in candidates(ctx, "mart.bess_candidates")
    assert not (ctx.out_dir / "dossiers" / "bess" / "DE-P001.md").exists()
    assert "P004" not in candidates(ctx, "mart.bess_candidates")      # PA1 kept its last good version


def test_second_run_is_refused_while_one_is_active(ctx, monkeypatch):
    monkeypatch.setenv("PILOT_DATABASE_URL", ctx.db_url)
    monkeypatch.setenv("PILOT_OUT_DIR", str(ctx.out_dir))
    with connect(ctx.db_url) as holder:
        holder.execute("SELECT pg_advisory_lock(%s)", (cli.RUN_LOCK,))
        assert cli.main(["run"]) == 1
    assert not (ctx.out_dir / "last_run.json").exists()
