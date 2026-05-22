"""Write order events to partitioned JSONL files."""
from __future__ import annotations
import json
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from simulator.models import OrderEvent


def write_events(events: list[OrderEvent], raw_base_path: str) -> dict[str, int]:
    """Partition events by date/hour and write JSONL files. Returns file counts."""
    partitioned: dict[tuple[str, str], list[OrderEvent]] = defaultdict(list)

    for evt in events:
        dt = datetime.fromisoformat(evt.occurred_at.replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d")
        hour_str = dt.strftime("%H")
        partitioned[(date_str, hour_str)].append(evt)

    base = Path(raw_base_path) / "order_events"
    file_counts: dict[str, int] = {}

    for (date_str, hour_str), batch in sorted(partitioned.items()):
        out_dir = base / date_str / hour_str
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = f"events_{hour_str}_{uuid.uuid4().hex[:8]}.jsonl"
        out_path = out_dir / filename

        with open(out_path, "w", encoding="utf-8") as f:
            for evt in batch:
                f.write(json.dumps(evt.to_dict(), ensure_ascii=False) + "\n")

        key = f"{date_str}/{hour_str}"
        file_counts[key] = file_counts.get(key, 0) + len(batch)

    return file_counts
