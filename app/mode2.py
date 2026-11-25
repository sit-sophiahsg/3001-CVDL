"""Mode 2: the shopper-facing scale kiosk."""

from __future__ import annotations

from datetime import datetime
from html import escape

import streamlit as st

import numpy as np

import models
import pipeline
import views
from backend import TYPES
from components import BARCODE_SVG, WEIGHT_KG, icon_svg, label_of, produce_svg

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
DEMO_RULES = (1, 2, 6)  # stopped scans that get a demo price, if the detector is confident (>= tau_det)
RULE_NAMES = {
    1: "Not produce, or nothing found",
    2: "Freshness confidence below τ_conf",
    3: "Two or more types",
    4: "Another type than selected",
    5: "Unsellable with confidence ≥ τ_rotten",
    6: "Unsellable but unsure",
    7: "Price from bag freshness",
}
TIER_SHORT = {"A": "full price", "B": "20% off", "C": "50% off", "D": "not for sale"}
DETECTOR_RULE_NOTE = "Detector rule applied in demo (freshness rules bypassed)."


# ---------------------------------------------------------------- helpers
def is_priced(result: dict | None) -> bool:
    return bool(result) and result.get("rule_id") == 7 and result.get("price", {}).get("total") is not None


def banner_for(screen: str, result: dict | None) -> tuple[str, str]:
    """(text, css variant) for the prompt banner."""
    if screen == "result" and result:
        if is_priced(result):
            return PRICED_BANNER, ""
        demo = demo_price(result)
        if demo is not None:  # demo mode: banner as for a priced scan
            name = label_of(result.get("selected_type"))
            return f'{name} · Tier {demo["tier"]} · {TIER_SHORT.get(demo["tier"], "")}', ""
        rule = shown_rule(result)
        text = (demo_rule(result) or {}).get("message") or result.get("message") or FALLBACK_DETAIL
        return text, "stop" if rule == 5 else "warn"
    if screen == "live" and needs_type():
        return BANNERS["select"], "ask"
    return BANNERS.get(screen, BANNERS["live"]), ""


def wants_demo(result: dict | None) -> bool:
    """A real (not simulated) scan stopped by rule 1, 2 or 6 where at least one item has det_conf >= tau_det."""
    if not result or result.get("simulated") or result.get("rule_id") not in DEMO_RULES or not result.get("items"):
        return False
    tau_det = result.get("thresholds", {}).get("tau_det")
    return tau_det is not None and max(float(it.get("det_conf", 0.0)) for it in result["items"]) >= float(tau_det)


def demo_note(result: dict) -> str:
    """The grey note under a demo result (plain text, escape before use)."""
    if demo_rule(result) is not None:
        return DETECTOR_RULE_NOTE
    rule = result.get("rule_id")
    tau = float(result.get("thresholds", {}).get("tau_det", 0.8))
    return (f"Demo mode: real-life pricing rules bypassed (would stop at Rule {rule}: "
            f"{RULE_NAMES.get(rule, 'Unknown')}). Priced because the detector is confident it's produce "
            f"(≥ {tau:.2f}); freshness from the camera-tuned model, which was rejected for real pricing.")


def _area(items: list[dict]) -> np.ndarray:
    return np.array([max(1.0, (it["box"][2] - it["box"][0]) * (it["box"][3] - it["box"][1])) for it in items])


def _tier(f: float) -> str:
    try:
        rules = models.load_config().rules
    except Exception:  # noqa: BLE001
        return "?"
    return models.scale_pricing.TIERS[int(models.scale_pricing.tier_idx(f, rules))]  # calibrated tiers


def fresh_summary(result: dict | None) -> dict:
    """Bag-level (box-area-weighted) freshness from both models, for the panels.

    {"cam": {freshness, tier, days} or None (camera-tuned, display/demo only),
     "r50": {freshness, tier, days} or None (ResNet-50, r50_coral: the model the rules use)}.
    """
    items = (result or {}).get("items") or []
    if not items:
        return {"cam": None, "r50": None}
    w = _area(items)
    r50_f = float(np.average([it["freshness"] for it in items], weights=w))
    days = [it.get("days_left") for it in items]
    r50 = {"freshness": r50_f, "tier": _tier(r50_f),
           "days": float(np.average(days, weights=w)) if all(d is not None for d in days) else None}
    cam = None
    if all(it.get("freshness_display") is not None for it in items):
        cam_f = float(np.average([it["freshness_display"] for it in items], weights=w))
        cdays = [it.get("days_display") for it in items]
        cam = {"freshness": cam_f, "tier": _tier(cam_f),
               "days": float(np.average(cdays, weights=w)) if all(d is not None for d in cdays) else None}
    return {"cam": cam, "r50": r50}


def demo_outcome(result: dict | None) -> dict | None:
    """DEMO ONLY: what the demo shows for a real scan stopped by rule 1, 2 or 6 (``wants_demo``).

    The demo bypasses only the freshness rules (1, 2, 6). The detector rules still apply, checked here
    on the detections because decide() never reaches them once rule 1 or 2 fires:
      rule 3 if two or more types each have det_conf >= tau_det (both views);
      rule 4 (Shopper only) if a type other than the selected one has det_conf >= tau_det.
    Otherwise a price from the camera-tuned bag freshness with the calibrated tiers.
    Runs after pricing.decide and never feeds back into it. Cached on the result as "demo".
    {"kind": "rule", rule_id, message} or {"kind": "price", freshness, tier, days, discount (None for D),
    price_per_kg, weight_kg, total (None for D)}; None if no demo (or no camera-tuned values).
    """
    if not wants_demo(result):
        return None
    if "demo" in result:
        return result["demo"]
    try:
        cfg = models.load_config()
    except Exception:  # noqa: BLE001 - no bundle: no demo
        return None
    items, tau = result["items"], float(result["thresholds"]["tau_det"])
    messages = cfg.rules.get("messages", {})
    sure = [it for it in items if float(it["det_conf"]) >= tau]
    selected = result.get("selected_type")
    others = [it for it in sure if it["produce"] != selected]
    if len({it["produce"] for it in sure}) >= 2:
        out = {"kind": "rule", "rule_id": 3, "message": messages.get("r3")}
    elif others and result.get("for_view") != "model":
        det = max(others, key=lambda it: it["det_conf"])["produce"]
        out = {"kind": "rule", "rule_id": 4, "message": (messages.get("r4") or "").format(detected=det)}
    else:
        cam = fresh_summary(result)["cam"]
        if cam is None:  # camera-tuned model not available
            return None
        tier = cam["tier"]
        ppk = float(cfg.prices.get(selected, 0.0))  # the scan's type (Shopper pick or detector)
        disc = cfg.rules["tiers"][tier]["discount"]
        total = None if tier == "D" or disc is None else round(WEIGHT_KG * ppk * (1 - float(disc)) + 1e-9, 2)
        out = {"kind": "price", **cam, "discount": None if total is None else float(disc),
               "price_per_kg": ppk, "weight_kg": WEIGHT_KG, "total": total}
    result["demo"] = out
    return out


def demo_price(result: dict | None) -> dict | None:
    """The demo price, if the demo prices this scan (not a detector rule)."""
    out = demo_outcome(result)
    return out if out and out["kind"] == "price" else None


def demo_rule(result: dict | None) -> dict | None:
    """The detector rule (3 or 4) the demo applies instead of a price, if any."""
    out = demo_outcome(result)
    return out if out and out["kind"] == "rule" else None


def shown_rule(result: dict) -> int | None:
    """The rule the screen shows: the demo's detector rule if one applies, else decide's rule."""
    return (demo_rule(result) or {}).get("rule_id") or result.get("rule_id")


def shown_price(result: dict | None) -> dict | None:
    """What the shopper sees as the price: rule 7's real price (r50_coral), else the demo price
    (camera-tuned), else None. {tier, discount, weight_kg, price_per_kg, total (None = not for sale),
    freshness, days, demo}.
    """
    if is_priced(result):
        p = result["price"]
        return {"tier": p.get("tier") or "A", "discount": p.get("discount") or 0.0, "weight_kg": float(p["weight_kg"]),
                "price_per_kg": float(p["price_per_kg"]), "total": float(p["total"]),
                "freshness": result.get("bag_freshness", 0.0), "days": result.get("fields", {}).get("days"),
                "demo": False}
    demo = demo_price(result)
    if demo is None:
        return None
    return {**demo, "discount": demo["discount"] or 0.0, "demo": True}


def _fmt(vals: dict) -> str:
    days = f' · {vals["days"]:.0f} days left' if vals.get("days") is not None else ""
    return f'{vals["freshness"]:.0%} · tier {vals["tier"]}{days}'


def fresh_card(result: dict, primary: bool | None = None) -> str:
    """Both models' bag freshness for the right-hand panel (HTML).

    Camera-tuned on top, prominent, tagged "camera-tuned (demo)"; "Actual model (ResNet-50)" below, muted.
    A real rule-7 price: the price uses ResNet-50, so only the camera-tuned values are added here,
    muted and tagged "camera-tuned (display only)". ``primary=False`` leaves the prominent row out
    (when the panel already shows those values, e.g. the demo ticket).
    """
    vals = fresh_summary(result)
    cam, r50 = vals["cam"], vals["r50"]
    if r50 is None:
        return ""
    rows = []
    if is_priced(result):
        if cam is not None:
            rows.append(f'<div class="fr-sub"><span class="fr-h">Camera-tuned <span class="fr-tag">camera-tuned '
                        f'(display only)</span></span><span class="fr-v">{escape(_fmt(cam))}</span></div>')
    else:
        if cam is not None and primary is not False:
            days = "" if cam.get("days") is None else f'<span class="fr-v">{cam["days"]:.0f} days left</span>'
            rows.append(f'<div class="fr-main"><span class="fr-h"><span class="fr-tag hl">camera-tuned (demo)</span>'
                        f'</span><span class="fr-big">{cam["freshness"]:.0%} <span class="pill" style="background:'
                        f'{TIER_BG.get(cam["tier"], "#1F6F47")}">Tier {escape(cam["tier"])}</span></span>{days}</div>')
        rows.append(f'<div class="fr-sub"><span class="fr-h">Actual model (ResNet-50)</span>'
                    f'<span class="fr-v">{escape(_fmt(r50))}</span></div>')
    return f'<div class="fr-card">{"".join(rows)}</div>' if rows else ""


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
    weight = WEIGHT_KG if on_scale else 0.0
    selected = st.session_state.selected_type
    unit = prices.get(selected, 0.0) if selected else 0.0
    shown = shown_price(result) if screen in ("result", "printed") else None
    total_label, total_cls, total_text = f"TOTAL ({D})", "rv", "0.00"
    if shown is not None:
        total_text = "NOT FOR SALE" if shown["total"] is None else f'{shown["total"]:.2f}'
        if shown["total"] is None:
            total_cls = "rv nfs"
        if shown["demo"]:  # demo mode: the real decision stopped the scan
            total_label += ' <span class="demo-tag">DEMO</span>'
    cells = [(escape("NET WEIGHT (kg)"), "rv", f"{weight:.3f}"),
             (escape("UNIT PRICE ($/kg)").replace("$", D), "rv", f"{unit:.2f}"),
             (total_label, total_cls, total_text)]
    html = "".join(f'<div class="readout"><span class="rl">{k}</span>'
                   f'<span class="{c}">{v}</span></div>' for k, c, v in cells)
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
    """A priced scan: rule 7's real price, or (demo mode) the demo price with a note under it."""
    shown = shown_price(result)
    tier, discount = shown["tier"], shown["discount"]
    weight, unit, total = shown["weight_kg"], shown["price_per_kg"], shown["total"]
    fresh = shown["freshness"]  # demo: camera-tuned; real rule 7: ResNet-50 (matches the price)
    days = shown.get("days")
    days = float(days) if days is not None else float(result.get("fields", {}).get("days") or 0)
    count = len(result.get("items", []))
    if total is None:
        msg, colour = "Not for sale", "#8A1C0E"
    elif tier == "B":
        msg, colour = f"Freshness discount 20%, best within {max(1, int(days))} days", "#7A3E00"
    elif tier == "C":
        msg, colour = "Freshness discount 50%, eat today or tomorrow", "#7A3E00"
    else:
        msg, colour = f"Full price · best within {max(1, int(days))} days", "#1F6F47"
    name = label_of(st.session_state.selected_type or result.get("fields", {}).get("detected")).upper()
    with st.container(key="ticket"):
        with st.container(key="t_left"):
            st.markdown(
                f'<div class="t-name">{escape(name)}</div><div class="t-row">'
                f'<span class="pill" style="background:{TIER_BG.get(tier, "#1F6F47")}">Tier {tier} · {fresh:.0%} fresh</span>'
                + ('<span class="fr-tag hl">camera-tuned (demo)</span>' if shown["demo"] else "")
                + f'<span class="t-count">{count} item{"s" if count != 1 else ""} found</span></div>'
                f'<div class="t-msg" style="color:{colour}">{escape(msg)}</div>',
                unsafe_allow_html=True)
            if st.button("Why this price?", key="why_toggle", type="tertiary"):
                why_dialog(result)
        with st.container(key="t_right"):
            if total is None:
                st.markdown('<div class="t-right"><span class="t-total">Not for sale</span></div>',
                            unsafe_allow_html=True)
            else:
                strike = f'<span class="t-strike">{D}{weight * unit:.2f}</span>' if discount else ""
                st.markdown(f'<div class="t-right">{strike}<span class="t-total">{D}{total:.2f}</span>'
                            f'<span class="t-calc">{weight:.3f} kg × {D}{unit * (1 - discount):.2f}/kg</span></div>',
                            unsafe_allow_html=True)
    with st.container(key="ticket_actions", horizontal=True, horizontal_alignment="distribute",
                      vertical_alignment="center"):
        st.button("Change item", key="res_back", on_click=change_item)
        if total is not None:
            st.button("PRINT", key="print_btn", on_click=go, args=("printed",))
    # the other model's numbers, smaller: ResNet-50 under a demo price, camera-tuned under a real price
    card = fresh_card(result, primary=False)
    if card:
        st.markdown(card, unsafe_allow_html=True)
    if shown["demo"]:
        st.markdown(f'<p class="demo-grey" role="note">{escape(demo_note(result))}</p>', unsafe_allow_html=True)


def result_stopped(result: dict) -> None:
    rule = shown_rule(result)  # the demo's detector rule (3/4) if one applies, else decide's
    detail = STOP_DETAIL.get(rule, FALLBACK_DETAIL).format(selected=label_of(st.session_state.selected_type))
    colour = "#B23A12" if rule == 5 else "#9A5300"
    staff = result.get("staff_alert") or st.session_state.staff_called
    pill = '<span class="staff-pill">A staff member is on the way to help</span>' if staff else ""
    st.markdown(f'<div class="stop-box"><div class="stop-icon" style="background:{colour}">'
                f'{icon_svg("alert", "#FFFFFF", 48)}</div><p class="stop-detail">{escape(detail)}</p>{pill}</div>',
                unsafe_allow_html=True)
    card = fresh_card(result)  # camera-tuned on top, ResNet-50 below
    if card:
        st.markdown(card, unsafe_allow_html=True)
    if demo_rule(result) is not None:
        st.markdown(f'<p class="demo-grey" role="note">{escape(demo_note(result))}</p>', unsafe_allow_html=True)
    with st.container(horizontal=True, horizontal_alignment="center"):
        st.button("Change item", key="change_item", on_click=change_item)
        st.button("Scan again", key="scan_again", on_click=scan_again)


def printed(result: dict) -> None:
    price = shown_price(result)  # rule 7, or the demo price
    discount, tier = price["discount"], price["tier"]
    demo_row = ('<div class="row"><span class="demo-tag">DEMO</span><span>rules bypassed</span></div>'
                if price["demo"] else "")
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
        f'<div class="row"><span>Freshness</span><span>{price["freshness"]:.0%} · tier {tier}</span></div>'
        f'{demo_row}<div class="row tot"><strong style="font-size:18px">Total</strong>'
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
    shown = shown_price(result) if screen in ("result", "printed") else None
    if screen == "printed" and (shown is None or shown["total"] is None):
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
                    side = "priced" if shown is not None else "stop"  # rule 7, or a demo price
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
