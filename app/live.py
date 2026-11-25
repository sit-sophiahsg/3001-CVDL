"""The live camera component (app/live_component) and the Python side of an auto-scan.

The browser runs the detector on every frame and sends one JPEG frame when the scene has been
still for 1.5 s: ``{"kind": "frame", "ts", "frame", "w", "h", "boxes"}``. Python grades that frame
with ``pipeline.analyse_real`` (its own detector, the notebook's code) and passes the grades back
as args, matched to the browser's boxes by IoU. The component also sends ``{"kind": "scene"}``
when the scene changes after a scan, and ``{"kind": "live"}`` to leave an uploaded photo.
"""

from __future__ import annotations

import base64
import binascii
import io
import os
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps, UnidentifiedImageError

import models
import views

COMPONENT_DIR = Path(__file__).parent / "live_component"
MATCH_IOU = 0.5
_component = components.declare_component("live_scale", path=str(COMPONENT_DIR))


# ---------------------------------------------------------------- detector URL
def detector_url() -> str | None:
    """Hub resolve URL of the detector named in deploy_config.json, pinned to the bundle's commit."""
    try:
        cfg = models.load_config()
    except Exception:  # noqa: BLE001 - no bundle: the component shows its own error
        return None
    repo = models._repo()
    local = models._local_dir() is not None
    revision = (os.environ.get("FRESHMART_MODELS_REVISION") or "main") if local else cfg.folder.name
    return f"https://huggingface.co/{repo}/resolve/{revision}/{cfg.deploy['files']['detector']}"


# ---------------------------------------------------------------- frames in
def decode_frame(value: dict) -> Image.Image | None:
    """The JPEG data URI the component sent, as an RGB image (None if it is not an image)."""
    data = str(value.get("frame") or "")
    if "," in data:
        data = data.split(",", 1)[1]
    try:
        with Image.open(io.BytesIO(base64.b64decode(data))) as image:
            return ImageOps.exif_transpose(image).convert("RGB")
    except (binascii.Error, ValueError, UnidentifiedImageError, OSError):
        return None


def frame_meta(value: dict, image: Image.Image) -> dict:
    """What we keep of a frame besides the image: its ts, size and the browser's boxes."""
    boxes = [[float(v) for v in b[:4]] for b in (value.get("boxes") or []) if len(b) >= 4]
    return {"ts": value.get("ts"), "w": image.width, "h": image.height, "boxes": boxes}


# ---------------------------------------------------------------- matching
def iou(a, b) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def match_items(items: list[dict], live_boxes: list[list[float]], simulated: bool = False) -> list[int | None]:
    """For each server item, the index of the browser box it matches (IoU >= 0.5), else None.

    Greedy, best pair first, one-to-one. Stand-in (simulated) items have made-up boxes, so they
    are given to the browser boxes in order.
    """
    if simulated:
        return [i if i < len(live_boxes) else None for i in range(len(items))]
    pairs = sorted(((iou(it["box"], lb), i, j) for i, it in enumerate(items) for j, lb in enumerate(live_boxes)),
                   reverse=True)
    out: list[int | None] = [None] * len(items)
    used: set[int] = set()
    for value, i, j in pairs:
        if value < MATCH_IOU:
            break
        if out[i] is None and j not in used:
            out[i] = j
            used.add(j)
    return out


# ---------------------------------------------------------------- args out
def _png_uri(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _item_arg(item: dict, cap: int | None, blemish: bool, occlusion: bool, display: bool = False) -> dict:
    out = {"cap": cap, "box": [float(v) for v in item["box"]], "produce": item.get("produce"),
           "det_conf": float(item.get("det_conf", 0.0)), "freshness": float(item["freshness"]),
           "tier": item.get("tier")}
    # camera-tuned % (display only): sent only for Model view with its toggle on, never to the Shopper view
    if display and item.get("freshness_display") is not None:
        out["fresh_disp"], out["tier_disp"] = float(item["freshness_display"]), item.get("tier_display")
    if blemish:
        patch = views.blemish_patch(item)
        if patch is not None:
            out["mask"] = _png_uri(patch)
    if occlusion and item.get("gradcam") is not None:
        x0, y0, x1, y1 = (int(v) for v in item["box"])
        heat = item["gradcam"].convert("RGB").resize((max(1, x1 - x0), max(1, y1 - y0)))
        heat.thumbnail((320, 320))
        out["heat"], out["heat_alpha"] = views.data_uri(heat, 320), float(item.get("cam_alpha", 0.45))
    return out


def grades_arg(result: dict | None, frame: dict | None, blemish: bool = False, occlusion: bool = False,
               display: bool = False) -> dict | None:
    """Grades for the frame the browser sent: one entry per server item, with the browser box it matches."""
    if not frame or frame.get("ts") is None:
        return None
    base = {"ts": frame["ts"], "w": frame["w"], "h": frame["h"], "cap": frame["boxes"]}
    if result is None or result.get("frame_ts") != frame["ts"]:
        return {**base, "items": [], "need_type": True}
    caps = match_items(result.get("items", []), frame["boxes"], bool(result.get("simulated")))
    items = [_item_arg(it, cap, blemish, occlusion and k == 0, display)
             for k, (it, cap) in enumerate(zip(result["items"], caps))]
    return {**base, "items": items, "need_type": False}


def still_arg(image: Image.Image | None, result: dict | None, blemish: bool = False, occlusion: bool = False,
              display: bool = False) -> dict | None:
    """An uploaded photo for the component to show instead of the camera, with the server's boxes."""
    if image is None:
        return None
    items = [] if result is None else [_item_arg(it, None, blemish, occlusion and k == 0, display)
                                       for k, it in enumerate(result.get("items", []))]
    return {"src": views.data_uri(image, 1280), "w": image.width, "h": image.height, "items": items}


def render(view: str, *, key: str, on_change, grades: dict | None, still: dict | None, rearm: int,
           show_boxes: bool = True, show_fresh: bool = True, show_blemish: bool = False, show_occ: bool = False,
           show_disp: bool = False, aspect: float = 0.62, max_height: int = 620) -> Any:
    classes = []
    try:
        classes = list(models.load_config().classes)
    except Exception:  # noqa: BLE001
        pass
    return _component(view=view, det_url=detector_url(), classes=classes, grades=grades, still=still,
                      rearm=int(rearm), show_boxes=bool(show_boxes), show_fresh=bool(show_fresh),
                      show_blemish=bool(show_blemish), show_occ=bool(show_occ), show_disp=bool(show_disp),
                      aspect=aspect,
                      max_height=max_height, key=key, on_change=on_change, default=None)

