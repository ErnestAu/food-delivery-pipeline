"""Operations — the business view of the gold layer.

Five views over one date range: headline KPIs, a trend with a metric switch, when
orders arrive, the top vendors, and why orders get cancelled.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db import run_query
from ui import PLOTLY_CONFIG, palette

RANGES = {"7d": 7, "30d": 30, "90d": 90, "All": None}
METRICS = ["Orders", "GMV", "Cancellation rate", "Delivery time"]
ACTORS = ["customer", "vendor", "driver", "system"]  # fixed order, so each keeps its color
OTHER_COLOR = "#8e8e93"
CHART_MARGIN = dict(l=0, r=0, t=8, b=0)


# ---------- Data access ----------
def load_date_range() -> tuple[date, date]:
    df = run_query(
        """
        SELECT MIN(order_date) AS min_date, MAX(order_date) AS max_date
        FROM food_delivery.gold_dbt.fct_daily_metrics
        WHERE order_date IS NOT NULL
        """
    )
    return df["min_date"].iloc[0], df["max_date"].iloc[0]


def load_daily_metrics(start: date, end: date) -> pd.DataFrame:
    return run_query(
        """
        SELECT *
        FROM food_delivery.gold_dbt.fct_daily_metrics
        WHERE order_date IS NOT NULL
          AND order_date BETWEEN :start AND :end
        ORDER BY order_date
        """,
        params={"start": str(start), "end": str(end)},
    )


def load_hour_heatmap(start: date, end: date) -> pd.DataFrame:
    return run_query(
        """
        SELECT
            DAYOFWEEK(placed_at) AS dow,        -- 1=Sun, 7=Sat
            HOUR(placed_at) AS hour_of_day,
            COUNT(*) AS orders
        FROM food_delivery.gold_dbt.fct_orders
        WHERE placed_at IS NOT NULL
          AND DATE(placed_at) BETWEEN :start AND :end
        GROUP BY DAYOFWEEK(placed_at), HOUR(placed_at)
        """,
        params={"start": str(start), "end": str(end)},
    )


def load_top_vendors(start: date, end: date) -> pd.DataFrame:
    return run_query(
        """
        SELECT
            v.name AS vendor_name,
            v.cuisine_type,
            COUNT(o.order_id) AS orders,
            SUM(CASE WHEN o.final_status = 'delivered' THEN o.gmv END) AS gmv,
            ROUND(SUM(CASE WHEN o.final_status = 'cancelled' THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 3)
                AS cancellation_rate
        FROM food_delivery.gold_dbt.fct_orders o
        JOIN food_delivery.gold_dbt.dim_vendor v ON o.vendor_id = v.vendor_id
        WHERE o.placed_at IS NOT NULL
          AND DATE(o.placed_at) BETWEEN :start AND :end
        GROUP BY v.name, v.cuisine_type
        ORDER BY gmv DESC NULLS LAST
        LIMIT 10
        """,
        params={"start": str(start), "end": str(end)},
    )


def load_cancellation_reasons(start: date, end: date) -> pd.DataFrame:
    return run_query(
        """
        SELECT cancelled_by, cancel_reason, COUNT(*) AS cnt
        FROM food_delivery.gold_dbt.fct_orders
        WHERE final_status = 'cancelled'
          AND placed_at IS NOT NULL
          AND DATE(placed_at) BETWEEN :start AND :end
        GROUP BY cancelled_by, cancel_reason
        ORDER BY cnt DESC
        """,
        params={"start": str(start), "end": str(end)},
    )


# ---------- Header and date range ----------
min_date, max_date = load_date_range()
end_date = max_date - timedelta(days=1) if max_date == date.today() else max_date  # skip the partial day

title_col, range_col = st.columns([3, 2], vertical_alignment="bottom")
title_col.title("Operations")
choice = range_col.segmented_control("Date range", list(RANGES), default="30d", label_visibility="collapsed")
days = RANGES[choice or "30d"]
start_date = min_date if days is None else max(min_date, end_date - timedelta(days=days - 1))
st.html(f'<p class="fd-muted">{start_date:%-d %b %Y} – {end_date:%-d %b %Y} · from the dbt gold layer</p>')

daily = load_daily_metrics(start_date, end_date)
if daily.empty:
    st.info("No orders in this range yet.")
    st.stop()

colors = palette()

# ---------- KPIs ----------
orders = int(daily["total_orders"].sum())
gmv = int(daily["total_gmv"].fillna(0).sum())
delivered = int(daily["delivered_orders"].sum())
cancelled = int(daily["cancelled_orders"].sum())
k1, k2, k3, k4 = st.columns(4)
k1.metric("Orders", f"{orders:,}")
k2.metric("GMV", f"¥{gmv:,}")
k3.metric("Average order", f"¥{gmv / max(delivered, 1):,.0f}")
k4.metric("Cancellation rate", f"{cancelled / max(orders, 1):.1%}")

# ---------- Trend ----------
st.subheader("Trend")
metric = st.segmented_control("Metric", METRICS, default="Orders", label_visibility="collapsed") or "Orders"
fig = go.Figure()
if metric == "Orders":
    fig.add_bar(x=daily["order_date"], y=daily["delivered_orders"], name="Delivered",
                marker_color=colors["categorical"][0])
    fig.add_bar(x=daily["order_date"], y=daily["cancelled_orders"], name="Cancelled",
                marker_color=colors["categorical"][1])
    fig.update_layout(barmode="stack", barcornerradius=4,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None,
                                  traceorder="normal"))
else:
    column, tickformat = {
        "GMV": ("total_gmv", "~s"),
        "Cancellation rate": ("cancellation_rate", ".1%"),
        "Delivery time": ("avg_delivery_time_minutes", ".0f"),
    }[metric]
    fig.add_scatter(x=daily["order_date"], y=daily[column], name=metric, mode="lines",
                    line=dict(color=colors["categorical"][0], width=2))
    fig.update_yaxes(tickformat=tickformat, ticksuffix=" min" if metric == "Delivery time" else "")
    fig.update_layout(showlegend=False)
fig.update_layout(height=320, margin=CHART_MARGIN, hovermode="x unified")
st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)

# ---------- When orders arrive ----------
st.subheader("When orders arrive")
st.html('<p class="fd-muted">Orders by weekday and hour (UTC) across the range, with today\'s weekday last.</p>')
heatmap = load_hour_heatmap(start_date, end_date)
if heatmap.empty:
    st.info("Not enough orders in this range for the heatmap.")
else:
    dow_names = {1: "Sun", 2: "Mon", 3: "Tue", 4: "Wed", 5: "Thu", 6: "Fri", 7: "Sat"}  # Spark DAYOFWEEK
    heatmap["day"] = heatmap["dow"].map(dow_names)
    pivot = heatmap.pivot(index="day", columns="hour_of_day", values="orders").fillna(0)
    iso_to_name = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}
    today = datetime.now().isoweekday()
    week = [iso_to_name[((today - offset - 1) % 7) + 1] for offset in range(6, -1, -1)]
    pivot = pivot.reindex([d for d in week if d in pivot.index])
    fig = px.imshow(pivot, labels=dict(x="Hour of day (UTC)", y="", color="Orders"), aspect="auto",
                    color_continuous_scale=colors["sequential"])
    fig.update_layout(height=280, margin=CHART_MARGIN, coloraxis_colorbar=dict(thickness=10, title=None))
    fig.update_xaxes(dtick=2)
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)

# ---------- Top vendors ----------
st.subheader("Top vendors")
vendors = load_top_vendors(start_date, end_date)
if vendors.empty:
    st.info("No vendor activity in this range.")
else:
    vendors["cancellation_rate"] = vendors["cancellation_rate"] * 100  # one decimal for every row
    st.dataframe(
        vendors,
        hide_index=True,
        width="stretch",
        column_config={
            "vendor_name": st.column_config.TextColumn("Vendor"),
            "cuisine_type": st.column_config.TextColumn("Cuisine"),
            "orders": st.column_config.NumberColumn("Orders", format="localized"),
            "gmv": st.column_config.NumberColumn("GMV (¥)", format="localized"),
            "cancellation_rate": st.column_config.NumberColumn("Cancel rate", format="%.1f%%"),
        },
    )

# ---------- Cancellations ----------
st.subheader("Cancellations")
cancel = load_cancellation_reasons(start_date, end_date)
if cancel.empty:
    st.info("No cancellations in this range.")
else:
    cancel["actor"] = cancel["cancelled_by"].where(cancel["cancelled_by"].isin(ACTORS), "other")
    actor_order = ACTORS + ["other"]
    cancel["rank"] = cancel["actor"].map({a: i for i, a in enumerate(actor_order)})
    cancel = cancel.sort_values(["rank", "cnt"], ascending=[True, False])
    actor_colors = dict(zip(ACTORS, colors["categorical"])) | {"other": OTHER_COLOR}
    fig = go.Figure()
    for actor in actor_order:
        part = cancel[cancel["actor"] == actor]
        if part.empty:
            continue
        fig.add_bar(
            y=part["cancel_reason"].str.replace("_", " "), x=part["cnt"], orientation="h",
            name=actor.title(), marker_color=actor_colors[actor],
            text=part["cnt"], textposition="outside", cliponaxis=False,
        )
    reasons = list(cancel["cancel_reason"].str.replace("_", " "))
    fig.update_yaxes(categoryorder="array", categoryarray=reasons[::-1])  # grouped by actor, top down
    fig.update_layout(
        height=60 + 30 * len(reasons), margin=dict(l=0, r=24, t=8, b=0), barcornerradius=4,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None,
                    traceorder="normal"),
    )
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)
