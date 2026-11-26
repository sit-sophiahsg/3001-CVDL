"""Mode 1: what the models saw (developer / marker view)."""

from __future__ import annotations

from html import escape

import altair as alt
import pandas as pd
import streamlit as st

import models
import pipeline
import views
from components import label_of
from mode2 import (FALLBACK_DETAIL, PRICED_BANNER, RULE_NAMES, TIER_BG, demo_note, demo_price, demo_rule,
                   fresh_card, is_priced)

SIM_OPTIONS = {
    "auto": "Auto (models decide)",
    "1": "Rule 1 · not recognised",
    "2": "Rule 2 · unsure, rescan",
    "3": "Rule 3 · mixed types",
    "4": "Rule 4 · check selection",
    "5": "Rule 5 · not for sale",
    "6": "Rule 6 · unsellable but unsure",
    "7": "Rule 7 · priced",
}
D = "&#36;"


def type_line(result: dict | None) -> str:
    """Model view: the scan's type comes from the detector, not the shopper's pick."""
    info = (result or {}).get("type_from_detector")
    if not info:
        return "No type yet"
    return f'Type from detector: {label_of(info["type"])} ({info["conf"]:.2f})'


def _top_row() -> None:
    """Heading, stand-in note and Developer box in one compact row (wraps when narrow)."""
    with st.container(key="mv_top", horizontal=True, vertical_alignment="center"):
        result = st.session_state.mv_result  # Model view's own (frozen) capture
        if result is not None:
            info = f"Captured scan · {type_line(result)}"
        elif st.session_state.mv_image is not None:
            info = "Still frame captured · No type yet"
        else:
            info = "Waiting for a still scene · No type yet"
        st.markdown(f'<div class="mv-head"><h1 class="mv-title">What the models see, live</h1>'
                    f'<span class="mv-sub">{escape(info)}</span></div>', unsafe_allow_html=True)
        if result is not None and result.get("simulated"):  # only a forced rule uses the stand-in
            st.markdown('<div class="standin" role="note">Simulated result (developer control): '
                        'not from the models.</div>', unsafe_allow_html=True)
        with st.container(key="devbox", horizontal=True, vertical_alignment="bottom"):
            st.markdown('<span class="dev-tag">DEVELOPER</span>', unsafe_allow_html=True)
            st.selectbox("Simulate outcome", list(SIM_OPTIONS), format_func=SIM_OPTIONS.get,
                         key="simulate_rule")


def _decision_card(result: dict, bypassed: bool = False) -> str:
    """The real decision. ``bypassed`` (demo mode): a smaller, muted card under the demo price."""
    rule = result["rule_id"]
    text = PRICED_BANNER if is_priced(result) else (result.get("message") or FALLBACK_DETAIL)
    formula = ""
    if is_priced(result):
        p = result["price"]
        formula = (f'<span class="mono" style="font-size:15px">{p["weight_kg"]:.3f} kg × {D}{p["price_per_kg"]:.2f}'
                   f' × (1 − {(p["discount"] or 0):.0%}) = {D}{p["total"]:.2f}</span>')
    alert = (('<span class="chip" style="background:#FFE9E4;color:#8A1C0E">Staff alert raised</span>')
             if result.get("staff_alert") else '<span class="chip">No staff alert</span>')
    chips = (f'<div style="display:flex;flex-wrap:wrap;gap:8px"><span class="chip">Energy score '
             f'{result.get("energy", 0):.2f}</span>{alert}</div>')
    if bypassed:  # demo mode: decide's real result, muted, under the demo card
        return (f'<div class="card real-muted"><span class="card-tag">REAL-LIFE RULE (BYPASSED IN DEMO)</span>'
                f'<span class="dec-rule-sm">Real-life rule (bypassed in demo): Rule {rule} · '
                f'{escape(RULE_NAMES.get(rule, "Unknown"))}</span>'
                f'<span style="font-size:14px">“{escape(text)}”</span>{chips}'
                f'<span class="demo-grey">{escape(demo_note(result))}</span></div>')
    return (f'<div class="card"><span class="card-tag">DECISION</span>'
            f'<span class="dec-rule">Rule {rule} · {escape(RULE_NAMES.get(rule, "Unknown"))}</span>'
            f'<span style="font-size:15px">“{escape(text)}”</span>{formula}{chips}</div>')


def _demo_card(result: dict, demo: dict) -> str:
    """DEMO MODE: the camera-tuned price, the main card (the real decision follows, muted)."""
    if demo["total"] is None:
        price, formula = "Not for sale", ""
    else:
        price = f'{D}{demo["total"]:.2f}'
        formula = (f'<span class="mono" style="font-size:15px">{demo["weight_kg"]:.3f} kg × {D}{demo["price_per_kg"]:.2f}'
                   f' × (1 − {demo["discount"]:.0%}) = {D}{demo["total"]:.2f}</span>')
    days = "" if demo.get("days") is None else f' · {demo["days"]:.0f} days left'
    return (f'<div class="card demo-card" role="note"><span class="card-tag"><span class="demo-tag">DEMO</span> '
            f'DEMO PRICE · {escape(label_of(result.get("selected_type")).upper())} '
            f'<span class="fr-tag hl">camera-tuned (demo)</span></span>'
            f'<span class="demo-price">{price} <span class="demo-tier" style="background:{TIER_BG.get(demo["tier"], "#1F6F47")}">Tier {escape(demo["tier"])}</span></span>'
            f'<span style="font-size:15px">Camera-tuned bag freshness <b>{demo["freshness"]:.0%}</b>{days}</span>{formula}</div>')


def _demo_rule_card(outcome: dict) -> str:
    """DEMO MODE: the detector rule (3 or 4) the demo applies instead of a price."""
    rule = outcome["rule_id"]
    return (f'<div class="card demo-card" role="note"><span class="card-tag"><span class="demo-tag">DEMO</span> '
            f'DETECTOR RULE APPLIED</span>'
            f'<span class="dec-rule">Rule {rule} · {escape(RULE_NAMES.get(rule, "Unknown"))}</span>'
            f'<span style="font-size:15px">“{escape(outcome.get("message") or FALLBACK_DETAIL)}”</span></div>')


def _decision_tab(result: dict) -> str:
    """Decision tab, top to bottom. Camera-tuned values lead, the actual model (ResNet-50) follows,
    except under a real rule-7 price, which uses ResNet-50 (camera-tuned shown below it, display only)."""
    demo, rule_out = demo_price(result), demo_rule(result)
    if demo is not None:      # demo price: camera-tuned price, ResNet-50 values, the real rule (muted)
        top = _demo_card(result, demo) + fresh_card(result, primary=False) + _decision_card(result, bypassed=True)
    elif rule_out is not None:  # demo with a detector rule: that rule, both models, the real rule (muted)
        top = _demo_rule_card(rule_out) + fresh_card(result) + _decision_card(result, bypassed=True)
    elif is_priced(result):   # real price (ResNet-50), camera-tuned below, display only
        top = _decision_card(result) + fresh_card(result)
    else:                     # no demo: camera-tuned values, ResNet-50 values, the real decision
        top = fresh_card(result) + _decision_card(result)
    return top


def _trace_card(fired: int) -> str:
    rows = []
    for n, name in RULE_NAMES.items():
        if n < fired:
            bg, fg, status, sc = "#EEF1EF", "#3D5A4B", "passed", "#3D5A4B"
        elif n == fired:
            bg, fg, status, sc = "#1F6F47", "#FFFFFF", "fired", "#1F6F47"
        else:
            bg, fg, status, sc = "#F6F8F7", "#9DB0A6", "not reached", "#8AA095"
        rows.append(f'<div class="trace-row"><span class="trace-n" style="background:{bg};color:{fg}">{n}</span>'
                    f'<span class="trace-t">{escape(name)}</span>'
                    f'<span class="trace-s" style="color:{sc}">{status}</span></div>')
    return f'<div class="card" style="gap:6px"><span class="card-tag">RULES, CHECKED IN ORDER</span>{"".join(rows)}</div>'


def _thresholds_card(thresholds: dict, simulated: bool = True) -> str:
    label = "STAND-IN VALUES" if simulated else "CALIBRATED ON VALIDATION"
    cells = "".join(f'<span>{escape(str(k))}</span><span class="mono">{v:.2f}</span>'
                    if isinstance(v, (int, float)) else f'<span>{escape(str(k))}</span><span class="mono">{escape(str(v))}</span>'
                    for k, v in thresholds.items())
    return (f'<div class="card" style="gap:6px"><span class="card-tag">THRESHOLDS ({label})</span>'
            f'<div class="thr">{cells}</div></div>')


def _forecast_strip(image, item: dict) -> str:
    graded = dict(zip(_curve_days(item), item.get("curve", [])))
    cells = []
    for label, day, frame in views.forecast_frames(image, item):
        grade = f"graded {graded[day]:.0%}" if day in graded else ""
        cells.append(f'<div><img src="{views.data_uri(frame, 220)}" alt="{escape(label)}">'
                     f'<b>{escape(label)}</b><span>{grade}</span></div>')
    return (f'<span class="why-title">Forecast (item #1)</span><div class="mv-fc">{"".join(cells)}</div>'
            f'<span class="illus">Illustration (AI-generated), not used for the price</span>')


def _curve_days(item: dict) -> list[int]:
    """Days for each curve point: 0, 1, 3, 7 for the models; 0..7 for the stand-in."""
    return list(item.get("curve_days") or range(len(item.get("curve", []))))


DISPLAY_COL = "Camera-tuned %"
DISPLAY_HELP = ("Fine-tuned on our own photos. Shown for comparison only; rejected for pricing because it "
                "sold rotten produce 3× as often (notebook 9.11).")


R50_COL = "Actual model (ResNet-50)"


def _items_table(result: dict) -> pd.DataFrame:
    """One row per item. Camera-tuned columns first, then "Actual model (ResNet-50)"; a real rule-7
    price uses ResNet-50, so then its columns come first and camera-tuned is display only."""
    items = result.get("items", [])
    display = any(it.get("freshness_display") is not None for it in items)  # never decides
    cam_name = DISPLAY_COL + (" (display only)" if is_priced(result) else " (demo)")
    rows = []
    for i, it in enumerate(items, start=1):
        cam = {cam_name: (f'{it["freshness_display"]:.0%} · {it.get("tier_display") or "—"}'
                          + (f' · {it["days_display"]:.0f} d' if it.get("days_display") is not None else "")
                          if it.get("freshness_display") is not None else "—")} if display else {}
        r50 = {R50_COL: f'{it["freshness"]:.0%} · {it.get("tier") or "—"} · {float(it.get("days_left") or 0):.0f} d',
               "Fresh. conf.": f'{it["fresh_conf"]:.0%}'}
        head = {"#": f"#{i}", "Detector type": label_of(it.get("produce")), "Box conf.": f'{it["det_conf"]:.0%}'}
        tail = {"Blemish %": f'{it["blemish_pct"]:.1f}', "Seg. conf.": f'{it["seg_conf"]:.0%}'}
        rows.append({**head, **(r50 if is_priced(result) else cam), **(cam if is_priced(result) else r50), **tail})
    return pd.DataFrame(rows)


def _toggles() -> None:
    with st.container(horizontal=True, key="mv_toggles"):
        st.toggle("Boxes + type (detector)", key="ov_boxes")
        st.toggle("Freshness % (ResNet-50)", key="ov_fresh")
        st.toggle("Blemish mask (U-Net)", key="ov_blemish")
        if models.has_display():
            st.toggle("Camera-tuned % (display only)", key="ov_disp",
                      help="Not used for the price. " + DISPLAY_HELP)
        st.toggle("Occlusion map (item #1)", key="ov_cam")


def render(live_view) -> None:
    with st.container(key="modelpage"):
        _top_row()
        result = st.session_state.mv_result  # the frozen capture (kept until "Reset scan")
        image = st.session_state.mv_image
        # spinners go in fixed slots, so the live view keeps its place in the page (and is not remounted)
        slot = st.empty()
        if result is not None and image is not None and result["items"] and "forecasts" not in result["items"][0]:
            with slot, st.spinner("Running the forecast model…"):
                pipeline.ensure_forecast(result, image)  # once per scan, stored on the result
            slot.empty()
        with st.container(key="mv_cols"):
            left, right = st.columns([1.7, 1])
            # the toggles are drawn in the right panel; their values are already in Session State here
            cam = bool(st.session_state.ov_cam)
            with left, st.container(key="mv_left"):
                occ_slot = st.empty()
                if st.session_state.ov_disp and models.has_display():
                    pipeline.ensure_display(result, image)  # scan made without it (e.g. in Shopper); once
                if cam and result is not None and image is not None and result["items"] \
                        and "gradcam" not in result["items"][0]:
                    with occ_slot, st.spinner("Computing the occlusion map…"):
                        pipeline.ensure_occlusion(result, image, 0)  # item #1, on demand, cached on the result
                    occ_slot.empty()
                live_view("model")
                st.markdown('<span class="mv-foot">Live: boxes and types update every frame (detector in the '
                            'browser). Once the scene is still the frame is captured, graded on the server and held '
                            'with its overlays until Reset scan.</span>', unsafe_allow_html=True)
            with right, st.container(key="mv_right"):
                _toggles()
                decision, items, curve_tab, log = st.tabs(["Decision", "Items", "Curve", "Log"])
                with decision:
                    if result is None:
                        st.markdown('<p class="mv-none">No scan yet. The scale scans by itself once the items '
                                    'are still.</p>', unsafe_allow_html=True)
                    else:
                        st.markdown(_decision_tab(result) + _trace_card(result["rule_id"])
                                    + _thresholds_card(result.get("thresholds", {}), bool(result.get("simulated"))),
                                    unsafe_allow_html=True)
                with items:
                    st.markdown('<span class="card-tag">ITEMS IN THIS SCAN</span>', unsafe_allow_html=True)
                    if result is not None:
                        card = fresh_card(result)  # bag level: camera-tuned first, ResNet-50 below
                        if card:
                            st.markdown(card, unsafe_allow_html=True)
                        st.dataframe(_items_table(result), hide_index=True)
                with curve_tab:
                    st.markdown('<span class="card-tag">FRESHNESS CURVE (ITEM #1)</span>', unsafe_allow_html=True)
                    first = result["items"][0] if result is not None and result["items"] else {}
                    if first.get("curve"):
                        points = pd.DataFrame({"day": _curve_days(first), "freshness": first["curve"]})
                        chart = alt.Chart(points).mark_line(point=True, color="#1F6F47").encode(
                            x=alt.X("day:Q", title="Days from today"),
                            y=alt.Y("freshness:Q", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
                        ).properties(height=240)
                        st.altair_chart(chart, use_container_width=True)  # 1.50 altair_chart has no width=
                        if image is not None:
                            st.markdown(_forecast_strip(image, first), unsafe_allow_html=True)
                    else:
                        st.caption("No curve yet.")
                with log:
                    st.markdown(f'<span class="card-tag">SESSION LOG ({len(st.session_state.scan_logs)})</span>',
                                unsafe_allow_html=True)
                    if st.session_state.scan_logs:
                        st.dataframe(pd.DataFrame(st.session_state.scan_logs), hide_index=True)
                    else:
                        st.caption("No scans yet.")
