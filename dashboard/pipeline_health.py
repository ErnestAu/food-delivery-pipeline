"""Pipeline Health — data-engineering observability view.

Answers the three questions an on-call DE asks:
  1. Is data arriving?   (freshness)
  2. Is volume normal?   (hourly trend)
  3. Is the data sane?   (quality tracker + medallion funnel)
"""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db import run_query

FRESHNESS_STALE_MINUTES = 60 * 24 * 2  # 2 days — only flag genuinely stale data

st.title("🟢 Pipeline Health")
st.caption(
    "Data-engineering observability — freshness, volume, and data-quality tracking "
    "across the medallion layers. Cache 5 min."
)

if st.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()

# ---------- Panel 1: Freshness ----------
st.subheader("🕒 Freshness — minutes since the newest event")
st.caption("Flagged stale only if the newest event is over 2 days old. (Operational paging is handled separately by a Databricks SQL Alert.)")

fresh = run_query(
    """
    -- greatest(...,0): simulator assigns random minutes across the whole hour,
    -- so a "live" event can land slightly ahead of wall-clock time when queried.
    -- Clamp to 0 ("just now") instead of showing a negative minutes-ago.
    SELECT 'silver' AS layer,
           greatest(timestampdiff(MINUTE, max(occurred_at), current_timestamp()), 0) AS mins
    FROM food_delivery.silver.order_events
    UNION ALL
    SELECT 'gold',
           greatest(timestampdiff(MINUTE, max(occurred_at), current_timestamp()), 0)
    FROM food_delivery.gold_dbt.fct_order_events
    """
)
order = {"silver": 0, "gold": 1}
fresh = fresh.sort_values("layer", key=lambda s: s.map(order))

fcols = st.columns(len(fresh))
for col, (_, row) in zip(fcols, fresh.iterrows()):
    mins = row["mins"]
    label = f"{row['layer'].title()} — last event"
    if mins is None:
        col.metric(label, "no data")
    else:
        stale = int(mins) > FRESHNESS_STALE_MINUTES
        col.metric(
            label,
            f"{int(mins)} min ago",
            delta="⚠️ stale" if stale else "✅ fresh",
            delta_color="inverse" if stale else "normal",
        )

st.divider()

# ---------- Panel 2: Volume trend (vs 7-day-average baseline) ----------
st.subheader("📦 Volume — orders per hour vs 7-day average")
st.caption(
    "Bars = actual orders per hour (anchored to the newest event, so pipeline lag never shows a false gap). "
    "Dotted line = average for that hour-of-day over the trailing 7 days — bars dropping well below it flag an anomaly."
)


def volume_panel(window_hours: int) -> None:
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
    fig.add_bar(x=df["hr"], y=df["orders"], name="Actual", marker_color="#3b82f6")
    fig.add_scatter(
        x=df["hr"],
        y=df["expected"],
        name="7-day avg (same hour)",
        mode="lines",
        line=dict(color="#f59e0b", width=2, dash="dot"),
    )
    fig.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, width="stretch")


window_options = {"24h": 24, "48h": 48, "72h": 72, "7d": 24 * 7, "14d": 24 * 14}
choice = st.segmented_control(
    "Window",
    options=list(window_options.keys()),
    default="72h",
    label_visibility="collapsed",
)
volume_panel(window_options[choice or "72h"])

st.divider()

# ---------- Panel 3: Data-quality tracker ----------
st.subheader("🧪 Data quality — known issues we're tracking")
st.caption(
    "These run as `warn`-severity dbt tests: surfaced here, **not** alerted "
    "(they're known/unfixed, so an alert would be constant noise). Tracked to watch the trend."
)

q = run_query(
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

qcols = st.columns(3)
qcols[0].metric("Negative GMV orders", f"{int(q['negative_gmv']):,}")
qcols[1].metric("Unknown event types", f"{int(q['unknown_event_types']):,}")
qcols[2].metric("Orphan vendor FKs", f"{int(q['orphan_vendors']):,}")

st.divider()

# ---------- Panel 4: Medallion funnel ----------
st.subheader("🔻 Medallion funnel — event row counts by layer")
st.caption("Large drops between layers can signal silent loss (e.g. watermark drops in silver).")

funnel = run_query(
    """
    SELECT 'bronze' AS layer, count(*) AS row_count FROM food_delivery.bronze.order_events
    UNION ALL SELECT 'silver', count(*) FROM food_delivery.silver.order_events
    UNION ALL SELECT 'gold', count(*) FROM food_delivery.gold_dbt.fct_order_events
    """
)
funnel_order = {"bronze": 0, "silver": 1, "gold": 2}
funnel = funnel.sort_values("layer", key=lambda s: s.map(funnel_order))
fig = px.funnel(funnel, x="row_count", y="layer", labels={"row_count": "Events", "layer": ""})
fig.update_traces(marker_color="#6366f1")
fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig, width="stretch")
