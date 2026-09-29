# IRIS Pilot: One-Command Orchestration

One command that **promotes accepted data**, **refreshes the BESS and peatland views**,
**exports sample dossiers** and **writes a run status**. Failed and stale stages are always
visible.

## Run it

Needs Docker and Python 3.12+ (if `python3` is older: `make install PYTHON=python3.12`).
On Apple Silicon the PostGIS image runs emulated: it works, just slower (the tests take about 50 s).

To look inside the database: `docker compose exec db psql -U pilot -d pilot`, run from the project
folder (or connect any SQL client to `localhost:54320`, user/password/database `pilot`).

```bash
make up        # start PostgreSQL 16 + PostGIS 3.4
make install   # create .venv
make run       # the one command
make test      # 20 tests
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

LEFT OUT (not used; fix in staging):
  parcel P900: invalid geometry: Self-intersection[470150 5483150]
  parcel P901: missing country_code
  substation S5: missing or invalid voltage_kv

OUTPUT          STATE   WHY
bess_dossiers   fresh   -
bess_view       fresh   -
peat_dossiers   fresh   -
peat_view       fresh   -

OK: all reports are up to date (last update 2026-09-29 15:55 UTC). Safe to use.

RUN SUCCEEDED  manifest: out/runs/20260929T155517609019Z.json
```

Files produced:

- `out/dossiers/READ_ME_FIRST.txt`: **one plain sentence for non-technical readers**. It is either "OK: all reports are up to date … Safe to use." or "DO NOT USE: … Ask the pilot operator to fix it and rerun." While a run is in progress it says "DO NOT USE YET".
- `out/dossiers/bess/*.md` and `out/dossiers/peat/*.md`: sample dossiers
- `out/runs/<run_id>.json`: run manifest (one per run)
- `out/last_run.json`: the latest manifest

## What it does: 5 stages, in order

| # | Stage | What it does |
|---|---|---|
| 1 | `check_prerequisites` | Database reachable, PostgreSQL 16+, PostGIS 3.4+, tables exist, accepted data exists for all 4 datasets |
| 2 | `promote_accepted_data` | Makes `core` match what the data steward **accepted**: valid rows are inserted or updated, withdrawn rows are deleted. Invalid rows are left out and listed. If a dataset has **no** valid rows, the stage fails instead of screening with an empty input |
| 3 | `refresh_bess_view` | Refreshes `mart.bess_candidates` |
| 4 | `refresh_peat_view` | Refreshes `mart.peat_candidates` |
| 5 | `export_dossiers` | Writes the top 3 candidates of each vertical as Markdown dossiers |

If a stage fails, it is marked `failed` with its error, every later stage is marked `skipped`,
and the run is `failed` (exit code 1). Only one run can be active at a time, because a PostgreSQL
advisory lock makes a second `pilot run` stop with "Another pilot run is already in progress".

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

If the first two stages fail, all outputs become STALE, because nothing downstream can be trusted.
This shows in every manifest, in `pilot status` (exit 1 unless OK) and, in plain words, in
`out/dossiers/READ_ME_FIRST.txt`.
*Test:* `test_stale_outputs_are_visible`

**4. Rerun is safe.**
- Promotion is an upsert that skips identical rows, so a rerun changes 0 rows and the data
  version stays the same.
- Views are recomputed from core, which gives the same result every time.
- Dossiers are overwritten atomically (temp file + rename), and old ones are removed.
- A second run started at the same time is refused, by an advisory lock.
- `pilot setup` uses `IF NOT EXISTS` and `ON CONFLICT DO NOTHING`.

*Tests:* `test_rerun_changes_nothing`, `test_second_run_is_refused_while_one_is_active`

## Engineering constraints

- **Stack:** Python 3.12, PostgreSQL 16, PostGIS 3.4.
- **Geometry:** the column is always `geom`. Everything is stored in EPSG:3035, so areas are in
  m² and distances in metres.
- **country_code:** NOT NULL in every core table, part of every primary key, and used in every
  spatial join.
- **Data contracts:** each staged row carries its CRS (the geometry's SRID), units, source date
  and positional uncertainty. Promotion rejects a row, with the reason, when any of these is
  missing or wrong, e.g. `substation S5: missing or invalid voltage_kv`.
- **Never invent data:** missing values are rejected, not filled in. If a dataset has no accepted
  rows, or none of them is valid (e.g. no usable protected areas), the run stops, because
  screening without it would wrongly report "0 % overlap". A bad re-delivery of one row keeps
  that row's last good version, so a broken reserve polygon can never make a reserve disappear.
- **Country codes:** must be 2 capital letters (`DE`); anything else is left out with a reason.
- **Also left out with a reason:** 3D geometries, NaN/infinite uncertainty, voltage or peat depth ≤ 0,
  and feature ids with characters other than letters, digits, `_ . -` (they become file names).
- **Dossiers** end with the project's reference uncertainty wording ("Preliminary prospecting material…").
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
| Status via exit code, manifest, `pilot status` and `READ_ME_FIRST.txt` | Scheduler plus alerts, e.g. cron: `0 6 * * * cd /repo && make run \|\| mail -s "IRIS run FAILED" pm@example.com` |
| Dossiers show the parcel's source date and uncertainty | Also show those of the peat, substation and reserve data each verdict depends on |
| Plain `REFRESH MATERIALIZED VIEW` (readers wait briefly; `lock_timeout` = 60 s stops endless waits) | `REFRESH … CONCURRENTLY` once people read the views live |
| `make run` also loads the fixture | Separate `make seed` for production data |
| Every run keeps its manifest | Retention for `out/runs/` |
| No "borderline" flag (P008 passes at 2,997 m of 3,000 m, ±2.5 m) | Flag results within the positional uncertainty |

## Trials

Beyond the unit tests, 43 scenarios were run as real `pilot` processes against PostgreSQL 16 +
PostGIS 3.4, each on a fresh database:

| Area | Scenarios | Result |
|---|---|---|
| Happy path and reruns | clean run; 5 reruns (identical files, `changed=0`, same data version); `status` before and after | all pass |
| Data contract | 21 kinds of bad row: missing/empty/3D/wrong-type/invalid geometry, unknown or no CRS, future or missing date, missing/negative/NaN uncertainty, wrong attribute type, wrong unit, negative voltage, bad country code, unsafe id | 4 defects found and fixed (below); all pass |
| Whole dataset bad | no accepted substations; all peat rows invalid (last good data kept, everything STALE); staging empty | all pass |
| Data changes | new attribute; withdrawn then re-accepted; pending then accepted; geometry moved 1 m | all pass |
| Country scope | same parcel id in DE and NL: separate rows, NL never joins DE substations | pass |
| Operations | database down; not set up; wrong password (not printed); 4 runs started at once; `kill -9` mid-refresh; refresh blocked past `lock_timeout` (fails after 60 s, STALE); `out/` deleted; stray old dossier; `status` during a run | all pass |
| Scale | 20,000 parcels, 200 substations, 400 peat polygons, 100 reserves | 2.8 s per run, rerun changes 0 rows |

Defects the trials found (each now has a test in `test_bad_delivery_is_left_out_and_run_still_succeeds`):

| Bad row | Before | Now |
|---|---|---|
| 3D polygon | whole promotion crashed | left out: "geometry must be 2D" |
| uncertainty `NaN` | accepted | left out |
| voltage −110 kV | accepted | left out: "must be greater than 0" |
| feature id `../evil` | dossier export crashed | left out: "feature_id may only use …" |

## Time and space complexity

N = staged rows, P = parcels, S = substations, A = protected areas, K = peat polygons,
R = rejected rows. "Local" means the few features near one parcel, found through a GiST index.

| Stage | Time | Space | Why |
|---|---|---|---|
| check_prerequisites | O(N) | O(1) | one `GROUP BY` count over staging |
| promote_accepted_data | O(N log N) | O(N) in core, O(R) in Python | each row checked once, upsert and delete use the primary-key and unique indexes; identical rows are not rewritten |
| refresh_bess_view | O(P · (log S + log A + local)) | O(P) | one pass over parcels; nearest substation via GiST KNN, protected areas via GiST lookup |
| refresh_peat_view | O(P · (log K + local)) | O(P) | same pattern with peat polygons |
| export_dossiers | O(P) | O(1) | top 3 per vertical (top-N sort), at most 6 files |
| manifest + status | O(stages + R) | O(R) | the manifest keeps every rejected row; the screen shows the first 20 |

PostgreSQL's JIT compiler is switched off for the pipeline's connections: it spent about 0.25 s
compiling each view (seen in `EXPLAIN ANALYZE`) and saved nothing, because the work is many small
index lookups. Refreshing both views at 40,000 parcels went from about 3.3 s to 2.6 s.

Every spatial join uses its GiST index (checked with `EXPLAIN`), so no parcel is compared with
every substation, reserve or peat polygon. `REFRESH MATERIALIZED VIEW` briefly needs space for the
old and the new copy of a view.

Measured (whole `pilot run`, constant density, growing region):

| Parcels | Run | Rerun (0 rows changed) | Python memory | core + views on disk |
|---|---|---|---|---|
| 5,000 | 0.8 s | 0.8 s | 40 MB | 3 MB |
| 20,000 | 2.8 s | 2.4 s | 40 MB | 11 MB |
| 80,000 | 8.6 s | 7.7 s | 43 MB | 44 MB |
| 160,000 | 15.9 s | 15.6 s | 47 MB | 86 MB |

2× the data takes about 2× the time, i.e. linear, and Python memory stays flat because the work
happens in PostgreSQL. A rerun costs about as much as a first run because both views are always
fully recomputed. For production, an incremental refresh of only the changed parcels would make
reruns cheap.

## Design review

Before submission the code was reviewed adversarially by four reviewers: a prosecutor looking
for defects, a defence guarding simplicity, a user advocate for non-technical users, and an
on-call engineer. They cross-examined each other and an independent judge ruled. They found and
reproduced the following problems. Each is now fixed and has a test.

| Problem found | Fix |
|---|---|
| After a failed run, `pilot status` still said "fresh" | Failures in the first two stages mark every output STALE; `status` exits 1 unless OK |
| All protected areas invalid → screened as "0 % overlap" and exported | Stop when a dataset has no valid rows |
| A parcel withdrawn by the data steward was still exported | Withdrawn rows are deleted from `core` |
| One bad country code (`DEU`) crashed the whole promotion | Rejected with a reason like any other bad row |
| Two runs at once could mark an old view "fresh" | Advisory lock: one run at a time |
| A blocked refresh could hang forever | `lock_timeout` = 60 s: it fails and shows as STALE |
| Non-technical readers had no plain answer | `READ_ME_FIRST.txt` next to the dossiers; left-out rows printed |

Rejected to keep it simple: dashboards, alerting services, parallel stages, retries and new
dependencies.
