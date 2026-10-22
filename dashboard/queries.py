"""Warehouse queries shared by the Overview and Pipeline health pages."""
from __future__ import annotations

import pandas as pd

import db

LAYERS = ("bronze", "silver", "gold")

_WHY = {
    "bronze": "Raw events as landed by Auto Loader",
    "silver": "Duplicate event IDs, and events over an hour late",
    "gold": "Modeled by dbt; should match silver",
}


def reconcile(counts: dict[str, int | None]) -> list[dict]:
    """Rows per layer and how many each layer dropped relative to the one before it."""
    rows, previous = [], None
    for layer in LAYERS:
        count = counts.get(layer)
        if previous is None or count is None:
            dropped = pct = None
        else:
            dropped = previous - count
            pct = dropped / previous * 100 if previous else 0.0
        rows.append({"layer": layer.title(), "rows": count, "dropped": dropped, "dropped_pct": pct, "why": _WHY[layer]})
        previous = count
    return rows


def layer_stats() -> pd.DataFrame:
    """Rows and newest event per layer: one round trip for the flow and freshness tiles."""
    return db.run_query(
        """
        SELECT 'bronze' AS layer, count(*) AS row_count,
               max(try_cast(occurred_at AS TIMESTAMP)) AS last_event_at
        FROM food_delivery.bronze.order_events
        UNION ALL
        SELECT 'silver', count(*), max(occurred_at) FROM food_delivery.silver.order_events
        UNION ALL
        SELECT 'gold', count(*), max(occurred_at) FROM food_delivery.gold_dbt.fct_order_events
        """
    )


def last_pipeline_run() -> pd.Timestamp | None:
    """When the scheduled job last wrote silver, from Delta commit history."""
    df = db.run_query(
        """
        SELECT timestamp AS last_refresh_at
        FROM (DESCRIBE HISTORY food_delivery.silver.order_events)
        ORDER BY version DESC
        LIMIT 1
        """
    )
    return None if df.empty else df["last_refresh_at"].iloc[0]


def known_issues() -> pd.Series:
    """Counts of the known data-quality issues kept visible on Pipeline health."""
    return db.run_query(
        """
        SELECT
          (SELECT count(*) FROM food_delivery.gold_dbt.fct_orders WHERE gmv < 0) AS negative_gmv,
          (SELECT count(*) FROM food_delivery.gold_dbt.fct_order_events
             WHERE event_type NOT IN ('order_placed','order_confirmed','order_prepared',
                                      'order_picked_up','order_delivered','order_cancelled')) AS unknown_event_types,
          (SELECT count(*) FROM food_delivery.gold_dbt.fct_orders o
             LEFT JOIN food_delivery.gold_dbt.dim_vendor v ON o.vendor_id = v.vendor_id
             WHERE v.vendor_id IS NULL AND o.vendor_id IS NOT NULL) AS orphan_vendors
        """
    ).iloc[0]


def gold_model_count() -> int:
    df = db.run_query(
        """
        SELECT count(*) AS models
        FROM food_delivery.information_schema.tables
        WHERE table_schema = 'gold_dbt'
        """
    )
    return int(df["models"].iloc[0])
