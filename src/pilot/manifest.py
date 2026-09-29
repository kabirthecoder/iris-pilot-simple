"""Run manifest (what happened) and output states (is each output fresh or STALE?)."""

import json
from datetime import UTC, datetime
from pathlib import Path

from pilot.db import Context, connect


def output_states(ctx: Context) -> list[dict]:
    """For every output: fresh or STALE, and why.

    STALE when it was never built, its last attempt failed, or it was built from older data
    than what is now in core (data_version went up since)."""
    try:
        with connect(ctx.db_url) as conn:
            current = conn.execute("SELECT value FROM ops.state WHERE key = 'data_version'").fetchone()["value"]
            rows = conn.execute("SELECT * FROM ops.artifact ORDER BY name").fetchall()
    except Exception as exc:
        first_line = str(exc).splitlines()[0]
        return [{"name": "reports", "state": "UNKNOWN",
                 "reason": f'database not reachable or not set up (new install: run "pilot setup"): {first_line}'}]

    states = []
    for a in rows:
        if a["status"] == "never built":
            state, reason = "STALE", "never built"
        elif a["status"] == "failed":
            state, reason = "STALE", f"last attempt failed: {a['error']}"
        elif a["data_version"] < current:
            state, reason = "STALE", f"built from data version {a['data_version']}, data is now at {current}"
        else:
            state, reason = "fresh", ""
        states.append({"name": a["name"], "state": state, "reason": reason,
                       "built_at": a["built_at"].isoformat(timespec="seconds") if a["built_at"] else None,
                       "data_version": a["data_version"]})
    return states


def verdict(outputs: list[dict]) -> str:
    """One plain sentence for non-technical readers: can the dossiers be used?"""
    bad = [o for o in outputs if o["state"] != "fresh"]
    if outputs and not bad:
        oldest = min(datetime.fromisoformat(o["built_at"]) for o in outputs).astimezone(UTC)
        return f"OK: all reports are up to date (last update {oldest:%Y-%m-%d %H:%M} UTC). Safe to use."
    name, reason = (bad[0]["name"], bad[0]["reason"].splitlines()[0]) if bad else ("reports", "no outputs recorded")
    return (f"DO NOT USE: {name} cannot be trusted ({reason}). These dossiers may be outdated. "
            "Ask the pilot operator to fix it and rerun.")


def write_manifest(out_dir: Path, run: dict) -> Path:
    """out/runs/<run_id>.json (one per run) and out/last_run.json (always the latest)."""
    runs = out_dir / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    text = json.dumps(run, indent=2, default=str) + "\n"
    path = runs / f"{run['run_id']}.json"
    for target in (path, out_dir / "last_run.json"):
        tmp = target.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(target)
    return path
