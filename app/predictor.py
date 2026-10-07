"""Produce quality predictor - real ONNX model (AAI3001 P1-9, Phase 1).

Drop-in replacement for the FakePredictor version: same `predict(image, selected_id) -> dict`
signature and the same returned keys, so app.py needs no changes.

Files expected next to this file:
    models/best_config.json      written by the export cell in Colab
    models/produce_int8.onnx     (used if present and PREFER_INT8 is True)
    models/produce_fp32.onnx

Extra requirements:  onnxruntime, numpy  (no PyTorch needed)

Return value of predict():
    valid_scan          bool   False if the photo does not look like the training data
    produce_id          str    id from config.yaml of the produce the model sees
    produce_confidence  float  0-1, probability of that produce class
    status              str    "Fresh" or "Rotten"
    fresh_probability   float  0-1, model probability of Fresh (shown as "Model confidence")
    defect_percent      None   reserved for a future segmentation model (% area defective)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
import streamlit as st
import yaml
from PIL import Image

IS_DEMO = False  # hides the demo banner and the sidebar demo controls

_HERE = Path(__file__).parent
MODEL_DIR = _HERE / "models"
MODEL_CONFIG = MODEL_DIR / "best_config.json"
APP_CONFIG = _HERE / "config.yaml"
PREFER_INT8 = False  # INT8 is 4x smaller but less accurate (val stage acc 98.6% vs 99.4%)

# Model class name -> produce id in config.yaml, only where the two differ.
# Model classes: apple, banana, bitter_gourd, capsicum, cucumber, okra, orange, potato, tomato
ID_ALIASES: dict[str, str] = {
    # "bitter_gourd": "bittergourd",
}


def _app_id(model_class: str) -> str:
    return ID_ALIASES.get(model_class, model_class)


def _check_ids(model_classes: list[str]) -> None:
    """Print a warning if a model class has no matching item in config.yaml."""
    try:
        with open(APP_CONFIG, encoding="utf-8") as f:
            app_ids = {p["id"] for p in yaml.safe_load(f)["produce"]}
    except (OSError, KeyError, TypeError):
        return
    missing = [c for c in model_classes if _app_id(c) not in app_ids]
    if missing:
        print(f"[predictor] WARNING: model classes with no item in config.yaml: {missing}. "
              f"Add them to config.yaml or map them in ID_ALIASES.")


@st.cache_resource  # load once per server, not on every rerun
def _load() -> tuple[ort.InferenceSession, dict, str]:
    if not MODEL_CONFIG.exists():
        raise FileNotFoundError(
            f"{MODEL_CONFIG} not found. Download the 'deploy' folder from Google Drive "
            f"and put its files in {MODEL_DIR}.")
    cfg = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    files = cfg["onnx"]
    name = files["fp32"]
    if PREFER_INT8 and files.get("int8") and (MODEL_DIR / files["int8"]).exists():
        name = files["int8"]
    session = ort.InferenceSession(str(MODEL_DIR / name), providers=["CPUExecutionProvider"])
    _check_ids(cfg["produce_classes"])
    print(f"[predictor] loaded {name} ({cfg['backbone']}, val F1 {cfg['val_stage_f1']:.4f})")
    return session, cfg, name


def preprocess(image: Image.Image, cfg: dict) -> np.ndarray:
    """Exactly the validation transform used in training:
    shorter side -> 255 (bilinear), centre crop 224, /255, ImageNet mean/std, HWC -> NCHW."""
    p = cfg["preprocess"]
    img = image.convert("RGB")
    w, h = img.size
    short = p["resize_shorter_side"]
    if w <= h:
        new_w, new_h = short, int(short * h / w)
    else:
        new_w, new_h = int(short * w / h), short
    img = img.resize((new_w, new_h), Image.BILINEAR)

    crop = p["center_crop"]
    left = int(round((new_w - crop) / 2.0))
    top = int(round((new_h - crop) / 2.0))
    img = img.crop((left, top, left + crop, top + crop))

    x = np.asarray(img, dtype=np.float32) / 255.0
    x = (x - np.asarray(p["mean"], dtype=np.float32)) / np.asarray(p["std"], dtype=np.float32)
    return x.transpose(2, 0, 1)[None].astype(np.float32)  # (1, 3, 224, 224)


def _energy(logits: np.ndarray) -> float:
    """-logsumexp(logits): lower = more like the training data."""
    m = float(logits.max())
    return -(m + float(np.log(np.exp(logits - m).sum())))


def predict(image: Image.Image, selected_id: str) -> dict:
    session, cfg, _ = _load()
    x = preprocess(image, cfg)
    produce_probs, stage_probs, produce_logits = session.run(None, {cfg["onnx"]["input"]: x})
    pp, sp = produce_probs[0], stage_probs[0]
    pl = produce_logits[0].astype(np.float64)

    thr = cfg["valid_scan"]
    valid = _energy(pl) <= thr["energy_thr"] and float(sp.max()) >= thr["stage_conf_thr"]

    stages = cfg["stage_classes"]
    i = int(pp.argmax())
    return {
        "valid_scan": bool(valid),
        "produce_id": _app_id(cfg["produce_classes"][i]),
        "produce_confidence": round(float(pp[i]), 4),
        "status": stages[int(sp.argmax())],
        "fresh_probability": round(float(sp[stages.index("Fresh")]), 4),
        "defect_percent": None,
    }
