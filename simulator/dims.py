"""Generate dimension tables. Run once; orders reference these IDs."""
from __future__ import annotations
import csv
import random
import uuid
from pathlib import Path

from faker import Faker

from simulator.config import CUISINE_TYPES, VEHICLE_TYPES, SimConfig
from simulator.models import Customer, Driver, MenuItem, Vendor

# Tokyo-area cities weighted by population
CITIES = [
    ("Tokyo", 35.6762, 139.6503),
    ("Osaka", 34.6937, 135.5023),
    ("Nagoya", 35.1815, 136.9066),
    ("Fukuoka", 33.5902, 130.4017),
    ("Sapporo", 43.0642, 141.3469),
    ("Kyoto", 35.0116, 135.7681),
    ("Yokohama", 35.4437, 139.6380),
]

MENU_CATEGORIES = ["Main", "Side", "Drink", "Dessert"]

MENU_ITEMS_POOL: dict[str, list[tuple[str, str, int]]] = {
    "Japanese":  [("Chicken Teriyaki Set", "Main", 980), ("Miso Soup", "Side", 200), ("Edamame", "Side", 300), ("Green Tea", "Drink", 150)],
    "Ramen":     [("Tonkotsu Ramen", "Main", 850), ("Shoyu Ramen", "Main", 800), ("Gyoza (6pc)", "Side", 400), ("Karaage", "Side", 500), ("Chashu Rice", "Side", 350)],
    "Sushi":     [("Salmon Nigiri (2pc)", "Main", 600), ("Tuna Roll", "Main", 700), ("Ebi Tempura Roll", "Main", 780), ("Miso Soup", "Side", 200), ("Edamame", "Side", 250)],
    "Chinese":   [("Fried Rice", "Main", 750), ("Mapo Tofu", "Main", 820), ("Spring Rolls (3pc)", "Side", 380), ("Gyoza (5pc)", "Side", 400), ("Jasmine Tea", "Drink", 180)],
    "Korean":    [("Bibimbap", "Main", 900), ("Bulgogi Rice Bowl", "Main", 950), ("Kimchi", "Side", 200), ("Tteokbokki", "Side", 480), ("Barley Tea", "Drink", 150)],
    "Thai":      [("Pad Thai", "Main", 880), ("Green Curry", "Main", 920), ("Tom Yum Soup", "Side", 450), ("Spring Rolls (2pc)", "Side", 350), ("Thai Milk Tea", "Drink", 380)],
    "Italian":   [("Spaghetti Carbonara", "Main", 1100), ("Margherita Pizza", "Main", 1200), ("Garlic Bread", "Side", 300), ("Caesar Salad", "Side", 550), ("Soft Drink", "Drink", 200)],
    "Burger":    [("Classic Burger", "Main", 950), ("Double Cheeseburger", "Main", 1150), ("Fries (M)", "Side", 350), ("Onion Rings", "Side", 380), ("Cola", "Drink", 200)],
    "Pizza":     [("Pepperoni Pizza (M)", "Main", 1400), ("Margherita (M)", "Main", 1200), ("BBQ Chicken (M)", "Main", 1500), ("Garlic Knots", "Side", 400), ("Soft Drink", "Drink", 200)],
    "Indian":    [("Butter Chicken Curry", "Main", 1050), ("Naan (2pc)", "Side", 300), ("Dal Makhani", "Main", 900), ("Mango Lassi", "Drink", 420), ("Samosa (2pc)", "Side", 380)],
    "Cafe":      [("Club Sandwich", "Main", 850), ("Avocado Toast", "Main", 780), ("Coffee", "Drink", 450), ("Matcha Latte", "Drink", 500), ("Chocolate Cake", "Dessert", 600)],
    "Dessert":   [("Parfait", "Dessert", 680), ("Crepe Set", "Dessert", 750), ("Waffle", "Dessert", 700), ("Ice Cream (2 scoops)", "Dessert", 480), ("Coffee", "Drink", 400)],
}


def _jitter(lat: float, lon: float, rng: random.Random) -> tuple[float, float]:
    return round(lat + rng.uniform(-0.05, 0.05), 6), round(lon + rng.uniform(-0.05, 0.05), 6)


def generate_dims(cfg: SimConfig) -> tuple[list[Customer], list[Vendor], list[Driver], list[MenuItem]]:
    rng = random.Random(cfg.seed)
    fake = Faker("ja_JP")
    fake.seed_instance(cfg.seed)

    customers = _gen_customers(cfg, rng, fake)
    vendors = _gen_vendors(cfg, rng, fake)
    drivers = _gen_drivers(cfg, rng, fake)
    menu_items = _gen_menu_items(vendors, cfg, rng)

    return customers, vendors, drivers, menu_items


def _gen_customers(cfg: SimConfig, rng: random.Random, fake: Faker) -> list[Customer]:
    customers = []
    for _ in range(cfg.num_customers):
        city_name, base_lat, base_lon = rng.choice(CITIES)
        lat, lon = _jitter(base_lat, base_lon, rng)
        customers.append(Customer(
            customer_id=f"cust_{uuid.uuid4().hex[:12]}",
            name=fake.name(),
            email=fake.email(),
            phone=fake.phone_number(),
            city=city_name,
            lat=lat,
            lon=lon,
            registration_date=fake.date_between(start_date="-3y", end_date="today").isoformat(),
        ))
    return customers


def _gen_vendors(cfg: SimConfig, rng: random.Random, fake: Faker) -> list[Vendor]:
    vendors = []
    for _ in range(cfg.num_vendors):
        city_name, base_lat, base_lon = rng.choice(CITIES)
        lat, lon = _jitter(base_lat, base_lon, rng)
        cuisine, prep_mult = rng.choice(CUISINE_TYPES)
        avg_prep = int(20 * prep_mult)
        vendors.append(Vendor(
            vendor_id=f"vend_{uuid.uuid4().hex[:12]}",
            name=f"{fake.last_name()} {cuisine}",
            cuisine_type=cuisine,
            city=city_name,
            lat=lat,
            lon=lon,
            avg_prep_minutes=avg_prep,
            rating=round(rng.uniform(3.0, 5.0), 1),
            prep_time_multiplier=prep_mult,
        ))
    return vendors


def _gen_drivers(cfg: SimConfig, rng: random.Random, fake: Faker) -> list[Driver]:
    drivers = []
    for _ in range(cfg.num_drivers):
        drivers.append(Driver(
            driver_id=f"driv_{uuid.uuid4().hex[:12]}",
            name=fake.name(),
            vehicle_type=rng.choice(VEHICLE_TYPES),
            city=rng.choice(CITIES)[0],
            rating=round(rng.uniform(3.5, 5.0), 1),
        ))
    return drivers


def _gen_menu_items(vendors: list[Vendor], cfg: SimConfig, rng: random.Random) -> list[MenuItem]:
    items = []
    for vendor in vendors:
        pool = MENU_ITEMS_POOL.get(vendor.cuisine_type, MENU_ITEMS_POOL["Japanese"])
        # fill up to num_menu_items_per_vendor by cycling through pool
        chosen = (pool * ((cfg.num_menu_items_per_vendor // len(pool)) + 2))[: cfg.num_menu_items_per_vendor]
        for name, category, base_price in chosen:
            # small price variance per vendor
            price = base_price + rng.randint(-50, 100)
            items.append(MenuItem(
                menu_item_id=f"item_{uuid.uuid4().hex[:12]}",
                vendor_id=vendor.vendor_id,
                name=name,
                category=category,
                price=max(100, price),
                is_available=rng.random() > 0.05,
            ))
    return items


def write_dims(
    customers: list[Customer],
    vendors: list[Vendor],
    drivers: list[Driver],
    menu_items: list[MenuItem],
    cfg: SimConfig,
) -> None:
    base = Path(cfg.raw_base_path) / "dims"
    base.mkdir(parents=True, exist_ok=True)

    _write_csv(base / "customers.csv", [c.to_dict() for c in customers])
    _write_csv(base / "vendors.csv", [v.to_dict() for v in vendors])
    _write_csv(base / "drivers.csv", [d.to_dict() for d in drivers])
    _write_csv(base / "menu_items.csv", [m.to_dict() for m in menu_items])

    print(f"  Wrote {len(customers)} customers, {len(vendors)} vendors, "
          f"{len(drivers)} drivers, {len(menu_items)} menu items → {base}/")


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
