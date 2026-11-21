from __future__ import annotations

from datetime import date

import streamlit as st

from backend import TYPES, TIERS

LABELS = {"apple": "Apple", "banana": "Banana", "orange": "Orange", "capsicum": "Capsicum",
          "tomato": "Tomato", "potato": "Potato"}
EMOJI = {"apple": "🍎", "banana": "🍌", "orange": "🍊", "capsicum": "🫑", "tomato": "🍅", "potato": "🥔"}


def label(result: dict) -> None:
    price = result["price"]
    st.markdown(f"""<div class="kiosk"><h3>FreshMart produce label</h3>
    <p><b>{LABELS[result["fields"]["detected"]]}</b> · {date.today().isoformat()}</p>
    <p>Weight: {price["weight_kg"]:.3f} kg<br>Price/kg: ${price["price_per_kg"]:.2f}<br>
    Discount: {price["discount"] or 0:.0%}<br><b>Total: ${price["total"]:.2f}</b></p>
    <div style="font-size:2rem;letter-spacing:.25rem">▌▌▌▌ ▌▌ ▌▌▌▌</div></div>""", unsafe_allow_html=True)


def render(st_module, scan, read_input_image) -> None:
    screen = st.session_state.screen
    if screen == "idle":
        st.markdown('<div class="kiosk"><h1>Place your produce on the scale</h1><p>Choose a demo image or add a photo to begin.</p></div>', unsafe_allow_html=True)
        if st.button("Start scan", type="primary", use_container_width=True):
            st.session_state.screen = "input"
            st.rerun()
        return
    if screen == "input":
        st.session_state.image = read_input_image()
        st.image(st.session_state.image, caption="Scale camera view", use_container_width=True)
        if st.button("Continue to produce selection", type="primary", use_container_width=True):
            st.session_state.screen = "select"
            st.rerun()
        return
    if screen == "select":
        st.header("What are you weighing?")
        columns = st.columns(3)
        for index, item in enumerate(TYPES):
            with columns[index % 3]:
                if st.button(f"{EMOJI[item]}  {LABELS[item]}", key=f"pick_{item}", use_container_width=True):
                    if st.session_state.selected_type != item:
                        st.session_state.failed_scans = 0
                    st.session_state.selected_type = item
                    st.session_state.screen = "weigh"
                    st.rerun()
        return
    if screen == "weigh":
        selected = st.session_state.selected_type
        st.header(f"{EMOJI[selected]} {LABELS[selected]}")
        st.session_state.weight_kg = st.number_input("Simulated weight (kg)", 0.05, 5.0,
                                                      float(st.session_state.weight_kg), 0.05)
        if st.button("Scan produce", type="primary", use_container_width=True):
            scan()
        return
    result = st.session_state.result
    if result is None:
        st.session_state.screen = "idle"
        st.rerun()
    if result["rule_id"] == 7:
        price = result["price"]
        st.markdown('<div class="result"><h1>Scan complete</h1>'
                    f'<div class="metric">${price["total"]:.2f}</div>'
                    f'<p>{price["weight_kg"]:.3f} kg · ${price["price_per_kg"]:.2f}/kg · '
                    f'{price["discount"] or 0:.0%} discount · Tier {price["tier"]}</p></div>',
                    unsafe_allow_html=True)
        label(result)
    else:
        css = "danger" if result["staff_alert"] else "warning"
        st.markdown(f'<div class="{css}"><h2>{result["message"]}</h2></div>', unsafe_allow_html=True)
    if st.button("New scan", type="primary", use_container_width=True):
        st.session_state.screen = "idle"
        st.session_state.result = None
        st.session_state.selected_type = None
        st.rerun()
