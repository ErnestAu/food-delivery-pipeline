"""Inject data defects into a batch of OrderEvents, gated by --corrupt-rate.
Off by default — only used to demo dbt tests catching what Spark won't."""
from __future__ import annotations
import random
from collections import defaultdict

from simulator.models import OrderEvent

DEFECT_TYPES = [
    "duplicate_event_id",
    "null_fk",
    "negative_amount",
    "unannounced_event_type",
    "orphan_vendor",
    "timestamp_inversion",
]

# New event types a non-data team might bolt onto the existing stream
# without telling the data platform team — schema drift, not garbage data.
UNANNOUNCED_EVENT_TYPES = [
    {
        "event_type": "order_shared_to_social",
        "payload": lambda rng: {
            "platform": rng.choice(["instagram", "tiktok", "x"]),
            "referral_code": f"ref_{rng.randint(1000, 9999)}",
        },
    },
    {
        "event_type": "delivery_photo_uploaded",
        "payload": lambda rng: {
            "photo_url": f"https://cdn.example.com/proof/{rng.randint(100000, 999999)}.jpg",
        },
    },
]


def corrupt_events(events: list[OrderEvent], rate: float, rng: random.Random) -> list[OrderEvent]:
    """Mutate a fraction of orders in-place to inject realistic data defects."""
    if rate <= 0:
        return events

    by_order: dict[str, list[OrderEvent]] = defaultdict(list)
    for evt in events:
        by_order[evt.order_id].append(evt)

    order_ids = list(by_order.keys())
    n_corrupt = int(len(order_ids) * rate)
    targets = rng.sample(order_ids, n_corrupt)

    for order_id in targets:
        group = by_order[order_id]
        defect = rng.choice(DEFECT_TYPES)
        _apply_defect(defect, group, events, rng)

    print(f"  Corrupted {n_corrupt}/{len(order_ids)} orders ({rate:.0%} target rate).")
    return events


def _apply_defect(defect: str, group: list[OrderEvent], all_events: list[OrderEvent], rng: random.Random) -> None:
    if defect == "duplicate_event_id":
        victim = rng.choice(group)
        donor = rng.choice(all_events)
        victim.event_id = donor.event_id

    elif defect == "null_fk":
        victim = rng.choice(group)
        field = rng.choice(["customer_id", "vendor_id", "driver_id"])
        setattr(victim, field, None)

    elif defect == "negative_amount":
        placed = next((e for e in group if e.event_type == "order_placed"), None)
        if placed:
            key = rng.choice(["gmv", "food_cost"])
            if key in placed.payload:
                placed.payload[key] = -abs(placed.payload[key])

    elif defect == "unannounced_event_type":
        victim = rng.choice(group)
        new_type = rng.choice(UNANNOUNCED_EVENT_TYPES)
        victim.event_type = new_type["event_type"]
        victim.payload = new_type["payload"](rng)

    elif defect == "orphan_vendor":
        victim = rng.choice(group)
        victim.vendor_id = "vnd_doesnotexist"

    elif defect == "timestamp_inversion":
        placed = next((e for e in group if e.event_type == "order_placed"), None)
        delivered = next((e for e in group if e.event_type == "order_delivered"), None)
        if placed and delivered:
            placed.occurred_at, delivered.occurred_at = delivered.occurred_at, placed.occurred_at
