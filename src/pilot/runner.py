"""Stage runner: runs the stages in order, stops at the first failure, and never reports a
failed or skipped stage as success."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from pilot.db import Context, connect
from pilot.manifest import output_states, write_manifest
from pilot.stages import (
    StageError, check_prerequisites, export_dossiers, promote, refresh_bess, refresh_peat,
)


@dataclass(frozen=True)
class Stage:
    name: str
    run: Callable[[Context], dict]
    produces: tuple[str, ...] = ()       # outputs that become STALE if this stage fails


STAGES = [
    Stage("check_prerequisites", check_prerequisites),
    Stage("promote_accepted_data", promote),
    Stage("refresh_bess_view", refresh_bess, ("bess_view",)),
    Stage("refresh_peat_view", refresh_peat, ("peat_view",)),
    Stage("export_dossiers", export_dossiers, ("bess_dossiers", "peat_dossiers")),
]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _mark_failed(ctx: Context, outputs: tuple[str, ...], error: str) -> None:
    """Remember the failure on the outputs (their last good version stays, now marked stale)."""
    if not outputs:
        return
    try:
        with connect(ctx.db_url) as conn:
            conn.execute("UPDATE ops.artifact SET status = 'failed', error = %s WHERE name = ANY(%s)",
                         (error, list(outputs)))
    except Exception:
        pass  # the database may be the thing that failed; the manifest still records the error


def run_pipeline(ctx: Context, stages: list[Stage] = STAGES) -> dict:
    run = {"run_id": datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"), "started_at": _now(), "stages": []}
    stopped = False

    for stage in stages:
        record = {"name": stage.name}
        run["stages"].append(record)
        if stopped:
            record.update(status="skipped", reason="an earlier stage failed")
            continue
        record["started_at"] = _now()
        t0 = time.perf_counter()
        try:
            record["counts"] = stage.run(ctx)
            record["status"] = "succeeded"
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = str(exc) if isinstance(exc, StageError) else f"{type(exc).__name__}: {exc}"
            _mark_failed(ctx, stage.produces, record["error"])
            stopped = True
        record["finished_at"] = _now()
        record["duration_ms"] = round((time.perf_counter() - t0) * 1000)

    # The rule: the run succeeded only if EVERY stage succeeded. Failed or skipped = failed run.
    run["status"] = "succeeded" if all(s["status"] == "succeeded" for s in run["stages"]) else "failed"
    run["finished_at"] = _now()
    run["outputs"] = output_states(ctx)
    run["manifest"] = str(write_manifest(ctx.out_dir, run))
    return run
