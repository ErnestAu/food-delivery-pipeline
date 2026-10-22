"""Food Delivery Pipeline — Streamlit multipage entrypoint.

Run with:
    streamlit run dashboard/app.py

Pages (top navigation):
    - Overview (default) — what this is, how data flows, proof it's live
    - Pipeline health — DE observability
    - Operations — business KPIs
"""
import streamlit as st

from ui import inject_css

st.set_page_config(page_title="Food Delivery Pipeline", layout="wide")
inject_css()

overview = st.Page("overview.py", title="Overview", default=True)
health = st.Page("pipeline_health.py", title="Pipeline health")
ops = st.Page("food_delivery_ops.py", title="Operations")

st.navigation([overview, health, ops], position="top").run()

# The keep-alive check reads this marker as "the page rendered with data". st.stop()
# and uncaught errors end the script before it, so it only appears on a clean render.
with st.container(key="dashboard-ready"):
    st.html("<span></span>")
