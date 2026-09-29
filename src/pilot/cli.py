"""Command line.

    pilot setup    create tables and views, load the fixture (safe to repeat)
    pilot run      run all stages once; exit code 0 = succeeded, 1 = failed
    pilot status   show whether each output is fresh or STALE; exit code 1 if any is stale
"""

import argparse
import sys

from pilot.db import Context, setup
from pilot.manifest import output_states
from pilot.runner import run_pipeline


def print_outputs(outputs: list[dict]) -> None:
    print("\nOUTPUT          STATE   WHY")
    for o in outputs:
        print(f"{o['name']:<15} {o['state']:<7} {o['reason'] or '-'}")


def cmd_run(ctx: Context) -> int:
    run = run_pipeline(ctx)
    print(f"\n{'STAGE':<23} {'STATUS':<10} DETAILS")
    for s in run["stages"]:
        details = s.get("error") or s.get("reason") or ", ".join(
            f"{k}={v}" for k, v in s["counts"].items() if k != "rejected_rows")
        print(f"{s['name']:<23} {s['status']:<10} {details}")
    print_outputs(run["outputs"])
    print(f"\nRUN {run['status'].upper()}  manifest: {run['manifest']}")
    return 0 if run["status"] == "succeeded" else 1


def cmd_status(ctx: Context) -> int:
    outputs = output_states(ctx)
    print_outputs(outputs)
    return 0 if all(o["state"] == "fresh" for o in outputs) else 1


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
