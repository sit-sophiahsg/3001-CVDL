"""Custom CSS: a clean, high-contrast self-service scale look."""

import streamlit as st

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Share+Tech+Mono&display=swap');

:root {
  --fs-green: #0b7a3e;
  --fs-green-dark: #075a2d;
  --fs-red: #c62828;
  --fs-ink: #111814;
  --fs-muted: #4a554e;
  --fs-bg: #f2f5f1;
  --fs-card: #ffffff;
  --fs-line: #cfd8d0;
}

/* Base: force a light, high-contrast look even if the browser is in dark mode */
.stApp { background: var(--fs-bg); color: var(--fs-ink); font-family: 'Inter', system-ui, sans-serif; }
.stApp [data-testid="stMarkdownContainer"],
.stApp [data-testid="stWidgetLabel"] p { color: var(--fs-ink); }
.stApp [data-testid="stCaptionContainer"] { color: var(--fs-muted); font-size: 0.95rem; }
[data-testid="stHeader"] { background: transparent; }
.stAppDeployButton { display: none; }
.block-container { max-width: 1100px; padding-top: 3rem; padding-bottom: 3rem; }

/* Header bar with the scale display in the top-right corner */
.fs-header {
  display: flex; justify-content: space-between; align-items: center; gap: 1rem;
  background: var(--fs-green); border-radius: 18px; padding: 0.9rem 1.1rem;
  box-shadow: 0 4px 14px rgba(0,0,0,0.12);
}
.fs-brand { display: flex; align-items: center; gap: 0.75rem; min-width: 0; }
.fs-logo {
  font-size: 2.1rem; background: #fff; border-radius: 14px;
  width: 3.4rem; height: 3.4rem; display: grid; place-items: center; flex-shrink: 0;
}
.fs-name { color: #fff; font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em; line-height: 1.1; }
.fs-sub { color: #d8f0df; font-size: 1rem; font-weight: 600; }
.fs-scale {
  background: #0c110e; border: 3px solid #36423a; border-radius: 12px;
  padding: 0.35rem 0.9rem 0.45rem; text-align: right; min-width: 13rem; flex-shrink: 0;
}
.fs-scale-label { color: #9fb5a6; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.14em; }
.fs-scale-value {
  font-family: 'Share Tech Mono', ui-monospace, monospace; color: #7dff9e;
  font-size: 3.2rem; line-height: 1; text-shadow: 0 0 10px rgba(125,255,158,0.45);
}
.fs-scale-unit { font-size: 1.3rem; margin-left: 0.3rem; }
.fs-scale-price { font-family: 'Share Tech Mono', ui-monospace, monospace; color: #ffcf5c; font-size: 1.05rem; min-height: 1.3rem; }

/* Titles */
.fs-title { font-size: 2rem; font-weight: 800; color: var(--fs-ink); margin: 0.6rem 0 0.4rem; }
.fs-subtitle { font-size: 1.15rem; color: var(--fs-muted); margin-bottom: 0.6rem; }

/* Buttons: big and touch-friendly */
.stButton > button {
  min-height: 3.6rem; border-radius: 14px; border: 2px solid var(--fs-line);
  background: #fff; color: var(--fs-ink);
}
.stButton > button p { font-size: 1.25rem !important; font-weight: 700; }
.stButton > button:hover { border-color: var(--fs-green); color: var(--fs-green-dark); }
.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {
  background: var(--fs-green); border-color: var(--fs-green); color: #fff;
}
.stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
  background: var(--fs-green-dark); border-color: var(--fs-green-dark); color: #fff;
}
.stButton > button:disabled { background: #e3e7e2; border-color: #d3d9d2; color: #8a948c; }
.st-key-scan_btn button { min-height: 5rem; }
.st-key-scan_btn button p { font-size: 1.9rem !important; letter-spacing: 0.04em; }

/* Back / Start over row stays side by side on phones */
.st-key-navbar [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; gap: 0.75rem; }
.st-key-navbar [data-testid="stColumn"] { min-width: 0 !important; flex: 1 1 0 !important; width: auto !important; }
.st-key-navbar .stButton > button { min-height: 3rem; }
.st-key-navbar .stButton > button p { font-size: 1.05rem !important; }

/* Category and item tiles */
[class*="st-key-cat_"], [class*="st-key-tile_"], [class*="st-key-tiledis_"] {
  background: var(--fs-card); border: 2px solid var(--fs-line); border-radius: 20px;
  padding: 1.1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
[class*="st-key-tiledis_"] { background: #e9ece8; box-shadow: none; }
.fs-cat, .fs-tile { text-align: center; }
.fs-cat-emoji { font-size: 4.5rem; line-height: 1.15; }
.fs-cat-name { font-size: 2.4rem; font-weight: 800; color: var(--fs-ink); }
.fs-cat-count { font-size: 1.1rem; color: var(--fs-muted); }
.fs-tile-emoji { font-size: 4rem; line-height: 1.15; }
.fs-tile-name { font-size: 1.55rem; font-weight: 800; color: var(--fs-ink); }
.fs-tile-price { font-size: 1.3rem; font-weight: 800; color: var(--fs-green-dark); }
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
.fs-itembar-price { font-size: 1.25rem; font-weight: 700; color: var(--fs-green-dark); }

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
.fs-row.total .v { color: var(--fs-green-dark); }

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
  .block-container { padding: 2.8rem 1rem 2rem; }
  .fs-header { padding: 0.7rem; gap: 0.5rem; }
  .fs-logo { width: 2.5rem; height: 2.5rem; font-size: 1.5rem; border-radius: 10px; }
  .fs-name { font-size: 1.35rem; }
  .fs-sub { display: none; }
  .fs-scale { min-width: 0; padding: 0.3rem 0.6rem; }
  .fs-scale-value { font-size: 2.1rem; }
  .fs-scale-unit { font-size: 1rem; }
  .fs-scale-price { font-size: 0.85rem; }
  .fs-title { font-size: 1.6rem; }
  .fs-cat-emoji { font-size: 3.2rem; }
  .fs-cat-name { font-size: 1.9rem; }
  .fs-badge { font-size: 2.2rem; }
  .fs-alert-title { font-size: 1.6rem; }
}
"""


def inject_css() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
