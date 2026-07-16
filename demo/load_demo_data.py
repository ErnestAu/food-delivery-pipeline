#!/usr/bin/env python3
"""Create a deterministic, demo-only DuckDB source layer for the dbt project."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import duckdb


REPO_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = REPO_ROOT / "dbt" / "food_delivery" / "data" / "demo" / "food_delivery.duckdb"
SCHEMA = "demo"
SEED = 20260716

NUM_CUSTOMERS = 120
NUM_VENDORS = 30
NUM_DRIVERS = 45
MENU_ITEMS_PER_VENDOR = 12
NUM_ORDERS = 500

CITIES = ["Tokyo", "Osaka", "Yokohama", "Kyoto", "Nagoya"]
CUISINES = ["Japanese", "Ramen", "Sushi", "Chinese", "Korean", "Thai", "Italian", "Burger", "Pizza", "Indian"]
FIRST_NAMES = ["Aiko", "Haruto", "Yui", "Ren", "Sakura", "Sota", "Mio", "Yuto", "Hana", "Kaito"]
LAST_NAMES = ["Tanaka", "Sato", "Suzuki", "Takahashi", "Watanabe", "Ito", "Yamamoto", "Nakamura", "Kobayashi", "Kato"]
MENU_ITEMS = [
    ("Signature Bowl", "Main", 980),
    ("Chef Special", "Main", 1180),
    ("Seasonal Set", "Main", 1080),
    ("Gyoza", "Side", 380),
    ("Edamame", "Side", 280),
    ("Salad", "Side", 420),
    ("Iced Tea", "Drink", 220),
    ("Sparkling Water", "Drink", 180),
    ("Matcha Latte", "Drink", 460),
    ("Mochi", "Dessert", 320),
    ("Cheesecake", "Dessert", 480),
    ("Ice Cream", "Dessert", 360),
]


def name(rng: random.Random) -> str:
    return f"{rng.choice(LAST_NAMES)} {rng.choice(FIRST_NAMES)}"


def iso_timestamp(value: datetime) -> datetime:
    """Keep timestamps as native DuckDB values, not strings."""
    return value.replace(microsecond=0)


def make_dimensions(rng: random.Random) -> tuple[list[tuple], list[tuple], list[tuple], list[tuple]]:
    customers = [
        (
            f"cust_{index:03d}",
            name(rng),
            f"customer{index:03d}@example.com",
            f"080-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
            rng.choice(CITIES),
            round(rng.uniform(35.60, 35.80), 6),
            round(rng.uniform(139.60, 139.80), 6),
            datetime(2023, 1, 1).date() + timedelta(days=rng.randint(0, 900)),
        )
        for index in range(1, NUM_CUSTOMERS + 1)
    ]
    vendors = [
        (
            f"vend_{index:03d}",
            f"{rng.choice(LAST_NAMES)} {rng.choice(CUISINES)}",
            rng.choice(CUISINES),
            rng.choice(CITIES),
            round(rng.uniform(35.60, 35.80), 6),
            round(rng.uniform(139.60, 139.80), 6),
            rng.randint(12, 32),
            round(rng.uniform(3.8, 4.9), 1),
        )
        for index in range(1, NUM_VENDORS + 1)
    ]
    drivers = [
        (
            f"driv_{index:03d}",
            name(rng),
            rng.choice(["bicycle", "motorbike", "car"]),
            rng.choice(CITIES),
            round(rng.uniform(3.8, 5.0), 1),
        )
        for index in range(1, NUM_DRIVERS + 1)
    ]
    menu_items = [
        (
            f"item_{vendor_index:03d}_{item_index:02d}",
            f"vend_{vendor_index:03d}",
            item_name,
            category,
            base_price + rng.randint(-80, 140),
            rng.random() > 0.04,
        )
        for vendor_index in range(1, NUM_VENDORS + 1)
        for item_index, (item_name, category, base_price) in enumerate(MENU_ITEMS, start=1)
    ]
    return customers, vendors, drivers, menu_items


def make_events(rng: random.Random, customers: list[tuple], vendors: list[tuple], drivers: list[tuple]) -> list[tuple]:
    """Generate complete and cancelled order lifecycles that satisfy current dbt contracts."""
    events: list[tuple] = []
    start = datetime(2026, 6, 1, 8, 0, 0)

    for index in range(1, NUM_ORDERS + 1):
        customer = rng.choice(customers)[0]
        vendor = rng.choice(vendors)[0]
        driver = rng.choice(drivers)[0]
        placed_at = start + timedelta(minutes=rng.randint(0, 14 * 24 * 60))
        order_id = f"ord_{index:04d}"
        food_cost = rng.randrange(800, 3200, 100)
        delivery_fee = 200
        service_fee = round(food_cost * 0.05)
        discount = rng.choice([0, 0, 0, 100, 200, 300])
        gmv = food_cost + delivery_fee + service_fee - discount

        def add(event_type: str, occurred_at: datetime, driver_id: str | None = None, **measures: int | str | None) -> None:
            events.append(
                (
                    f"evt_{len(events) + 1:05d}",
                    event_type,
                    order_id,
                    iso_timestamp(occurred_at),
                    customer,
                    vendor,
                    driver_id,
                    measures.get("gmv"),
                    measures.get("food_cost"),
                    measures.get("delivery_fee"),
                    measures.get("service_fee"),
                    measures.get("discount"),
                    measures.get("cancelled_by"),
                    measures.get("cancel_reason"),
                )
            )

        add(
            "order_placed",
            placed_at,
            gmv=gmv,
            food_cost=food_cost,
            delivery_fee=delivery_fee,
            service_fee=service_fee,
            discount=discount,
        )

        cancellation_roll = rng.random()
        if cancellation_roll < 0.04:
            add("order_cancelled", placed_at + timedelta(minutes=rng.randint(1, 3)), cancelled_by="customer", cancel_reason="changed_mind")
            continue

        confirmed_at = placed_at + timedelta(minutes=rng.randint(1, 4))
        add("order_confirmed", confirmed_at)
        if cancellation_roll < 0.07:
            add("order_cancelled", confirmed_at + timedelta(minutes=1), cancelled_by="vendor", cancel_reason="item_unavailable")
            continue

        prepared_at = confirmed_at + timedelta(minutes=rng.randint(10, 28))
        add("order_prepared", prepared_at)
        if cancellation_roll < 0.08:
            add("order_cancelled", prepared_at + timedelta(minutes=1), cancelled_by="vendor", cancel_reason="closing_early")
            continue

        picked_up_at = prepared_at + timedelta(minutes=rng.randint(3, 10))
        add("order_picked_up", picked_up_at, driver)
        if cancellation_roll < 0.09:
            add("order_cancelled", picked_up_at + timedelta(minutes=1), driver, cancelled_by="driver", cancel_reason="vehicle_breakdown")
            continue

        add("order_delivered", picked_up_at + timedelta(minutes=rng.randint(15, 40)), driver)

    return events


def load_demo_data() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    customers, vendors, drivers, menu_items = make_dimensions(rng)
    events = make_events(rng, customers, vendors, drivers)

    connection = duckdb.connect(str(DATABASE_PATH))
    try:
        connection.execute(f"create schema if not exists {SCHEMA}")
        for table in ("dim_customers", "dim_vendors", "dim_drivers", "dim_menu_items", "order_events"):
            connection.execute(f"drop table if exists {SCHEMA}.{table}")

        connection.execute(
            f"""
            create table {SCHEMA}.dim_customers (
                customer_id varchar, name varchar, email varchar, phone varchar, city varchar,
                lat double, lon double, registration_date date
            )
            """
        )
        connection.execute(
            f"""
            create table {SCHEMA}.dim_vendors (
                vendor_id varchar, name varchar, cuisine_type varchar, city varchar,
                lat double, lon double, avg_prep_minutes integer, rating double
            )
            """
        )
        connection.execute(
            f"""
            create table {SCHEMA}.dim_drivers (
                driver_id varchar, name varchar, vehicle_type varchar, city varchar, rating double
            )
            """
        )
        connection.execute(
            f"""
            create table {SCHEMA}.dim_menu_items (
                menu_item_id varchar, vendor_id varchar, name varchar, category varchar,
                price integer, is_available boolean
            )
            """
        )
        connection.execute(
            f"""
            create table {SCHEMA}.order_events (
                event_id varchar, event_type varchar, order_id varchar, occurred_at timestamp,
                customer_id varchar, vendor_id varchar, driver_id varchar, gmv integer,
                food_cost integer, delivery_fee integer, service_fee integer, discount integer,
                cancelled_by varchar, cancel_reason varchar
            )
            """
        )

        connection.executemany(f"insert into {SCHEMA}.dim_customers values (?, ?, ?, ?, ?, ?, ?, ?)", customers)
        connection.executemany(f"insert into {SCHEMA}.dim_vendors values (?, ?, ?, ?, ?, ?, ?, ?)", vendors)
        connection.executemany(f"insert into {SCHEMA}.dim_drivers values (?, ?, ?, ?, ?)", drivers)
        connection.executemany(f"insert into {SCHEMA}.dim_menu_items values (?, ?, ?, ?, ?, ?)", menu_items)
        connection.executemany(f"insert into {SCHEMA}.order_events values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", events)
    finally:
        connection.close()

    print(
        "Loaded demo-only DuckDB fixture: "
        f"{len(customers)} customers, {len(vendors)} vendors, {len(drivers)} drivers, "
        f"{len(menu_items)} menu items, {NUM_ORDERS} orders, {len(events)} events."
    )


if __name__ == "__main__":
    load_demo_data()
