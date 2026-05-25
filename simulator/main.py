"""CLI entry point for the event simulator.

Usage:
  # Single date
  python -m simulator.main --date 2024-01-15 --num-orders 200

  # Date range with realistic volume variation
  python -m simulator.main --start-date 2024-01-17 --base-orders 100

  # Date range with fixed end and explicit volume
  python -m simulator.main --start-date 2024-01-17 --end-date 2024-02-01 --base-orders 150
"""
from __future__ import annotations
import argparse
import hashlib
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from simulator.config import SimConfig
from simulator.dims import generate_dims, write_dims
from simulator.lifecycle import simulate_order
from simulator.models import Customer, Driver, MenuItem, Vendor
from simulator.writer import write_events


def _load_or_generate_dims(
    cfg: SimConfig, regen: bool
) -> tuple[list[Customer], list[Vendor], list[Driver], list[MenuItem]]:
    dims_dir = Path(cfg.raw_base_path) / "dims"
    already_exist = (
        (dims_dir / "customers.csv").exists()
        and (dims_dir / "vendors.csv").exists()
        and (dims_dir / "drivers.csv").exists()
        and (dims_dir / "menu_items.csv").exists()
    )

    if already_exist and not regen:
        print("  Dims already exist, loading from CSV...")
        return _load_dims_from_csv(cfg)

    print("  Generating dimension tables...")
    customers, vendors, drivers, menu_items = generate_dims(cfg)
    write_dims(customers, vendors, drivers, menu_items, cfg)
    return customers, vendors, drivers, menu_items


def _load_dims_from_csv(
    cfg: SimConfig,
) -> tuple[list[Customer], list[Vendor], list[Driver], list[MenuItem]]:
    import csv

    def read_csv(name: str) -> list[dict]:
        path = Path(cfg.raw_base_path) / "dims" / name
        with open(path, encoding="utf-8") as f:
            return list(csv.DictReader(f))

    customers = [
        Customer(
            customer_id=r["customer_id"],
            name=r["name"],
            email=r["email"],
            phone=r["phone"],
            city=r["city"],
            lat=float(r["lat"]),
            lon=float(r["lon"]),
            registration_date=r["registration_date"],
        )
        for r in read_csv("customers.csv")
    ]

    vendors_raw = read_csv("vendors.csv")
    cuisine_mult = {c: m for c, m in __import__("simulator.config", fromlist=["CUISINE_TYPES"]).CUISINE_TYPES}
    vendors = [
        Vendor(
            vendor_id=r["vendor_id"],
            name=r["name"],
            cuisine_type=r["cuisine_type"],
            city=r["city"],
            lat=float(r["lat"]),
            lon=float(r["lon"]),
            avg_prep_minutes=int(r["avg_prep_minutes"]),
            rating=float(r["rating"]),
            prep_time_multiplier=cuisine_mult.get(r["cuisine_type"], 1.0),
        )
        for r in vendors_raw
    ]

    drivers = [
        Driver(
            driver_id=r["driver_id"],
            name=r["name"],
            vehicle_type=r["vehicle_type"],
            city=r["city"],
            rating=float(r["rating"]),
        )
        for r in read_csv("drivers.csv")
    ]

    menu_items = [
        MenuItem(
            menu_item_id=r["menu_item_id"],
            vendor_id=r["vendor_id"],
            name=r["name"],
            category=r["category"],
            price=int(r["price"]),
            is_available=r["is_available"] == "True",
        )
        for r in read_csv("menu_items.csv")
    ]

    return customers, vendors, drivers, menu_items


def _pick_placed_at(date_str: str, cfg: SimConfig, rng: random.Random) -> datetime:
    """Pick a random UTC timestamp biased toward meal-time hours."""
    date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    hour = rng.choices(range(24), weights=cfg.hourly_order_weights, k=1)[0]
    minute = rng.randint(0, 59)
    second = rng.randint(0, 59)
    return date + timedelta(hours=hour, minutes=minute, seconds=second)


def _pick_placed_at_in_hour(date_str: str, hour: int, rng: random.Random) -> datetime:
    """Pick a random UTC timestamp within a specific hour (for --live mode)."""
    date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    minute = rng.randint(0, 59)
    second = rng.randint(0, 59)
    return date + timedelta(hours=hour, minutes=minute, seconds=second)


def _orders_for_hour(cfg: SimConfig, hour: int, daily_target: int, rng: random.Random) -> int:
    """Compute order count for a specific hour using the hourly weight curve + jitter."""
    weights = cfg.hourly_order_weights
    share = weights[hour] / sum(weights)
    expected = daily_target * share
    jitter = rng.uniform(0.85, 1.15)
    return max(1, int(expected * jitter))


def _orders_for_date(
    date: datetime,
    base: int,
    day_index: int,
    total_days: int,
    rng: random.Random,
) -> int:
    """Vary order volume by weekday + growth trend + jitter."""
    weekday_mult = 1.4 if date.weekday() >= 5 else 1.0          # Sat/Sun busier
    growth_mult = 1.0 + (0.3 * day_index / max(total_days, 1))  # ~30% growth across range
    jitter = rng.uniform(0.85, 1.15)                            # ±15% noise
    return max(10, int(base * weekday_mult * growth_mult * jitter))


def _derive_seed(base_seed: int, date_str: str) -> int:
    """Derive a per-date seed so each date produces different (but reproducible) data."""
    return int(hashlib.md5(f"{base_seed}-{date_str}".encode()).hexdigest()[:8], 16)


def run(
    cfg: SimConfig,
    date: str,
    num_orders: int,
    regen_dims: bool,
    hour: int | None = None,
) -> None:
    """Generate orders for a date. If hour is provided, only generate within that hour."""
    label = f"{date} hour={hour:02d}" if hour is not None else date
    print(f"\n=== Food Delivery Simulator ===")
    print(f"  {label}  |  Orders: {num_orders}  |  Seed: {cfg.seed}")

    customers, vendors, drivers, menu_items = _load_or_generate_dims(cfg, regen_dims)

    # Build vendor → items lookup (only available items)
    from collections import defaultdict
    vendor_items: dict[str, list[MenuItem]] = defaultdict(list)
    for item in menu_items:
        if item.is_available:
            vendor_items[item.vendor_id].append(item)

    active_vendors = [v for v in vendors if vendor_items[v.vendor_id]]
    if not active_vendors:
        print("ERROR: no vendors have available menu items.", file=sys.stderr)
        sys.exit(1)

    # Per-date deterministic seed → different data per day, reproducible across runs
    # In hour mode, derive seed from date+hour so re-runs of the same hour are stable
    if hour is not None:
        seed = _derive_seed(cfg.seed, f"{date}-{hour:02d}")
    else:
        seed = _derive_seed(cfg.seed, date)
    rng = random.Random(seed)

    all_events: list = []

    print(f"  Simulating {num_orders} orders...")
    for i in range(num_orders):
        if hour is not None:
            placed_at = _pick_placed_at_in_hour(date, hour, rng)
        else:
            placed_at = _pick_placed_at(date, cfg, rng)
        customer = rng.choice(customers)
        vendor = rng.choice(active_vendors)
        driver = rng.choice(drivers)

        available = vendor_items[vendor.vendor_id]
        num_items = rng.randint(1, min(4, len(available)))
        chosen_items = rng.sample(available, num_items)
        basket = [(item, rng.randint(1, 3)) for item in chosen_items]

        events = simulate_order(placed_at, customer, vendor, driver, basket, cfg, rng)
        all_events.extend(events)

    print(f"  Generated {len(all_events)} events from {num_orders} orders.")

    file_counts = write_events(all_events, cfg.raw_base_path)
    total_files = len(file_counts)
    print(f"  Written to {total_files} partition(s) under data/raw/order_events/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Food delivery event simulator")

    # Date selection (single OR range OR live)
    parser.add_argument("--date", help="Single simulation date (YYYY-MM-DD)")
    parser.add_argument("--start-date", help="Start of date range (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End of date range (YYYY-MM-DD), defaults to today UTC")
    parser.add_argument("--live", action="store_true",
                        help="Generate events for the current UTC hour only (for hourly cron)")
    parser.add_argument("--hour", type=int,
                        help="Specific UTC hour 0-23 (requires --date). Used for backfilling missed hours.")

    # Volume
    parser.add_argument("--num-orders", type=int,
                        help="Exact order count per day (overrides volume variation)")
    parser.add_argument("--base-orders", type=int, default=100,
                        help="Base daily order volume (varied by weekday + growth trend)")
    parser.add_argument("--daily-target", type=int, default=300,
                        help="Target daily orders (only used with --live, distributed by hour)")

    # Misc
    parser.add_argument("--regen-dims", action="store_true",
                        help="Regenerate dimension CSVs even if they exist")
    parser.add_argument("--seed", type=int, default=42, help="Base random seed")
    args = parser.parse_args()

    if not args.date and not args.start_date and not args.live:
        parser.error("One of --date, --start-date, or --live is required.")

    cfg = SimConfig(seed=args.seed)

    # --live mode: generate only for the current hour
    if args.live:
        now = datetime.utcnow()
        date_str = now.strftime("%Y-%m-%d")
        hour = now.hour
        live_rng = random.Random()  # truly random jitter for live mode
        num = _orders_for_hour(cfg, hour, args.daily_target, live_rng)
        print(f"\n>>> Live mode: {date_str} hour={hour:02d}")
        run(cfg, date_str, num, regen_dims=False, hour=hour)
        print(f"\n>>> Done. {num} orders for hour {hour:02d}.")
        return

    # --date + --hour: backfill a specific past hour
    if args.date and args.hour is not None:
        hour_rng = random.Random(_derive_seed(cfg.seed, f"{args.date}-{args.hour:02d}"))
        num = args.num_orders or _orders_for_hour(cfg, args.hour, args.daily_target, hour_rng)
        print(f"\n>>> Backfill: {args.date} hour={args.hour:02d}")
        run(cfg, args.date, num, regen_dims=False, hour=args.hour)
        print(f"\n>>> Done. {num} orders for {args.date} hour {args.hour:02d}.")
        return

    # Build list of dates to simulate
    if args.date:
        dates = [args.date]
    else:
        start = datetime.strptime(args.start_date, "%Y-%m-%d")
        end = (
            datetime.strptime(args.end_date, "%Y-%m-%d")
            if args.end_date
            else datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        )
        num_days = (end - start).days + 1
        dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(num_days)]

    print(f"\n>>> Simulating {len(dates)} date(s) from {dates[0]} to {dates[-1]}")

    # Volume RNG seeded only by base seed → reproducible jitter, independent of per-date seed
    volume_rng = random.Random(cfg.seed)

    total_orders = 0
    for i, date_str in enumerate(dates):
        if args.num_orders is not None:
            num = args.num_orders
        else:
            num = _orders_for_date(
                datetime.strptime(date_str, "%Y-%m-%d"),
                args.base_orders,
                i,
                len(dates),
                volume_rng,
            )
        total_orders += num
        run(cfg, date_str, num, regen_dims=(args.regen_dims and i == 0))

    print(f"\n>>> All done. {total_orders} orders across {len(dates)} dates.")


if __name__ == "__main__":
    main()
