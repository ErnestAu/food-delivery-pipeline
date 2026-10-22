"""Food Delivery Pipeline — Streamlit multipage entrypoint.

Run with:
    streamlit run dashboard/app.py

Pages:
    - Pipeline Health   (default landing) — DE observability
    - Food Delivery Ops — business KPIs
"""
import streamlit as st

st.set_page_config(
    page_title="Food Delivery Pipeline",
    page_icon="🍱",
    layout="wide",
    initial_sidebar_state="expanded",
)

health = st.Page(
    "pipeline_health.py",
    title="Pipeline Health",
    icon="🟢",
    default=True,
)
ops = st.Page(
    "food_delivery_ops.py",
    title="Food Delivery Ops",
    icon="🍱",
)

st.navigation([health, ops]).run()

# The keep-alive check reads this marker as "the page rendered with data". st.stop()
# and uncaught errors end the script before it, so it only appears on a clean render.
with st.container(key="dashboard-ready"):
    st.html("<span></span>")
