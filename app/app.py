"""FreshScale - self-service produce scale UI (screens and navigation).

Run from the repo root with:  streamlit run app/app.py
"""

from __future__ import annotations

import html
import io
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

CATEGORY_LABELS = {"fruit": "Fruits", "vegetable": "Vegetables"}
BACK_TO = {"items": "home", "scan": "items", "result": "scan"}
DEFAULTS = {
    "screen": "home",
    "category": None,
    "item_id": None,
    "weight_kg": 0.0,
    "result": None,
    "image_bytes": None,
    "scan_weight": 0.0,
    "scanned_at": None,
    "show_label": False,
}

ss = st.session_state


# ---------- helpers ----------

def show(markup: str) -> None:
    """Render HTML. Lines are stripped so Markdown never turns indentation into code blocks."""
    st.markdown("\n".join(l.strip() for l in markup.splitlines() if l.strip()),
                unsafe_allow_html=True)


def esc(value) -> str:
    return html.escape(str(value))


def money(amount, config: dict) -> str:
    return pricing.format_money(amount, config["currency"])


def item_by_id(config: dict, item_id: str | None) -> dict | None:
    return next((p for p in config["produce"] if p["id"] == item_id), None)


def item_name(config: dict, item_id: str) -> str:
    item = item_by_id(config, item_id)
    return item["name"] if item else item_id.replace("_", " ").title()


# ---------- navigation (used as button callbacks) ----------

def init_state() -> None:
    for key, value in DEFAULTS.items():
        ss.setdefault(key, value)
    ss.setdefault("capture_nonce", 0)


def go(screen: str, **updates) -> None:
    ss.update(updates)
    ss.screen = screen


def clear_capture() -> None:
    """New widget keys so the camera / uploader start empty."""
    ss.capture_nonce += 1


def go_back() -> None:
    go(BACK_TO.get(ss.screen, "home"), show_label=False)


def start_over() -> None:
    ss.update(DEFAULTS)
    clear_capture()


def select_item(item_id: str) -> None:
    clear_capture()
    go("scan", item_id=item_id, result=None, show_label=False)


def rescan() -> None:
    clear_capture()
    go("scan", result=None, show_label=False)


def change_item(category: str) -> None:
    clear_capture()
    go("items", category=category, result=None, show_label=False)


def sync_weight() -> None:
    ss.weight_kg = float(ss.weight_widget or 0.0)


# ---------- shared layout ----------

def render_header(config: dict) -> None:
    item = item_by_id(config, ss.item_id) if ss.screen in ("scan", "result") else None
    weight = ss.scan_weight if ss.screen == "result" else ss.weight_kg
    unit = f"{money(item['price_per_kg'], config)}/kg" if item else "&nbsp;"
    show(f"""
        <div class="fs-header">
          <div class="fs-brand">
            <div class="fs-logo">🥬</div>
            <div>
              <div class="fs-name">{esc(config.get("store_name", "FreshScale"))}</div>
              <div class="fs-sub">Self-service produce scale</div>
            </div>
          </div>
          <div class="fs-scale">
            <div class="fs-scale-label">WEIGHT</div>
            <div class="fs-scale-value">{weight:.3f}<span class="fs-scale-unit">kg</span></div>
            <div class="fs-scale-price">{unit}</div>
          </div>
        </div>
    """)


def render_nav() -> None:
    with st.container(key="navbar"):
        back, reset = st.columns(2)
        back.button("← Back", key="nav_back", on_click=go_back,
                    disabled=ss.screen == "home", width="stretch")
        reset.button("⟲ Start over", key="nav_reset", on_click=start_over, width="stretch")


def render_item_bar(item: dict, config: dict) -> None:
    show(f"""
        <div class="fs-itembar">
          <div class="fs-itembar-emoji">{esc(item["emoji"])}</div>
          <div>
            <div class="fs-itembar-name">{esc(item["name"])}</div>
            <div class="fs-itembar-price">{money(item["price_per_kg"], config)} per kg</div>
          </div>
        </div>
    """)


def render_demo_controls() -> None:
    if not IS_DEMO:
        return
    with st.sidebar:
        st.header("Demo controls")
        st.radio("Force the next scan result", predictor.DEMO_OUTCOMES, key="demo_force",
                 help="Auto: decided by a hash of the photo, so the same photo "
                      "always gives the same result.")
        st.caption("Uses the fake predictor. Pick an outcome, then press Scan.")


# ---------- screens ----------

def screen_home(config: dict) -> None:
    show('<div class="fs-title">What are you weighing today?</div>')
    for col, (category, label) in zip(st.columns(2, gap="large"), CATEGORY_LABELS.items()):
        items = [p for p in config["produce"] if p["category"] == category]
        enabled = [p for p in items if p["enabled"]]
        emojis = "".join(p["emoji"] for p in enabled[:3])
        with col, st.container(key=f"cat_{category}"):
            show(f"""
                <div class="fs-cat">
                  <div class="fs-cat-emoji">{esc(emojis)}</div>
                  <div class="fs-cat-name">{label}</div>
                  <div class="fs-cat-count">{len(enabled)} items available</div>
                </div>
            """)
            st.button(f"Choose {label}", key=f"pick_cat_{category}", type="primary",
                      width="stretch", on_click=go, args=("items",),
                      kwargs={"category": category})


def item_tile(item: dict, config: dict) -> None:
    enabled = item["enabled"]
    key = f"tile_{item['id']}" if enabled else f"tiledis_{item['id']}"
    soon = '<div class="fs-soon">COMING SOON</div>' if not enabled else ""
    with st.container(key=key):
        show(f"""
            <div class="fs-tile{'' if enabled else ' off'}">
              <div class="fs-tile-emoji">{esc(item["emoji"])}</div>
              <div class="fs-tile-name">{esc(item["name"])}</div>
              <div class="fs-tile-price">{money(item["price_per_kg"], config)}/kg</div>
              {soon}
            </div>
        """)
        st.button("Select" if enabled else "Not available yet", key=f"pick_{item['id']}",
                  type="primary", width="stretch", disabled=not enabled,
                  on_click=select_item, args=(item["id"],))


def screen_items(config: dict) -> None:
    category = ss.category
    if category not in CATEGORY_LABELS:
        go("home")
        st.rerun()
    show(f'<div class="fs-title">Choose your {CATEGORY_LABELS[category].lower()}</div>')
    items = [p for p in config["produce"] if p["category"] == category]
    items.sort(key=lambda p: not p["enabled"])  # "coming soon" items last
    per_row = 3
    for start in range(0, len(items), per_row):
        for col, item in zip(st.columns(per_row, gap="medium"), items[start:start + per_row]):
            with col:
                item_tile(item, config)


def run_scan(upload, item: dict) -> None:
    data = upload.getvalue()
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except (UnidentifiedImageError, OSError):
        st.error("That file could not be read as a photo. Please try another one.")
        return
    if IS_DEMO and hasattr(predictor, "set_demo_override"):
        predictor.set_demo_override(ss.get("demo_force", "Auto"))
    with st.spinner("Checking your produce..."):
        result = predictor.predict(image, item["id"])
    go("result", result=result, image_bytes=data, scan_weight=ss.weight_kg,
       scanned_at=datetime.now(SGT), show_label=False)
    st.rerun()


def screen_scan(config: dict) -> None:
    item = item_by_id(config, ss.item_id)
    if item is None or not item["enabled"]:
        go("items" if ss.category else "home")
        st.rerun()
    render_item_bar(item, config)

    photo_col, weigh_col = st.columns([3, 2], gap="large")
    with photo_col:
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
            st.caption("On a phone, this also lets you use the back camera.")

    with weigh_col:
        ss.weight_widget = ss.weight_kg
        st.number_input("Weight (kg) - simulated scale", key="weight_widget",
                        min_value=0.0, max_value=50.0, step=0.05, format="%.3f",
                        on_change=sync_weight,
                        help="There is no real scale yet, so type the weight here. "
                             "It appears on the display in the top-right corner.")
        photo = camera if camera is not None else upload
        if photo is None:
            st.caption("Take or upload a photo to continue.")
        elif ss.weight_kg <= 0:
            st.caption("Enter the weight to continue.")
        elif camera is not None and upload is not None:
            st.caption("Using the camera photo.")
        if st.button("SCAN", key="scan_btn", type="primary", width="stretch",
                     disabled=photo is None or ss.weight_kg <= 0):
            run_scan(photo, item)


def render_badge(status: str, subtitle: str = "") -> None:
    css = status.lower() if status in ("Fresh", "Rotten") else "other"
    small = f"<small>{esc(subtitle)}</small>" if subtitle else ""
    show(f'<div class="fs-badge {css}">{esc(status.upper())}{small}</div>')


def render_model_rows(result: dict, config: dict) -> None:
    defect = result.get("defect_percent")
    defect_html = (f'<span class="v">{defect:.1f}%</span>' if defect is not None
                   else '<span class="v soon">Coming soon</span>')
    show(f"""
        <div class="fs-rows">
          <div class="fs-row"><span class="k">Model confidence (Fresh)</span>
            <span class="v">{result["fresh_probability"]:.0%}</span></div>
          <div class="fs-row"><span class="k">Defect area</span>{defect_html}</div>
          <div class="fs-row"><span class="k">Identified as</span>
            <span class="v">{esc(item_name(config, result["produce_id"]))}
            ({result["produce_confidence"]:.0%})</span></div>
        </div>
    """)
    st.caption("Model confidence is how sure the model is that this item is fresh. "
               "It is not the percentage of the item that is damaged.")


def render_label(item: dict, price: pricing.PriceBreakdown, config: dict) -> None:
    scanned = ss.scanned_at or datetime.now(SGT)
    demo = ('<div class="fs-label-demo">DEMO LABEL - NOT VALID FOR SALE</div>'
            if IS_DEMO else "")
    show(f"""
        <div class="fs-label">
          <div class="fs-label-head">{esc(config.get("store_name", "FreshScale")).upper()}</div>
          <hr>
          <div class="fs-label-row"><span>Item</span><span>{esc(item["name"])}</span></div>
          <div class="fs-label-row"><span>Weight</span><span>{price.weight_kg:.3f} kg</span></div>
          <div class="fs-label-row"><span>Unit price</span>
            <span>{money(price.price_per_kg, config)}/kg</span></div>
          <div class="fs-label-row"><span>Discount</span>
            <span>{price.discount_rate:.0%} (-{money(price.discount_amount, config)})</span></div>
          <hr>
          <div class="fs-label-row total"><span>TOTAL</span><span>{money(price.total, config)}</span></div>
          <hr>
          <div class="fs-label-meta">{scanned.strftime("%d %b %Y  %H:%M")}</div>
          <div class="fs-barcode"></div>
          {demo}
        </div>
    """)


def screen_result(config: dict) -> None:
    result, item = ss.result, item_by_id(config, ss.item_id)
    if result is None or item is None:
        go("scan" if item else "home")
        st.rerun()
    if IS_DEMO:
        show('<div class="fs-demo">⚠ DEMO MODE - not a real prediction</div>')

    photo_col, result_col = st.columns([1, 2], gap="large")
    with photo_col:
        if ss.image_bytes:
            st.image(ss.image_bytes, caption="Scanned photo", width="stretch")

    with result_col:
        if not result["valid_scan"]:
            show("""
                <div class="fs-alert">
                  <div class="fs-alert-title">Please rescan</div>
                  <div class="fs-alert-body">We couldn't recognise the produce in this photo.
                  Place the item in the middle of the frame, in good light.</div>
                </div>
            """)
            st.button("📷 Rescan", key="res_rescan", type="primary", width="stretch",
                      on_click=rescan)
            return

        if result["produce_id"] != item["id"]:
            predicted = item_by_id(config, result["produce_id"])
            show(f"""
                <div class="fs-alert">
                  <div class="fs-alert-title">This looks like
                    {esc(item_name(config, result["produce_id"]))}, not {esc(item["name"])}.</div>
                  <div class="fs-alert-body">Rescan the item, or choose the correct item.</div>
                </div>
            """)
            rescan_col, change_col = st.columns(2)
            rescan_col.button("📷 Rescan", key="res_rescan", type="primary",
                              width="stretch", on_click=rescan)
            change_col.button("Change item", key="res_change", width="stretch",
                              on_click=change_item,
                              args=(predicted["category"] if predicted else item["category"],))
            return

        rule = pricing.status_rule(config, result["status"])
        if not rule["sellable"]:
            render_badge(result["status"], "Not for sale - please inform staff")
            render_model_rows(result, config)
            st.button("Scan another item", key="res_next", type="primary", width="stretch",
                      on_click=change_item, args=(item["category"],))
            return

        price = pricing.compute_price(ss.scan_weight, item["price_per_kg"], rule["discount"],
                                      config["currency"].get("decimals", 2))
        render_badge(result["status"], f"Total {money(price.total, config)}")
        render_model_rows(result, config)
        show(f"""
            <div class="fs-rows">
              <div class="fs-row"><span class="k">Weight</span>
                <span class="v">{price.weight_kg:.3f} kg</span></div>
              <div class="fs-row"><span class="k">Unit price</span>
                <span class="v">{money(price.price_per_kg, config)}/kg</span></div>
              <div class="fs-row"><span class="k">Discount</span>
                <span class="v">{price.discount_rate:.0%}
                (-{money(price.discount_amount, config)})</span></div>
              <div class="fs-row total"><span class="k">Total</span>
                <span class="v">{money(price.total, config)}</span></div>
            </div>
        """)
        print_col, next_col = st.columns(2)
        print_col.button("🖨️ Print label", key="res_print", type="primary", width="stretch",
                         on_click=go, args=("result",), kwargs={"show_label": True})
        next_col.button("Scan next item", key="res_next", width="stretch",
                        on_click=change_item, args=(item["category"],))

    if ss.show_label:
        render_label(item, price, config)


# ---------- main ----------

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
    render_header(config)
    render_nav()
    {
        "home": screen_home,
        "items": screen_items,
        "scan": screen_scan,
        "result": screen_result,
    }.get(ss.screen, screen_home)(config)


main()
