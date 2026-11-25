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


def _top_row(on_upload) -> None:
    """Heading, stand-in note and Developer box in one compact row (wraps when narrow)."""
    with st.container(key="mv_top", horizontal=True, vertical_alignment="center"):
        result = st.session_state.result
        if result is not None:
            source = "uploaded photo" if st.session_state.source == "upload" else "last auto-scan"
            info = f"{source.capitalize()} · selected type: {label_of(st.session_state.selected_type)}"
        elif st.session_state.image is not None:
            info = "Still frame captured · select the item in Shopper to grade it"
        else:
            info = "Waiting for a still scene"
        st.markdown(f'<div class="mv-head"><h1 class="mv-title">What the models see, live</h1>'
                    f'<span class="mv-sub">{escape(info)}</span></div>', unsafe_allow_html=True)
        if result is not None and result.get("simulated"):  # only a forced rule uses the stand-in
            st.markdown('<div class="standin" role="note">Simulated result (developer control): '
                        'not from the models.</div>', unsafe_allow_html=True)
        with st.container(key="devbox", horizontal=True, vertical_alignment="bottom"):
            st.markdown('<span class="dev-tag">DEVELOPER</span>', unsafe_allow_html=True)
            st.selectbox("Simulate outcome", list(SIM_OPTIONS), format_func=SIM_OPTIONS.get,
                         key="simulate_rule")
            st.number_input("Simulated weight (kg)", 0.05, 5.0, step=0.05, key="weight_kg")
            key = f"up_{st.session_state.input_nonce}"
            st.file_uploader("Upload photo (backup)", type=["png", "jpg", "jpeg"], key=key,
                             on_change=on_upload, args=(key,),
                             help="A backup if the camera fails: the photo goes through the same path as an auto-scan.")
    if st.session_state.get("photo_error"):
        st.error(st.session_state.photo_error)


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


DISPLAY_COL = "Camera-tuned %"
DISPLAY_HELP = ("Fine-tuned on our own photos. Shown for comparison only; rejected for pricing because it "
                "sold rotten produce 3× as often (notebook 9.11).")


def _items_table(result: dict) -> pd.DataFrame:
    items = result.get("items", [])
    display = any(it.get("freshness_display") is not None for it in items)  # display only, never decides
    return pd.DataFrame([{
        "#": f"#{i}",
        "Detector type": label_of(it.get("produce")),
        "Box conf.": f'{it["det_conf"]:.0%}',
        "Freshness": f'{it["freshness"]:.0%}',
        **({DISPLAY_COL: (f'{it["freshness_display"]:.0%} · {it.get("tier_display") or "—"}'
                          if it.get("freshness_display") is not None else "—")} if display else {}),
        "Tier": it.get("tier") or "—",
        "Fresh. conf.": f'{it["fresh_conf"]:.0%}',
        "Days left": it.get("days_left"),
        "Blemish %": f'{it["blemish_pct"]:.1f}',
        "Seg. conf.": f'{it["seg_conf"]:.0%}',
    } for i, it in enumerate(items, start=1)])


def render(live_view, on_upload) -> None:
    with st.container(key="modelpage"):
        _top_row(on_upload)
        result = st.session_state.result
        image = st.session_state.image
        # spinners go in fixed slots, so the live view keeps its place in the page (and is not remounted)
        slot = st.empty()
        if result is not None and image is not None and result["items"] and "forecasts" not in result["items"][0]:
            with slot, st.spinner("Running the forecast model…"):
                pipeline.ensure_forecast(result, image)  # once per scan, stored on the result
            slot.empty()
        with st.container(key="mv_cols"):
            left, right = st.columns([1.7, 1])
            with left, st.container(key="mv_left"):
                with st.container(horizontal=True, key="mv_toggles"):
                    st.toggle("Boxes + type (detector)", key="ov_boxes")
                    st.toggle("Freshness % (ResNet-50)", key="ov_fresh")
                    st.toggle("Blemish mask (U-Net)", key="ov_blemish")
                    if models.has_display():
                        st.toggle("Camera-tuned % (display only)", key="ov_disp",
                                  help="Not used for the price. " + DISPLAY_HELP)
                    cam = st.toggle("Occlusion map (item #1)", key="ov_cam")
                occ_slot = st.empty()
                if st.session_state.ov_disp and models.has_display():
                    pipeline.ensure_display(result, image)  # scan made without it (e.g. in Shopper); once
                if cam and result is not None and image is not None and result["items"] \
                        and "gradcam" not in result["items"][0]:
                    with occ_slot, st.spinner("Computing the occlusion map…"):
                        pipeline.ensure_occlusion(result, image, 0)  # item #1, on demand, cached on the result
                    occ_slot.empty()
                live_view("model")
                st.markdown('<span class="mv-foot">Boxes and types update every frame (detector in the browser). '
                            'Freshness and the blemish mask come from the last auto-scan, run on the server.</span>',
                            unsafe_allow_html=True)
            with right, st.container(key="mv_right"):
                decision, items, curve_tab, log = st.tabs(["Decision", "Items", "Curve", "Log"])
                with decision:
                    if result is None:
                        st.markdown('<p class="mv-none">No scan yet. The scale scans by itself once the items '
                                    'are still.</p>', unsafe_allow_html=True)
                    else:
                        st.markdown(_decision_card(result) + _trace_card(result["rule_id"])
                                    + _thresholds_card(result.get("thresholds", {}), bool(result.get("simulated"))),
                                    unsafe_allow_html=True)
                with items:
                    st.markdown('<span class="card-tag">ITEMS IN THIS SCAN</span>', unsafe_allow_html=True)
                    if result is not None:
                        st.dataframe(_items_table(result), hide_index=True,
                                     column_config={DISPLAY_COL: st.column_config.TextColumn(DISPLAY_COL,
                                                                                             help=DISPLAY_HELP)})
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
