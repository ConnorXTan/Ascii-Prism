"""User settings for the customizer, with JSON persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .charsets import DEFAULT_CHARSET_ID, by_id

COLUMNS_RANGE = (16, 200)
SMOOTHING_RANGE = (0.0, 0.95)
COLOR_MODES = ("sampled", "vivid", "mono")


def default_path() -> Path:
    return Path.home() / ".config" / "ascii-prism" / "settings.json"


@dataclass
class Settings:
    charset_id: str = DEFAULT_CHARSET_ID
    charset: str = by_id(DEFAULT_CHARSET_ID).chars
    columns: int = 80
    color_mode: str = "sampled"
    ink: str = "#7cff6b"
    background: str = "#000000"
    invert: bool = False
    smoothing: float = 0.6
    show_tips: bool = True
    mirror: bool = True

    def clamp(self) -> "Settings":
        self.columns = int(min(COLUMNS_RANGE[1], max(COLUMNS_RANGE[0], self.columns)))
        self.smoothing = float(min(SMOOTHING_RANGE[1], max(SMOOTHING_RANGE[0], self.smoothing)))
        if self.color_mode not in COLOR_MODES:
            self.color_mode = "sampled"
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
                if f.name in data and isinstance(data[f.name], type(f.default)):
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


def hex_to_bgr(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    if len(v) != 6:
        return (0, 0, 0)
    r, g, b = int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    return (b, g, r)
