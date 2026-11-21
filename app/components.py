from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw

ROOT = Path(__file__).parent.parent


def style() -> None:
    st.markdown("""<style>
    .stApp { background:#f4fbf6; color:#183b2b; }
    .brand { display:flex; justify-content:space-between; align-items:center; background:#183b2b;
      color:white; padding:1rem 1.4rem; border-radius:0 0 14px 14px; margin:-1rem -1rem 1.2rem; }
    .brand b { font-size:2rem; color:#a8e063; } .brand span { letter-spacing:.12em; font-size:.8rem; }
    .kiosk { background:white; border:1px solid #d5e8d8; border-radius:16px; padding:1.3rem; }
    .result { background:#e5f5df; border-left:8px solid #5b9e45; padding:1.2rem; border-radius:12px; }
    .warning { background:#fff1d6; border-left:8px solid #e3a72f; padding:1.2rem; border-radius:12px; }
    .danger { background:#ffe0dc; border-left:8px solid #c84b42; padding:1.2rem; border-radius:12px; }
    .metric { font-size:1.8rem; font-weight:700; color:#183b2b; }
    </style>""", unsafe_allow_html=True)


def load_prices() -> dict[str, float]:
    path = ROOT / "configs" / "prices.csv"
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as file:
        return {row["produce"]: float(row["price_per_kg"]) for row in csv.DictReader(file)}


def log_scan(entry: dict) -> None:
    path = ROOT / "logs" / "scans.csv"
    path.parent.mkdir(exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["time", "selected_type", "rule_id", "staff_alert"])
        if not exists:
            writer.writeheader()
        writer.writerow(entry)


def reset_scan_state() -> None:
    for key, value in {"screen": "idle", "selected_type": None, "weight_kg": 0.25,
                       "image": None, "result": None, "failed_scans": 0, "scan_logs": []}.items():
        st.session_state[key] = value


def draw_boxes(image: Image.Image, items: list[dict], blemishes: bool = False) -> Image.Image:
    output = image.copy().convert("RGB")
    draw = ImageDraw.Draw(output)
    colours = {"A": "#2e8b57", "B": "#d99b18", "C": "#de6b2b", "D": "#c84b42"}
    for item in items:
        x0, y0, x1, y1 = item["box"]
        colour = colours[item["tier"]]
        draw.rectangle((x0, y0, x1, y1), outline=colour, width=5)
        draw.text((x0 + 5, y0 + 5), f'{item["produce"]} · {item["freshness"]:.0%} · Tier {item["tier"]}',
                  fill=colour, stroke_width=2, stroke_fill="white")
        if blemishes and item["blemish_pct"]:
            draw.rectangle((x0, y0, x1, y1), fill="#c84b4238")
    return output
