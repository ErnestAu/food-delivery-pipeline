"""Order lifecycle state machine. One call per order, returns list of events."""
from __future__ import annotations
import random
from datetime import datetime, timezone

from simulator.config import CANCEL_REASONS, SimConfig
from simulator.models import Customer, Driver, MenuItem, OrderEvent, Vendor


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _new_id(prefix: str, rng: random.Random) -> str:
    """Derive the ID from the seeded rng (not uuid4) so re-running the same
    date/hour with the same seed regenerates identical IDs — makes silver's
    dropDuplicates(event_id) dedup actually catch reprocessed/replayed batches."""
    return f"{prefix}_{rng.getrandbits(128):032x}"


def _delay(mean: float, std: float, rng: random.Random, minimum: float = 10.0) -> float:
    return max(minimum, rng.gauss(mean, std))


def _cancel_event(
    order_id: str,
    customer_id: str,
    vendor_id: str,
    driver_id: str | None,
    actor: str,
    ts: datetime,
    rng: random.Random,
) -> OrderEvent:
    reason = rng.choice(CANCEL_REASONS[actor])
    return OrderEvent(
        event_id=_new_id("evt", rng),
        event_type="order_cancelled",
        order_id=order_id,
        occurred_at=_iso(ts),
        customer_id=customer_id,
        vendor_id=vendor_id,
        driver_id=driver_id,
        payload={"cancelled_by": actor, "reason": reason},
    )


def simulate_order(
    placed_at: datetime,
    customer: Customer,
    vendor: Vendor,
    driver: Driver,
    items: list[tuple[MenuItem, int]],  # (item, quantity)
    cfg: SimConfig,
    rng: random.Random,
) -> list[OrderEvent]:
    order_id = _new_id("ord", rng)
    events: list[OrderEvent] = []

    # --- order_placed ---
    food_cost = sum(item.price * qty for item, qty in items)
    delivery_fee = cfg.delivery_fee
    service_fee = round(food_cost * cfg.service_fee_pct)
    discount = (
        rng.choice(cfg.discount_amounts) if rng.random() < cfg.discount_prob else 0
    )
    gmv = food_cost + delivery_fee + service_fee - discount

    placed_payload = {
        "items": [
            {
                "menu_item_id": item.menu_item_id,
                "name": item.name,
                "quantity": qty,
                "unit_price": item.price,
                "line_total": item.price * qty,
            }
            for item, qty in items
        ],
        "delivery_address": f"{customer.city}, Japan",
        "food_cost": food_cost,
        "delivery_fee": delivery_fee,
        "service_fee": service_fee,
        "discount": discount,
        "gmv": gmv,
    }
    events.append(OrderEvent(
        event_id=_new_id("evt", rng),
        event_type="order_placed",
        order_id=order_id,
        occurred_at=_iso(placed_at),
        customer_id=customer.customer_id,
        vendor_id=vendor.vendor_id,
        driver_id=None,
        payload=placed_payload,
    ))

    ts = placed_at

    # Customer cancels before vendor confirms
    if rng.random() < cfg.cancel_before_confirm_prob:
        cancel_delay = _delay(30, 15, rng)
        ts = _advance(ts, cancel_delay)
        events.append(_cancel_event(order_id, customer.customer_id, vendor.vendor_id, None, "customer", ts, rng))
        return events

    # --- order_confirmed ---
    ts = _advance(ts, _delay(*cfg.confirm_delay_secs, rng))

    if rng.random() < cfg.cancel_at_confirm_prob:
        events.append(_cancel_event(order_id, customer.customer_id, vendor.vendor_id, None, "vendor", ts, rng))
        return events

    events.append(OrderEvent(
        event_id=_new_id("evt", rng),
        event_type="order_confirmed",
        order_id=order_id,
        occurred_at=_iso(ts),
        customer_id=customer.customer_id,
        vendor_id=vendor.vendor_id,
        driver_id=None,
        payload={"estimated_prep_minutes": vendor.avg_prep_minutes},
    ))

    # --- order_prepared ---
    prep_mean = vendor.prep_time_multiplier * cfg.prep_time_secs[0]
    prep_std = vendor.prep_time_multiplier * cfg.prep_time_secs[1]
    ts = _advance(ts, _delay(prep_mean, prep_std, rng))

    if rng.random() < cfg.cancel_at_prep_prob:
        events.append(_cancel_event(order_id, customer.customer_id, vendor.vendor_id, None, "vendor", ts, rng))
        return events

    events.append(OrderEvent(
        event_id=_new_id("evt", rng),
        event_type="order_prepared",
        order_id=order_id,
        occurred_at=_iso(ts),
        customer_id=customer.customer_id,
        vendor_id=vendor.vendor_id,
        driver_id=None,
        payload={},
    ))

    # --- order_picked_up ---
    ts = _advance(ts, _delay(*cfg.pickup_delay_secs, rng))

    if rng.random() < cfg.cancel_at_pickup_prob:
        actor = rng.choice(["driver", "system"])
        events.append(_cancel_event(order_id, customer.customer_id, vendor.vendor_id, driver.driver_id, actor, ts, rng))
        return events

    events.append(OrderEvent(
        event_id=_new_id("evt", rng),
        event_type="order_picked_up",
        order_id=order_id,
        occurred_at=_iso(ts),
        customer_id=customer.customer_id,
        vendor_id=vendor.vendor_id,
        driver_id=driver.driver_id,
        payload={"driver_id": driver.driver_id, "vehicle_type": driver.vehicle_type},
    ))

    # --- order_delivered ---
    ts = _advance(ts, _delay(*cfg.delivery_time_secs, rng))

    events.append(OrderEvent(
        event_id=_new_id("evt", rng),
        event_type="order_delivered",
        order_id=order_id,
        occurred_at=_iso(ts),
        customer_id=customer.customer_id,
        vendor_id=vendor.vendor_id,
        driver_id=driver.driver_id,
        payload={},
    ))

    return events


def _advance(dt: datetime, seconds: float) -> datetime:
    from datetime import timedelta
    return dt + timedelta(seconds=seconds)
