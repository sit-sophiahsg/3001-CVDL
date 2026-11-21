"""The real scan pipeline on the ONNX bundle (numpy + OpenCV + Pillow, no torch).

``analyse_real`` returns the same dict shape as ``backend.analyse`` so the UI is unchanged.
The forecast/curve (``ensure_forecast``) and the occlusion map (``ensure_occlusion``) are not run
by ``analyse_real``; the UI asks for them, and they are stored on the result in session state.
"""

from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np
from PIL import Image

import models

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
DET_SIZE, DET_CONF, DET_IOU, MAX_ITEMS = 640, 0.25, 0.7, 12
CROP_PAD = 0.05
FORECAST_DAYS = (1, 3, 7)
OCC_GRID, OCC_PATCH, OCC_GREY, OCC_ALPHA = 8, 28, 114 / 255, 0.45

# step -> {"shape": ..., "seconds": ...} for the most recent call of each step (unit check / timing)
TIMINGS: dict[str, dict[str, Any]] = {}


def _timed(step: str, start: float, shape) -> None:
    TIMINGS[step] = {"shape": shape, "seconds": time.perf_counter() - start}


# ---------------------------------------------------------------- preprocessing
def _letterbox(rgb: np.ndarray) -> tuple[np.ndarray, float, int, int]:
    """Keep aspect ratio, pad with grey 114, centred (as Ultralytics does)."""
    h, w = rgb.shape[:2]
    r = min(DET_SIZE / h, DET_SIZE / w)
    nw, nh = int(round(w * r)), int(round(h * r))
    resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_LINEAR) if (nw, nh) != (w, h) else rgb
    left, top = int(round((DET_SIZE - nw) / 2 - 0.1)), int(round((DET_SIZE - nh) / 2 - 0.1))
    canvas = np.full((DET_SIZE, DET_SIZE, 3), 114, dtype=np.uint8)
    canvas[top:top + nh, left:left + nw] = resized
    return canvas, r, left, top


def _resize_short(image: Image.Image, size: int) -> Image.Image:
    w, h = image.size
    nw, nh = (size, int(size * h / w)) if w <= h else (int(size * w / h), size)
    return image.resize((nw, nh), Image.BILINEAR)


def _centre_offsets(w: int, h: int, size: int) -> tuple[int, int]:
    return int(round((w - size) / 2.0)), int(round((h - size) / 2.0))


def _centre_crop(image: Image.Image, size: int) -> Image.Image:
    left, top = _centre_offsets(*image.size, size)
    return image.crop((left, top, left + size, top + size))


def _normalise(unit: np.ndarray) -> np.ndarray:
    """HxWx3 in [0, 1] -> 3xHxW ImageNet-normalised float32."""
    return ((unit - MEAN) / STD).transpose(2, 0, 1).astype(np.float32)


def _fresh_unit(image: Image.Image, short: int = 256) -> np.ndarray:
    """Freshness input before normalising: shorter side 256, centre crop 224, /255."""
    return np.asarray(_centre_crop(_resize_short(image, short), 224), dtype=np.float32) / 255.0


def _logsumexp(x: np.ndarray) -> np.ndarray:
    m = x.max(axis=1, keepdims=True)
    return (m + np.log(np.exp(x - m).sum(axis=1, keepdims=True)))[:, 0]


# ---------------------------------------------------------------- model steps
def detect(session, rgb: np.ndarray) -> list[dict]:
    """[{box:[x0,y0,x1,y1] on the photo, cls, conf}], at most 12, best first."""
    t = time.perf_counter()
    canvas, r, left, top = _letterbox(rgb)
    x = (canvas.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
    out = session.run(None, {session.get_inputs()[0].name: x})[0]          # [1, 4+6, N]
    pred = out[0].T                                                          # [N, 10]
    scores = pred[:, 4:]
    cls, conf = scores.argmax(axis=1), scores.max(axis=1)
    keep = conf >= DET_CONF
    pred, cls, conf = pred[keep], cls[keep], conf[keep]
    found: list[dict] = []
    if len(pred):
        xywh = np.stack([pred[:, 0] - pred[:, 2] / 2, pred[:, 1] - pred[:, 3] / 2, pred[:, 2], pred[:, 3]], axis=1)
        idx = np.asarray(cv2.dnn.NMSBoxes(xywh.tolist(), conf.tolist(), DET_CONF, DET_IOU)).reshape(-1)
        h, w = rgb.shape[:2]
        for i in idx:                                                        # class-agnostic NMS, sorted by score
            x0, y0 = (xywh[i, 0] - left) / r, (xywh[i, 1] - top) / r
            x1, y1 = x0 + xywh[i, 2] / r, y0 + xywh[i, 3] / r
            box = [int(np.clip(np.floor(x0), 0, w)), int(np.clip(np.floor(y0), 0, h)),
                   int(np.clip(np.ceil(x1), 0, w)), int(np.clip(np.ceil(y1), 0, h))]
            if box[2] - box[0] >= 2 and box[3] - box[1] >= 2:
                found.append({"box": box, "cls": int(cls[i]), "conf": float(conf[i])})
            if len(found) == MAX_ITEMS:
                break
    _timed("detector", t, {"input": list(x.shape), "output": list(out.shape), "kept": len(found)})
    return found


def crop_box(box: list[int], size: tuple[int, int]) -> list[int]:
    """The box grown by 5% on every side, clipped to the photo."""
    w, h = size
    x0, y0, x1, y1 = box
    dx, dy = (x1 - x0) * CROP_PAD, (y1 - y0) * CROP_PAD
    return [max(0, int(x0 - dx)), max(0, int(y0 - dy)), min(w, int(np.ceil(x1 + dx))), min(h, int(np.ceil(y1 + dy)))]


def grade(session, units: list[np.ndarray]) -> dict[str, np.ndarray]:
    """Freshness model on a batch of 224x224 [0, 1] inputs."""
    batch = np.stack([_normalise(u) for u in units])
    logits, fresh, days = session.run(["produce_logits", "freshness", "days_left"], {"image": batch})
    return {"batch": batch, "logits": logits, "freshness": fresh, "days_left": days, "energy": -_logsumexp(logits)}


def blemish(session, crops: list[Image.Image], min_pct: float) -> list[dict]:
    t = time.perf_counter()
    batch = np.stack([_normalise(np.asarray(c.resize((224, 224), Image.BILINEAR), dtype=np.float32) / 255.0)
                      for c in crops])
    prob = session.run(["blemish_prob"], {"image": batch})[0]                # [N, 1, 224, 224], sigmoid applied
    out = []
    for crop, p in zip(crops, prob[:, 0]):
        rgb = np.asarray(crop)
        p = cv2.resize(p.astype(np.float32), crop.size, interpolation=cv2.INTER_LINEAR)
        mask = p > 0.5
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        item_px = ~((hsv[..., 2] > 225) & (hsv[..., 1] < 30))               # white/bright background left out
        conf = np.abs(2 * p - 1)
        pct = float(mask.mean() * 100)
        out.append({"mask": mask, "blemish_pct": pct, "show": pct >= min_pct,
                    "seg_conf": float(conf[item_px].mean() if item_px.any() else conf.mean())})
    _timed("blemish", t, {"input": list(batch.shape), "output": list(prob.shape)})
    return out


# ---------------------------------------------------------------- full scan
def analyse_real(image: Image.Image, selected_type: str, weight_kg: float, failed_scans: int) -> dict[str, Any]:
    """Detector -> crops -> freshness -> rule engine -> blemish. Same dict shape as backend.analyse."""
    bundle = models.load_models()
    cfg, sess = bundle.config, bundle.sessions
    image = image.convert("RGB")
    rgb = np.asarray(image)
    t_all = time.perf_counter()

    found = detect(sess["detector"], rgb)
    crops_xy = [crop_box(d["box"], image.size) for d in found]
    crops = [image.crop(tuple(c)) for c in crops_xy]

    scan_items = []
    if found:
        t = time.perf_counter()
        g = grade(sess["freshness"], [_fresh_unit(c) for c in crops])
        _timed("freshness", t, {"input": list(g["batch"].shape), "produce_logits": list(g["logits"].shape),
                                "freshness": list(g["freshness"].shape), "days_left": list(g["days_left"].shape)})
        for i, d in enumerate(found):
            scan_items.append({"box": d["box"], "produce": cfg.classes[d["cls"]], "det_conf": d["conf"],
                               "freshness": float(g["freshness"][i]), "days_left": float(g["days_left"][i]),
                               "energy": float(g["energy"][i])})

    scan = {"selected_type": selected_type, "weight_kg": float(weight_kg), "failed_scans": int(failed_scans),
            "items": scan_items}
    decision = models.scale_pricing.decide(scan, cfg.rules, cfg.prices, cfg.residuals)

    blem = blemish(sess["blemish"], crops, float(cfg.rules["display"]["blemish_overlay_min_pct"])) if crops else []

    items = []
    for d_item, cxy, b in zip(decision["items"], crops_xy, blem):
        x0, y0, x1, y1 = d_item["box"]
        ox, oy = x0 - cxy[0], y0 - cxy[1]
        shown = b["mask"][oy:oy + (y1 - y0), ox:ox + (x1 - x0)] if b["show"] else np.zeros((y1 - y0, x1 - x0), bool)
        items.append({**d_item, "days_left": round(float(d_item["days_left"]), 1), "crop_box": cxy,
                      "blemish_mask": shown, "blemish_pct": b["blemish_pct"], "seg_conf": b["seg_conf"]})

    fields = dict(decision.get("fields") or {})
    others = [it for it in items if it["produce"] != selected_type]
    fields["detected"] = (max(others, key=lambda it: it["det_conf"])["produce"]
                          if decision["rule_id"] == 4 and others else selected_type)
    if items:
        area = np.array([max(1.0, (it["box"][2] - it["box"][0]) * (it["box"][3] - it["box"][1])) for it in items])
        fields["days"] = round(float(np.average([it["days_left"] for it in scan_items], weights=area)), 1)
        bag_fresh = float(np.average([it["freshness"] for it in items], weights=area))
    else:
        fields["days"], bag_fresh = 0.0, 0.0
    priced = decision["rule_id"] == 7
    TIMINGS["scan_total"] = {"shape": {"items": len(items)}, "seconds": time.perf_counter() - t_all}
    return {
        "rule_id": decision["rule_id"],
        "message": decision["message"],
        "fields": fields,
        "staff_alert": bool(decision["staff_alert"]),
        "review": bool(decision.get("review")),
        "failed_scans": int(decision["failed_scans"]),
        "price": {"weight_kg": float(weight_kg),
                  "price_per_kg": float(fields.get("price_per_kg", cfg.prices.get(selected_type, 0.0))),
                  "tier": decision["bag_tier"],
                  "discount": fields["discount_pct"] / 100 if priced else None,
                  "total": decision["price"]},
        "bag_freshness": decision["bag_freshness"] if decision["bag_freshness"] is not None else bag_fresh,
        "energy": max((it["energy"] for it in items), default=0.0),
        "thresholds": dict(cfg.rules["thresholds"]),
        "items": items,
        "simulated": False,
    }


# ---------------------------------------------------------------- on request
def ensure_forecast(result: dict | None, image: Image.Image | None) -> None:
    """Forecast images (+1, +3, +7 days) and the 4-point freshness curve for item #1, once per scan."""
    if not result or image is None or not result.get("items") or "forecasts" in result["items"][0]:
        return
    sess = models.load_models().sessions
    item = result["items"][0]
    crop = image.convert("RGB").crop(tuple(item["crop_box"]))
    t = time.perf_counter()
    x = np.asarray(_centre_crop(_resize_short(crop, 128), 128), dtype=np.float32) / 127.5 - 1.0
    batch = np.repeat(x.transpose(2, 0, 1)[None], len(FORECAST_DAYS), axis=0).astype(np.float32)
    days = np.array(FORECAST_DAYS, dtype=np.float32)
    future = sess["forecast"].run(["future"], {"image": batch, "days": days})[0]
    frames = [Image.fromarray(np.clip((f.transpose(1, 2, 0) + 1) * 127.5, 0, 255).round().astype(np.uint8))
              for f in future]
    graded = grade(sess["freshness"], [_fresh_unit(f) for f in frames])["freshness"]
    _timed("forecast", t, {"image": list(batch.shape), "days": list(days.shape), "future": list(future.shape),
                           "graded": list(graded.shape)})
    item["forecasts"] = dict(zip(FORECAST_DAYS, frames))
    item["curve"] = [float(item["freshness"])] + [float(v) for v in graded]
    item["curve_days"] = [0, *FORECAST_DAYS]


def _occlusion_heat(session, crop: Image.Image) -> np.ndarray:
    """Importance in [0, 1] at crop size: |freshness(occluded) - freshness(original)| per 28-px patch."""
    resized = _resize_short(crop, 256)
    unit = _fresh_unit(crop)
    copies = [unit]
    for r in range(OCC_GRID):
        for c in range(OCC_GRID):
            u = unit.copy()
            u[r * OCC_PATCH:(r + 1) * OCC_PATCH, c * OCC_PATCH:(c + 1) * OCC_PATCH] = OCC_GREY
            copies.append(u)
    fresh = grade(session, copies)["freshness"]
    grid = np.abs(fresh[1:] - fresh[0]).reshape(OCC_GRID, OCC_GRID).astype(np.float32)
    heat224 = cv2.resize(grid, (224, 224), interpolation=cv2.INTER_LINEAR)
    # map the 224 centre crop of the 256-short-side image back onto the crop
    scale = resized.size[0] / crop.size[0]
    left, top = _centre_offsets(*resized.size, 224)
    cw, ch = crop.size
    side = max(1, int(round(224 / scale)))
    x0, y0 = int(round(left / scale)), int(round(top / scale))
    heat = np.zeros((ch, cw), np.float32)
    patch = cv2.resize(heat224, (side, side), interpolation=cv2.INTER_LINEAR)
    heat[y0:y0 + side, x0:x0 + side] = patch[:max(0, min(side, ch - y0)), :max(0, min(side, cw - x0))]
    peak = float(heat.max())
    return heat / peak if peak > 0 else heat


def ensure_occlusion(result: dict | None, image: Image.Image | None) -> None:
    """Occlusion map per item (in place of Grad-CAM, which needs gradients ONNX does not have)."""
    if not result or image is None or result.get("simulated"):
        return
    todo = [it for it in result.get("items", []) if "gradcam" not in it]
    if not todo:
        return
    sess = models.load_models().sessions
    t = time.perf_counter()
    rgb_image = image.convert("RGB")
    for item in todo:
        cxy = item["crop_box"]
        heat = _occlusion_heat(sess["freshness"], rgb_image.crop(tuple(cxy)))
        x0, y0, x1, y1 = item["box"]
        heat = heat[y0 - cxy[1]:y1 - cxy[1], x0 - cxy[0]:x1 - cxy[0]]
        colour = cv2.applyColorMap((heat * 255).astype(np.uint8), cv2.COLORMAP_JET)[..., ::-1]
        item["gradcam"] = Image.fromarray(np.ascontiguousarray(colour))
        item["cam_alpha"] = OCC_ALPHA
    _timed("occlusion", t, {"items": len(todo), "batch_per_item": [1 + OCC_GRID ** 2, 3, 224, 224]})
