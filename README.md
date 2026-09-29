# IRIS Pilot: One-Command Orchestration

One command that **promotes accepted data**, **refreshes the BESS and peatland views**,
**exports sample dossiers** and **writes a run status**. Failed and stale stages are always
visible.

## Run it

Needs Docker and Python 3.12+.

```bash
make up        # start PostgreSQL 16 + PostGIS 3.4
make install   # create .venv
make run       # the one command
make test      # 10 tests
make status    # is each output fresh or STALE?
```

Output of `make run`:

```text
STAGE                   STATUS     DETAILS
check_prerequisites     succeeded  postgres=160013, postgis=3.4.2, accepted_rows=28
promote_accepted_data   succeeded  valid=25, changed=25, rejected=3, not_accepted=1
refresh_bess_view       succeeded  parcels=13, candidates=3
refresh_peat_view       succeeded  parcels=13, candidates=2
export_dossiers         succeeded  bess=3, peat=2

OUTPUT          STATE   WHY
bess_dossiers   fresh   -
bess_view       fresh   -
peat_dossiers   fresh   -
peat_view       fresh   -

RUN SUCCEEDED  manifest: out/runs/20260929T152303940141Z.json
```

Files produced:

- `out/dossiers/bess/*.md` and `out/dossiers/peat/*.md`: sample dossiers
- `out/runs/<run_id>.json`: run manifest (one per run)
- `out/last_run.json`: the latest manifest

## What it does: 5 stages, in order

| # | Stage | What it does |
|---|---|---|
| 1 | `check_prerequisites` | Database reachable, PostgreSQL 16+, PostGIS 3.4+, tables exist, accepted data exists for all 4 datasets |
| 2 | `promote_accepted_data` | Copies rows the data steward **accepted** and that meet the data contract from `staging` into `core` |
| 3 | `refresh_bess_view` | Refreshes `mart.bess_candidates` |
| 4 | `refresh_peat_view` | Refreshes `mart.peat_candidates` |
| 5 | `export_dossiers` | Writes the top 3 candidates of each vertical as Markdown dossiers |

If a stage fails, it is marked `failed` with its error, every later stage is marked `skipped`,
and the run is `failed` (exit code 1).

## The deliverables

| Deliverable | File |
|---|---|
| CLI | `src/pilot/cli.py`: `pilot setup`, `pilot run`, `pilot status` |
| Stage runner | `src/pilot/runner.py` |
| Run manifest | `src/pilot/manifest.py`: JSON with counts, timestamps, failure details and output states |
| Stages | `src/pilot/stages.py` |
| SQL | `sql/001_schema.sql` (tables), `sql/002_views.sql` (the two views) |
| Fixture | `fixtures/seed.sql`: one synthetic region near Mannheim |
| Tests | `tests/test_pipeline.py`: success, failing stage, stale, rerun, data contract |

## How each acceptance criterion is met

**1. One command produces both vertical outputs.** `make run` runs all 5 stages and writes both
the BESS and the peatland dossiers.
*Test:* `test_success_produces_both_verticals`

**2. A failed critical stage cannot be reported as success.** The runner has one rule: the run
succeeded only if **every** stage succeeded. A failed or skipped stage means a failed run and
exit code 1.
*Tests:* `test_failing_stage_fails_the_run`, `test_missing_input_fails_prerequisites_and_cli_exits_1`

**3. Stale view/export state is visible.** `ops.state.data_version` goes up whenever promotion
changes data. Each output remembers the data version it was built from and whether its last
attempt failed. An output is **STALE** if:
- it was never built,
- its last attempt failed, or
- it was built from an older data version.

This shows in every manifest and in `pilot status`, which exits 1 if anything is stale.
*Test:* `test_stale_outputs_are_visible`

**4. Rerun is safe.**
- Promotion is an upsert that skips identical rows, so a rerun changes 0 rows and the data
  version stays the same.
- Views are recomputed from core, which gives the same result every time.
- Dossiers are overwritten atomically (temp file + rename), and old ones are removed.
- `pilot setup` uses `IF NOT EXISTS` and `ON CONFLICT DO NOTHING`.

*Test:* `test_rerun_changes_nothing`

## Engineering constraints

- **Stack:** Python 3.12, PostgreSQL 16, PostGIS 3.4.
- **Geometry:** the column is always `geom`. Everything is stored in EPSG:3035, so areas are in
  m² and distances in metres.
- **country_code:** NOT NULL in every core table, part of every primary key, and used in every
  spatial join.
- **Data contracts:** each staged row carries its CRS (the geometry's SRID), units, source date
  and positional uncertainty. Promotion rejects a row, with the reason, when any of these is
  missing or wrong, e.g. `substation S5: missing or invalid voltage_kv`.
- **Never invent data:** missing values are rejected, not filled in. If a whole dataset is
  missing (e.g. no protected areas), the run stops, because screening without it would wrongly
  report "0 % overlap".
- **Setup:** SQL files and a CLI, not notebooks. There are no credentials; the fixture is local.

## Screening rules

- **BESS:** area ≥ 20,000 m², land use arable/grassland/brownfield, ≤ 3,000 m to a substation of
  ≥ 110 kV, and ≤ 5 % inside protected areas.
- **Peatland:** ≥ 30 % of the parcel on peat, ≥ 30 % on drained peat, and mean peat depth
  ≥ 30 cm.

Each view has one yes/no column per rule, so every dossier shows why a parcel passed.

## Fixture

13 parcels, each built to show one rule. The expected results are:
- **BESS:** P001, P005, P008 pass.
- **Peat:** P009, P013 pass.
- **Rejected on promotion:** P900 (self-intersecting shape), P901 (no country code) and S5 (no
  voltage).
- **Never promoted:** P902, which is still `pending` review.

## Assumptions and simplifications

| Kept simple | How it would grow for production |
|---|---|
| Stages run one after another and stop at the first failure | Let independent stages (BESS and peat) continue in parallel |
| `pilot setup` runs the SQL files with `IF NOT EXISTS` | Versioned migrations (e.g. Alembic or numbered, checksummed files) |
| Fixture loaded from `seed.sql` | Source adapters (WFS, cadastre API, files) filling `staging` |
| Thresholds written in the view SQL | A rules table per country |
| No lock against two runs at the same time | `pg_try_advisory_lock` so only one run can be active |
| Upsert only (no deletes) | Handle features removed at the source |
| Status via exit code, manifest and `pilot status` | Scheduler (cron, Airflow) plus alerts on exit code 1 |
