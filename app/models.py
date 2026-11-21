"""The trained model bundle: download it from the Hugging Face Hub and open one ONNX session per model.

The bundle is read, not guessed: ``deploy_config.json`` names the files, the class order and each
model's input/output names and shapes, and every session is checked against it before use.

Environment variables
    FRESHMART_MODELS_REPO      Hub model repo (default ``sophiahsgsit/freshmart-models``)
    FRESHMART_MODELS_REVISION  optional commit / tag to pin
    FRESHMART_MODELS_DIR       if this folder exists, load from it instead (offline use)
"""

from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = "sophiahsgsit/freshmart-models"
CONFIG_NAME = "deploy_config.json"
MODEL_KEYS = ("detector", "freshness", "blemish", "forecast")


def _load_scale_pricing():
    """The notebook's rule engine (src/pricing.py), imported by path under its own name."""
    spec = importlib.util.spec_from_file_location("scale_pricing", ROOT / "src" / "pricing.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scale_pricing = _load_scale_pricing()


# ---------------------------------------------------------------- download
def _repo() -> str:
    return os.environ.get("FRESHMART_MODELS_REPO") or DEFAULT_REPO


def _local_dir() -> Path | None:
    folder = os.environ.get("FRESHMART_MODELS_DIR")
    return Path(folder) if folder and Path(folder).is_dir() else None


def bundle_files(deploy: dict, include_models: bool = True) -> list[str]:
    """Every file the app needs: the model files named in deploy_config, plus the configs."""
    names = list(deploy.get("configs") or ["rules.yaml", "prices.csv", "fresh_residuals.npz"])
    if include_models:
        names = [deploy["files"][key] for key in MODEL_KEYS] + names
    return names


def download_bundle(include_models: bool = True, revision: str | None = None) -> Path:
    """Folder holding deploy_config.json and the bundle files (downloaded to the HF cache if needed).

    All files come from the same commit: deploy_config.json is fetched first and the rest are
    pinned to the snapshot it landed in.
    """
    local = _local_dir()
    if local is not None:
        return local
    from huggingface_hub import hf_hub_download

    repo, revision = _repo(), revision or os.environ.get("FRESHMART_MODELS_REVISION") or None
    config_path = Path(hf_hub_download(repo, CONFIG_NAME, revision=revision))
    folder = config_path.parent                     # .../snapshots/<commit>/
    commit = folder.name
    deploy = json.loads(config_path.read_text(encoding="utf-8"))
    for name in bundle_files(deploy, include_models):
        hf_hub_download(repo, name, revision=commit)
    return folder


# ---------------------------------------------------------------- config (small files)
@dataclass
class Config:
    folder: Path
    deploy: dict
    classes: list[str]
    rules: dict
    prices: dict[str, float]
    residuals: Any


@st.cache_resource(show_spinner=False)
def load_config() -> Config:
    """deploy_config.json, rules.yaml, prices.csv and fresh_residuals.npz (no ONNX files)."""
    folder = download_bundle(include_models=False)
    deploy = json.loads((folder / CONFIG_NAME).read_text(encoding="utf-8"))
    rules, prices, residuals = scale_pricing.load(folder)
    return Config(folder, deploy, list(deploy["produce_classes"]), rules,
                  {k: float(v) for k, v in prices.items()}, residuals)


# ---------------------------------------------------------------- sessions
def _check_io(name: str, session, spec: dict) -> None:
    """Names must match deploy_config exactly; fixed dimensions must match where both sides are fixed."""
    for kind, actual in (("inputs", session.get_inputs()), ("outputs", session.get_outputs())):
        expected = spec[kind]
        got = [(node.name, list(node.shape)) for node in actual]
        if [n for n, _ in got] != [n for n, _ in expected]:
            raise RuntimeError(f"{name}: {kind} {got} do not match deploy_config {expected}")
        for (node, shape), (_, want) in zip(got, expected):
            if len(shape) != len(want) or any(isinstance(a, int) and isinstance(b, int) and a != b
                                               for a, b in zip(shape, want)):
                raise RuntimeError(f"{name}: {kind[:-1]} {node} shape {shape} != deploy_config {want}")


@dataclass
class Models:
    config: Config
    sessions: dict


@st.cache_resource(show_spinner=False)
def load_models() -> Models:
    """One CPU InferenceSession per FP32 model, checked against deploy_config['io']. Never the INT8 files."""
    import onnxruntime as ort

    config = load_config()
    folder = download_bundle(include_models=True,
                             revision=None if _local_dir() else config.folder.name)  # same commit as the config
    deploy = json.loads((folder / CONFIG_NAME).read_text(encoding="utf-8"))
    options = ort.SessionOptions()
    options.log_severity_level = 3
    sessions = {}
    for key in MODEL_KEYS:
        filename = deploy["files"][key]
        if "int8" in filename.lower():
            raise RuntimeError(f"{key}: refusing to load {filename} (INT8 files were rejected on validation)")
        session = ort.InferenceSession(str(folder / filename), options, providers=["CPUExecutionProvider"])
        _check_io(key, session, deploy["io"][key])
        sessions[key] = session
    return Models(config, sessions)
