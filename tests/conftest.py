import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database.db as dbmod  # noqa: E402

# `import app` runs init_db()/seed_db() at import time. Point DB_PATH at a
# throwaway file FIRST so the real expense_tracker.db is never touched.
dbmod.DB_PATH = os.path.join(tempfile.mkdtemp(), "import.db")

from app import app as flask_app  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", str(tmp_path / "test.db"))
    flask_app.config["TESTING"] = True
    with flask_app.app_context():
        dbmod.init_db()
        dbmod.seed_db()
    yield flask_app


def fetch_all(sql, params=()):
    conn = dbmod.get_db()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()
