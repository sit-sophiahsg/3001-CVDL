"""Produce quality predictor - the ONLY file the real model will replace.

HOW TO SWAP IN THE REAL MODEL
-----------------------------
1. Export the trained model to ONNX (e.g. models/produce.onnx) and add
   `onnxruntime` to requirements.txt.
2. Replace the FakePredictor below with something like:

       import numpy as np
       import onnxruntime as ort
       import streamlit as st

       IS_DEMO = False  # hides the demo banner and sidebar demo controls

       @st.cache_resource  # load the session once per server, not on every rerun
       def _load_session() -> ort.InferenceSession:
           return ort.InferenceSession("models/produce.onnx",
                                       providers=["CPUExecutionProvider"])

       def predict(image, selected_id):
           x = preprocess(image)  # resize, normalise, HWC->NCHW float32, same as training
           produce_logits, fresh_logits = _load_session().run(None, {"input": x})
           ...  # softmax, map class index -> produce id, threshold for valid_scan
           return {"valid_scan": ..., "produce_id": ..., "produce_confidence": ...,
                   "status": "Fresh" or "Rotten", "fresh_probability": ...,
                   "defect_percent": None}

3. Keep the `predict(image, selected_id) -> dict` signature and the returned keys
   exactly as documented below; app.py relies on nothing else. `IS_DEMO`,
   `DEMO_OUTCOMES` and `set_demo_override` are optional and can be deleted.

Return value of predict():
    valid_scan          bool   False if the photo does not show recognisable produce
    produce_id          str    id from config.yaml of the produce the model sees
    produce_confidence  float  0-1, probability of that produce class
    status              str    "Fresh" or "Rotten"
    fresh_probability   float  0-1, model probability of Fresh (shown as "Model confidence")
    defect_percent      None   reserved for a future segmentation model (% area defective)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from PIL import Image

IS_DEMO = True
DEMO_OUTCOMES = ("Auto", "Fresh", "Rotten", "Invalid scan", "Mismatch")

_CONFIG_PATH = Path(__file__).with_name("config.yaml")


class FakePredictor:
    """Deterministic stand-in: the same photo always gives the same result."""

    def __init__(self, produce_ids: list[str]):
        self.produce_ids = produce_ids
        self.force = "Auto"

    def predict(self, image: Image.Image, selected_id: str) -> dict:
        digest = hashlib.sha256(image.tobytes() + repr(image.size).encode()).digest()
        u = [b / 255 for b in digest[:8]]  # stable pseudo-random numbers in [0, 1]

        outcome = self.force
        if outcome == "Auto":
            fresh_p = 0.02 + 0.96 * u[3]
            if u[0] < 0.10:
                outcome = "Invalid scan"
            elif u[1] < 0.10:
                outcome = "Mismatch"
            else:
                outcome = "Fresh" if fresh_p >= 0.5 else "Rotten"
        elif outcome == "Fresh":
            fresh_p = 0.55 + 0.44 * u[3]
        else:
            fresh_p = 0.02 + 0.43 * u[3]

        produce_id = selected_id
        if outcome == "Mismatch":
            others = [p for p in self.produce_ids if p != selected_id] or [selected_id]
            produce_id = others[digest[2] % len(others)]

        return {
            "valid_scan": outcome != "Invalid scan",
            "produce_id": produce_id,
            "produce_confidence": round(0.80 + 0.19 * u[4], 4)
            if outcome != "Invalid scan" else round(0.10 + 0.25 * u[4], 4),
            "status": "Fresh" if fresh_p >= 0.5 else "Rotten",
            "fresh_probability": round(fresh_p, 4),
            "defect_percent": None,
        }


_predictor: FakePredictor | None = None


def _get_predictor() -> FakePredictor:
    global _predictor
    if _predictor is None:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        ids = [p["id"] for p in config["produce"] if p.get("enabled", True)]
        _predictor = FakePredictor(ids)
    return _predictor


def set_demo_override(outcome: str) -> None:
    """Force the next prediction's outcome (demo rehearsal only)."""
    if outcome not in DEMO_OUTCOMES:
        raise ValueError(f"Unknown demo outcome: {outcome!r}")
    _get_predictor().force = outcome


def predict(image: Image.Image, selected_id: str) -> dict:
    return _get_predictor().predict(image, selected_id)
