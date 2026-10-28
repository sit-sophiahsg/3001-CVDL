"""Custom CSS: a white, blue-banded self-service scale look."""

import streamlit as st

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Share+Tech+Mono&display=swap');

:root {
  --fs-blue: #1f5fa8;
  --fs-blue-dark: #174a85;
  --fs-navy: #1c2b45;
  --fs-red: #c62828;
  --fs-ink: #111827;
  --fs-muted: #4b5563;
  --fs-bg: #ffffff;
  --fs-card: #ffffff;
  --fs-line: #d5dbe3;
  --fs-strip: #dfe6ee;
}

/* Base: force a light, high-contrast look even if the browser is in dark mode */
.stApp { background: var(--fs-bg); color: var(--fs-ink); font-family: 'Inter', system-ui, sans-serif; }
.stApp [data-testid="stMarkdownContainer"],
.stApp [data-testid="stWidgetLabel"] p { color: var(--fs-ink); }
.stApp [data-testid="stCaptionContainer"] { color: var(--fs-muted); font-size: 0.95rem; }
/* Full-screen kiosk: no Streamlit toolbar, no page margins, no gaps between the bands */
[data-testid="stHeader"] { display: none; }
.block-container { max-width: none; padding: 0; }
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"],
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] { gap: 0; }
.st-key-body { padding: 1rem 1.5rem 1.5rem; }

/* Scale readout: navy label strip over a blue band of big white digits */
.fs-readout-labels, .fs-readout-values { display: grid; grid-template-columns: repeat(4, 1fr); }
.fs-readout-labels { background: var(--fs-navy); padding: 0.35rem 0; }
.fs-readout-labels div {
  color: #c9d4e5; font-size: 0.8rem; font-weight: 600; letter-spacing: 0.08em; text-align: center;
}
.fs-readout-labels small { font-size: 0.7rem; margin-right: 0.35rem; opacity: 0.8; }
.fs-readout-values { background: var(--fs-blue); padding: 1.1rem 0 1.2rem; }
.fs-readout-values div {
  color: #fff; font-family: 'Share Tech Mono', ui-monospace, monospace;
  font-size: 4.2rem; line-height: 1.1; text-align: right; padding-right: 1.4rem;
}

/* Bottom instruction strip */
.fs-footer {
  display: flex; justify-content: space-between; align-items: center; gap: 1rem;
  background: var(--fs-strip); padding: 1.1rem 1.5rem;
}
.fs-footer-msg { font-size: 2.1rem; font-weight: 700; color: var(--fs-navy); line-height: 1.25; }
.fs-footer-brand { font-size: 1.3rem; font-style: italic; font-weight: 800; color: var(--fs-blue); white-space: nowrap; }

/* Home: two big side-by-side category buttons split by a divider, filling the screen
   between the readout (~7.9rem) and the instruction strip (~4.8rem) */
.st-key-cats [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; gap: 0; }
.st-key-cats [data-testid="stColumn"] { min-width: 0 !important; flex: 1 1 0 !important; width: auto !important; }
.st-key-cats [data-testid="stColumn"]:first-child { border-right: 2px solid var(--fs-line); }
.st-key-cats .stButton > button {
  min-height: max(18rem, calc(100dvh - 12.7rem)); border: none; border-radius: 0; background: #fff; flex-direction: column;
}
.st-key-cats .stButton > button:hover { background: #f1f6fc; }
.st-key-cats .stButton > button:active { background: #e3edf9; }
.st-key-cats .stButton > button::before { display: block; font-size: 6rem; line-height: 1.2; margin-bottom: 1rem; }
.st-key-cats .stButton > button p { font-size: 2.2rem !important; font-weight: 800; color: var(--fs-ink); }

/* Titles */
.fs-title { font-size: 2rem; font-weight: 800; color: var(--fs-ink); margin: 0.6rem 0 0.4rem; }
.fs-subtitle { font-size: 1.15rem; color: var(--fs-muted); margin-bottom: 0.6rem; }

/* Buttons: big and touch-friendly */
.stButton > button {
  min-height: 3.6rem; border-radius: 14px; border: 2px solid var(--fs-line);
  background: #fff; color: var(--fs-ink);
}
.stButton > button p { font-size: 1.25rem !important; font-weight: 700; }
.stButton > button:hover { border-color: var(--fs-blue); color: var(--fs-blue-dark); }
.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {
  background: var(--fs-blue); border-color: var(--fs-blue); color: #fff;
}
.stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
  background: var(--fs-blue-dark); border-color: var(--fs-blue-dark); color: #fff;
}
.stButton > button:disabled { background: #e3e7e2; border-color: #d3d9d2; color: #8a948c; }
.st-key-scan_btn button { min-height: 5rem; }
.st-key-scan_btn button p { font-size: 1.9rem !important; letter-spacing: 0.04em; }

/* Back / Start over row stays side by side on phones */
.st-key-navbar [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; gap: 0.75rem; }
.st-key-navbar [data-testid="stColumn"] { min-width: 0 !important; flex: 1 1 0 !important; width: auto !important; }
.st-key-navbar .stButton > button { min-height: 3rem; }
.st-key-navbar .stButton > button p { font-size: 1.05rem !important; }

/* Item tiles */
[class*="st-key-tile_"], [class*="st-key-tiledis_"] {
  background: var(--fs-card); border: 2px solid var(--fs-line); border-radius: 20px;
  padding: 1.1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
[class*="st-key-tiledis_"] { background: #e9ece8; box-shadow: none; }
.fs-tile { text-align: center; }
.fs-tile-emoji { font-size: 4rem; line-height: 1.15; }
.fs-tile-name { font-size: 1.55rem; font-weight: 800; color: var(--fs-ink); }
.fs-tile-price { font-size: 1.3rem; font-weight: 800; color: var(--fs-blue-dark); }
.fs-tile.off .fs-tile-emoji { filter: grayscale(1); opacity: 0.45; }
.fs-tile.off .fs-tile-name, .fs-tile.off .fs-tile-price { color: #8a948c; }
.fs-soon {
  display: inline-block; margin-top: 0.3rem; background: #4a554e; color: #fff;
  border-radius: 999px; padding: 0.15rem 0.75rem; font-size: 0.85rem; font-weight: 800; letter-spacing: 0.06em;
}

/* Selected item bar */
.fs-itembar {
  display: flex; align-items: center; gap: 1rem; background: var(--fs-card);
  border: 2px solid var(--fs-line); border-radius: 18px; padding: 0.8rem 1.1rem; margin: 0.6rem 0 1rem;
}
.fs-itembar-emoji { font-size: 3rem; }
.fs-itembar-name { font-size: 1.8rem; font-weight: 800; color: var(--fs-ink); line-height: 1.1; }
.fs-itembar-price { font-size: 1.25rem; font-weight: 700; color: var(--fs-blue-dark); }

/* Result screen */
.fs-demo {
  background: #fff3cd; border: 2px dashed #b7791f; color: #6b4300; border-radius: 12px;
  text-align: center; font-weight: 800; letter-spacing: 0.04em; padding: 0.45rem; margin: 0.6rem 0;
}
.fs-badge { border-radius: 20px; padding: 1.1rem; text-align: center; color: #fff; font-size: 2.8rem; font-weight: 800; line-height: 1.15; }
.fs-badge small { display: block; font-size: 1.25rem; font-weight: 700; margin-top: 0.3rem; }
.fs-badge.fresh { background: #1b8a3f; }
.fs-badge.rotten { background: var(--fs-red); }
.fs-badge.other { background: #4a554e; }
.fs-alert {
  background: var(--fs-card); border: 2px solid #e0a800; border-left-width: 12px; border-radius: 16px;
  padding: 1.1rem 1.2rem; margin-bottom: 1rem;
}
.fs-alert-title { font-size: 2rem; font-weight: 800; color: var(--fs-ink); line-height: 1.2; }
.fs-alert-body { font-size: 1.15rem; color: var(--fs-muted); margin-top: 0.35rem; }
.fs-rows { background: var(--fs-card); border: 2px solid var(--fs-line); border-radius: 16px; padding: 0.3rem 1.1rem; margin: 1rem 0 0.4rem; }
.fs-row { display: flex; justify-content: space-between; gap: 1rem; padding: 0.65rem 0; border-bottom: 1px solid var(--fs-line); font-size: 1.15rem; }
.fs-row:last-child { border-bottom: none; }
.fs-row .k { color: var(--fs-muted); font-weight: 600; }
.fs-row .v { color: var(--fs-ink); font-weight: 800; text-align: right; }
.fs-row .v.soon { color: #8a948c; font-style: italic; }
.fs-row.total { font-size: 1.6rem; }
.fs-row.total .v { color: var(--fs-blue-dark); }

/* Receipt-style price label */
.fs-label {
  max-width: 380px; margin: 1rem auto; background: #fffef8; color: #111;
  font-family: 'Share Tech Mono', ui-monospace, monospace; font-size: 1.05rem;
  border: 1px solid #cfcfc4; border-radius: 6px; padding: 1rem 1.2rem;
  box-shadow: 0 6px 18px rgba(0,0,0,0.12);
}
.fs-label-head { text-align: center; font-size: 1.4rem; font-weight: 800; letter-spacing: 0.15em; }
.fs-label hr { border: none; border-top: 1px dashed #888; margin: 0.6rem 0; }
.fs-label-row { display: flex; justify-content: space-between; gap: 1rem; }
.fs-label-row.total { font-size: 1.5rem; font-weight: 800; }
.fs-label-meta { text-align: center; color: #444; }
.fs-barcode {
  height: 52px; margin: 0.7rem 0 0.3rem;
  background: repeating-linear-gradient(90deg, #111 0 2px, transparent 2px 4px, #111 4px 5px,
              transparent 5px 8px, #111 8px 11px, transparent 11px 13px);
}
.fs-label-demo { text-align: center; font-size: 0.85rem; color: #8a4b00; margin-top: 0.4rem; }

/* Phones */
@media (max-width: 640px) {
  .st-key-body { padding: 0.75rem 1rem 1rem; }
  .fs-readout-labels div { font-size: 0.6rem; letter-spacing: 0.02em; }
  .fs-readout-labels small { display: none; }
  .fs-readout-values { padding: 0.7rem 0 0.8rem; }
  .fs-readout-values div { font-size: 1.9rem; padding-right: 0.5rem; }
  .fs-footer-msg { font-size: 1.5rem; }
  .fs-footer-brand { display: none; }
  .st-key-cats .stButton > button::before { font-size: 3.2rem; }
  .st-key-cats .stButton > button p { font-size: 1.6rem !important; }
  .fs-title { font-size: 1.6rem; }
  .fs-badge { font-size: 2.2rem; }
  .fs-alert-title { font-size: 1.6rem; }
}
"""


def inject_css() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
