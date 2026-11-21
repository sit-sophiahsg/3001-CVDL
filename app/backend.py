from __future__ import annotations

import hashlib
import random
import csv
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance
import yaml

TYPES = ["apple", "banana", "orange", "capsicum", "tomato", "potato"]
TIERS = {"A": "Full price", "B": "20% off", "C": "50% off", "D": "Not for sale"}
SIMULATE_RULE = "auto"
CONFIG_DIR = Path(__file__).parent.parent / "configs"


def _load_prices() -> dict[str, float]:
    with (CONFIG_DIR / "prices.csv").open(newline="", encoding="utf-8") as file:
        return {row["produce"]: float(row["price_per_kg"]) for row in csv.DictReader(file)}


def _load_messages() -> dict[str, str]:
    with (CONFIG_DIR / "messages.yaml").open(encoding="utf-8") as file:
        return {str(rule): message for rule, message in (yaml.safe_load(file) or {}).items()}


def _tier(value: float) -> str:
    return "A" if value >= 0.8 else "B" if value >= 0.55 else "C" if value >= 0.3 else "D"


def _preview(crop: Image.Image, days: int) -> Image.Image:
    return ImageEnhance.Color(crop).enhance(max(0.35, 1 - days * 0.08))


def analyse(image: Image.Image, selected_type: str, weight_kg: float, failed_scans: int) -> dict[str, Any]:
    """Return a realistic stand-in ScanResult; replace this function with real models later."""
    seed = int(hashlib.sha256(image.tobytes()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    width, height = image.size
    rule = int(SIMULATE_RULE) if SIMULATE_RULE != "auto" else rng.choice([3, 4, 7, 7, 7])
    detected = selected_type if rule not in (3, 4) else rng.choice(
        [item for item in TYPES if item != selected_type]
    )
    items = []
    for index in range(2 if rule == 3 else 1):
        freshness = 0.9 if rule == 7 else (0.18 if rule == 5 else rng.uniform(0.35, 0.9))
        tier = "D" if rule in (5, 6) else _tier(freshness)
        if rule == 5:
            tier, freshness = "D", 0.12
        x0, y0 = int(width * (0.12 + index * 0.42)), int(height * 0.18)
        x1, y1 = min(width - 1, x0 + int(width * 0.28)), min(height - 1, y0 + int(height * 0.58))
        crop = image.crop((x0, y0, x1, y1))
        mask = np.zeros((max(1, y1 - y0), max(1, x1 - x0)), dtype=bool)
        mask[mask.shape[0] // 3:, mask.shape[1] // 3:] = freshness < 0.4
        items.append({
            "box": [x0, y0, x1, y1], "produce": detected, "det_conf": rng.uniform(0.84, 0.98),
            "freshness": freshness, "tier": tier, "fresh_conf": rng.uniform(0.78, 0.97),
            "days_left": max(1, round(freshness * 8, 1)), "blemish_mask": mask,
            "blemish_pct": float(mask.mean() * 100), "seg_conf": rng.uniform(0.76, 0.95),
            "curve": [max(0.05, freshness - day * 0.07) for day in range(8)],
            "forecasts": {day: _preview(crop, day) for day in (1, 3, 7)},
            "gradcam": _preview(crop, 2),
        })
    prices = _load_prices()
    messages = _load_messages()
    price_per_kg = prices.get(selected_type, 0.0)
    if rule == 7:
        tier = items[0]["tier"]
        discount = {"A": 0.0, "B": 0.2, "C": 0.5}.get(tier)
        total = round(weight_kg * price_per_kg * (1 - discount), 2) if discount is not None else None
    else:
        tier, discount, total = None, None, None
    if rule in (2, 6) and failed_scans >= 1:
        message = messages["staff_after_failed_scans"]
    elif rule == 4:
        message = messages["4"].format(detected=detected)
    else:
        message = messages.get(str(rule))
    return {
        "rule_id": rule, "message": message, "fields": {"detected": detected, "days": items[0]["days_left"]},
        "staff_alert": rule == 5 or (rule in (2, 6) and failed_scans >= 1),
        "price": {"weight_kg": weight_kg, "price_per_kg": price_per_kg, "tier": tier,
                  "discount": discount, "total": total},
        "bag_freshness": sum(item["freshness"] for item in items) / len(items),
        "energy": rng.uniform(0.78, 0.98),
        "thresholds": {"tau_conf": 0.75, "tau_rotten": 0.2, "tau_det": 0.7, "E_thr": 0.65},
        "items": items,
    }
