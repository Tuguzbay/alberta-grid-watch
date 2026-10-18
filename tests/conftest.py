import os

import psycopg
import pytest

from gridwatch import db


@pytest.fixture
def conn():
    url = os.environ.get("DATABASE_URL")
    try:
        c = psycopg.connect(url, connect_timeout=2) if url else None
    except psycopg.OperationalError:
        c = None
    if c is None:
        pytest.skip("no Postgres at DATABASE_URL")
    # Temp table shadows any real `hourly`, so tests never touch stored data.
    c.execute(db.SCHEMA.replace("CREATE TABLE IF NOT EXISTS", "CREATE TEMP TABLE"))
    yield c
    c.close()
