"""Simulation parameters. Tune here without touching business logic."""
from dataclasses import dataclass, field


@dataclass
class SimConfig:
    # Dimension sizes
    num_vendors: int = 50
    num_customers: int = 500
    num_drivers: int = 80
    num_menu_items_per_vendor: int = 12

    # Order volume: base orders per hour across the day
    # Index 0 = midnight, index 12 = noon
    hourly_order_weights: list[float] = field(default_factory=lambda: [
        0.2, 0.1, 0.05, 0.05, 0.05, 0.1,   # 0-5
        0.3, 0.5, 0.7, 0.8, 0.9, 1.5,       # 6-11
        2.0, 1.8, 1.2, 0.9, 0.8, 1.2,       # 12-17
        2.5, 2.2, 1.5, 1.0, 0.6, 0.3,       # 18-23
    ])

    # Cancellation probabilities at each stage (independent)
    cancel_before_confirm_prob: float = 0.04   # customer cancels before vendor confirms
    cancel_at_confirm_prob: float = 0.03        # vendor rejects
    cancel_at_prep_prob: float = 0.005          # vendor cancels mid-prep
    cancel_at_pickup_prob: float = 0.005        # driver no-show / system cancel

    # Timing distributions (seconds): (mean, std_dev)
    confirm_delay_secs: tuple[float, float] = (90, 30)      # vendor confirm
    prep_time_secs: tuple[float, float] = (1200, 300)       # food prep (~20 min)
    pickup_delay_secs: tuple[float, float] = (240, 60)      # driver arrives
    delivery_time_secs: tuple[float, float] = (1500, 400)   # delivery (~25 min)

    # Pricing (JPY)
    delivery_fee: int = 200
    service_fee_pct: float = 0.05
    discount_prob: float = 0.15
    discount_amounts: list[int] = field(default_factory=lambda: [100, 200, 300, 500])

    # Output paths
    raw_base_path: str = "data/raw"

    seed: int = 42


# Cuisine types with rough prep-time multipliers
CUISINE_TYPES: list[tuple[str, float]] = [
    ("Japanese", 1.0),
    ("Ramen", 1.1),
    ("Sushi", 1.2),
    ("Chinese", 0.9),
    ("Korean", 1.0),
    ("Thai", 0.95),
    ("Italian", 1.05),
    ("Burger", 0.8),
    ("Pizza", 1.1),
    ("Indian", 1.15),
    ("Cafe", 0.7),
    ("Dessert", 0.6),
]

VEHICLE_TYPES = ["bicycle", "motorbike", "car"]

CANCEL_REASONS: dict[str, list[str]] = {
    "customer": ["changed_mind", "ordered_by_mistake", "wait_too_long"],
    "vendor": ["item_unavailable", "closing_early", "too_busy", "rejected"],
    "driver": ["unable_to_locate", "vehicle_breakdown"],
    "system": ["payment_failed", "no_driver_available", "timeout"],
}
