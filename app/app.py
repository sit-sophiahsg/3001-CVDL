"""FreshScale - FairPrice Finest-style self-service produce scale.

Flow: Home → Scan (camera identifies item) → auto-pick if confident,
      else Pick (user confirms from suggested list) → Result / Print label.

Run from the repo root:  streamlit run app/app.py
"""

from __future__ import annotations

import html
import io
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

import predictor
import pricing
import styles

CONFIG_PATH = Path(__file__).with_name("config.yaml")
SGT = timezone(timedelta(hours=8), "SGT")
IS_DEMO = getattr(predictor, "IS_DEMO", False)

_IMAGES_DIR = Path(__file__).with_name("images")
_WELCOME_IMG = _IMAGES_DIR / "welcome.png"
_HANDS0_IMG  = _IMAGES_DIR / "hands0.png"
_HANDS1_IMG  = _IMAGES_DIR / "hands1.png"

PLU_CODES: dict[str, str] = {
    "apple": "4131", "banana": "4011", "orange": "4012", "lemon": "4053",
    "tomato": "4664", "capsicum": "3148", "cucumber": "4062", "okra": "4530",
    "potato": "4072", "bitter_gourd": "3287", "onion": "4093",
}
ORIGINS: dict[str, str] = {
    "apple": "New Zealand", "banana": "Philippines", "orange": "Australia",
    "lemon": "South Africa", "tomato": "Malaysia", "capsicum": "Malaysia",
    "cucumber": "Malaysia", "okra": "Malaysia", "potato": "Australia",
    "bitter_gourd": "Malaysia", "onion": "India",
}
SINGLE_WEIGHT: dict[str, tuple[float, float]] = {
    "apple": (0.15, 0.30), "banana": (0.10, 0.25), "orange": (0.18, 0.38),
    "lemon": (0.07, 0.14), "tomato": (0.08, 0.20), "capsicum": (0.10, 0.25),
    "cucumber": (0.20, 0.55), "okra": (0.04, 0.12), "potato": (0.10, 0.30),
    "bitter_gourd": (0.15, 0.40), "onion": (0.08, 0.22),
}

# Back-nav: where each screen returns to
BACK_TO = {"scan": "home", "pick": "scan", "result": "scan"}

DEFAULTS = {
    "screen": "home",
    "item_id": None,
    "weight_kg": 0.0,
    "result": None,
    "image_bytes": None,
    "scan_weight": 0.0,
    "scanned_at": None,
    "show_label": False,
    "scan_error": False,
    "failed_scans": 0,   # resets on a successful price; triggers staff alert at 2
}

FOOTER_SPEC = "Max 6/15 kg  Min 40 g  e = d = 2/5 g"

ss = st.session_state


# ── helpers ────────────────────────────────────────────────────────────────

def show(markup: str) -> None:
    st.markdown("\n".join(l.strip() for l in markup.splitlines() if l.strip()),
                unsafe_allow_html=True)

def esc(v) -> str: return html.escape(str(v))
def money(amount, config: dict) -> str: return pricing.format_money(amount, config["currency"])

def item_by_id(config: dict, item_id: str | None) -> dict | None:
    return next((p for p in config["produce"] if p["id"] == item_id), None)

def item_name(config: dict, item_id: str) -> str:
    item = item_by_id(config, item_id)
    return item["name"] if item else item_id.replace("_", " ").title()

def plu(item_id: str) -> str: return PLU_CODES.get(item_id, "9999")
def origin(item_id: str) -> str: return ORIGINS.get(item_id, "Singapore")


# ── navigation callbacks ───────────────────────────────────────────────────

def init_state() -> None:
    for key, value in DEFAULTS.items():
        ss.setdefault(key, value)
    ss.setdefault("capture_nonce", 0)

def go(screen: str, **updates) -> None:
    ss.update(updates)
    ss.screen = screen

def clear_capture() -> None:
    ss.capture_nonce += 1

def start_over() -> None:
    ss.update(DEFAULTS)
    clear_capture()

def go_back() -> None:
    dest = BACK_TO.get(ss.screen, "home")
    if dest == "scan":
        # Reset scan state so weight returns to 0 and camera is fresh
        ss.result = None
        ss.item_id = None
        ss.weight_kg = 0.0
        ss.scan_weight = 0.0
        ss.scan_error = False
    go(dest, show_label=False)
    clear_capture()

def tap_start() -> None:
    """Welcome → Scan.  Weight stays 0 until the scan completes."""
    ss.weight_kg = 0.0
    go("scan")

def confirm_item(item_id: str) -> None:
    """User manually picks the item from the pick screen."""
    if ss.result:
        ss.result = {**ss.result, "produce_id": item_id}
    ss.item_id = item_id
    ss.screen = "result"

def rescan() -> None:
    ss.result = None
    ss.item_id = None
    ss.weight_kg = 0.0
    ss.scan_weight = 0.0
    ss.scan_error = False
    clear_capture()
    go("scan")


# ── shared layout ──────────────────────────────────────────────────────────

def render_header(config: dict) -> None:
    item = item_by_id(config, ss.item_id) if ss.screen in ("result",) else None
    scan_w = ss.scan_weight if ss.screen == "result" else ss.weight_kg
    unit_price = item["price_per_kg"] if item else 0.0
    total = scan_w * unit_price
    sym = esc(config["currency"].get("symbol", "S$"))
    dec = config["currency"].get("decimals", 2)

    if ss.screen == "home":
        show(f"""
            <div class="fs-header fs-header-welcome">
              <div class="fs-rw-labels">
                <div>TARE (kg)</div><div>WEIGHT (kg)</div><div></div>
              </div>
              <div class="fs-rw-values">
                <div>0.000</div><div>0.000</div>
                <div class="fs-welcome-cell">WELCOME!</div>
              </div>
            </div>
        """)
    else:
        cells_l = ["TARE (kg)", "WEIGHT (kg)", f"UNIT PRICE ({sym}/kg)", f"TOTAL PRICE ({sym})"]
        cells_v = ["0.000", f"{scan_w:.3f}", f"{unit_price:.{dec}f}", f"{total:.{dec}f}"]
        labels = "".join(f"<div>{l}</div>" for l in cells_l)
        values = "".join(f"<div>{v}</div>" for v in cells_v)
        show(f"""
            <div class="fs-header">
              <div class="fs-rw-labels">{labels}</div>
              <div class="fs-rw-values">{values}</div>
            </div>
        """)


def render_bubble(msg: str) -> None:
    show(f'<div class="fs-bubble">{esc(msg)}</div>')


def render_home_row(show_back: bool = False) -> None:
    with st.container(key="home_row"):
        cols = st.columns([1, 1, 3]) if show_back else st.columns([1, 4])
        with cols[0]:
            with st.container(key="home_btn"):
                st.button("🏠 Home", key="btn_home", on_click=start_over, width="stretch")
        if show_back:
            with cols[1]:
                with st.container(key="back_btn"):
                    st.button("← Back", key="btn_back", on_click=go_back, width="stretch")


def render_footer(config: dict) -> None:
    store = esc(config.get("store_name", "FreshScale"))
    show(f"""
        <div class="fs-footer">
          <span class="fs-footer-spec">{FOOTER_SPEC}</span>
          <span class="fs-footer-brand">{store}<em>scale</em></span>
        </div>
        <div class="fs-disclaimer">Student demo — not affiliated with any retailer.</div>
    """)


def render_demo_controls() -> None:
    if not IS_DEMO:
        return
    with st.sidebar:
        st.header("Demo controls")
        st.radio("Force next result", predictor.DEMO_OUTCOMES, key="demo_force")
        st.caption("Pick an outcome, then press SCAN.")


# ── item count estimator (colour-mask based) ────────────────────────────────

def _count_items(image: Image.Image, item_id: str) -> int:
    import numpy as np
    SIZE = 200
    arr = np.array(image.resize((SIZE, SIZE), Image.BILINEAR), dtype=np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    diff = np.maximum(maxc - minc, 1e-9)
    v = maxc
    s = np.where(maxc > 0.08, diff / maxc, 0.0)
    rc = (maxc - r) / diff; gc = (maxc - g) / diff; bc = (maxc - b) / diff
    h = np.where(maxc == r, (bc - gc) % 6,
        np.where(maxc == g, 2.0 + rc - bc, 4.0 + gc - rc)) / 6.0

    if item_id in ("apple", "tomato"):
        mask = ((h < 0.055) | (h > 0.945)) & (s > 0.35) & (v > 0.15)
    elif item_id in ("banana", "lemon"):
        mask = (h > 0.09) & (h < 0.20) & (s > 0.28) & (v > 0.40)
    elif item_id == "orange":
        mask = (h > 0.035) & (h < 0.11) & (s > 0.40) & (v > 0.30)
    elif item_id in ("capsicum", "cucumber", "okra", "bitter_gourd"):
        mask = (h > 0.20) & (h < 0.44) & (s > 0.20) & (v > 0.08)
    elif item_id in ("potato", "onion"):
        mask = (h > 0.05) & (h < 0.16) & (s > 0.08) & (v > 0.15)
    else:
        mask = s > 0.25

    single_fracs = {
        "apple": 0.08, "banana": 0.10, "orange": 0.09, "lemon": 0.06,
        "tomato": 0.07, "capsicum": 0.10, "cucumber": 0.14, "okra": 0.05,
        "potato": 0.08, "bitter_gourd": 0.10, "onion": 0.07,
    }
    single_area = int(single_fracs.get(item_id, 0.08) * SIZE * SIZE)
    fruit_pixels = int(mask.sum())
    if fruit_pixels < single_area * 0.30:
        return 1
    return min(8, max(1, round(fruit_pixels / single_area)))


# ── scan logic ─────────────────────────────────────────────────────────────

# Confidence threshold above which we auto-pick the detected item
_AUTO_PICK_THRESHOLD = 0.65


def _run_scan(upload, config: dict) -> None:
    data = upload.getvalue()
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except (UnidentifiedImageError, OSError):
        st.error("That file could not be read as a photo. Please try another.")
        return

    if IS_DEMO and hasattr(predictor, "set_demo_override"):
        predictor.set_demo_override(ss.get("demo_force", "Auto"))

    with st.spinner("Scanning your produce..."):
        result = predictor.predict(image, "")  # selected_id unused by model

    if not result["valid_scan"]:
        ss.scan_error = True
        ss.failed_scans = ss.get("failed_scans", 0) + 1
        return

    # Weight is set HERE — simulates the scale reading when item is placed
    detected_id = result["produce_id"]
    count = _count_items(image, detected_id)
    lo, hi = SINGLE_WEIGHT.get(detected_id, (0.10, 0.30))
    weight = round(random.uniform(lo, hi) * count, 3)
    ss.weight_kg = weight

    ss.failed_scans = 0  # successful identification resets the counter
    kwargs = dict(result=result, image_bytes=data,
                  scan_weight=weight, scanned_at=datetime.now(SGT),
                  show_label=False, scan_error=False)

    if result["produce_confidence"] >= _AUTO_PICK_THRESHOLD:
        # Confident — auto-pick and go straight to result
        go("result", item_id=detected_id, **kwargs)
    else:
        # Uncertain — ask user to confirm from a short list
        go("pick", item_id=None, **kwargs)

    st.rerun()


# ── screens ────────────────────────────────────────────────────────────────

def _thumb(path: Path, height_px: int) -> Image.Image | None:
    """Load and resize an image to a fixed height, preserving aspect ratio."""
    if not path.exists():
        return None
    img = Image.open(path).convert("RGBA")
    ratio = height_px / img.height
    return img.resize((int(img.width * ratio), height_px), Image.LANCZOS)


def screen_home(_config: dict) -> None:
    render_bubble("Please place item to start")
    with st.container(key="welcome_cols"):
        left_col, mid_col, right_col = st.columns([0.8, 0.6, 0.3], gap="small")
        with left_col:
            img = _thumb(_HANDS0_IMG, 230)
            if img:
                st.image(img, use_container_width=False)
        with mid_col:
            img = _thumb(_WELCOME_IMG, 400)
            if img:
                st.image(img, use_container_width=False)
            else:
                show('<div class="fs-welcome-art"><span>🛍️</span></div>')
        with right_col:
            img = _thumb(_HANDS1_IMG, 230)
            if img:
                st.image(img, use_container_width=False)
    with st.container(key="start_btn"):
        st.button("TAP TO START", key="btn_start", type="primary",
                  on_click=tap_start, width="stretch")
    render_home_row(show_back=False)


def screen_scan(config: dict) -> None:
    render_bubble("Place your item on the scale and take a photo to identify it.")

    with st.container(key="body"):
        if ss.scan_error:
            if ss.get("failed_scans", 0) >= 2:
                show('<div class="fs-staff-alert">🔔 A staff member is on the way to help.</div>')
            else:
                show("""
                    <div class="fs-alert">
                      <div class="fs-alert-title">Could not identify the item</div>
                      <div class="fs-alert-body">Make sure the item is centred in the frame
                      with good lighting, then try again.</div>
                    </div>
                """)
            ss.scan_error = False

        cam_tab, upload_tab = st.tabs(["📷 Camera", "🖼️ Upload photo"])
        with cam_tab:
            camera = st.camera_input("Take a photo of the item",
                                     key=f"cam_{ss.capture_nonce}")
        with upload_tab:
            upload = st.file_uploader("Upload a photo of the item",
                                      type=["jpg", "jpeg", "png", "webp"],
                                      key=f"upload_{ss.capture_nonce}")
            if upload is not None:
                st.image(upload, width="stretch")
            st.caption("On a phone, the upload option also lets you use the back camera.")

        photo = camera if camera is not None else upload
        if photo is None:
            st.caption("Take or upload a photo to continue.")

        with st.container(key="scan_btn"):
            if st.button("SCAN", key="btn_scan", type="primary",
                         width="stretch", disabled=photo is None):
                _run_scan(photo, config)

    render_home_row(show_back=True)


def screen_pick(config: dict) -> None:
    result = ss.result
    if result is None:
        go("scan"); st.rerun()

    detected_id = result.get("produce_id", "")
    detected = item_by_id(config, detected_id)
    if detected:
        render_bubble(f"Looks like {detected['name']} — is that right? Select the correct item below.")
    else:
        render_bubble("We couldn't be sure what this is. Please select the correct item below.")

    enabled_items = [p for p in config["produce"] if p["enabled"]]

    with st.container(key="body"):
        cols = st.columns(len(enabled_items), gap="small")
        for col, item in zip(cols, enabled_items):
            with col:
                is_suggested = (item["id"] == detected_id)
                badge = ('<div class="fp-tile-suggested-label">Best match</div>'
                         if is_suggested else "")
                show(f"""
                    <div class="fp-tile{'  fp-tile-suggested' if is_suggested else ''}">
                      <div class="fp-tile-plu">{plu(item['id'])}</div>
                      <div class="fp-tile-uprice">{money(item['price_per_kg'], config)}/kg</div>
                      <div class="fp-tile-emoji">{esc(item['emoji'])}</div>
                      <div class="fp-tile-name">{esc(item['name'])}</div>
                      {badge}
                    </div>
                """)
                with st.container(key=f"pick_{item['id']}"):
                    st.button("SELECT", key=f"btn_pick_{item['id']}",
                              on_click=confirm_item, args=(item["id"],),
                              width="stretch")

    render_home_row(show_back=True)


def _render_label(item: dict, price: pricing.PriceBreakdown, config: dict,
                  status: str) -> None:
    scanned = ss.scanned_at or datetime.now(SGT)
    demo_html = ('<div class="fs-label-demo">⚠ DEMO — NOT VALID FOR SALE</div>'
                 if IS_DEMO else "")
    fc = "#1b8a3f" if status == "Fresh" else "#c0392b"
    fl = "✓ FRESH" if status == "Fresh" else "✗ ROTTEN"
    sym = esc(config["currency"].get("symbol", "S$"))
    dec = config["currency"].get("decimals", 2)
    show(f"""
        <div class="fs-label-wrap">
          <div class="fs-label-inner">
            <div class="fs-label-top">
              <div>
                <div class="fs-label-title">{esc(item['name'].upper())}</div>
                <div class="fs-label-origin">PRODUCT OF {esc(origin(item['id']).upper())}</div>
                <div style="margin-top:0.5rem;display:inline-block;
                     background:{fc};color:#fff;border-radius:6px;
                     padding:0.15rem 0.6rem;font-size:0.85rem;font-weight:800;">{fl}</div>
              </div>
              <div class="fs-label-emojibox">
                <div style="font-size:3.2rem;">{esc(item['emoji'])}</div>
                <div class="fs-label-plu">L{plu(item['id'])}</div>
              </div>
            </div>
            <div class="fs-label-rows">
              <div class="fs-label-row">
                <span class="k">Weight</span><span class="v">{price.weight_kg:.3f} kg</span></div>
              <div class="fs-label-row">
                <span class="k">Unit price</span>
                <span class="v">{money(price.price_per_kg, config)}/kg</span></div>
              <div class="fs-label-row">
                <span class="k">Discount</span>
                <span class="v">{price.discount_rate:.0%} (-{money(price.discount_amount, config)})</span></div>
            </div>
            <div class="fs-label-total">
              <span>TOTAL</span><span>{money(price.total, config)}</span>
            </div>
            <div style="text-align:right;font-size:0.7rem;color:#aaa;margin-top:0.3rem;">
              {scanned.strftime('%d %b %Y  %H:%M')}</div>
            {demo_html}
          </div>
          <div class="fs-label-wave"></div>
        </div>
    """)


def screen_result(config: dict) -> None:
    result = ss.result
    item = item_by_id(config, ss.item_id)

    if result is None or item is None:
        go("scan"); st.rerun()

    if IS_DEMO:
        show('<div class="fs-demo">⚠ DEMO MODE — not a real prediction</div>')

    # Invalid scan (shouldn't reach here via new flow, but keep as safety net)
    if not result["valid_scan"]:
        render_bubble("We couldn't recognise the produce — please rescan.")
        with st.container(key="body"):
            st.button("📷 Rescan", key="btn_rescan", type="primary",
                      on_click=rescan, width="stretch")
        render_home_row(show_back=True)
        return

    # Rotten / not for sale
    rule = pricing.status_rule(config, result["status"])
    if not rule["sellable"]:
        render_bubble("This item is not for sale — please inform staff.")
        show(f"""
            <div class="fs-rotten-badge">
              {esc(result['status'].upper())}
              <small>Not for sale — please inform staff</small>
            </div>
        """)
        with st.container(key="body"):
            if ss.image_bytes:
                st.image(ss.image_bytes, width=220)
            st.caption(f"Model confidence: {result['fresh_probability']:.0%}")
            st.button("Scan another item", key="btn_next", type="primary",
                      on_click=rescan, width="stretch")
        render_home_row(show_back=True)
        return

    # Fresh / sellable
    price = pricing.compute_price(ss.scan_weight, item["price_per_kg"],
                                  rule["discount"],
                                  config["currency"].get("decimals", 2))

    render_bubble("Please press the PRINT button to print your label.")

    with st.container(key="body"):
        photo_col, label_col = st.columns([1, 2], gap="large")
        with photo_col:
            if ss.image_bytes:
                st.image(ss.image_bytes, caption="Scanned photo", width="stretch")
            show(f"""
                <div class="fs-fresh-badge">
                  {esc(result['status'].upper())}
                  <small>Confidence: {result['fresh_probability']:.0%}</small>
                </div>
            """)
        with label_col:
            _render_label(item, price, config, result["status"])
            with st.container(key="print_btn"):
                if st.button("🖨️\nPRINT", key="btn_print", type="primary"):
                    st.toast("🖨️ Label sent to printer!", icon="✅")
            c1, c2 = st.columns(2)
            c1.button("📷 Rescan", key="btn_rescan3", on_click=rescan, width="stretch")
            c2.button("Next item", key="btn_next2", on_click=rescan, width="stretch")

    render_home_row(show_back=True)


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(page_title="FreshScale", page_icon="🥬", layout="wide",
                       initial_sidebar_state="collapsed")
    styles.inject_css()
    init_state()

    try:
        config = pricing.load_config(CONFIG_PATH)
    except (OSError, ValueError, KeyError, TypeError) as err:
        st.error(f"Could not load config.yaml: {err}")
        st.stop()

    render_demo_controls()
    if IS_DEMO:
        st.markdown('<style>[data-testid="stHeader"] { display: block; }</style>',
                    unsafe_allow_html=True)

    render_header(config)

    screen_fn = {
        "home":   screen_home,
        "scan":   screen_scan,
        "pick":   screen_pick,
        "result": screen_result,
    }
    screen_fn.get(ss.screen, screen_home)(config)
    render_footer(config)


main()
