"""Shared look (CSS, icons, labels) and session helpers for the FreshMart app."""

from __future__ import annotations

import csv
from pathlib import Path
from urllib.parse import quote

import streamlit as st

ROOT = Path(__file__).parent.parent

LABELS = {"apple": "Apple", "banana": "Banana", "orange": "Orange", "capsicum": "Capsicum",
          "tomato": "Tomato", "potato": "Potato"}


def label_of(produce: str | None) -> str:
    """Display name; never crashes on a type outside the six (audit risk 9)."""
    if not produce:
        return "—"
    return LABELS.get(produce, str(produce).title())


# ---------------------------------------------------------------- icons (from design_ref)
LOGO_SVG = ('<svg width="34" height="34" viewBox="0 0 34 34" aria-hidden="true">'
            '<circle cx="17" cy="18" r="12" fill="#B9E26A"></circle>'
            '<path d="M17 7 C17 3 21 2 23 2 C23 5 21 7 17 7Z" fill="#7CC04B"></path>'
            '<path d="M12 18 l4 4 l7 -8" fill="none" stroke="#123826" stroke-width="3" '
            'stroke-linecap="round" stroke-linejoin="round"></path></svg>')

_STROKE = ('fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="round" '
           'stroke-linejoin="round"')
ICON_PATHS = {
    "camera": ('<path d="M3 8h4l2-3h6l2 3h4v11H3z"></path><circle cx="12" cy="13" r="4"></circle>', 2),
    "upload": ('<path d="M12 16V4"></path><path d="M7 9l5-5 5 5"></path><path d="M4 20h16"></path>', 2),
    "photo": ('<rect x="3" y="4" width="18" height="16" rx="2"></rect><circle cx="9" cy="10" r="2">'
              '</circle><path d="M21 16l-5-5-9 9"></path>', 2),
    "chevron": ('<path d="M15 6l-6 6 6 6"></path>', 2.4),
    "house": ('<path d="M3 11l9-7 9 7"></path><path d="M5 10v10h14V10"></path>', 2.2),
    "alert": ('<path d="M12 7v6"></path><path d="M12 17h.01"></path>', 2.4),
}


def icon_svg(name: str, colour: str, size: int = 24) -> str:
    body, width = ICON_PATHS[name]
    stroke = _STROKE.format(c=colour, w=width)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 24 24" aria-hidden="true" {stroke}>{body}</svg>')


PRODUCE_SVG = {
    "apple": '<path d="M35 18 C24 10 8 16 10 36 C12 56 26 64 35 58 C44 64 58 56 60 36 C62 16 46 10 35 18Z" fill="#D63B34"></path><path d="M35 18 C35 10 38 6 42 4" stroke="#6B4B2A" stroke-width="3" fill="none"></path><path d="M38 12 C44 6 52 8 54 10 C48 16 42 15 38 12Z" fill="#6BAE3C"></path>',
    "banana": '<path d="M10 22 C14 50 40 62 62 50 C56 52 30 50 20 20 Z" fill="#F3C623"></path><path d="M10 22 L8 16 L13 18 Z" fill="#6B5A20"></path>',
    "orange": '<circle cx="35" cy="38" r="24" fill="#F28C1C"></circle><circle cx="35" cy="16" r="3" fill="#5E8C2C"></circle><circle cx="28" cy="32" r="1.6" fill="#D97510"></circle><circle cx="42" cy="44" r="1.6" fill="#D97510"></circle><circle cx="40" cy="30" r="1.6" fill="#D97510"></circle>',
    "capsicum": '<path d="M18 26 C14 44 18 60 28 60 C32 60 34 56 35 56 C36 56 38 60 42 60 C52 60 56 44 52 26 C46 20 24 20 18 26Z" fill="#CF2A2A"></path><path d="M30 22 C30 14 36 12 40 10 L40 22 Z" fill="#3E8B3A"></path>',
    "tomato": '<circle cx="35" cy="38" r="23" fill="#E2412F"></circle><path d="M35 16 L39 24 L47 22 L41 28 L45 34 L36 30 L28 34 L31 28 L24 22 L32 24 Z" fill="#3F8E33"></path>',
    "potato": '<ellipse cx="35" cy="38" rx="27" ry="19" fill="#C49A5E"></ellipse><circle cx="26" cy="34" r="1.8" fill="#8E6A38"></circle><circle cx="42" cy="42" r="1.8" fill="#8E6A38"></circle><circle cx="46" cy="32" r="1.8" fill="#8E6A38"></circle>',
}


def produce_svg(produce: str, size: int = 70) -> str:
    body = PRODUCE_SVG.get(produce, '<circle cx="35" cy="38" r="22" fill="#9DB8AD"></circle>')
    return f'<svg width="{size}" height="{size}" viewBox="0 0 70 70" aria-hidden="true">{body}</svg>'


_BARS = [(0, 3), (6, 1.5), (10, 4), (17, 1.5), (21, 2.5), (27, 1.5), (31, 4), (38, 2), (43, 1.5),
         (48, 3), (54, 1.5), (58, 4), (65, 2), (70, 1.5), (74, 3), (80, 1.5), (84, 2.5), (90, 4),
         (97, 1.5), (101, 3), (107, 1.5), (111, 2), (116, 4), (123, 1.5), (127, 3), (133, 1.5),
         (137, 2.5), (143, 1.5), (147, 4), (154, 2), (159, 1.5), (163, 3), (169, 1.5), (173, 4),
         (180, 2), (185, 1.5), (189, 3), (195, 1.5), (199, 2.5), (205, 4), (212, 1.5), (216, 3),
         (222, 1.5), (226, 2), (231, 4), (238, 1.5), (242, 3), (248, 1.5), (252, 4)]
BARCODE_SVG = ('<svg width="100%" height="44" viewBox="0 0 260 44" role="img" aria-label="Barcode">'
               '<g fill="#10261B">'
               + "".join(f'<rect x="{x}" width="{w}" height="44"></rect>' for x, w in _BARS)
               + "</g></svg>")


# ---------------------------------------------------------------- CSS
def _icon_rule(key: str, icon: str, colour: str, size: int = 24) -> str:
    uri = "data:image/svg+xml," + quote(icon_svg(icon, colour, size))
    return (f'.st-key-{key} button::before{{content:"";flex:none;width:{size}px;height:{size}px;'
            f'margin-right:10px;background:url("{uri}") center/contain no-repeat;}}')


_FILLED = "background:#1F6F47 !important;color:#FFFFFF !important;border:none !important;"
_OUTLINE = "background:#FFFFFF !important;color:#10261B !important;border:2px solid #9DB8AD !important;"


def _buttons(keys: list[str], css: str) -> str:
    return ",".join(f".st-key-{k} button" for k in keys) + "{" + css + "}"


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&family=Share+Tech+Mono&display=swap');

/* page frame: no Streamlit chrome, no sidebar (test-ids from the 1.50 bundle) */
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stSidebar"],
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"] { display:none !important; }
.stApp { background:#E9EFEB; color:#10261B; font-family:Inter, system-ui, sans-serif; }
.stApp p, .stApp li, .stApp label, .stApp input, .stApp button, .stApp select { font-family:Inter, system-ui, sans-serif; }
.stApp h1, .stApp h2, .stApp h3, .sg { font-family:'Space Grotesk', Inter, sans-serif !important; }
.mono { font-family:'Share Tech Mono', monospace !important; }
[data-testid="stMainBlockContainer"] { padding:0 0 40px !important; max-width:none !important; }
.stApp button p { font-size:inherit !important; font-weight:inherit !important; color:inherit !important; font-family:inherit !important; }
.stApp button:focus-visible { outline:3px solid #2B7FD6 !important; outline-offset:2px; }

/* navbar */
.st-key-navbar { background:#123826; color:#FFFFFF; padding:12px 28px; box-sizing:border-box; }
.st-key-navbar [data-testid="stHorizontalBlock"] { align-items:center; }
.brand { display:flex; align-items:center; gap:12px; }
.brand-name { font-family:'Space Grotesk', Inter, sans-serif; font-weight:700; font-size:22px; color:#FFFFFF; line-height:1.2; }
.brand-sub { font-size:12px; color:#BFD8C9; }
.nav-date { font-size:14px; color:#DDEBE2; }
.st-key-view [data-testid="stButtonGroup"] { width:fit-content; }
.st-key-view [data-testid="stButtonGroup"] > div { background:#0B2A1C; border-radius:999px; padding:4px; gap:4px; width:fit-content; }
.st-key-view button { border:none !important; border-radius:999px !important; min-height:44px; padding:10px 20px !important;
  font-size:15px !important; font-weight:600 !important; background:transparent !important; color:#DDEBE2 !important; margin:0 !important; }
.st-key-view button[data-testid="stBaseButton-segmented_controlActive"] { background:#B9E26A !important; color:#0B2A1C !important; }
.st-key-nav_reset button { border:1px solid #5E8C73 !important; background:transparent !important; color:#FFFFFF !important;
  border-radius:10px !important; padding:8px 14px !important; min-height:40px; font-size:14px !important; }

/* page body */
.st-key-page { padding:24px 28px 0; box-sizing:border-box; }
.foot-note { margin:0; text-align:center; font-size:13px; color:#4B6357; }

/* scale bezel + screen */
.st-key-scale { width:100%; max-width:860px; margin:0 auto; background:#1C2022; border-radius:28px; padding:18px;
  box-shadow:0 18px 40px rgba(16,38,27,.25); box-sizing:border-box; }
.st-key-screen { background:#EAF3F1; border-radius:14px; overflow:hidden; min-height:720px; gap:0 !important; }
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-body_"]) { flex:1 1 auto !important; display:flex; flex-direction:column; }
[class*="st-key-body_"] { flex:1 1 auto; padding:26px 18px 18px; box-sizing:border-box; gap:14px; }
.st-key-body_welcome, .st-key-body_stop, .st-key-body_printed, .st-key-body_upload { justify-content:center; }
.st-key-scale_foot { background:#D7E6E2; padding:10px 18px; box-sizing:border-box; }
.scale-foot-mid { font-size:13px; color:#3D5A4B; text-align:center; }

.readouts { display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:6px; padding:10px; background:#D7E6E2; }
.readout { background:#FFFFFF; border-radius:8px; overflow:hidden; display:flex; flex-direction:column; }
.readout .rl { background:#2C6B4D; color:#FFFFFF; font-size:12px; font-weight:600; letter-spacing:.6px; padding:4px 10px; }
.readout .rv { font-family:'Share Tech Mono', monospace; font-size:38px; text-align:right; padding:4px 12px; color:#10261B; line-height:1.25; }

.banner { position:relative; margin:14px 18px 0; border-radius:12px; padding:16px 22px; font-size:22px; font-weight:700;
  text-align:center; background:#F2D35E; color:#3B2F00; line-height:1.35; }
.banner::after { content:""; position:absolute; left:44px; bottom:-14px; width:28px; height:16px; background:inherit;
  clip-path:polygon(0 0, 100% 0, 21% 100%); }
.banner.warn { background:#FFD9A8; color:#4A1206; }
.banner.stop { background:#F6C9BF; color:#4A1206; }

/* welcome */
.st-key-welcome_img { align-items:center; }
.st-key-welcome_img [data-testid="stImage"], .st-key-welcome_img [data-testid="stImageContainer"] { display:flex; justify-content:center; margin:0 auto; }
.st-key-welcome_img img { max-height:220px; width:auto !important; object-fit:contain; }
.st-key-welcome_btns { max-width:680px; margin:0 auto; width:100%; }
.st-key-w_camera button, .st-key-w_upload button, .st-key-w_demo button { min-height:64px; border-radius:14px !important; font-size:18px !important; font-weight:600 !important; }
.st-key-w_upload button { background:#FFFFFF !important; color:#1F6F47 !important; border:2px solid #1F6F47 !important; }
.small-note { font-size:14px; color:#3D5A4B; text-align:center; margin:0; }

/* shared big buttons */
.st-key-cam_back button, .st-key-up_back button, .st-key-res_back button, .st-key-change_item button,
.st-key-scan_again button, .st-key-next_item button, .st-key-go_shopper button {
  min-height:56px; border-radius:14px !important; padding:0 24px !important; font-size:17px !important; font-weight:600 !important; }

/* produce tiles: the whole card is the button */
[class*="st-key-tile_"] { position:relative; background:#FFFFFF; border:2px solid #C9DAD3; box-shadow:0 2px 0 #C9DAD3;
  border-radius:14px; min-height:150px; padding:14px 10px 12px; box-sizing:border-box; align-items:center; justify-content:center; gap:6px !important; }
[class*="st-key-tile_"]:hover { border-color:#1F6F47; }
[class*="st-key-tile_"]:has(button:focus-visible) { outline:3px solid #2B7FD6; outline-offset:2px; }
.tile { display:flex; flex-direction:column; align-items:center; gap:6px; text-align:center; }
.tile-name { font-size:17px; font-weight:700; color:#10261B; }
.tile-price { font-size:14px; color:#3D5A4B; }
[class*="st-key-pick_"] { position:absolute !important; inset:0; z-index:2; width:auto !important; margin:0 !important; }
[class*="st-key-pick_"] div { width:100% !important; height:100% !important; }
[class*="st-key-pick_"] button { width:100% !important; height:100% !important; background:transparent !important; border:none !important;
  color:transparent !important; box-shadow:none !important; border-radius:14px !important; cursor:pointer; }
.not-here { margin:6px 0 0; font-size:15px; color:#3D5A4B; text-align:center; }

/* priced ticket */
.st-key-ticket { position:relative; background:#FFFFFF; border-radius:14px 14px 0 0; padding:22px 24px 30px; box-sizing:border-box; }
.st-key-ticket::after { content:""; position:absolute; left:0; right:0; bottom:0; height:10px;
  background:linear-gradient(45deg, #EAF3F1 50%, transparent 50%) 0 0 / 20px 20px repeat-x,
             linear-gradient(-45deg, #EAF3F1 50%, transparent 50%) 0 0 / 20px 20px repeat-x; }
.t-name { font-family:'Space Grotesk', Inter, sans-serif; font-size:30px; font-weight:700; letter-spacing:.4px; line-height:1.2; }
.t-row { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:10px 0; }
.pill { border-radius:999px; padding:6px 14px; font-size:15px; font-weight:700; color:#FFFFFF; }
.t-count { font-size:16px; color:#3D5A4B; }
.t-msg { font-size:18px; font-weight:600; }
.t-right { display:flex; flex-direction:column; align-items:flex-end; gap:4px; }
.t-strike { font-size:16px; color:#6B7F75; text-decoration:line-through; }
.t-total { font-family:'Share Tech Mono', monospace; font-size:52px; line-height:1.1; }
.t-calc { font-size:14px; color:#3D5A4B; }
.st-key-why_toggle button { color:#1F6F47 !important; text-decoration:underline; font-size:16px !important; font-weight:600 !important;
  padding:8px 0 !important; min-height:44px; }
.why-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:14px; margin-top:6px; }
.why-card { background:#FFFFFF; border-radius:12px; padding:14px; display:flex; flex-direction:column; gap:8px; }
.why-title { font-size:14px; font-weight:700; color:#3D5A4B; }
.why-photo { width:100% !important; height:150px !important; max-width:none !important; object-fit:cover; border-radius:8px; background:#F1F4F2; }
.fc-grid { display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:6px; }
.fc { display:flex; flex-direction:column; align-items:center; gap:4px; font-size:12px; color:#3D5A4B; }
.fc img { width:100% !important; aspect-ratio:1; object-fit:cover; border-radius:8px; }
.illus { font-size:12px; color:#5A6E64; }
.st-key-print_btn button { width:120px; height:120px; border-radius:50% !important; border:none !important; background:#F2C94C !important;
  color:#3B2F00 !important; font-family:'Space Grotesk', Inter, sans-serif !important; font-size:24px !important; font-weight:700 !important;
  box-shadow:0 6px 0 #C9A12C; }
.st-key-print_btn button:active { transform:translateY(4px); box-shadow:0 2px 0 #C9A12C; }

/* not priced */
.stop-box { display:flex; flex-direction:column; align-items:center; gap:22px; text-align:center; padding-top:20px; }
.stop-icon { width:96px; height:96px; border-radius:50%; display:flex; align-items:center; justify-content:center; }
.stop-detail { margin:0; font-size:20px; max-width:560px; }
.staff-pill { background:#FFE9E4; color:#8A1C0E; border-radius:999px; padding:10px 18px; font-size:16px; font-weight:600; }

/* printed label */
.label-card { width:300px; margin:0 auto; background:#FFFFFF; border-radius:10px; box-shadow:0 10px 24px rgba(16,38,27,.18);
  padding:18px 20px; display:flex; flex-direction:column; gap:6px; font-size:14px; box-sizing:border-box; }
.label-card .row { display:flex; justify-content:space-between; gap:8px; }
.label-card .disc { color:#7A3E00; font-weight:600; }
.label-card .tot { border-top:1px dashed #9DB8AD; padding-top:8px; margin-top:2px; align-items:baseline; }
.label-thanks { margin:0; font-size:18px; color:#3D5A4B; text-align:center; }

/* scale footer */
.st-key-foot_home button { min-height:48px; padding:0 16px !important; border-radius:12px !important; border:none !important;
  background:#2C6B4D !important; color:#FFFFFF !important; font-size:15px !important; font-weight:600 !important; }
.st-key-foot_staff button { min-height:48px; padding:0 16px !important; border-radius:12px !important; border:2px solid #2C6B4D !important;
  background:transparent !important; color:#1F4F37 !important; font-size:15px !important; font-weight:600 !important; }

/* model view */
.st-key-modelpage { width:100%; max-width:1360px; margin:0 auto; gap:16px; }
.stApp h1.mv-title { margin:0; padding:0; font-family:'Space Grotesk', Inter, sans-serif; font-size:28px !important; font-weight:700; line-height:1.25; }
.mv-photo { display:block; width:100% !important; max-width:none !important; border-radius:12px; background:#DFF2E1; }
.st-key-mv_left [data-testid="stCheckbox"] label:has(input[aria-checked="true"]) > div:first-child { background:#1F6F47 !important; }
.st-key-mv_left [data-testid="stCheckbox"] p { font-size:14px !important; font-weight:600; }
.mv-sub { font-size:14px; color:#3D5A4B; }
.st-key-devbox { background:#FFFFFF; border:1px solid #C9DAD3; border-radius:14px; padding:12px 14px; box-sizing:border-box; }
.dev-tag { font-size:12px; font-weight:700; color:#3D5A4B; letter-spacing:.4px; }
.standin { background:#FFF4D6; border:1px solid #E8C766; color:#5A4300; border-radius:12px; padding:10px 14px; font-size:14px; }
.st-key-mv_left, .st-key-mv_items, .st-key-mv_empty { background:#FFFFFF; border-radius:16px; padding:16px; box-sizing:border-box; }
.card { background:#FFFFFF; border-radius:16px; padding:16px; display:flex; flex-direction:column; gap:8px; margin-bottom:14px; }
.card-tag { font-size:13px; font-weight:700; color:#3D5A4B; letter-spacing:.4px; }
.dec-rule { font-family:'Space Grotesk', Inter, sans-serif; font-size:22px; font-weight:700; }
.chip { border-radius:999px; padding:4px 10px; font-size:13px; background:#EEF1EF; }
.trace-row { display:flex; align-items:center; gap:10px; padding:6px 0; border-bottom:1px solid #EEF1EF; }
.trace-n { width:26px; height:26px; flex:none; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; }
.trace-t { flex:1; font-size:14px; }
.trace-s { font-size:13px; font-weight:600; }
.thr { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:6px; font-size:14px; }
.thr .mono { text-align:right; }
.mv-fc { display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:10px; }
.mv-fc div { display:flex; flex-direction:column; gap:4px; }
.mv-fc img { width:100% !important; aspect-ratio:1; object-fit:cover; border-radius:10px; }
.mv-fc b { font-size:13px; } .mv-fc span { font-size:12px; color:#3D5A4B; }
.stApp [data-testid="stExpander"] details { background:#FFFFFF; border-radius:16px; border:none; }
"""


def style() -> None:
    rules = [
        CSS,
        _buttons(["w_camera", "scan_again", "next_item", "go_shopper"], _FILLED),
        _buttons(["w_demo", "cam_back", "up_back", "res_back", "change_item"], _OUTLINE),
        _icon_rule("w_camera", "camera", "#FFFFFF"),
        _icon_rule("w_upload", "upload", "#1F6F47"),
        _icon_rule("w_demo", "photo", "#10261B"),
        _icon_rule("res_back", "chevron", "#10261B", 20),
        _icon_rule("foot_home", "house", "#FFFFFF", 20),
    ]
    st.html("<style>" + "\n".join(rules) + "</style>")


# ---------------------------------------------------------------- data + state
def load_prices() -> dict[str, float]:
    path = ROOT / "configs" / "prices.csv"
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as file:
        return {row["produce"]: float(row["price_per_kg"]) for row in csv.DictReader(file)}


def log_scan(entry: dict) -> None:
    path = ROOT / "logs" / "scans.csv"
    path.parent.mkdir(exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["time", "selected_type", "rule_id", "staff_alert"])
        if not exists:
            writer.writeheader()
        writer.writerow(entry)


def bump_nonce() -> None:
    """New widget keys for camera/uploader, so they come back empty."""
    st.session_state.input_nonce = st.session_state.get("input_nonce", 0) + 1


def reset_scan_state() -> None:
    """Reset scan: same keys as before, plus the new per-scan UI flags."""
    for key, value in {"screen": "welcome", "selected_type": None, "weight_kg": 0.25,
                       "image": None, "result": None, "failed_scans": 0, "scan_logs": [],
                       "staff_called": False, "show_why": False}.items():
        st.session_state[key] = value
    bump_nonce()
