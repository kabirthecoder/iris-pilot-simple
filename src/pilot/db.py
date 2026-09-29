"""Database connection and one-time setup (tables, views, fixture)."""

import os
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_URL = "postgresql://pilot:pilot@localhost:54320/pilot"


@dataclass(frozen=True)
class Context:
    """Everything a stage needs: where the database is and where to write files."""
    db_url: str
    out_dir: Path

    @classmethod
    def from_env(cls) -> "Context":
        return cls(
            db_url=os.environ.get("PILOT_DATABASE_URL", DEFAULT_URL),
            out_dir=Path(os.environ.get("PILOT_OUT_DIR", ROOT / "out")),
        )


def connect(db_url: str) -> psycopg.Connection:
    """One connection = one transaction: committed if the block succeeds, rolled back if it raises."""
    # lock_timeout: a blocked step fails (and shows as STALE) instead of hanging forever.
    # jit=off: the views are many small index lookups; compiling them costs ~0.25 s per view
    # and saves nothing (measured, see README "Time and space complexity").
    return psycopg.connect(db_url, row_factory=dict_row, connect_timeout=5,
                           options="-c lock_timeout=60s -c jit=off")


def setup(db_url: str) -> None:
    """Create tables and views, then load the fixture. Safe to run again."""
    with connect(db_url) as conn:
        for path in sorted((ROOT / "sql").glob("*.sql")):
            conn.execute(path.read_text())
        conn.execute((ROOT / "fixtures" / "seed.sql").read_text())
