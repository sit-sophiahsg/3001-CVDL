"""Config loading, price and discount logic (no Streamlit code here)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import yaml

CATEGORIES = ("fruit", "vegetable")
_NOT_FOR_SALE = {"discount": None, "sellable": False}


def load_config(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    for key in ("currency", "status_rules", "produce"):
        if key not in config:
            raise ValueError(f"config.yaml is missing '{key}'")
    for item in config["produce"]:
        missing = {"id", "name", "category", "emoji", "price_per_kg"} - item.keys()
        if missing:
            raise ValueError(f"Produce item {item.get('id', '?')} is missing {sorted(missing)}")
        if item["category"] not in CATEGORIES:
            raise ValueError(f"Produce item {item['id']} has unknown category {item['category']!r}")
        item.setdefault("enabled", True)
    return config


def status_rule(config: dict, status: str) -> dict:
    """Discount/sellable rule for a status. Unknown statuses are never sold."""
    rule = config["status_rules"].get(status) or _NOT_FOR_SALE
    return {"discount": rule.get("discount") or 0.0, "sellable": bool(rule.get("sellable"))}


@dataclass(frozen=True)
class PriceBreakdown:
    weight_kg: Decimal
    price_per_kg: Decimal
    discount_rate: Decimal
    subtotal: Decimal
    discount_amount: Decimal
    total: Decimal


def _cents(value: Decimal, decimals: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def compute_price(weight_kg: float, price_per_kg: float, discount_rate: float,
                  decimals: int = 2) -> PriceBreakdown:
    """price = weight x price per kg x (1 - discount), rounded half-up to cents."""
    if weight_kg < 0 or price_per_kg < 0 or not 0 <= discount_rate <= 1:
        raise ValueError("weight, price and discount must be non-negative (discount <= 1)")
    weight = Decimal(str(weight_kg))
    unit = Decimal(str(price_per_kg))
    rate = Decimal(str(discount_rate))
    subtotal = _cents(weight * unit, decimals)
    discount_amount = _cents(subtotal * rate, decimals)
    return PriceBreakdown(weight, unit, rate, subtotal, discount_amount, subtotal - discount_amount)


def format_money(amount: float | Decimal, currency: dict) -> str:
    return f"{currency['symbol']}{float(amount):,.{currency.get('decimals', 2)}f}"
