"""Mode 2: the shopper-facing scale kiosk."""

from __future__ import annotations

import io
from datetime import datetime
from html import escape
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

import views
from backend import TYPES
from components import BARCODE_SVG, bump_nonce, icon_svg, label_of, produce_svg

SCREENS = ("welcome", "camera", "upload", "select", "result", "printed")
WELCOME_PATH = Path(__file__).parent / "images" / "welcome.png"

BANNERS = {
    "welcome": "Place your item on the scale, then take or upload a photo",
    "camera": "Hold the item in view and take a photo",
    "upload": "Choose a photo of your item",
    "select": "Select the item you are weighing",
    "printed": "Label printed. Thank you!",
}
PRICED_BANNER = "Please press PRINT"
SPINNER_TEXT = "Finding items, grading freshness, checking blemishes…"
TIER_BG = {"A": "#1F6F47", "B": "#9A5300", "C": "#B23A12", "D": "#8A1C0E"}
STOP_DETAIL = {
    1: "Nothing here looks like one of our six types.",
    2: "We could not grade this item clearly. Open the bag or turn the item, then scan again.",
    3: "There is more than one kind of produce on the scale.",
    4: "You selected {selected}, but the scale sees a different type.",
    5: "This item is past its best and should not be sold.",
    6: "We could not grade this item clearly. Open the bag or turn the item, then scan again.",
}
FALLBACK_DETAIL = "This item could not be priced. Please ask a staff member."
D = "&#36;"  # a literal "$" that Markdown never reads as LaTeX


# ---------------------------------------------------------------- helpers
def is_priced(result: dict | None) -> bool:
    return bool(result) and result.get("rule_id") == 7 and result.get("price", {}).get("total") is not None


def banner_for(screen: str, result: dict | None) -> tuple[str, str]:
    """(text, css variant) for the prompt banner."""
    if screen == "result" and result:
        if is_priced(result):
            return PRICED_BANNER, ""
        rule = result.get("rule_id")
        text = result.get("message") or FALLBACK_DETAIL
        return text, "stop" if rule == 5 else "warn"
    return BANNERS.get(screen, BANNERS["welcome"]), ""


@st.cache_resource(show_spinner=False)
def _welcome_image() -> Image.Image | None:
    if not WELCOME_PATH.exists():
        return None
    image = Image.open(WELCOME_PATH)
    image.thumbnail((440, 440))
    return image


# ---------------------------------------------------------------- callbacks
def go(screen: str) -> None:
    st.session_state.screen = screen


def go_home() -> None:
    """Home / Next item: clear image, selection and result."""
    st.session_state.update(screen="welcome", image=None, selected_type=None, result=None,
                            staff_called=False)
    bump_nonce()


def scan_again() -> None:
    """Keep selected_type and failed_scans; ask for a fresh photo."""
    st.session_state.update(screen="welcome", image=None, result=None)
    bump_nonce()


def use_demo(demo_image) -> None:
    st.session_state.image = demo_image()
    st.session_state.photo_error = None
    st.session_state.screen = "select"


def on_photo(widget_key: str) -> None:
    """Camera / uploader on_change: store the photo only when a file actually arrived."""
    file = st.session_state.get(widget_key)
    if file is None:
        return
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(file.getvalue()))).convert("RGB")
    except (UnidentifiedImageError, OSError):
        st.session_state.photo_error = "That file is not a photo we can read. Please try another."
        return
    st.session_state.image = image
    st.session_state.photo_error = None
    st.session_state.screen = "select"
    bump_nonce()


def call_staff() -> None:
    st.session_state.staff_called = True


# ---------------------------------------------------------------- pieces
def readouts(screen: str, result: dict | None, prices: dict[str, float]) -> None:
    weight = 0.0 if screen in ("welcome", "camera", "upload") else float(st.session_state.weight_kg)
    selected = st.session_state.selected_type
    unit = prices.get(selected, 0.0) if selected else 0.0
    total = result["price"]["total"] if screen in ("result", "printed") and is_priced(result) else 0.0
    cells = [("TARE (kg)", "0.000"), ("NET WEIGHT (kg)", f"{weight:.3f}"),
             ("UNIT PRICE ($/kg)", f"{unit:.2f}"), ("TOTAL ($)", f"{total:.2f}")]
    html = "".join(f'<div class="readout"><span class="rl">{escape(k).replace("$", D)}</span>'
                   f'<span class="rv">{v}</span></div>' for k, v in cells)
    st.markdown(f'<div class="readouts">{html}</div>', unsafe_allow_html=True)


def banner(screen: str, result: dict | None) -> None:
    text, variant = banner_for(screen, result)
    st.markdown(f'<div class="banner {variant}" role="status">{escape(text)}</div>',
                unsafe_allow_html=True)


def footer() -> None:
    with st.container(key="scale_foot"):
        left, mid, right = st.columns(3, vertical_alignment="center")
        with left:
            st.button("Home", key="foot_home", on_click=go_home)
        with mid:
            st.markdown('<div class="scale-foot-mid">Prices per kg</div>', unsafe_allow_html=True)
        with right:
            with st.container(horizontal=True, horizontal_alignment="right"):
                st.button("Staff called" if st.session_state.staff_called else "Call staff",
                          key="foot_staff", on_click=call_staff)


# ---------------------------------------------------------------- screens
def welcome(demo_image) -> None:
    image = _welcome_image()
    if image is not None:
        with st.container(key="welcome_img"):
            st.image(image, width="content")
    with st.container(key="welcome_btns", horizontal=True):
        st.button("Use camera", key="w_camera", on_click=go, args=("camera",), width="stretch")
        st.button("Upload photo", key="w_upload", on_click=go, args=("upload",), width="stretch")
        st.button("Demo photo", key="w_demo", on_click=use_demo, args=(demo_image,), width="stretch")


def _photo_error() -> None:
    if st.session_state.get("photo_error"):
        st.error(st.session_state.photo_error)


def camera() -> None:
    key = f"cam_{st.session_state.input_nonce}"
    st.camera_input("Take a photo", key=key, label_visibility="collapsed", on_change=on_photo, args=(key,))
    st.markdown('<p class="small-note">Your browser will ask for camera permission. '
                'The camera only works on localhost or https.</p>', unsafe_allow_html=True)
    _photo_error()
    with st.container(horizontal=True, horizontal_alignment="center"):
        st.button("Back", key="cam_back", on_click=go, args=("welcome",))


def upload() -> None:
    key = f"up_{st.session_state.input_nonce}"
    st.file_uploader("Choose a photo (PNG or JPG)", type=["png", "jpg", "jpeg"], key=key,
                     on_change=on_photo, args=(key,))
    _photo_error()
    with st.container(horizontal=True, horizontal_alignment="center"):
        st.button("Back", key="up_back", on_click=go, args=("welcome",))


def select(scan, prices: dict[str, float]) -> None:
    clicked = None
    for row in (TYPES[:3], TYPES[3:]):
        for column, produce in zip(st.columns(3), row):
            price = prices.get(produce, 0.0)
            name = label_of(produce)
            with column, st.container(key=f"tile_{produce}"):
                st.markdown(f'<div class="tile">{produce_svg(produce)}<span class="tile-name">{name}</span>'
                            f'<span class="tile-price">{D}{price:.2f} / kg</span></div>',
                            unsafe_allow_html=True)
                if st.button(f"{name}, ${price:.2f} per kg", key=f"pick_{produce}"):
                    clicked = produce
    st.markdown('<p class="not-here">Your item isn\'t here? Only these six types are supported in this demo.</p>',
                unsafe_allow_html=True)
    if clicked:
        if st.session_state.selected_type != clicked:
            st.session_state.failed_scans = 0
        st.session_state.selected_type = clicked
        with st.spinner(SPINNER_TEXT):
            scan()
        st.rerun()


@st.dialog("Why this price?", width="large")
def why_dialog(result: dict) -> None:
    """Pop-up with the blemish card and forecast row; never grows the page."""
    st.markdown(_why_panel(result), unsafe_allow_html=True)


def _why_panel(result: dict) -> str:
    image = st.session_state.image
    item = result["items"][0]
    if image is None:
        return ""
    blem = views.data_uri(views.blemish_photo(image, result["items"]))
    frames = "".join(f'<div class="fc"><img src="{views.data_uri(img, 200)}" alt="{escape(lbl)}">'
                     f'<span>{escape(lbl)}</span></div>' for lbl, _, img in views.forecast_frames(image, item))
    return (f'<div class="why-grid"><div class="why-card"><span class="why-title">Blemishes found '
            f'({item["blemish_pct"]:.0f}% of the item)</span>'
            f'<div class="why-photo" role="img" aria-label="Your photo with any blemish area marked in red" '
            f'style="background-image:url({blem})"></div></div>'
            f'<div class="why-card"><span class="why-title">How it may look in a few days</span>'
            f'<div class="fc-grid">{frames}</div>'
            f'<span class="illus">Illustration (AI-generated), not used for the price</span></div></div>')


def result_priced(result: dict) -> None:
    price = result["price"]
    tier = price.get("tier") or "A"
    discount = price.get("discount") or 0.0
    weight, unit, total = float(price["weight_kg"]), float(price["price_per_kg"]), float(price["total"])
    fresh = result.get("bag_freshness", 0.0)
    days = result.get("fields", {}).get("days", "?")
    count = len(result.get("items", []))
    if tier == "B":
        msg, colour = f"Freshness discount 20%, best within {days:g} days", "#7A3E00"
    elif tier == "C":
        msg, colour = "Freshness discount 50%, eat today or tomorrow", "#7A3E00"
    else:
        msg, colour = f"Full price · best within {days:g} days", "#1F6F47"
    name = label_of(st.session_state.selected_type or result.get("fields", {}).get("detected")).upper()
    with st.container(key="ticket"):
        left, right = st.columns([1.5, 1], vertical_alignment="center")
        with left:
            st.markdown(
                f'<div class="t-name">{escape(name)}</div><div class="t-row">'
                f'<span class="pill" style="background:{TIER_BG.get(tier, "#1F6F47")}">Tier {tier} · {fresh:.0%} fresh</span>'
                f'<span class="t-count">{count} item{"s" if count != 1 else ""} found</span></div>'
                f'<div class="t-msg" style="color:{colour}">{escape(msg)}</div>',
                unsafe_allow_html=True)
            if st.button("Why this price?", key="why_toggle", type="tertiary"):
                why_dialog(result)
        with right:
            strike = f'<span class="t-strike">{D}{weight * unit:.2f}</span>' if discount else ""
            st.markdown(f'<div class="t-right">{strike}<span class="t-total">{D}{total:.2f}</span>'
                        f'<span class="t-calc">{weight:.3f} kg × {D}{unit * (1 - discount):.2f}/kg</span></div>',
                        unsafe_allow_html=True)
    with st.container(key="ticket_actions", horizontal=True, horizontal_alignment="distribute",
                      vertical_alignment="center"):
        st.button("Back", key="res_back", on_click=go, args=("select",))
        st.button("PRINT", key="print_btn", on_click=go, args=("printed",))


def result_stopped(result: dict) -> None:
    rule = result.get("rule_id")
    detail = STOP_DETAIL.get(rule, FALLBACK_DETAIL).format(selected=label_of(st.session_state.selected_type))
    colour = "#B23A12" if rule == 5 else "#9A5300"
    staff = result.get("staff_alert") or st.session_state.staff_called
    pill = '<span class="staff-pill">A staff member is on the way to help</span>' if staff else ""
    st.markdown(f'<div class="stop-box"><div class="stop-icon" style="background:{colour}">'
                f'{icon_svg("alert", "#FFFFFF", 48)}</div><p class="stop-detail">{escape(detail)}</p>{pill}</div>',
                unsafe_allow_html=True)
    with st.container(horizontal=True, horizontal_alignment="center"):
        st.button("Change item", key="change_item", on_click=go, args=("select",))
        st.button("Scan again", key="scan_again", on_click=scan_again)


def printed(result: dict) -> None:
    price = result["price"]
    discount = price.get("discount") or 0.0
    tier = price.get("tier") or "A"
    name = label_of(st.session_state.selected_type or result.get("fields", {}).get("detected"))
    disc_row = (f'<div class="row disc"><span>Freshness discount</span><span>−{discount:.0%}</span></div>'
                if discount else "")
    st.markdown(
        f'<div class="label-card" aria-label="Printed price label">'
        f'<div class="row"><strong class="sg" style="font-size:18px">FreshMart</strong>'
        f'<span style="color:#3D5A4B">{datetime.now():%d/%m/%y}</span></div>'
        f'<span style="font-weight:700;font-size:18px">{escape(name)}</span>'
        f'<div class="row"><span>Net weight</span><span>{float(price["weight_kg"]):.3f} kg</span></div>'
        f'<div class="row"><span>Price per kg</span><span>{D}{float(price["price_per_kg"]):.2f}</span></div>'
        f'{disc_row}'
        f'<div class="row"><span>Freshness</span><span>{result.get("bag_freshness", 0):.0%} · tier {tier}</span></div>'
        f'<div class="row tot"><strong style="font-size:18px">Total</strong>'
        f'<strong class="mono" style="font-size:22px">{D}{float(price["total"]):.2f}</strong></div>'
        f'{BARCODE_SVG}</div>',
        unsafe_allow_html=True)
    st.markdown('<p class="label-thanks">Please stick the label on your bag.</p>', unsafe_allow_html=True)
    with st.container(horizontal=True, horizontal_alignment="center"):
        st.button("Next item", key="next_item", on_click=go_home)


# ---------------------------------------------------------------- entry
def render(scan, demo_image, prices: dict[str, float]) -> None:
    screen = st.session_state.screen
    result = st.session_state.result
    # Screens that need data fall back safely instead of crashing.
    if screen in ("result", "printed") and not result:
        screen = st.session_state.screen = "welcome"
    if screen == "printed" and not is_priced(result):
        screen = st.session_state.screen = "result"
    if screen == "select" and st.session_state.image is None:
        screen = st.session_state.screen = "welcome"

    with st.container(key="scale"):
        with st.container(key="screen"):
            readouts(screen, result, prices)
            banner(screen, result)
            body = "stop" if screen == "result" and not is_priced(result) else screen
            with st.container(key=f"body_{body}"):
                if screen == "welcome":
                    welcome(demo_image)
                elif screen == "camera":
                    camera()
                elif screen == "upload":
                    upload()
                elif screen == "select":
                    select(scan, prices)
                elif screen == "result":
                    result_priced(result) if is_priced(result) else result_stopped(result)
                elif screen == "printed":
                    printed(result)
            footer()
