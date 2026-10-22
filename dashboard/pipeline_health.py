"""Pipeline health — the deep dive behind the Overview's status pill.

Answers the questions an on-call data engineer asks, one section each:
  1. Is data arriving?          (freshness)
  2. Is volume normal?          (hourly orders vs a 7-day same-hour baseline)
  3. Is the data sane?          (known issues, tracked rather than hidden)
  4. Does every layer add up?   (row reconciliation bronze → silver → gold)
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db import run_query
from freshness import ago_text, freshness_state, minutes_since
from queries import LAYERS, known_issues, last_pipeline_run, layer_stats, reconcile
from ui import PLOTLY_CONFIG, number, palette, tile, tiles

BASELINE_COLOR = "#8e8e93"  # neutral reference line; readable on both themes
WINDOWS = {"24h": 24, "48h": 48, "72h": 72, "7d": 24 * 7, "14d": 24 * 14}

now = datetime.now(timezone.utc)
stats = layer_stats().set_index("layer")


def layer_age(layer: str) -> float | None:
    return minutes_since(stats.at[layer, "last_event_at"], now) if layer in stats.index else None


st.title("Pipeline health")
st.html(
    '<p class="fd-lede">Is data arriving, is volume normal, is the data sane, '
    "and does every layer add up?</p>"
)

# ---------- Freshness ----------
st.subheader("Freshness")
run_age = minutes_since(last_pipeline_run(), now)
st.html(
    tiles([
        tile("Pipeline last ran", ago_text(run_age), note="Latest commit to silver", state=freshness_state(run_age)),
        tile("Silver", ago_text(layer_age("silver")), note="Newest order event",
             state=freshness_state(layer_age("silver"))),
        tile("Gold", ago_text(layer_age("gold")), note="Newest order event",
             state=freshness_state(layer_age("gold"))),
    ])
)

# ---------- Volume ----------
st.subheader("Volume against the 7-day baseline")
st.html(
    '<p class="fd-muted">Orders per hour; the dashed line is the average for that hour '
    "over the previous seven days. Bars well below it flag an anomaly.</p>"
)


def volume_chart(window_hours: int) -> None:
    window_hours = int(window_hours)  # interpolated into SQL below — keep it a literal int
    df = run_query(
        f"""
        WITH hourly AS (
            SELECT date_trunc('HOUR', placed_at) AS hr, count(*) AS orders
            FROM food_delivery.gold_dbt.fct_orders
            WHERE placed_at >= (SELECT max(placed_at) FROM food_delivery.gold_dbt.fct_orders)
                               - INTERVAL {window_hours} HOURS
            GROUP BY date_trunc('HOUR', placed_at)
        ),
        baseline AS (
            SELECT hour(hr) AS hour_of_day, avg(cnt) AS expected
            FROM (
                SELECT date_trunc('HOUR', placed_at) AS hr, count(*) AS cnt
                FROM food_delivery.gold_dbt.fct_orders
                WHERE placed_at >= (SELECT max(placed_at) FROM food_delivery.gold_dbt.fct_orders)
                                   - INTERVAL 7 DAYS
                GROUP BY date_trunc('HOUR', placed_at)
            )
            GROUP BY hour(hr)
        )
        SELECT h.hr, h.orders, round(b.expected, 0) AS expected
        FROM hourly h
        JOIN baseline b ON hour(h.hr) = b.hour_of_day
        ORDER BY h.hr
        """
    )
    if df.empty:
        st.info("No orders in this window.")
        return
    fig = go.Figure()
    fig.add_bar(x=df["hr"], y=df["orders"], name="Orders", marker_color=palette()["categorical"][0])
    fig.add_scatter(
        x=df["hr"], y=df["expected"], name="7-day average, same hour",
        mode="lines", line=dict(color=BASELINE_COLOR, width=2, dash="dash"),
    )
    fig.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=8, b=0),
        bargap=0.2,
        barcornerradius=4,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None),
    )
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)


choice = st.segmented_control("Window", options=list(WINDOWS), default="72h", label_visibility="collapsed")
volume_chart(WINDOWS[choice or "72h"])

# ---------- Known issues ----------
st.subheader("Known issues, tracked not hidden")
st.html(
    '<p class="fd-muted">Real problems the dbt tests caught, left visible on purpose and '
    "counted here rather than alerted on.</p>"
)
issues = known_issues()
st.html(
    tiles([
        tile("Negative GMV orders", f"{int(issues['negative_gmv']):,}",
             note="Uncapped ¥500 discount on small orders"),
        tile("Unknown event types", f"{int(issues['unknown_event_types']):,}",
             note="Simulator events outside the agreed contract"),
        tile("Orphaned vendor IDs", f"{int(issues['orphan_vendors']):,}",
             note="Dimension IDs regenerated outside the warehouse"),
    ])
)

# ---------- Layer reconciliation ----------
st.subheader("Layer reconciliation")
counts = {layer: int(stats.at[layer, "row_count"]) if layer in stats.index else None for layer in LAYERS}
rows = reconcile(counts)
right = {"alignment": "right"}
st.dataframe(
    pd.DataFrame({
        "Layer": [r["layer"] for r in rows],
        "Rows": [number(r["rows"]) for r in rows],
        "Dropped": [number(r["dropped"]) for r in rows],
        "Dropped %": [number(r["dropped_pct"], ".1f", "%") for r in rows],
        "Why rows drop": [r["why"] for r in rows],
    }),
    hide_index=True,
    width="stretch",
    column_config={
        "Rows": st.column_config.TextColumn(**right),
        "Dropped": st.column_config.TextColumn(**right),
        "Dropped %": st.column_config.TextColumn(**right),
        "Why rows drop": st.column_config.TextColumn(width="large"),
    },
)
