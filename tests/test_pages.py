"""Smoke tests: every page renders against canned query results, no warehouse needed."""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py")
NOW = datetime.now(timezone.utc).replace(tzinfo=None)  # Databricks returns naive UTC


def minutes_ago(minutes):
    return pd.Timestamp(NOW) - pd.Timedelta(minutes=minutes)


def fake_query(query, params=None):
    """Stand-in for db._query: answers each dashboard query by a keyword in its SQL."""
    q = " ".join(query.split())
    hours = pd.date_range(end=pd.Timestamp(NOW).floor("h"), periods=72, freq="h")
    if "DESCRIBE HISTORY" in q:
        return pd.DataFrame({"last_refresh_at": [minutes_ago(40)]})
    if "WITH hourly" in q:
        return pd.DataFrame({"hr": hours, "orders": 30, "expected": 28})
    if "negative_gmv" in q:
        return pd.DataFrame({"negative_gmv": [55], "unknown_event_types": [1], "orphan_vendors": [5]})
    if "AS last_event_at" in q:
        return pd.DataFrame({"layer": ["silver", "gold"], "last_event_at": [minutes_ago(10), minutes_ago(10)]})
    if "AS row_count" in q:
        return pd.DataFrame({"layer": ["bronze", "silver", "gold"], "row_count": [758512, 727208, 727208]})
    raise AssertionError(f"fake_query has no answer for: {q[:120]}")


@pytest.fixture
def app(monkeypatch):
    for key in ("DATABRICKS_SERVER_HOSTNAME", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN"):
        monkeypatch.setenv(key, "test")
    import db

    monkeypatch.setattr(db, "_query", fake_query)
    return AppTest.from_file(APP, default_timeout=60)


def unavailable(at):
    return [w.value for w in at.warning if "Live data is unavailable" in w.value]


def test_app_renders_without_exception(app):
    at = app.run()
    assert not at.exception
    assert not unavailable(at)
