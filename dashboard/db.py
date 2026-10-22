"""Shared Databricks SQL connection + query helper for the dashboard pages."""
from __future__ import annotations

import logging
import os
from typing import NoReturn

import pandas as pd
import streamlit as st
from databricks import sql
from dotenv import load_dotenv

from status import MESSAGES, classify_error

load_dotenv()  # local dev only — no-op on Streamlit Cloud

log = logging.getLogger(__name__)


def get_secret(key: str) -> str:
    """Read a secret from Streamlit Cloud secrets, falling back to env vars locally."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError, AttributeError):
        return os.environ[key]


DATABRICKS_HOST = get_secret("DATABRICKS_SERVER_HOSTNAME")
DATABRICKS_HTTP_PATH = get_secret("DATABRICKS_HTTP_PATH")
DATABRICKS_TOKEN = get_secret("DATABRICKS_TOKEN")


@st.cache_data(ttl=300, show_spinner="Loading live data…")
def _query(query: str, params: dict | None = None) -> pd.DataFrame:
    with sql.connect(
        server_hostname=DATABRICKS_HOST,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall_arrow().to_pandas()


def run_query(query: str, params: dict | None = None) -> pd.DataFrame:
    """Run a query; on any warehouse failure, show a status instead of a stack trace."""
    try:
        return _query(query, params)
    except Exception as exc:
        kind = classify_error(exc)
        log.exception("Warehouse query failed (%s)", kind)  # full error stays in the app logs
        show_status(kind)


def show_status(kind: str) -> NoReturn:
    """Render a public-safe status and stop the page. The keep-alive reads the container key."""
    with st.container(key=f"dashboard-status-{kind}"):
        st.warning(f"**Live data is unavailable right now.** {MESSAGES[kind]}")
    st.stop()
