"""User settings for the customizer, with JSON persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .charsets import DEFAULT_CHARSET_ID, by_id

COLUMNS_RANGE = (16, 200)
SMOOTHING_RANGE = (0.0, 0.95)
SATURATION_RANGE = (0.0, 2.0)
HUE_RANGE = (-180.0, 180.0)
BRIGHTNESS_RANGE = (0.5, 2.0)
OPACITY_RANGE = (0.0, 1.0)

RANGES: dict[str, tuple[float, float]] = {
    "columns": COLUMNS_RANGE,
    "smoothing": SMOOTHING_RANGE,
    "saturation": SATURATION_RANGE,
    "hue": HUE_RANGE,
    "brightness": BRIGHTNESS_RANGE,
    "opacity": OPACITY_RANGE,
}


def default_path() -> Path:
    return Path.home() / ".config" / "ascii-prism" / "settings.json"


@dataclass
class Settings:
    charset_id: str = DEFAULT_CHARSET_ID
    charset: str = by_id(DEFAULT_CHARSET_ID).chars
    columns: int = 80
    invert: bool = False
    # Colour grading of the sampled video colours, applied to every character.
    saturation: float = 1.0  # 0 is greyscale, 1 is the video as-is, 2 is twice as vivid
    hue: float = 0.0  # degrees of hue rotation
    brightness: float = 1.0  # gain on the sampled colours
    opacity: float = 1.0  # 1 covers the video completely, 0 lets it all through
    background: str = "#000000"
    smoothing: float = 0.6
    show_tips: bool = True
    mirror: bool = True

    def clamp(self) -> "Settings":
        for name, (lo, hi) in RANGES.items():
            setattr(self, name, min(hi, max(lo, getattr(self, name))))
        self.columns = int(self.columns)
        for name in ("saturation", "hue", "brightness", "opacity", "smoothing"):
            setattr(self, name, float(getattr(self, name)))
        if not self.charset:
            self.charset = " "
        return self

    def chars(self) -> list[str]:
        return list(self.charset) or [" "]

    def reset(self) -> None:
        for f in fields(Settings):
            setattr(self, f.name, f.default)

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or default_path()
        s = cls()
        try:
            data = json.loads(path.read_text())
            for f in fields(cls):
                if f.name in data and _matches(data[f.name], type(f.default)):
                    setattr(s, f.name, data[f.name])
        except (OSError, ValueError):
            pass
        return s.clamp()

    def save(self, path: Path | None = None) -> None:
        path = path or default_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self), indent=2))
        except OSError:
            pass


def _matches(value, expected: type) -> bool:
    """Type check for JSON values: ints are fine for floats, bools are not numbers."""
    if isinstance(value, bool):
        return expected is bool
    if expected is float:
        return isinstance(value, (int, float))
    return isinstance(value, expected)


def hex_to_bgr(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    if len(v) != 6:
        return (0, 0, 0)
    r, g, b = int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    return (b, g, r)
