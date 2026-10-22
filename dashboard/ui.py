"""Shared presentation helpers: the stylesheet loader and small HTML builders."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

_CSS = Path(__file__).with_name("style.css")


def inject_css() -> None:
    """Load the dashboard's only stylesheet. Called once per run, from app.py."""
    st.html(f"<style>{_CSS.read_text()}</style>")
