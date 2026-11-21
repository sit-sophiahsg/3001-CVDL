from __future__ import annotations

import random
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw, ImageOps

APP_DIR = Path(__file__).parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import backend
import mode1
import mode2
import models
import pipeline
from components import LOGO_SVG, load_prices, log_scan, reset_scan_state, style

st.set_page_config(page_title="FreshMart Produce Scale", page_icon="🥬", layout="wide",
                   initial_sidebar_state="collapsed")

PRICES = load_prices()
TYPES = backend.TYPES
VIEWS = ["Shopper", "Model view"]
DEMO_DIR = APP_DIR / "demo"

# Widget keys that must survive while their widget is not on screen (Model view
# controls are not rendered in Shopper mode, and Streamlit drops unrendered widget state).
PERSISTENT_WIDGET_KEYS = ("simulate_rule", "weight_kg", "ov_boxes", "ov_blemish", "ov_cam")


def demo_image() -> Image.Image:
    """A random photo from app/demo/*.jpg if there is one, otherwise the drawn demo image."""
    photos = sorted(p for p in DEMO_DIR.glob("*") if p.suffix.lower() in (".jpg", ".jpeg")) if DEMO_DIR.is_dir() else []
    if photos:
        with Image.open(random.choice(photos)) as photo:
            return ImageOps.exif_transpose(photo).convert("RGB")
    image = Image.new("RGB", (900, 600), "#dff2e1")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 410, 900, 600), fill="#a8cf8d")
    for x, y, colour in ((180, 285, "#e94848"), (420, 270, "#f5bd32"), (660, 300, "#78b84a")):
        draw.ellipse((x - 90, y - 90, x + 90, y + 90), fill=colour, outline="#fff", width=5)
    draw.text((30, 30), "FreshMart demo produce", fill="#183b2b")
    return image


def init_state() -> None:
    defaults = {
        "screen": "welcome",
        "selected_type": None,
        "weight_kg": 0.25,
        "image": None,
        "result": None,
        "failed_scans": 0,
        "scan_logs": [],
        "simulate_rule": "auto",
        "input_nonce": 0,
        "staff_called": False,
        "ov_boxes": True,
        "ov_blemish": True,
        "ov_cam": False,
        "view": "Shopper",
        "_view_prev": "Shopper",
        "model_error": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    if st.session_state.screen not in mode2.SCREENS:  # e.g. old "idle"/"weigh" screens
        st.session_state.screen = "welcome"
    for key in PERSISTENT_WIDGET_KEYS:
        st.session_state[key] = st.session_state[key]


# ---------------------------------------------------------------- callbacks
def on_view_change() -> None:
    """segmented_control returns None when the active option is clicked again: undo that."""
    if st.session_state.view is None:
        st.session_state.view = st.session_state._view_prev
    else:
        st.session_state._view_prev = st.session_state.view


def set_view(view: str) -> None:
    """For buttons that switch mode; only ever used as an on_click callback."""
    st.session_state.view = view
    st.session_state._view_prev = view


def on_reset() -> None:
    reset_scan_state()


# ---------------------------------------------------------------- scan
def scan() -> bool:
    """Auto: the real models (pipeline.analyse_real). A forced rule: the stand-in backend.

    Returns False if there is no photo, or if the models could not be loaded.
    """
    image = st.session_state.image
    if image is None:  # never fall back to the demo image silently (audit risk 2)
        st.session_state.screen = "welcome"
        return False
    simulate = str(st.session_state.simulate_rule or "auto")
    args = (image, st.session_state.selected_type, float(st.session_state.weight_kg), st.session_state.failed_scans)
    if simulate == "auto":
        try:
            models.load_models()
        except Exception as exc:  # noqa: BLE001 - e.g. no internet and nothing cached
            st.session_state.model_error = (
                "The trained models could not be loaded, so Auto (models decide) cannot run. "
                "Check the internet connection (or set FRESHMART_MODELS_DIR). The simulated outcomes in "
                f"Model view still work. Details: {type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else ''}")
            return False
        st.session_state.model_error = None
        result = pipeline.analyse_real(*args)
    else:
        result = backend.analyse(*args, simulate)
    st.session_state.result = result
    rule_id = result["rule_id"]
    # decide() counts failed scans (and raises the staff alert); the app only stores the count
    st.session_state.failed_scans = 0 if rule_id == 7 else int(result["failed_scans"])
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "selected_type": st.session_state.selected_type,
        "rule_id": rule_id,
        "staff_alert": result["staff_alert"],
    }
    st.session_state.scan_logs.append(entry)
    log_scan(entry)
    st.session_state.screen = "result"
    return True


# ---------------------------------------------------------------- frame
def navbar() -> None:
    with st.container(key="navbar"):
        left, mid, right = st.columns([1, 1, 1], vertical_alignment="center")
        with left:
            st.markdown(
                f'<div class="brand">{LOGO_SVG}<div style="display:flex;flex-direction:column">'
                '<span class="brand-name">FreshMart</span>'
                '<span class="brand-sub">Smart produce scale · student demo</span>'
                '<span class="brand-note">Student demo, not affiliated with any retailer.</span></div></div>',
                unsafe_allow_html=True,
            )
        with mid:
            with st.container(key="nav_mid", horizontal=True, horizontal_alignment="center"):
                # The "Shopper" default is seeded in Session State (init_state), not via
                # default=: callbacks write st.session_state.view, and a non-None default
                # plus a Session State write makes Streamlit show a warning. A constant
                # default also keeps the widget's identity stable across reruns.
                st.segmented_control("View", VIEWS, key="view", label_visibility="collapsed",
                                     default=None, on_change=on_view_change)
        with right:
            with st.container(key="nav_right", horizontal=True, horizontal_alignment="right",
                              vertical_alignment="center"):
                st.markdown(f'<span class="nav-date">{datetime.now():%d/%m/%y}</span>',
                            unsafe_allow_html=True)
                st.button("Reset scan", key="nav_reset", on_click=on_reset)


def main() -> None:
    init_state()
    style()
    navbar()  # before the mode content, so st.rerun() never skips it
    view = st.session_state.get("view") or st.session_state._view_prev
    with st.container(key="page"):
        error = st.session_state.model_error or (
            None if PRICES else "The model bundle (prices, rules and models) could not be downloaded. "
                                "Check the internet connection (or set FRESHMART_MODELS_DIR).")
        if error:
            st.error(error)
        if view == "Model view":
            mode1.render(set_view)
        else:
            mode2.render(scan, demo_image, PRICES)


if __name__ == "__main__":
    main()