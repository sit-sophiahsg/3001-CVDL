from __future__ import annotations

import io
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw

APP_DIR = Path(__file__).parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import backend
import mode1
import mode2
from components import load_prices, log_scan, reset_scan_state, style

st.set_page_config(page_title="FreshMart Produce Scale", page_icon="🥬", layout="wide")
style()

PRICES = load_prices()
TYPES = backend.TYPES


def demo_image() -> Image.Image:
    image = Image.new("RGB", (900, 600), "#dff2e1")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 410, 900, 600), fill="#a8cf8d")
    for x, y, colour in ((180, 285, "#e94848"), (420, 270, "#f5bd32"), (660, 300, "#78b84a")):
        draw.ellipse((x - 90, y - 90, x + 90, y + 90), fill=colour, outline="#fff", width=5)
    draw.text((30, 30), "FreshMart demo produce", fill="#183b2b")
    return image


def read_input_image() -> Image.Image:
    source = st.sidebar.radio("Input source", ["Bundled demo", "Upload photo", "Camera snapshot"])
    if source == "Upload photo":
        uploaded = st.sidebar.file_uploader("Choose an image", type=["png", "jpg", "jpeg"])
        if uploaded:
            return Image.open(io.BytesIO(uploaded.getvalue())).convert("RGB")
    elif source == "Camera snapshot":
        captured = st.sidebar.camera_input("Take a snapshot")
        if captured:
            return Image.open(io.BytesIO(captured.getvalue())).convert("RGB")
    return demo_image()


def init_state() -> None:
    defaults = {
        "screen": "idle",
        "mode": "Mode 2 · Shopper",
        "selected_type": None,
        "weight_kg": 0.25,
        "image": None,
        "result": None,
        "failed_scans": 0,
        "scan_logs": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def do_reset() -> None:
    reset_scan_state()
    st.rerun()


def sidebar() -> None:
    st.sidebar.title("FreshMart")
    st.sidebar.caption("Produce quality scale · student demo")
    st.session_state.mode = st.sidebar.radio("View", ["Mode 2 · Shopper", "Mode 1 · Model view"],
                                               index=0 if st.session_state.mode.startswith("Mode 2") else 1)
    backend.SIMULATE_RULE = st.sidebar.selectbox(
        "Developer · Simulate rule", ["auto", "1", "2", "3", "4", "5", "6", "7"],
    )
    if st.sidebar.button("Reset scan", use_container_width=True):
        do_reset()
    st.sidebar.caption("Student demo — not affiliated with any retailer.")


def scan() -> None:
    image = st.session_state.image or demo_image()
    result = backend.analyse(
        image, st.session_state.selected_type, st.session_state.weight_kg, st.session_state.failed_scans
    )
    st.session_state.result = result
    rule_id = result["rule_id"]
    if rule_id in (1, 2, 6):
        st.session_state.failed_scans += 1
    elif rule_id == 7:
        st.session_state.failed_scans = 0
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "selected_type": st.session_state.selected_type,
        "rule_id": rule_id,
        "staff_alert": result["staff_alert"],
    }
    st.session_state.scan_logs.append(entry)
    log_scan(entry)
    st.session_state.screen = "result"


def main() -> None:
    init_state()
    sidebar()
    st.markdown('<div class="brand"><b>FreshMart</b><span>SMART PRODUCE SCALE</span></div>', unsafe_allow_html=True)
    if st.session_state.mode.startswith("Mode 2"):
        mode2.render(st, scan, read_input_image)
    else:
        mode1.render(st, scan, read_input_image)
    st.caption("Student demo — not affiliated with any retailer.")


if __name__ == "__main__":
    main()
