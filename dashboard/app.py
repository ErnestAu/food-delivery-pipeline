"""Food Delivery Ops Dashboard.

Run with:
    streamlit run dashboard/app.py
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from databricks import sql
from dotenv import load_dotenv

# ---------- Config ----------
load_dotenv()

DATABRICKS_HOST = os.environ["DATABRICKS_SERVER_HOSTNAME"]
DATABRICKS_HTTP_PATH = os.environ["DATABRICKS_HTTP_PATH"]
DATABRICKS_TOKEN = os.environ["DATABRICKS_TOKEN"]

st.set_page_config(
    page_title="Food Delivery Ops",
    page_icon="🍱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Color palette
COLOR_DELIVERED = "#22c55e"
COLOR_CANCELLED = "#ef4444"
COLOR_IN_PROGRESS = "#f59e0b"
COLOR_PRIMARY = "#3b82f6"
COLOR_MUTED = "#94a3b8"

STATUS_COLORS = {
    "delivered": COLOR_DELIVERED,
    "cancelled": COLOR_CANCELLED,
    "in_transit": COLOR_IN_PROGRESS,
    "prepared": COLOR_IN_PROGRESS,
    "confirmed": COLOR_IN_PROGRESS,
    "placed": COLOR_IN_PROGRESS,
}


# ---------- Data access ----------
@st.cache_data(ttl=300)
def run_query(query: str) -> pd.DataFrame:
    with sql.connect(
        server_hostname=DATABRICKS_HOST,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall_arrow().to_pandas()


@st.cache_data(ttl=300)
def load_daily_metrics(start: date, end: date) -> pd.DataFrame:
    return run_query(
        f"""
        SELECT *
        FROM food_delivery.gold.fct_daily_metrics
        WHERE order_date IS NOT NULL
          AND order_date BETWEEN '{start}' AND '{end}'
        ORDER BY order_date
        """
    )


@st.cache_data(ttl=300)
def load_status_breakdown(start: date, end: date) -> pd.DataFrame:
    return run_query(
        f"""
        SELECT final_status, COUNT(*) AS cnt
        FROM food_delivery.gold.fct_orders
        WHERE placed_at IS NOT NULL
          AND DATE(placed_at) BETWEEN '{start}' AND '{end}'
        GROUP BY final_status
        """
    )


@st.cache_data(ttl=300)
def load_top_vendors(start: date, end: date, limit: int = 10) -> pd.DataFrame:
    return run_query(
        f"""
        SELECT
            v.name AS vendor_name,
            v.cuisine_type,
            v.city,
            COUNT(o.order_id) AS orders,
            SUM(CASE WHEN o.final_status = 'delivered' THEN o.gmv END) AS gmv,
            ROUND(AVG(CASE WHEN o.final_status = 'delivered' THEN o.gmv END), 0) AS avg_order_value,
            ROUND(
                SUM(CASE WHEN o.final_status = 'cancelled' THEN 1 ELSE 0 END) * 1.0 / COUNT(*),
                3
            ) AS cancellation_rate
        FROM food_delivery.gold.fct_orders o
        JOIN food_delivery.gold.dim_vendor v ON o.vendor_id = v.vendor_id
        WHERE o.placed_at IS NOT NULL
          AND DATE(o.placed_at) BETWEEN '{start}' AND '{end}'
        GROUP BY v.name, v.cuisine_type, v.city
        ORDER BY gmv DESC NULLS LAST
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=300)
def load_cuisine_mix(start: date, end: date) -> pd.DataFrame:
    return run_query(
        f"""
        SELECT
            v.cuisine_type,
            COUNT(o.order_id) AS orders,
            SUM(CASE WHEN o.final_status = 'delivered' THEN o.gmv END) AS gmv
        FROM food_delivery.gold.fct_orders o
        JOIN food_delivery.gold.dim_vendor v ON o.vendor_id = v.vendor_id
        WHERE o.placed_at IS NOT NULL
          AND DATE(o.placed_at) BETWEEN '{start}' AND '{end}'
        GROUP BY v.cuisine_type
        ORDER BY gmv DESC NULLS LAST
        """
    )


@st.cache_data(ttl=300)
def load_hour_heatmap(start: date, end: date) -> pd.DataFrame:
    return run_query(
        f"""
        SELECT
            DAYOFWEEK(placed_at) AS dow,        -- 1=Sun, 7=Sat
            HOUR(placed_at) AS hour_of_day,
            COUNT(*) AS orders
        FROM food_delivery.gold.fct_orders
        WHERE placed_at IS NOT NULL
          AND DATE(placed_at) BETWEEN '{start}' AND '{end}'
        GROUP BY DAYOFWEEK(placed_at), HOUR(placed_at)
        """
    )


@st.cache_data(ttl=300)
def load_lifecycle_stages(start: date, end: date) -> pd.DataFrame:
    """Average minutes spent in each stage of the order lifecycle, per day."""
    return run_query(
        f"""
        SELECT
            DATE(placed_at) AS order_date,
            AVG((unix_timestamp(confirmed_at) - unix_timestamp(placed_at)) / 60.0) AS confirm_wait,
            AVG((unix_timestamp(prepared_at) - unix_timestamp(confirmed_at)) / 60.0) AS prep,
            AVG((unix_timestamp(picked_up_at) - unix_timestamp(prepared_at)) / 60.0) AS pickup_wait,
            AVG((unix_timestamp(delivered_at) - unix_timestamp(picked_up_at)) / 60.0) AS in_transit
        FROM food_delivery.gold.fct_orders
        WHERE final_status = 'delivered'
          AND placed_at IS NOT NULL
          AND DATE(placed_at) BETWEEN '{start}' AND '{end}'
        GROUP BY DATE(placed_at)
        ORDER BY DATE(placed_at)
        """
    )


@st.cache_data(ttl=300)
def load_cancellation_reasons(start: date, end: date) -> pd.DataFrame:
    return run_query(
        f"""
        SELECT
            cancelled_by,
            cancel_reason,
            COUNT(*) AS cnt
        FROM food_delivery.gold.fct_orders
        WHERE final_status = 'cancelled'
          AND placed_at IS NOT NULL
          AND DATE(placed_at) BETWEEN '{start}' AND '{end}'
        GROUP BY cancelled_by, cancel_reason
        ORDER BY cnt DESC
        """
    )


@st.cache_data(ttl=300)
def load_date_range() -> tuple[date, date]:
    """Get earliest and latest order dates available."""
    df = run_query(
        """
        SELECT
            MIN(order_date) AS min_date,
            MAX(order_date) AS max_date
        FROM food_delivery.gold.fct_daily_metrics
        WHERE order_date IS NOT NULL
        """
    )
    return df["min_date"].iloc[0], df["max_date"].iloc[0]


# ---------- Sidebar ----------
st.sidebar.title("🎛️ Filters")

min_date, max_date = load_date_range()

# Default to last 30 complete days (skip today since it's partial)
default_end = max_date - timedelta(days=1) if max_date == date.today() else max_date
default_start = max(min_date, default_end - timedelta(days=30))

date_range = st.sidebar.date_input(
    "Date range",
    value=(default_start, default_end),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = end_date = date_range  # fallback if user selected single date

st.sidebar.caption(f"Data available: {min_date} → {max_date}")
st.sidebar.divider()

quick_range = st.sidebar.radio(
    "Quick ranges",
    ["Custom", "Last 7 days", "Last 30 days", "Last 90 days", "All time"],
    index=0,
)
if quick_range != "Custom":
    if quick_range == "All time":
        start_date, end_date = min_date, default_end
    else:
        days = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}[quick_range]
        end_date = default_end
        start_date = max(min_date, end_date - timedelta(days=days - 1))

st.sidebar.caption(f"Showing {start_date} → {end_date}")

if st.sidebar.button("🔄 Refresh data"):
    st.cache_data.clear()
    st.rerun()

# ---------- Page header ----------
st.title("🍱 Food Delivery Ops")
st.caption(
    f"`food_delivery.gold` · range: **{start_date}** → **{end_date}** "
    f"· cache 5min · use sidebar to filter"
)

# ---------- Load main data ----------
daily = load_daily_metrics(start_date, end_date)

if daily.empty:
    st.warning("No data in the selected range. Try widening the date filter.")
    st.stop()

# ---------- KPI tiles ----------
total_orders = int(daily["total_orders"].sum())
total_gmv = int(daily["total_gmv"].fillna(0).sum())
total_delivered = int(daily["delivered_orders"].sum())
total_cancelled = int(daily["cancelled_orders"].sum())
avg_order_value = total_gmv / max(total_delivered, 1)
overall_cancel_rate = total_cancelled / max(total_orders, 1)
avg_delivery_time = daily["avg_delivery_time_minutes"].dropna().mean() or 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total orders", f"{total_orders:,}")
k2.metric("Total GMV", f"¥{total_gmv:,}")
k3.metric("Avg order value", f"¥{avg_order_value:,.0f}")
k4.metric(
    "Cancellation rate",
    f"{overall_cancel_rate * 100:.1f}%",
    delta_color="inverse",
)
k5.metric("Avg delivery time", f"{avg_delivery_time:.1f} min")

st.divider()

# ---------- Trends ----------
st.subheader("📈 Daily trends")

trend_col1, trend_col2 = st.columns(2)

with trend_col1:
    fig = px.area(
        daily,
        x="order_date",
        y=["delivered_orders", "cancelled_orders", "in_progress_orders"],
        labels={"value": "Orders", "order_date": "Date", "variable": "Status"},
        color_discrete_map={
            "delivered_orders": COLOR_DELIVERED,
            "cancelled_orders": COLOR_CANCELLED,
            "in_progress_orders": COLOR_IN_PROGRESS,
        },
        title="Orders by status",
    )
    fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0), legend_title=None)
    st.plotly_chart(fig, use_container_width=True)

with trend_col2:
    fig = px.line(
        daily,
        x="order_date",
        y="total_gmv",
        labels={"order_date": "Date", "total_gmv": "GMV (¥)"},
        title="Daily GMV",
    )
    fig.update_traces(line_color=COLOR_PRIMARY, line_width=2)
    fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True)

trend_col3, trend_col4 = st.columns(2)

with trend_col3:
    fig = px.line(
        daily,
        x="order_date",
        y="cancellation_rate",
        labels={"order_date": "Date", "cancellation_rate": "Cancellation rate"},
        title="Cancellation rate over time",
    )
    fig.update_traces(line_color=COLOR_CANCELLED, line_width=2)
    fig.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=40, b=0),
        yaxis_tickformat=".1%",
    )
    st.plotly_chart(fig, use_container_width=True)

with trend_col4:
    stages = load_lifecycle_stages(start_date, end_date)
    if not stages.empty:
        stages_long = stages.melt(
            id_vars="order_date",
            var_name="stage",
            value_name="minutes",
        )
        stage_labels = {
            "confirm_wait": "1. Confirm wait",
            "prep": "2. Prep time",
            "pickup_wait": "3. Pickup wait",
            "in_transit": "4. In transit",
        }
        stages_long["stage"] = stages_long["stage"].map(stage_labels)
        # Force stack order from start of lifecycle → end
        category_order = list(stage_labels.values())
        fig = px.area(
            stages_long,
            x="order_date",
            y="minutes",
            color="stage",
            category_orders={"stage": category_order},
            labels={"order_date": "Date", "minutes": "Minutes", "stage": ""},
            title="Where time is spent in the order lifecycle",
            color_discrete_sequence=["#fbbf24", "#f97316", "#a855f7", "#22c55e"],
        )
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Not enough delivered orders for lifecycle breakdown.")

st.divider()

# ---------- Status funnel + Cuisine mix ----------
st.subheader("🎯 Operational breakdown")

ops_col1, ops_col2 = st.columns(2)

with ops_col1:
    status_df = load_status_breakdown(start_date, end_date)
    status_df["color"] = status_df["final_status"].map(STATUS_COLORS).fillna(COLOR_MUTED)
    status_df = status_df.sort_values("cnt", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=status_df["cnt"],
            y=status_df["final_status"],
            orientation="h",
            marker_color=status_df["color"],
            text=status_df["cnt"].map(lambda x: f"{x:,}"),
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Order status distribution",
        height=300,
        margin=dict(l=0, r=20, t=40, b=0),
        xaxis_title="Orders",
        yaxis_title=None,
    )
    st.plotly_chart(fig, use_container_width=True)

with ops_col2:
    cuisine_df = load_cuisine_mix(start_date, end_date)
    cuisine_df = cuisine_df.dropna(subset=["gmv"]).sort_values("gmv", ascending=True)
    fig = px.bar(
        cuisine_df,
        x="gmv",
        y="cuisine_type",
        orientation="h",
        labels={"gmv": "GMV (¥)", "cuisine_type": ""},
        title="GMV by cuisine type",
    )
    fig.update_traces(marker_color=COLOR_PRIMARY)
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True)

# ---------- Hourly heatmap ----------
st.subheader("🗓️ Order volume heatmap")

heatmap = load_hour_heatmap(start_date, end_date)

if not heatmap.empty:
    # Reshape: rows = day of week, cols = hour of day
    dow_names = {1: "Sun", 2: "Mon", 3: "Tue", 4: "Wed", 5: "Thu", 6: "Fri", 7: "Sat"}
    heatmap["day_name"] = heatmap["dow"].map(dow_names)

    pivot = heatmap.pivot(index="day_name", columns="hour_of_day", values="orders").fillna(0)
    # Reorder rows Mon → Sun for natural reading
    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    pivot = pivot.reindex([d for d in day_order if d in pivot.index])

    fig = px.imshow(
        pivot,
        labels=dict(x="Hour of day (UTC)", y="", color="Orders"),
        aspect="auto",
        color_continuous_scale="Blues",
    )
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
    fig.update_xaxes(dtick=2)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Heatmap needs more data — widen the date range.")

# ---------- Vendor leaderboard ----------
st.subheader("🏆 Top vendors")

vendors_df = load_top_vendors(start_date, end_date, limit=15)
if not vendors_df.empty:
    display_df = vendors_df.copy()
    display_df["gmv"] = display_df["gmv"].apply(lambda x: f"¥{int(x):,}" if pd.notna(x) else "—")
    display_df["avg_order_value"] = display_df["avg_order_value"].apply(
        lambda x: f"¥{int(x):,}" if pd.notna(x) else "—"
    )
    display_df["cancellation_rate"] = display_df["cancellation_rate"].apply(
        lambda x: f"{x * 100:.1f}%" if pd.notna(x) else "—"
    )
    display_df.columns = ["Vendor", "Cuisine", "City", "Orders", "GMV", "Avg order", "Cancel rate"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.info("No vendor activity in this range.")

# ---------- Cancellation breakdown ----------
st.subheader("❌ Cancellation analysis")

cancel_df = load_cancellation_reasons(start_date, end_date)

cancel_col1, cancel_col2 = st.columns(2)

with cancel_col1:
    by_actor = cancel_df.groupby("cancelled_by")["cnt"].sum().reset_index().sort_values("cnt", ascending=False)
    if not by_actor.empty:
        fig = px.pie(
            by_actor,
            values="cnt",
            names="cancelled_by",
            title="Who cancels?",
            hole=0.5,
        )
        fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No cancellations in this range.")

with cancel_col2:
    if not cancel_df.empty:
        fig = px.bar(
            cancel_df.sort_values("cnt", ascending=True).tail(10),
            x="cnt",
            y="cancel_reason",
            color="cancelled_by",
            orientation="h",
            labels={"cnt": "Cancellations", "cancel_reason": "", "cancelled_by": "Cancelled by"},
            title="Top cancellation reasons",
        )
        fig.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

# ---------- Raw data ----------
with st.expander("🔍 Raw daily metrics (debug)"):
    st.dataframe(daily, use_container_width=True, hide_index=True)
