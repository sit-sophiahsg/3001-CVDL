"""Custom CSS: FairPrice Finest produce-scale kiosk look."""

import streamlit as st

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800;900&family=Share+Tech+Mono&display=swap');

:root {
  --fp-sky:    #a8d4f0;
  --fp-sky2:   #c5e3f7;
  --fp-yellow: #f5c518;
  --fp-yellow-dark: #d4a800;
  --fp-navy:   #1a2b4a;
  --fp-blue:   #0a5aa5;
  --fp-red:    #c0392b;
  --fp-green:  #1b8a3f;
  --fp-white:  #ffffff;
  --fp-muted:  #555e70;
  --fp-line:   #d8e4f0;
}

/* ── base ── */
html, body { margin: 0; padding: 0; }
.stApp {
  background: var(--fp-sky);
  color: var(--fp-navy);
  font-family: 'Inter', system-ui, sans-serif;
  min-height: 100dvh;
}
.stApp [data-testid="stMarkdownContainer"],
.stApp [data-testid="stWidgetLabel"] p { color: var(--fp-navy); }
.stApp [data-testid="stCaptionContainer"] { color: var(--fp-muted); font-size: 0.95rem; }

/* ── kiosk chrome: hide Streamlit toolbar and collapse all outer gaps ── */
[data-testid="stHeader"] { display: none; }
.block-container { max-width: none !important; padding: 0 !important; }
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"],
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] { gap: 0 !important; }

/* ── scale readout header ── */
.fs-header { background: var(--fp-white); border-bottom: 3px solid var(--fp-yellow); }
.fs-rw-labels {
  display: grid; grid-template-columns: repeat(4, 1fr);
  background: var(--fp-yellow);
}
.fs-rw-labels div {
  color: var(--fp-navy); font-size: 0.72rem; font-weight: 800;
  letter-spacing: 0.06em; text-align: center;
  padding: 0.3rem 0.5rem;
  border-right: 1px solid rgba(0,0,0,0.12);
}
.fs-rw-labels div:last-child { border-right: none; }
.fs-rw-values {
  display: grid; grid-template-columns: repeat(4, 1fr);
  background: var(--fp-white);
}
.fs-rw-values div {
  color: var(--fp-navy);
  font-family: 'Share Tech Mono', ui-monospace, monospace;
  font-size: 3.4rem; line-height: 1.1;
  text-align: right; padding: 0.6rem 1.2rem 0.7rem;
  border-right: 1px solid var(--fp-line);
}
.fs-rw-values div:last-child { border-right: none; }

/* welcome header variant: 2 number cols + big WELCOME text */
.fs-header-welcome .fs-rw-labels { grid-template-columns: 1fr 1fr 2fr; }
.fs-header-welcome .fs-rw-values { grid-template-columns: 1fr 1fr 2fr; }
.fs-welcome-cell {
  display: flex; align-items: center; justify-content: center;
  font-size: 2.4rem; font-weight: 900; color: var(--fp-blue);
  letter-spacing: 0.04em;
}

/* ── speech bubble ── */
.fs-bubble {
  background: var(--fp-yellow); color: var(--fp-navy);
  border-radius: 14px; padding: 1.1rem 1.8rem;
  font-size: 1.55rem; font-weight: 800; text-align: center;
  position: relative; margin: 0.8rem 1.5rem 1.2rem;
  box-shadow: 0 4px 14px rgba(0,0,0,0.13);
}
.fs-bubble::before {
  content: "";
  position: absolute; left: -15px; top: 50%; transform: translateY(-50%);
  width: 0; height: 0;
  border-top: 11px solid transparent;
  border-bottom: 11px solid transparent;
  border-right: 15px solid var(--fp-yellow);
}
.fs-bubble.top::before { display: none; }

/* ── welcome illustration ── */
.fs-welcome-art {
  display: flex; justify-content: center; align-items: center;
  gap: 3rem; font-size: 9rem; padding: 2rem 1rem;
  flex: 1;
}
.fs-welcome-img-wrap img {
  opacity: 0.9;
  max-height: 16vh;
  object-fit: contain;
  display: block;
  margin: 0 auto;
  width: 85% !important;
}
/* Hand images flanking the grocery bag */
.fs-hand-wrap { display: flex; align-items: center; height: 100%; }
.fs-hand-wrap img {
  max-height: 14vh;
  object-fit: contain;
  width: 85% !important;
  display: block;
  margin: 0 auto;
}
.fs-hand-left  img { transform: scaleX(-1); }

/* Collapse gap between welcome columns so hands sit close to the bag */
.st-key-welcome_cols [data-testid="stHorizontalBlock"] {
  gap: 0 !important;
}
/* Right-align left hand so it presses against the bag */
.st-key-welcome_cols [data-testid="stColumn"]:first-child [data-testid="stImage"] {
  display: flex;
  justify-content: flex-end;
}
/* Left-align right hand so it presses against the bag */
.st-key-welcome_cols [data-testid="stColumn"]:last-child [data-testid="stImage"] {
  display: flex;
  justify-content: flex-start;
}
/* Centre the bag in its column */
.st-key-welcome_cols [data-testid="stColumn"]:nth-child(2) [data-testid="stImage"] {
  display: flex;
  justify-content: center;
}

/* Disclaimer bar */
.fs-disclaimer {
  text-align: center; font-size: 0.72rem; color: var(--fp-muted);
  padding: 0.3rem 1rem; background: rgba(255,255,255,0.6);
  border-top: 1px solid var(--fp-line);
}

/* Staff alert banner */
.fs-staff-alert {
  background: #c0392b; color: #fff; border-radius: 10px;
  padding: 0.9rem 1.2rem; text-align: center;
  font-size: 1.3rem; font-weight: 800; margin-bottom: 0.8rem;
}

/* Suggested tile highlight on pick screen */
.fp-tile-suggested {
  border-color: var(--fp-yellow) !important;
  box-shadow: 0 0 0 3px var(--fp-yellow) !important;
}
.fp-tile-suggested-label {
  display: inline-block; margin-top: 0.3rem;
  background: var(--fp-yellow); color: var(--fp-navy);
  border-radius: 6px; padding: 0.1rem 0.5rem;
  font-size: 0.65rem; font-weight: 800; letter-spacing: 0.04em;
}

/* ── START button (welcome screen) ── */
.st-key-start_btn button {
  min-height: 5rem !important; border-radius: 14px !important;
  font-size: 1.8rem !important; font-weight: 900 !important;
  letter-spacing: 0.08em !important;
  background: var(--fp-blue) !important; border-color: var(--fp-blue) !important;
  color: #fff !important;
}

/* ── generic buttons ── */
.stButton > button {
  min-height: 3.4rem; border-radius: 10px; border: 2px solid var(--fp-line);
  background: var(--fp-white); color: var(--fp-navy);
}
.stButton > button p { font-size: 1.15rem !important; font-weight: 700; }
.stButton > button:hover { border-color: var(--fp-blue); color: var(--fp-blue); }
.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {
  background: var(--fp-blue) !important; border-color: var(--fp-blue) !important; color: #fff !important;
}
.stButton > button:disabled { background: #d8dfe8 !important; border-color: #c5cdd8 !important; color: #8a95a3 !important; }

/* ── body padding ── */
.st-key-body { padding: 0 1.4rem 1.4rem; }

/* ── item tiles grid ── */
.fp-tile {
  background: var(--fp-white); border-radius: 12px;
  padding: 0.7rem 0.6rem 0.5rem;
  box-shadow: 0 2px 10px rgba(0,0,0,0.09);
  position: relative; text-align: center; height: 100%;
  border: 2px solid var(--fp-line);
}
.fp-tile-disabled { background: #e8ecf0; box-shadow: none; }
.fp-tile-plu {
  position: absolute; top: 0.4rem; left: 0.5rem;
  font-size: 0.65rem; color: #888; font-family: 'Share Tech Mono', monospace;
}
.fp-tile-uprice {
  position: absolute; top: 0.4rem; right: 0.5rem;
  font-size: 0.65rem; color: var(--fp-muted); font-weight: 700;
}
.fp-tile-emoji { font-size: 3.6rem; line-height: 1.2; margin: 0.3rem 0 0.2rem; }
.fp-tile-disabled .fp-tile-emoji { filter: grayscale(1); opacity: 0.5; }
.fp-tile-name {
  font-size: 0.9rem; font-weight: 800; color: var(--fp-navy);
  line-height: 1.2; margin-top: 0.2rem; text-transform: uppercase;
}
.fp-tile-disabled .fp-tile-name { color: #8a95a3; }
.fp-soon {
  display: inline-block; margin-top: 0.3rem;
  background: #c0392b; color: #fff;
  border-radius: 6px; padding: 0.1rem 0.5rem;
  font-size: 0.6rem; font-weight: 800; letter-spacing: 0.05em;
}

/* Select button inside tile */
[class*="st-key-pick_"] .stButton > button {
  min-height: 2.6rem !important; border-radius: 8px !important; margin-top: 0.3rem;
  background: var(--fp-yellow) !important; border-color: var(--fp-yellow-dark) !important;
  color: var(--fp-navy) !important;
}
[class*="st-key-pick_"] .stButton > button:disabled {
  background: #d8dfe8 !important; border-color: #c5cdd8 !important; color: #8a95a3 !important;
}
[class*="st-key-pick_"] .stButton > button p { font-size: 0.85rem !important; font-weight: 800; }

/* ── selected item bar (scan screen) ── */
.fs-itembar {
  display: flex; align-items: center; gap: 0.8rem;
  background: var(--fp-white); border-radius: 12px;
  padding: 0.7rem 1rem; margin: 0.5rem 0 0.8rem;
  border: 2px solid var(--fp-line);
  box-shadow: 0 2px 8px rgba(0,0,0,0.07);
}
.fs-itembar-emoji { font-size: 2.4rem; }
.fs-itembar-name  { font-size: 1.5rem; font-weight: 800; color: var(--fp-navy); }
.fs-itembar-price { font-size: 1.1rem; font-weight: 700; color: var(--fp-blue); }

/* ── SCAN button ── */
.st-key-scan_btn button {
  min-height: 4.5rem !important; border-radius: 50px !important;
  background: var(--fp-yellow) !important; border-color: var(--fp-yellow-dark) !important;
  color: var(--fp-navy) !important;
}
.st-key-scan_btn button p { font-size: 1.7rem !important; font-weight: 900 !important; letter-spacing: 0.08em; }

/* ── result: freshness badges ── */
.fs-fresh-badge {
  background: var(--fp-green); color: #fff;
  border-radius: 12px; padding: 0.9rem 1.5rem;
  font-size: 2rem; font-weight: 900; text-align: center; line-height: 1.2;
}
.fs-fresh-badge small { display: block; font-size: 1.1rem; font-weight: 700; margin-top: 0.2rem; }
.fs-rotten-badge {
  background: var(--fp-red); color: #fff;
  border-radius: 12px; padding: 0.9rem 1.5rem;
  font-size: 2rem; font-weight: 900; text-align: center; line-height: 1.2;
}
.fs-rotten-badge small { display: block; font-size: 1.1rem; font-weight: 700; margin-top: 0.2rem; }

/* ── label preview ── */
.fs-label-wrap {
  background: var(--fp-white); border-radius: 10px 10px 0 0;
  box-shadow: 0 4px 18px rgba(0,0,0,0.13);
  margin: 0.6rem 0 0; overflow: hidden;
}
.fs-label-inner { padding: 1.2rem 1.5rem 1rem; }
.fs-label-top {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 1rem;
}
.fs-label-title { font-size: 1.5rem; font-weight: 900; color: var(--fp-navy); line-height: 1.2; }
.fs-label-origin { font-size: 0.9rem; font-weight: 700; color: var(--fp-muted); margin-top: 0.1rem; }
.fs-label-emojibox {
  font-size: 3.5rem; line-height: 1;
  display: flex; flex-direction: column; align-items: flex-end; gap: 0.1rem;
}
.fs-label-plu { font-size: 0.65rem; color: #aaa; font-family: 'Share Tech Mono', monospace; }
.fs-label-rows { margin-top: 0.9rem; border-top: 1px solid var(--fp-line); padding-top: 0.7rem; }
.fs-label-row {
  display: flex; justify-content: space-between;
  font-size: 1rem; padding: 0.25rem 0;
}
.fs-label-row .k { color: var(--fp-muted); font-weight: 600; }
.fs-label-row .v { color: var(--fp-navy); font-weight: 800; }
.fs-label-total {
  display: flex; justify-content: space-between;
  font-size: 1.5rem; font-weight: 900;
  border-top: 2px solid var(--fp-navy); margin-top: 0.5rem; padding-top: 0.5rem;
  color: var(--fp-navy);
}
.fs-label-wave {
  height: 20px;
  background:
    linear-gradient(135deg, var(--fp-sky) 25%, transparent 25%) -10px 0,
    linear-gradient(225deg, var(--fp-sky) 25%, transparent 25%) -10px 0,
    linear-gradient(315deg, var(--fp-sky) 25%, transparent 25%),
    linear-gradient(45deg,  var(--fp-sky) 25%, transparent 25%);
  background-size: 20px 20px;
  background-color: var(--fp-white);
}
.fs-label-demo {
  text-align: center; font-size: 0.75rem; font-weight: 800;
  color: var(--fp-red); letter-spacing: 0.08em;
  padding: 0.3rem 0 0.5rem;
}

/* ── PRINT button ── */
.st-key-print_btn { display: flex; justify-content: center; padding: 0.8rem 0; }
.st-key-print_btn .stButton > button {
  width: 110px !important; height: 110px !important;
  border-radius: 50% !important;
  background: var(--fp-yellow) !important; border-color: var(--fp-yellow-dark) !important;
  color: var(--fp-navy) !important; min-height: unset !important;
}
.st-key-print_btn .stButton > button p { font-size: 1.15rem !important; font-weight: 900 !important; }

/* ── back / rescan row ── */
.st-key-result_actions [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; gap: 0.75rem; }
.st-key-result_actions [data-testid="stColumn"] { min-width: 0 !important; flex: 1 1 0 !important; }
.st-key-back_btn .stButton > button {
  background: #fff !important; color: var(--fp-red) !important;
  border-color: var(--fp-red) !important;
}

/* ── alert (invalid scan / wrong item) ── */
.fs-alert {
  background: var(--fp-white); border: 2px solid var(--fp-yellow);
  border-left-width: 10px; border-radius: 12px;
  padding: 1rem 1.2rem; margin-bottom: 0.8rem;
}
.fs-alert-title { font-size: 1.6rem; font-weight: 800; color: var(--fp-navy); }
.fs-alert-body  { font-size: 1rem;   color: var(--fp-muted); margin-top: 0.3rem; }

/* ── home / nav row ── */
.st-key-home_row [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; gap: 0.75rem; }
.st-key-home_row [data-testid="stColumn"] { min-width: 0 !important; flex: 1 1 0 !important; }
.st-key-home_row [data-testid="stColumn"]:first-child { flex: 0 0 auto !important; width: auto !important; }
.st-key-home_btn .stButton > button {
  background: var(--fp-yellow) !important; border-color: var(--fp-yellow-dark) !important;
  color: var(--fp-navy) !important;
  min-height: 3.4rem !important; border-radius: 10px !important;
}
.st-key-home_btn .stButton > button p { font-size: 1rem !important; font-weight: 900 !important; }

/* ── footer ── */
.fs-footer {
  display: flex; justify-content: space-between; align-items: center;
  background: rgba(255,255,255,0.75); border-top: 2px solid var(--fp-line);
  padding: 0.7rem 1.5rem;
}
.fs-footer-spec { font-size: 0.75rem; color: var(--fp-muted); font-family: 'Share Tech Mono', monospace; }
.fs-footer-brand { font-size: 1.3rem; font-weight: 900; color: var(--fp-blue); letter-spacing: 0.01em; }
.fs-footer-brand em { font-style: italic; color: var(--fp-navy); font-weight: 400; }

/* ── demo banner ── */
.fs-demo {
  background: #fff3cd; border: 2px dashed #b7791f; color: #6b4300;
  border-radius: 10px; text-align: center; font-weight: 800; padding: 0.4rem; margin: 0.5rem 0;
}

/* ── sidebar demo controls ── */
[data-testid="stSidebarContent"] { background: var(--fp-white); }

/* ── phones ── */
@media (max-width: 640px) {
  .fs-rw-labels div { font-size: 0.55rem; letter-spacing: 0.01em; }
  .fs-rw-values div { font-size: 1.8rem; padding: 0.4rem 0.5rem 0.5rem; }
  .fs-bubble { font-size: 1.15rem; padding: 0.9rem 1.2rem; margin: 0.6rem 1rem 0.9rem; }
  .fs-welcome-art { font-size: 5rem; gap: 1.5rem; }
  .fs-label-title { font-size: 1.15rem; }
}
"""


def inject_css() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
