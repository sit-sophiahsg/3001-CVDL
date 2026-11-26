from __future__ import annotations

import hashlib
import random
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance

import models

TYPES = ["apple", "banana", "orange", "capsicum", "tomato", "potato"]
TIERS = {"A": "Full price", "B": "20% off", "C": "50% off", "D": "Not for sale"}
MESSAGE_KEYS = {1: "r1", 2: "r2", 3: "r3", 4: "r4", 5: "r5", 6: "r2"}  # rule 6 says "scan again", as decide does


def _bundle() -> tuple[dict, dict[str, float]]:
    """rules.yaml and prices.csv from the model bundle (the only source of prices and messages)."""
    try:
        cfg = models.load_config()
        return cfg.rules, cfg.prices
    except Exception:  # noqa: BLE001 - no bundle at all (offline, nothing cached): simulate still runs
        return {}, {}


def _preview(crop: Image.Image, days: int) -> Image.Image:
    return ImageEnhance.Color(crop).enhance(max(0.35, 1 - days * 0.08))


def analyse(image: Image.Image, selected_type: str, weight_kg: float, failed_scans: int,
            simulate_rule: str = "auto") -> dict[str, Any]:
    """Stand-in ScanResult used when the developer forces a rule (1-7) in Model view.

    Prices, messages, tiers and thresholds come from the bundle's rules.yaml and prices.csv.
    Failed scans are counted as ``scale_pricing.decide`` counts them and returned in ``failed_scans``.
    """
    rules, prices = _bundle()
    tiers = rules.get("tiers", {})
    thresholds = dict(rules.get("thresholds", {}))
    messages = rules.get("messages", {})
    digest = hashlib.sha256(image.tobytes())
    digest.update(f"{selected_type}|{weight_kg:.3f}".encode())
    rng = random.Random(int(digest.hexdigest()[:8], 16))
    width, height = image.size
    simulate_rule = str(simulate_rule or "auto")
    rule = int(simulate_rule) if simulate_rule != "auto" else rng.choice([3, 4, 7, 7, 7])
    if rule == 1:
        detected = "unknown"
    elif rule in (3, 4):
        detected = rng.choice([item for item in TYPES if item != selected_type])
    else:
        detected = selected_type
    items = []
    for index in range(2 if rule == 3 else 1):
        freshness = rng.uniform(0.2, 0.95) if rule == 7 else (0.12 if rule == 5 else rng.uniform(0.35, 0.9))
        if rule in (5, 6):
            tier = "D"
        elif rules:
            tier = models.scale_pricing.TIERS[int(models.scale_pricing.tier_idx(freshness, rules))]
        else:
            tier = "A"
        x0, y0 = int(width * (0.12 + index * 0.42)), int(height * 0.18)
        x1, y1 = min(width - 1, x0 + int(width * 0.28)), min(height - 1, y0 + int(height * 0.58))
        crop = image.crop((x0, y0, x1, y1))
        mask = np.zeros((max(1, y1 - y0), max(1, x1 - x0)), dtype=bool)
        mask[mask.shape[0] // 3:, mask.shape[1] // 3:] = freshness < 0.4
        produce = selected_type if rule == 3 and index == 0 else detected
        items.append({
            "box": [x0, y0, x1, y1], "produce": produce, "det_conf": rng.uniform(0.84, 0.98),
            "freshness": freshness, "tier": tier, "fresh_conf": rng.uniform(0.78, 0.97),
            "days_left": max(1, round(freshness * 8, 1)), "blemish_mask": mask,
            "blemish_pct": float(mask.mean() * 100), "seg_conf": rng.uniform(0.76, 0.95),
            "curve": [max(0.05, freshness - day * 0.07) for day in range(8)],
            "forecasts": {day: _preview(crop, day) for day in (1, 3, 7)},
            "gradcam": _preview(crop, 2),
        })
    price_per_kg = prices.get(selected_type, 0.0)
    tier, discount, total = None, None, None
    if rule == 7:
        tier = items[0]["tier"]
        discount = tiers.get(tier, {}).get("discount")
        total = round(weight_kg * price_per_kg * (1 - discount) + 1e-9, 2) if discount is not None else None
    # failed scans as decide() counts them: rules 1, 2 and 6 add one; 2 and 6 call staff at the limit
    staff_alert = rule == 5
    if rule in (1, 2, 6):
        failed_scans += 1
    message = messages.get(MESSAGE_KEYS.get(rule, ""))
    if rule == 4 and message:
        message = message.format(detected=detected)
    if rule in (2, 6) and failed_scans >= thresholds.get("failed_scans_for_staff", 2):
        staff_alert = True
        message = f"{message} {messages.get('r2_staff', '')}".strip() if message else messages.get("r2_staff")
    return {
        "rule_id": rule, "message": message, "fields": {"detected": detected, "days": items[0]["days_left"]},
        "staff_alert": staff_alert, "failed_scans": failed_scans,
        "price": {"weight_kg": weight_kg, "price_per_kg": price_per_kg, "tier": tier,
                  "discount": discount, "total": total},
        "bag_freshness": sum(item["freshness"] for item in items) / len(items),
        "energy": rng.uniform(0.78, 0.98),
        "thresholds": thresholds,
        "items": items,
        "simulated": True,
    }
