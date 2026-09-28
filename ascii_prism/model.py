"""Download and cache the MediaPipe models: the hand landmarker, and the
selfie segmenter the person lens uses."""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
SEGMENTER_URL = (
    "https://storage.googleapis.com/mediapipe-models/image_segmenter/"
    "selfie_segmenter/float16/latest/selfie_segmenter.tflite"
)
CACHE_DIR = Path.home() / ".cache" / "ascii-prism"


def _download(url: str, path: Path, min_size: int, what: str, log) -> Path:
    if path.exists() and path.stat().st_size > min_size:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    log(f"Downloading {what} to {path} ...")
    tmp = path.with_suffix(".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(path)
    log("Model ready.")
    return path


def model_path() -> Path:
    override = os.environ.get("ASCII_PRISM_MODEL")
    return Path(override) if override else CACHE_DIR / "hand_landmarker.task"


def ensure_model(log=print) -> Path:
    return _download(MODEL_URL, model_path(), 1_000_000, "hand model", log)


def segmenter_path() -> Path:
    override = os.environ.get("ASCII_PRISM_SEGMENTER")
    return Path(override) if override else CACHE_DIR / "selfie_segmenter.tflite"


def ensure_segmenter(log=print) -> Path:
    return _download(SEGMENTER_URL, segmenter_path(), 100_000, "segmentation model", log)
