"""Mode 1: what the models saw (developer / marker view)."""

from __future__ import annotations

from html import escape

import altair as alt
import pandas as pd
import streamlit as st

import pipeline
import views
from components import label_of
from mode2 import banner_for, is_priced

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
RULE_NAMES = {
    1: "Not produce, or nothing found",
    2: "Freshness confidence below τ_conf",
    3: "Two or more types",
    4: "Another type than selected",
    5: "Unsellable with confidence ≥ τ_rotten",
    6: "Unsellable but unsure",
    7: "Price from bag freshness",
}
D = "&#36;"


def _top_row() -> None:
    """Heading, stand-in note and Developer box in one compact row (wraps when narrow)."""
    with st.container(key="mv_top", horizontal=True, vertical_alignment="center"):
        st.markdown(f'<div class="mv-head"><h1 class="mv-title">What the models saw</h1>'
                    f'<span class="mv-sub">Last scan · selected type: '
                    f'{escape(label_of(st.session_state.selected_type))}</span></div>', unsafe_allow_html=True)
        result = st.session_state.result
        if result is not None and result.get("simulated"):  # only a forced rule uses the stand-in
            st.markdown('<div class="standin" role="note">Simulated result (developer control): '
                        'not from the models.</div>', unsafe_allow_html=True)
        with st.container(key="devbox", horizontal=True, vertical_alignment="bottom"):
            st.markdown('<span class="dev-tag">DEVELOPER</span>', unsafe_allow_html=True)
            st.selectbox("Simulate outcome", list(SIM_OPTIONS), format_func=SIM_OPTIONS.get,
                         key="simulate_rule")
            st.number_input("Simulated weight (kg)", 0.05, 5.0, step=0.05, key="weight_kg")


def _decision_card(result: dict) -> str:
    rule = result["rule_id"]
    text, _ = banner_for("result", result)
    formula = ""
    if is_priced(result):
        p = result["price"]
        formula = (f'<span class="mono" style="font-size:15px">{p["weight_kg"]:.3f} kg × {D}{p["price_per_kg"]:.2f}'
                   f' × (1 − {(p["discount"] or 0):.0%}) = {D}{p["total"]:.2f}</span>')
    alert = (('<span class="chip" style="background:#FFE9E4;color:#8A1C0E">Staff alert raised</span>')
             if result.get("staff_alert") else '<span class="chip">No staff alert</span>')
    return (f'<div class="card"><span class="card-tag">DECISION</span>'
            f'<span class="dec-rule">Rule {rule} · {escape(RULE_NAMES.get(rule, "Unknown"))}</span>'
            f'<span style="font-size:15px">“{escape(text)}”</span>{formula}'
            f'<div style="display:flex;flex-wrap:wrap;gap:8px"><span class="chip">Energy score '
            f'{result.get("energy", 0):.2f}</span>{alert}</div></div>')


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


def _items_table(result: dict) -> pd.DataFrame:
    return pd.DataFrame([{
        "#": f"#{i}",
        "Detector type": label_of(it.get("produce")),
        "Box conf.": f'{it["det_conf"]:.0%}',
        "Freshness": f'{it["freshness"]:.0%}',
        "Tier": it.get("tier") or "—",
        "Fresh. conf.": f'{it["fresh_conf"]:.0%}',
        "Days left": it.get("days_left"),
        "Blemish %": f'{it["blemish_pct"]:.1f}',
        "Seg. conf.": f'{it["seg_conf"]:.0%}',
    } for i, it in enumerate(result.get("items", []), start=1)])


def render(set_view) -> None:
    with st.container(key="modelpage"):
        _top_row()
        result = st.session_state.result
        image = st.session_state.image
        if result is None or image is None:
            with st.container(key="mv_empty"):
                st.info("No scan yet. Run one in Shopper mode, then come back here.")
                st.button("Go to Shopper", key="go_shopper", on_click=set_view, args=("Shopper",))
            return

        if result["items"] and "forecasts" not in result["items"][0]:
            with st.spinner("Running the forecast model…"):
                pipeline.ensure_forecast(result, image)  # on request only; stored on the result
        with st.container(key="mv_cols"):
            left, right = st.columns([1.6, 1])
            with left, st.container(key="mv_left"):
                with st.container(horizontal=True, key="mv_toggles"):
                    boxes = st.toggle("Boxes (detector)", key="ov_boxes")
                    blemish = st.toggle("Blemish mask (U-Net)", key="ov_blemish")
                    cam = st.toggle("Occlusion map (freshness)", key="ov_cam")
                item_ix = int(st.session_state.get("mv_item", 0))  # item #1 unless another is selected
                if cam and 0 <= item_ix < len(result["items"]) and "gradcam" not in result["items"][item_ix]:
                    with st.spinner("Computing the occlusion map…"):
                        pipeline.ensure_occlusion(result, image, item_ix)
                composed = views.data_uri(views.compose(image, result["items"], boxes, blemish, cam), 1280)
                note = ('<span class="mv-photo-note">Grad-CAM overlay is a placeholder</span>'
                        if cam and result.get("simulated") else "")
                st.markdown(f'<div class="mv-photo-box"><img class="mv-photo" src="{composed}" alt="Scan with '
                            f'detector boxes, blemish areas and attention overlay">{note}</div>',
                            unsafe_allow_html=True)
                if result["items"]:
                    st.markdown(_forecast_strip(image, result["items"][0]), unsafe_allow_html=True)
            with right, st.container(key="mv_right"):
                decision, items, curve_tab, log = st.tabs(["Decision", "Items", "Curve", "Log"])
                with decision:
                    st.markdown(_decision_card(result) + _trace_card(result["rule_id"])
                                + _thresholds_card(result.get("thresholds", {}), bool(result.get("simulated"))), unsafe_allow_html=True)
                with items:
                    st.markdown('<span class="card-tag">ITEMS IN THIS SCAN</span>', unsafe_allow_html=True)
                    st.dataframe(_items_table(result), hide_index=True)
                with curve_tab:
                    st.markdown('<span class="card-tag">FRESHNESS CURVE (ITEM #1)</span>', unsafe_allow_html=True)
                    first = result["items"][0] if result["items"] else {}
                    curve = first.get("curve", [])
                    points = pd.DataFrame({"day": _curve_days(first), "freshness": curve})
                    chart = alt.Chart(points).mark_line(point=True, color="#1F6F47").encode(
                        x=alt.X("day:Q", title="Days from today"),
                        y=alt.Y("freshness:Q", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
                    ).properties(height=240)
                    st.altair_chart(chart, use_container_width=True)  # 1.50 altair_chart has no width=
                with log:
                    st.markdown(f'<span class="card-tag">SESSION LOG ({len(st.session_state.scan_logs)})</span>',
                                unsafe_allow_html=True)
                    if st.session_state.scan_logs:
                        st.dataframe(pd.DataFrame(st.session_state.scan_logs), hide_index=True)
                    else:
                        st.caption("No scans yet.")
