"""Shared Databricks SQL connection + query helper for the dashboard pages."""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from databricks import sql
from dotenv import load_dotenv

load_dotenv()  # local dev only — no-op on Streamlit Cloud


def get_secret(key: str) -> str:
    """Read a secret from Streamlit Cloud secrets, falling back to env vars locally."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError, AttributeError):
        return os.environ[key]


DATABRICKS_HOST = get_secret("DATABRICKS_SERVER_HOSTNAME")
DATABRICKS_HTTP_PATH = get_secret("DATABRICKS_HTTP_PATH")
DATABRICKS_TOKEN = get_secret("DATABRICKS_TOKEN")


@st.cache_data(ttl=300)
def run_query(query: str, params: dict | None = None) -> pd.DataFrame:
    with sql.connect(
        server_hostname=DATABRICKS_HOST,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall_arrow().to_pandas()
