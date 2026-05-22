"""CLI entry point for the event simulator.

Usage:
  python -m simulator.main --date 2024-01-15 --num-orders 200
  python -m simulator.main --date 2024-01-15 --num-orders 200 --regen-dims
"""
from __future__ import annotations
import argparse
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


def run(cfg: SimConfig, date: str, num_orders: int, regen_dims: bool) -> None:
    print(f"\n=== Food Delivery Simulator ===")
    print(f"  Date: {date}  |  Orders: {num_orders}  |  Seed: {cfg.seed}")

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

    rng = random.Random(cfg.seed)
    all_events = []

    print(f"  Simulating {num_orders} orders...")
    for i in range(num_orders):
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
    for partition, count in sorted(file_counts.items()):
        print(f"    {partition}: {count} events")

    print("\nDone.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Food delivery event simulator")
    parser.add_argument("--date", required=True, help="Simulation date (YYYY-MM-DD)")
    parser.add_argument("--num-orders", type=int, default=200, help="Number of orders to simulate")
    parser.add_argument("--regen-dims", action="store_true", help="Regenerate dimension CSVs even if they exist")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    cfg = SimConfig(seed=args.seed)
    run(cfg, args.date, args.num_orders, args.regen_dims)


if __name__ == "__main__":
    main()
