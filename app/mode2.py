"""Mode 2: the shopper-facing scale kiosk."""

from __future__ import annotations

from datetime import datetime
from html import escape

import streamlit as st

import pipeline
import views
from backend import TYPES
from components import BARCODE_SVG, icon_svg, label_of, produce_svg

SCREENS = ("live", "result", "printed")

BANNERS = {
    "live": "Place your items on the scale",
    "select": "Select the item you are weighing",
    "printed": "Label printed. Thank you!",
}
PRICED_BANNER = "Please press PRINT"
SPINNER_TEXT = "Checking freshness…"
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
    if screen == "live" and needs_type():
        return BANNERS["select"], "ask"
    return BANNERS.get(screen, BANNERS["live"]), ""


def needs_type() -> bool:
    """A still frame is waiting and no type is selected yet."""
    return st.session_state.get("image") is not None and not st.session_state.get("selected_type")


# ---------------------------------------------------------------- callbacks
def go(screen: str) -> None:
    st.session_state.screen = screen


def clear_frame() -> None:
    """Forget the captured frame and its result (the scene changed, or a new scan is wanted)."""
    st.session_state.update(screen="live", image=None, frame=None, source=None, result=None)


def rearm() -> None:
    """Tell the live view to scan again once the scene is still."""
    st.session_state.rearm = st.session_state.get("rearm", 0) + 1


def go_home() -> None:
    """Home / Next item: clear frame, selection and result; the live view re-arms."""
    clear_frame()
    st.session_state.update(selected_type=None, staff_called=False)
    rearm()


def scan_again() -> None:
    """Keep selected_type and failed_scans; scan again once the scene is still."""
    clear_frame()
    rearm()


def change_item() -> None:
    """Back to the tiles; the frame is kept, so picking a type grades it straight away."""
    st.session_state.update(screen="live", result=None, selected_type=None)


def call_staff() -> None:
    st.session_state.staff_called = True


# ---------------------------------------------------------------- pieces
def readouts(screen: str, result: dict | None, prices: dict[str, float]) -> None:
    on_scale = st.session_state.get("image") is not None or screen in ("result", "printed")
    weight = float(st.session_state.weight_kg) if on_scale else 0.0
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
            st.markdown('<div class="scale-foot-mid">Prices per kg · the scale checks automatically when '
                        'items are still</div>', unsafe_allow_html=True)
        with right:
            with st.container(horizontal=True, horizontal_alignment="right"):
                st.button("Staff called" if st.session_state.staff_called else "Call staff",
                          key="foot_staff", on_click=call_staff)


# ---------------------------------------------------------------- side panel
def tiles(scan, prices: dict[str, float]) -> None:
    """Which item are you weighing? Picking grades the waiting frame, if there is one."""
    st.markdown('<span class="side-head">Which item are you weighing?</span>', unsafe_allow_html=True)
    clicked = None
    asking = needs_type()
    for row in (TYPES[0:2], TYPES[2:4], TYPES[4:6]):
        for column, produce in zip(st.columns(2), row):
            price = prices.get(produce, 0.0)
            name = label_of(produce)
            state = " on" if st.session_state.selected_type == produce else (" ask" if asking else "")
            with column, st.container(key=f"tile_{produce}"):
                st.markdown(f'<div class="tile{state}">{produce_svg(produce, 40)}<span class="tile-txt">'
                            f'<span class="tile-name">{name}</span>'
                            f'<span class="tile-price">{D}{price:.2f} / kg</span></span></div>',
                            unsafe_allow_html=True)
                if st.button(f"{name}, ${price:.2f} per kg", key=f"pick_{produce}"):
                    clicked = produce
    st.markdown('<p class="not-here">Pick before or after placing; the scale checks as soon as the items '
                'are still.</p>', unsafe_allow_html=True)
    if clicked:
        if st.session_state.selected_type != clicked:
            st.session_state.failed_scans = 0
        st.session_state.selected_type = clicked
        if st.session_state.image is not None:  # a still frame is waiting: grade it now
            with st.spinner(SPINNER_TEXT):
                scan()
        st.rerun()


@st.dialog("Why this price?", width="large")
def why_dialog(result: dict) -> None:
    """Pop-up with the blemish card and forecast row; never grows the page."""
    pipeline.ensure_forecast(result, st.session_state.image)  # forecast runs only when asked for
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
        with st.container(key="t_left"):
            st.markdown(
                f'<div class="t-name">{escape(name)}</div><div class="t-row">'
                f'<span class="pill" style="background:{TIER_BG.get(tier, "#1F6F47")}">Tier {tier} · {fresh:.0%} fresh</span>'
                f'<span class="t-count">{count} item{"s" if count != 1 else ""} found</span></div>'
                f'<div class="t-msg" style="color:{colour}">{escape(msg)}</div>',
                unsafe_allow_html=True)
            if st.button("Why this price?", key="why_toggle", type="tertiary"):
                why_dialog(result)
        with st.container(key="t_right"):
            strike = f'<span class="t-strike">{D}{weight * unit:.2f}</span>' if discount else ""
            st.markdown(f'<div class="t-right">{strike}<span class="t-total">{D}{total:.2f}</span>'
                        f'<span class="t-calc">{weight:.3f} kg × {D}{unit * (1 - discount):.2f}/kg</span></div>',
                        unsafe_allow_html=True)
    with st.container(key="ticket_actions", horizontal=True, horizontal_alignment="distribute",
                      vertical_alignment="center"):
        st.button("Change item", key="res_back", on_click=change_item)
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
        st.button("Change item", key="change_item", on_click=change_item)
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
def render(scan, prices: dict[str, float], live_view) -> None:
    """Readouts and prompt; the live view on the left and the side panel on the right."""
    screen = st.session_state.screen
    result = st.session_state.result
    # Screens that need data fall back safely instead of crashing.
    if screen in ("result", "printed") and not result:
        screen = st.session_state.screen = "live"
    if screen == "printed" and not is_priced(result):
        screen = st.session_state.screen = "result"

    with st.container(key="scale"):
        with st.container(key="screen"):
            readouts(screen, result, prices)
            banner(screen, result)
            with st.container(key="sbody"):
                left, right = st.columns([1.65, 1], gap="medium")
                with left, st.container(key="s_live"):
                    live_view("shopper")
                if screen == "printed":
                    side = "printed"
                elif screen == "result":
                    side = "priced" if is_priced(result) else "stop"
                else:
                    side = "tiles"
                with right, st.container(key=f"side_{side}"):
                    if side == "tiles":
                        tiles(scan, prices)
                    elif side == "priced":
                        result_priced(result)
                    elif side == "stop":
                        result_stopped(result)
                    else:
                        printed(result)
            footer()
