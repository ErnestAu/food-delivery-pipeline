"""Warehouse queries shared by the Overview and Pipeline health pages."""
from __future__ import annotations

LAYERS = ("bronze", "silver", "gold")

_WHY = {
    "bronze": "Raw events as landed by Auto Loader",
    "silver": "Duplicates removed on event ID; events more than an hour late dropped by the watermark",
    "gold": "Modeled by dbt; expected to match silver",
}


def reconcile(counts: dict[str, int | None]) -> list[dict]:
    """Rows per layer and how many each layer dropped relative to the one before it."""
    rows, previous = [], None
    for layer in LAYERS:
        count = counts.get(layer)
        if previous is None or count is None:
            dropped = pct = None
        else:
            dropped = previous - count
            pct = dropped / previous * 100 if previous else 0.0
        rows.append({"layer": layer.title(), "rows": count, "dropped": dropped, "dropped_pct": pct, "why": _WHY[layer]})
        previous = count
    return rows
