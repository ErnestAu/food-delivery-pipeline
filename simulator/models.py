"""Dataclasses for all entities. These are the canonical shapes written to disk."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Customer:
    customer_id: str
    name: str
    email: str
    phone: str
    city: str
    lat: float
    lon: float
    registration_date: str  # YYYY-MM-DD

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Vendor:
    vendor_id: str
    name: str
    cuisine_type: str
    city: str
    lat: float
    lon: float
    avg_prep_minutes: int
    rating: float  # 1.0–5.0
    prep_time_multiplier: float  # used by simulator, not written to dim

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d.pop("prep_time_multiplier")
        return d


@dataclass
class Driver:
    driver_id: str
    name: str
    vehicle_type: str
    city: str
    rating: float

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class MenuItem:
    menu_item_id: str
    vendor_id: str
    name: str
    category: str
    price: int  # JPY
    is_available: bool = True

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class OrderEvent:
    event_id: str
    event_type: str
    order_id: str
    occurred_at: str          # ISO 8601 UTC
    customer_id: str
    vendor_id: str
    driver_id: str | None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "order_id": self.order_id,
            "occurred_at": self.occurred_at,
            "customer_id": self.customer_id,
            "vendor_id": self.vendor_id,
            "driver_id": self.driver_id,
            "payload": self.payload,
        }
