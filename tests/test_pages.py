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
    if "information_schema.tables" in q:
        return pd.DataFrame({"models": [8]})
    if "AS row_count" in q and "last_event_at" in q:
        return pd.DataFrame({
            "layer": ["bronze", "silver", "gold"],
            "row_count": [758512, 727208, 727208],
            "last_event_at": [minutes_ago(10), minutes_ago(10), minutes_ago(10)],
        })
    if "AS last_event_at" in q:
        return pd.DataFrame({"layer": ["silver", "gold"], "last_event_at": [minutes_ago(10), minutes_ago(10)]})
    if "AS row_count" in q:
        return pd.DataFrame({"layer": ["bronze", "silver", "gold"], "row_count": [758512, 727208, 727208]})
    days = pd.date_range(end=pd.Timestamp(NOW).normalize() - pd.Timedelta(days=1), periods=40, freq="D").date
    if "AS min_date" in q:
        return pd.DataFrame({"min_date": [days[0]], "max_date": [days[-1]]})
    if "fct_daily_metrics" in q:
        return pd.DataFrame({
            "order_date": days, "total_orders": 300, "total_gmv": 450000, "delivered_orders": 280,
            "cancelled_orders": 20, "cancellation_rate": 20 / 300, "avg_delivery_time_minutes": 34.5,
        })
    if "DAYOFWEEK" in q:
        return pd.DataFrame([{"dow": d, "hour_of_day": h, "orders": 3 + h % 5} for d in range(1, 8) for h in range(24)])
    if "vendor_name" in q:
        return pd.DataFrame({
            "vendor_name": ["Sushi <Zen>", "Ramen Ya"], "cuisine_type": ["japanese", "japanese"],
            "orders": [120, 90], "gmv": [180000, 99000], "cancellation_rate": [0.05, 0.08],
        })
    if "cancel_reason" in q:
        return pd.DataFrame({
            "cancelled_by": ["customer", "customer", "vendor", "driver", "system"],
            "cancel_reason": ["changed_mind", "too_slow", "out_of_stock", "vehicle_issue", "payment_failed"],
            "cnt": [40, 22, 15, 6, 3],
        })
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


def html_of(at):
    return "".join(h.value for h in at.html)


def test_overview_renders(app):
    at = app.run()
    assert not at.exception
    assert at.title[0].value == "Food Delivery Pipeline"
    page = html_of(at)
    assert "fd-state--live" in page and "758,512" in page and "dbt · 8 models" in page


def test_pipeline_health_renders(app):
    at = app.run()
    at.switch_page("pipeline_health.py").run()
    assert not at.exception
    assert not unavailable(at)
    assert [s.value for s in at.subheader] == [
        "Freshness",
        "Volume against the 7-day baseline",
        "Known issues, tracked not hidden",
        "Layer reconciliation",
    ]


def test_operations_renders(app):
    at = app.run()
    at.switch_page("operations.py").run()
    assert not at.exception
    assert not unavailable(at)
    assert [s.value for s in at.subheader] == ["Trend", "When orders arrive", "Top vendors", "Cancellations"]
    assert [m.label for m in at.metric] == ["Orders", "GMV", "Average order", "Cancellation rate"]


@pytest.mark.parametrize("page", ["operations.py", "pipeline_health.py"])
def test_controls_fall_back_when_deselected(app, page):
    at = app.run()
    at.switch_page(page).run()
    for control in at.button_group:
        control.set_value(None)
    at.run()
    assert not at.exception
    assert not unavailable(at)
