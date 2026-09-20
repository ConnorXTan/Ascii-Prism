"""Download and cache the MediaPipe hand landmarker model."""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)


def model_path() -> Path:
    override = os.environ.get("ASCII_PRISM_MODEL")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "ascii-prism" / "hand_landmarker.task"


def ensure_model(log=print) -> Path:
    path = model_path()
    if path.exists() and path.stat().st_size > 1_000_000:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    log(f"Downloading hand model to {path} ...")
    tmp = path.with_suffix(".part")
    urllib.request.urlretrieve(MODEL_URL, tmp)
    tmp.replace(path)
    log("Model ready.")
    return path
