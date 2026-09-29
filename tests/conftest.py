"""Each test gets its own fresh database (PostgreSQL 16 + PostGIS 3.4) with tables and fixture."""

import os
import uuid

import psycopg
import pytest

from pilot.db import Context, setup

ADMIN_URL = os.environ.get("PILOT_TEST_DATABASE_URL", "postgresql://pilot:pilot@localhost:54320/pilot")


@pytest.fixture
def ctx(tmp_path):
    name = f"pilot_test_{uuid.uuid4().hex[:8]}"
    base = ADMIN_URL.rsplit("/", 1)[0]
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    context = Context(db_url=f"{base}/{name}", out_dir=tmp_path / "out")
    setup(context.db_url)
    yield context
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
