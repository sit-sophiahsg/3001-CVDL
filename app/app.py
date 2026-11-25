from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image

APP_DIR = Path(__file__).parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import backend
import live
import mode1
import mode2
import models
import pipeline
from components import LOGO_SVG, WEIGHT_KG, load_prices, log_scan, reset_scan_state, style

st.set_page_config(page_title="FreshMart Produce Scale", page_icon="🥬", layout="wide",
                   initial_sidebar_state="collapsed")

PRICES = load_prices()
TYPES = backend.TYPES
VIEWS = ["Shopper", "Model view"]

# Widget keys that must survive while their widget is not on screen (Model view
# controls are not rendered in Shopper mode, and Streamlit drops unrendered widget state).
PERSISTENT_WIDGET_KEYS = ("simulate_rule", "ov_boxes", "ov_fresh", "ov_blemish", "ov_cam", "ov_disp")
LIVE_KEY = "live"


def init_state() -> None:
    defaults = {
        "screen": "live",
        "selected_type": None,
        "image": None,          # the frame being graded (camera auto-scan)
        "frame": None,          # {ts, w, h, boxes}: the browser's boxes for that frame
        "source": None,         # "camera" once a frame is taken
        "live_last_ts": None,   # last component value handled
        "rearm": 0,             # bumped to re-arm the live view ("Scan again", "Next item")
        "result": None,
        "failed_scans": 0,
        "failed_scans_model": 0,  # Model view's own count, so it never changes the Shopper flow
        # Model view's own capture: graded once, then frozen on screen until "Reset scan"
        "mv_image": None,
        "mv_frame": None,
        "mv_result": None,
        "scan_logs": [],
        "simulate_rule": "auto",
        "staff_called": False,
        "ov_boxes": True,
        "ov_fresh": True,
        "ov_blemish": False,
        "ov_cam": False,
        "ov_disp": True,      # camera-tuned % (display only), Model view
        "view": "Model view",
        "_view_prev": "Model view",
        "model_error": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    if st.session_state.screen not in mode2.SCREENS:  # e.g. old "welcome"/"select" screens
        st.session_state.screen = "live"
    for key in PERSISTENT_WIDGET_KEYS:
        st.session_state[key] = st.session_state[key]


# ---------------------------------------------------------------- callbacks
def current_view() -> str:
    return st.session_state.get("view") or st.session_state._view_prev


def on_view_change() -> None:
    """segmented_control returns None when the active option is clicked again: undo that.

    Each view keeps its own frame and result, so switching never changes the Shopper selection,
    the Shopper result or a frozen Model view capture. Model view with no capture yet adopts a
    Shopper frame that is waiting (and grades it with the detector's type).
    """
    s = st.session_state
    if s.view is None:
        s.view = s._view_prev
        return
    s._view_prev = s.view
    if s.view == "Model view" and s.mv_image is None and s.image is not None:
        s.update(mv_image=s.image, mv_frame=s.frame)
        scan_model()


def on_reset() -> None:
    reset_scan_state()
    mode2.rearm()


def take_frame(image: Image.Image, frame: dict, source: str) -> None:
    """A new frame. Shopper: grade it now if a type is selected, else wait for the pick.

    Model view: grade it and freeze it, unless a capture is already frozen (then it is ignored).
    """
    if current_view() == "Model view":
        if st.session_state.mv_image is None:
            st.session_state.update(mv_image=image, mv_frame=frame)
            scan_model()
        return
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
        # Shopper: items moved or were taken off, drop that frame and its grades (a printed label stays).
        # Model view: a capture stays frozen until "Reset scan".
        if current_view() != "Model view" and st.session_state.source == "camera" \
                and st.session_state.screen != "printed":
            mode2.clear_frame()
    elif kind == "live":
        mode2.clear_frame()
        mode2.rearm()


# ---------------------------------------------------------------- scan
def scan() -> bool:
    """Shopper: grade the waiting frame with the shopper's pick. False if no frame or no models."""
    if st.session_state.image is None:  # never grade anything but a captured frame
        st.session_state.screen = "live"
        return False
    result = _grade(st.session_state.image, st.session_state.frame, model_view=False)
    if result is None:
        return False
    st.session_state.result = result
    st.session_state.screen = "result"
    return True


def scan_model() -> bool:
    """Model view: grade the captured frame with the detector's type; it then stays frozen."""
    if st.session_state.mv_image is None:
        return False
    result = _grade(st.session_state.mv_image, st.session_state.mv_frame, model_view=True)
    st.session_state.mv_result = result
    return result is not None


def _grade(image: Image.Image, frame: dict | None, model_view: bool) -> dict | None:
    """Auto: the real models (pipeline.analyse_real). A forced rule: the stand-in backend.

    Shopper: the shopper's pick is the type. Model view: the type comes from the detector
    (pipeline.detector_type), passed to decide as the selected type; st.session_state.selected_type
    is never changed. The camera-tuned model runs on every real scan, after decide (never fed back).
    None if the models could not be loaded.
    """
    simulate = str(st.session_state.simulate_rule or "auto")
    counter = "failed_scans_model" if model_view else "failed_scans"
    scan_type = None if model_view else st.session_state.selected_type  # None: the detector decides
    type_info = None
    if model_view and simulate != "auto":  # the stand-in needs a type: run the detector only
        try:
            type_info = pipeline.type_from_image(image)
        except Exception:  # noqa: BLE001 - models unavailable: fall back below
            type_info = None
        scan_type = type_info["type"] if type_info else (st.session_state.selected_type or TYPES[0])
    args = (image, scan_type, WEIGHT_KG, st.session_state[counter])
    if simulate == "auto":
        try:
            models.load_models()
        except Exception as exc:  # noqa: BLE001 - e.g. no internet and nothing cached
            st.session_state.model_error = (
                "The trained models could not be loaded, so Auto (models decide) cannot run. "
                "Check the internet connection (or set FRESHMART_MODELS_DIR). The simulated outcomes in "
                f"Model view still work. Details: {type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else ''}")
            return None
        st.session_state.model_error = None
        result = pipeline.analyse_real(*args, display=True)  # camera-tuned after decide, both views
    else:
        result = backend.analyse(*args, simulate)
        result.update(selected_type=scan_type, type_from_detector=type_info)
    result["for_view"] = "model" if model_view else "shopper"
    result["frame_ts"] = (frame or {}).get("ts")  # which frame these grades belong to
    mode2.demo_outcome(result)  # demo only (rules 1/2/6): from the camera-tuned values, never fed back
    rule_id = result["rule_id"]
    # decide() counts failed scans (and raises the staff alert); the app only stores the count
    st.session_state[counter] = 0 if rule_id == 7 else int(result["failed_scans"])
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "selected_type": result.get("selected_type"),  # the scan's type (Model view: the detector's)
        "rule_id": rule_id,
        "staff_alert": result["staff_alert"],
    }
    st.session_state.scan_logs.append(entry)
    log_scan(entry)
    return result


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
                # The "Model view" default is seeded in Session State (init_state), not via
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
    """The live camera component. Shopper: live feed with the last grades. Model view: live feed
    until a capture, then the frozen captured frame with its cached overlays until "Reset scan"."""
    s = st.session_state
    model = view == "model"
    blemish, occ = model and bool(s.ov_blemish), model and bool(s.ov_cam)
    # Shopper labels: camera-tuned values, except on a real rule-7 price (ResNet-50, to match the ticket)
    disp = bool(s.ov_disp) if model else not mode2.is_priced(s.result)
    frozen = model and s.mv_image is not None
    still = None
    if frozen:
        still = live.still_arg(s.mv_image, s.mv_result, blemish, occ, disp)
        if still is not None:
            still["frozen"] = True
    live.render(
        view, key=LIVE_KEY, on_change=on_live, rearm=s.rearm,
        grades=None if frozen else live.grades_arg(s.result if not model else None,
                                                   s.frame if not model else None, blemish, occ, disp),
        still=still,
        show_boxes=bool(s.ov_boxes) if model else True, show_fresh=bool(s.ov_fresh) if model else True,
        show_blemish=blemish, show_occ=occ, show_disp=disp, aspect=0.62 if model else 0.7, max_height=640 if model else 560)


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
            mode1.render(live_view)
        else:
            mode2.render(scan, PRICES, live_view)


if __name__ == "__main__":
    main()