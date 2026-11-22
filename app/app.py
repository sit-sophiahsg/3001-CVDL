from __future__ import annotations

import io
import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

APP_DIR = Path(__file__).parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import backend
import live
import mode1
import mode2
import models
import pipeline
from components import LOGO_SVG, bump_nonce, load_prices, log_scan, reset_scan_state, style

st.set_page_config(page_title="FreshMart Produce Scale", page_icon="🥬", layout="wide",
                   initial_sidebar_state="collapsed")

PRICES = load_prices()
TYPES = backend.TYPES
VIEWS = ["Shopper", "Model view"]

# Widget keys that must survive while their widget is not on screen (Model view
# controls are not rendered in Shopper mode, and Streamlit drops unrendered widget state).
PERSISTENT_WIDGET_KEYS = ("simulate_rule", "weight_kg", "ov_boxes", "ov_fresh", "ov_blemish", "ov_cam")
LIVE_KEY = "live"


def init_state() -> None:
    defaults = {
        "screen": "live",
        "selected_type": None,
        "weight_kg": 0.25,
        "image": None,          # the frame being graded (camera auto-scan or the backup upload)
        "frame": None,          # {ts, w, h, boxes}: the browser's boxes for that frame
        "source": None,         # "camera" or "upload"
        "live_last_ts": None,   # last component value handled
        "rearm": 0,             # bumped to re-arm the live view ("Scan again", "Next item")
        "result": None,
        "failed_scans": 0,
        "scan_logs": [],
        "simulate_rule": "auto",
        "input_nonce": 0,
        "staff_called": False,
        "ov_boxes": True,
        "ov_fresh": True,
        "ov_blemish": False,
        "ov_cam": False,
        "view": "Shopper",
        "_view_prev": "Shopper",
        "model_error": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    if st.session_state.screen not in mode2.SCREENS:  # e.g. old "welcome"/"select" screens
        st.session_state.screen = "live"
    for key in PERSISTENT_WIDGET_KEYS:
        st.session_state[key] = st.session_state[key]


# ---------------------------------------------------------------- callbacks
def on_view_change() -> None:
    """segmented_control returns None when the active option is clicked again: undo that."""
    if st.session_state.view is None:
        st.session_state.view = st.session_state._view_prev
    else:
        st.session_state._view_prev = st.session_state.view


def on_reset() -> None:
    reset_scan_state()
    mode2.rearm()


def take_frame(image: Image.Image, frame: dict, source: str) -> None:
    """A new frame to grade: grade it now if a type is selected, else wait for the pick."""
    st.session_state.update(image=image, frame=frame, source=source, result=None, screen="live")
    if st.session_state.selected_type:
        scan()


def on_live() -> None:
    """The live component sent something: a still frame, a scene change, or 'back to live'."""
    value = st.session_state.get(LIVE_KEY)
    if not isinstance(value, dict) or value.get("ts") is None or value.get("ts") == st.session_state.live_last_ts:
        return
    st.session_state.live_last_ts = value["ts"]
    kind = value.get("kind")
    if kind == "frame":
        image = live.decode_frame(value)
        if image is not None:
            take_frame(image, live.frame_meta(value, image), "camera")
    elif kind == "scene":
        # items moved or were taken off: drop that frame and its grades (a printed label stays)
        if st.session_state.source == "camera" and st.session_state.screen != "printed":
            mode2.clear_frame()
    elif kind == "live":  # leave the uploaded photo
        mode2.clear_frame()
        mode2.rearm()


def on_upload(widget_key: str) -> None:
    """Model view backup: an uploaded photo goes through the same path as an auto-scan."""
    file = st.session_state.get(widget_key)
    if file is None:
        return
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(file.getvalue()))).convert("RGB")
    except (UnidentifiedImageError, OSError):
        st.session_state.photo_error = "That file is not a photo we can read. Please try another."
        return
    st.session_state.photo_error = None
    take_frame(image, {"ts": f"upload-{time.time_ns()}", "w": image.width, "h": image.height, "boxes": []}, "upload")
    bump_nonce()


# ---------------------------------------------------------------- scan
def scan() -> bool:
    """Auto: the real models (pipeline.analyse_real). A forced rule: the stand-in backend.

    Returns False if there is no frame, or if the models could not be loaded.
    """
    image = st.session_state.image
    if image is None:  # never grade anything but a captured frame or an upload
        st.session_state.screen = "live"
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
    result["frame_ts"] = (st.session_state.frame or {}).get("ts")  # which frame these grades belong to
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
                '<span class="brand-sub">Smart produce scale</span></div></div>',
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
                st.button("Reset scan", key="nav_reset", on_click=on_reset)


def live_view(view: str) -> None:
    """The live camera component, with the last grades (camera) or the uploaded photo (backup)."""
    s = st.session_state
    model = view == "model"
    blemish, occ = model and bool(s.ov_blemish), model and bool(s.ov_cam)
    upload = s.source == "upload"
    live.render(
        view, key=LIVE_KEY, on_change=on_live, rearm=s.rearm,
        grades=None if upload else live.grades_arg(s.result, s.frame, blemish, occ),
        still=live.still_arg(s.image, s.result, blemish, occ) if upload else None,
        show_boxes=bool(s.ov_boxes) if model else True, show_fresh=bool(s.ov_fresh) if model else True,
        show_blemish=blemish, show_occ=occ, aspect=0.62 if model else 0.7, max_height=640 if model else 560)


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
            mode1.render(live_view, on_upload)
        else:
            mode2.render(scan, PRICES, live_view)


if __name__ == "__main__":
    main()