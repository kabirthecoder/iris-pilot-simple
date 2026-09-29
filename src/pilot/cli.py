"""Command line.

    pilot setup    create tables and views, load the fixture (safe to repeat)
    pilot run      run all stages once; exit code 0 = succeeded, 1 = failed
    pilot status   show whether each output is fresh or STALE, plus one plain verdict; exit 1 unless OK
"""

import argparse
import sys

from pilot.db import Context, connect, setup
from pilot.manifest import output_states, verdict
from pilot.runner import run_pipeline

RUN_LOCK = 7431   # any fixed number; PostgreSQL lets only one session hold it
SHOW_LEFT_OUT = 20


def print_outputs(outputs: list[dict]) -> None:
    print("\nOUTPUT          STATE   WHY")
    for o in outputs:
        print(f"{o['name']:<15} {o['state']:<7} {o['reason'] or '-'}")


def cmd_run(ctx: Context) -> int:
    try:
        lock = connect(ctx.db_url)   # held until the process exits: one run at a time
        lock.autocommit = True       # don't sit "idle in transaction" for the whole run
        if not lock.execute("SELECT pg_try_advisory_lock(%s) AS ok", (RUN_LOCK,)).fetchone()["ok"]:
            print("Another pilot run is already in progress; nothing was done. Try again later.")
            return 1
    except Exception:
        pass  # database down: let check_prerequisites report it in the manifest
    run = run_pipeline(ctx)
    print(f"\n{'STAGE':<23} {'STATUS':<10} DETAILS")
    for s in run["stages"]:
        if s.get("error"):
            details = s["error"].splitlines()[0]          # full error is in the manifest
        elif s.get("reason"):
            details = s["reason"]
        else:
            details = ", ".join(f"{k}={v}" for k, v in s["counts"].items() if k != "rejected_rows")
        print(f"{s['name']:<23} {s['status']:<10} {details}")
    left_out = run["stages"][1].get("counts", {}).get("rejected_rows", [])   # from promote
    if left_out:
        print("\nLEFT OUT (not used; fix in staging):\n  " + "\n  ".join(left_out[:SHOW_LEFT_OUT]))
        if len(left_out) > SHOW_LEFT_OUT:   # the manifest keeps the full list
            print(f"  ... and {len(left_out) - SHOW_LEFT_OUT} more, all listed in the manifest")
    print_outputs(run["outputs"])
    print(f"\n{run['verdict']}")
    print(f"\nRUN {run['status'].upper()}  manifest: {run['manifest']}")
    return 0 if run["status"] == "succeeded" else 1


def cmd_status(ctx: Context) -> int:
    outputs = output_states(ctx)
    print_outputs(outputs)
    print(f"\n{verdict(outputs)}")
    return 0 if verdict(outputs).startswith("OK") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pilot", description="IRIS pilot: one-command run")
    parser.add_argument("command", choices=["setup", "run", "status"])
    args = parser.parse_args(argv)
    ctx = Context.from_env()
    if args.command == "setup":
        setup(ctx.db_url)
        print("setup done: tables, views and fixture are in place")
        return 0
    return cmd_run(ctx) if args.command == "run" else cmd_status(ctx)


if __name__ == "__main__":
    sys.exit(main())
