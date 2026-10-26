"""Overview — what this project is, how data flows, and proof that it's live.

The landing page for a reader with a minute to spare: one sentence of purpose, the
medallion flow with live counts, three health tiles, and the decisions behind it.
"""
from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from freshness import LABELS, ago_text, freshness_state, minutes_since
from queries import LAYERS, known_issues, last_pipeline_run, layer_stats
from ui import Node, defs, flow, status_pill, tile, tiles

REPO_URL = "https://github.com/ErnestAu/food-delivery-pipeline"

now = datetime.now(timezone.utc)
stats = layer_stats().set_index("layer")
rows = {layer: int(stats.at[layer, "row_count"]) if layer in stats.index else None for layer in LAYERS}
models = int(stats.at["models", "row_count"]) if "models" in stats.index else None
age = {
    layer: minutes_since(stats.at[layer, "last_event_at"], now) if layer in stats.index else None
    for layer in LAYERS
}
gold_state = freshness_state(age["gold"])

# ---------- Header ----------
title_col, pill_col = st.columns([3, 1], vertical_alignment="center")
title_col.title("Food Delivery Pipeline")
pill_text = f"{LABELS[gold_state]} · last order {ago_text(age['gold'])}"
pill_col.html(f'<div class="fd-align-end">{status_pill(gold_state, pill_text, age["gold"])}</div>')
st.html(
    '<p class="fd-lede">A simulated food-delivery marketplace, streamed through a medallion '
    "lakehouse on Databricks, modeled and tested with dbt, and monitored end to end.</p>"
)

# ---------- Medallion flow ----------
st.html(
    flow([
        Node("Source", "Simulator, hourly to S3", updated="Order lifecycle events", counts=False),
        Node("Bronze", "Auto Loader", rows["bronze"], f"newest event {ago_text(age['bronze'])}"),
        Node("Silver", "Dedup + watermark", rows["silver"], f"newest event {ago_text(age['silver'])}"),
        Node("Gold", f"dbt · {models} models" if models else "dbt", rows["gold"], f"newest event {ago_text(age['gold'])}"),
        Node("Serving", "This dashboard", updated="Cached for 15 minutes", counts=False),
    ])
)

# ---------- At a glance ----------
st.subheader("At a glance")
run_age = minutes_since(last_pipeline_run(), now)
issues = known_issues()
st.html(
    tiles([
        tile("Newest order", ago_text(age["gold"]), state=gold_state),
        tile("Pipeline last ran", ago_text(run_age), state=freshness_state(run_age)),
        tile("Known data issues", f"{int(issues.sum()):,}", note="Tracked on Pipeline health, not hidden"),
    ])
)
st.page_link("pipeline_health.py", label="Freshness, volume and data quality", icon=":material/arrow_forward:")

# ---------- How it's built ----------
st.subheader("How it's built")
st.html(
    defs([
        ("Ingestion", "Auto Loader batch every hour; streaming would be over-engineering at this cadence."),
        ("Processing", "Lakeflow SDP in PySpark: deduplicated on event ID, one-hour watermark for late events."),
        ("Modeling", "Gold modeled in dbt; tests fail the build in CI and warn in production."),
        ("Orchestration", "One Databricks job: the SDP pipeline, then dbt run and test, every hour."),
        ("Observability", "Freshness alert, job-failure emails, and an outside-in health check "
                          "that files an issue per outage."),
    ])
)

links = st.columns(3)
links[0].page_link("pipeline_health.py", label="Pipeline health", icon=":material/monitor_heart:")
links[1].page_link("operations.py", label="Operations", icon=":material/bar_chart:")
links[2].page_link(REPO_URL, label="Source on GitHub", icon=":material/code:")
