from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from components import draw_boxes


def render(st_module, scan, read_input_image) -> None:
    if st.session_state.result is None:
        st.info("Run a scan in Mode 2 first. Mode 1 reuses the same scan and never re-runs analyse when switching views.")
        if st.button("Open Mode 2"):
            st.session_state.mode = "Mode 2 · Shopper"
            st.rerun()
        return
    result = st.session_state.result
    image = st.session_state.image
    st.header("What the model sees")
    left, right = st.columns([1.5, 1])
    with left:
        blemishes = st.checkbox("Show blemish overlays")
        st.image(draw_boxes(image, result["items"], blemishes), use_container_width=True)
        labels = [f'{item["produce"]} · Tier {item["tier"]}' for item in result["items"]]
        selected = st.selectbox("Item detail", range(len(labels)), format_func=lambda i: labels[i])
        item = result["items"][selected]
        st.subheader("Item detail")
        st.write(f'Freshness: **{item["freshness"]:.0%}** · Tier **{item["tier"]} ({item["fresh_conf"]:.0%} confidence)**')
        st.write(f'Days left: **{item["days_left"]}** · Surface affected: **{item["blemish_pct"]:.1f}%**')
        st.write(f'Detector confidence: {item["det_conf"]:.0%} · Segmentation confidence: {item["seg_conf"]:.0%}')
        if st.checkbox("Show Grad-CAM placeholder"):
            st.image(item["gradcam"], caption="Grad-CAM placeholder")
        forecast = st.selectbox("Forecast preview", [1, 3, 7])
        st.image(item["forecasts"][forecast], caption=f"Generated day +{forecast} preview")
    with right:
        st.subheader("Model confidence")
        for name, key in (("Detector", "det_conf"), ("Freshness", "fresh_conf"), ("Segmentation", "seg_conf")):
            value = sum(entry[key] for entry in result["items"]) / len(result["items"])
            st.metric(name, f"{value:.0%}")
            st.progress(value)
        st.caption("Forecast generator: n/a — previews are checked by the freshness model.")
        st.subheader("Freshness curve")
        points = pd.DataFrame({"day": list(range(8)), "freshness": item["curve"]})
        chart = alt.Chart(points).mark_line(point=True, color="#4d934d").encode(
            x=alt.X("day:Q", title="Days from today"), y=alt.Y("freshness:Q", scale=alt.Scale(domain=[0, 1]))
        )
        st.altair_chart(chart, use_container_width=True)
        st.subheader("Rule trace")
        st.write(f'Rule **{result["rule_id"]}** fired: {result["message"] or "price result"}.')
        st.json(result["thresholds"])
        if result["staff_alert"]:
            st.error("Staff alert raised")
        st.subheader("Session log")
        if st.session_state.scan_logs:
            st.dataframe(pd.DataFrame(st.session_state.scan_logs), use_container_width=True, hide_index=True)
