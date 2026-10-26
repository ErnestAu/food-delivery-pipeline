"""Freshness states shared by the status pill and every freshness tile.

Live under 24 hours, delayed under 2 days, stale beyond that, unknown when a layer
has no timestamp yet. The producer runs on laptop cron, so overnight gaps of several
hours are normal and shouldn't read as a problem.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

LIVE_MINUTES = 24 * 60
STALE_MINUTES = 2 * 24 * 60
LABELS = {"live": "Live", "delayed": "Delayed", "stale": "Stale", "unknown": "No data"}


def minutes_since(ts, now: datetime) -> float | None:
    """Minutes between a query timestamp and `now`. Naive timestamps are UTC (Databricks)."""
    if ts is None or pd.isna(ts):
        return None
    ts = pd.Timestamp(ts)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return (pd.Timestamp(now) - ts).total_seconds() / 60


def freshness_state(minutes: float | None) -> str:
    if minutes is None:
        return "unknown"
    if minutes < LIVE_MINUTES:
        return "live"
    if minutes < STALE_MINUTES:
        return "delayed"
    return "stale"


def humanize(minutes: float | None) -> str:
    """'just now', '12 min', '3 h 5 min', '2 d 4 h'; a dash when there's no timestamp."""
    if minutes is None:
        return "—"
    if minutes < 1:
        return "just now"
    days, rest = divmod(int(minutes), 24 * 60)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days} d" + (f" {hours} h" if hours else "")
    if hours:
        return f"{hours} h" + (f" {mins} min" if mins else "")
    return f"{mins} min"


def ago_text(minutes: float | None) -> str:
    """'12 min ago' for a timestamp; reads naturally after 'last order' or 'updated'."""
    if minutes is None:
        return "no data yet"
    text = humanize(minutes)
    return text if text == "just now" else f"{text} ago"
