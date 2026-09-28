"""Glyph atlas and character grid sizing.

The flat character grid is composed with NumPy from a glyph atlas (coverage
masks rendered with Pillow from a monospace font). `AsciiRenderer` owns the
font, the atlas cache and the grid sizing that every character lens shares;
the warp into the fingertip quad lives in `warp.py` and the looks in
`lenses/`.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .geometry import quad_size
from .settings import Settings

MAX_ROWS = 400
PROBE_SIZE = 100

FONT_CANDIDATES = {
    "darwin": [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
    ],
    "linux": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ],
    "win32": [
        r"C:\Windows\Fonts\consola.ttf",
        r"C:\Windows\Fonts\cour.ttf",
    ],
}


def find_font(explicit: str | None = None) -> str | None:
    """Return a path to a monospace TrueType font, or None if none is found."""
    if explicit:
        return explicit if os.path.exists(explicit) else None
    platform = "darwin" if sys.platform == "darwin" else "win32" if sys.platform.startswith("win") else "linux"
    for candidate in FONT_CANDIDATES[platform]:
        if os.path.exists(candidate):
            return candidate
    return None


def _load_font(font_path: str | None, size: float) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_path:
        return ImageFont.truetype(font_path, max(1, int(round(size))))
    return ImageFont.load_default()


class GlyphAtlas:
    """Coverage masks (0..1) for each character of a ramp at one glyph height.

    The font size is chosen so a full block character exactly fills a cell,
    which keeps block ramps seamless and lets dense glyphs fill their cell the
    way they do in a terminal. The cell width follows the font's own block
    proportions.
    """

    def __init__(self, font_path: str | None, chars: list[str], glyph_h: int):
        self.glyph_h = glyph_h
        probe = _load_font(font_path, PROBE_SIZE)
        bx0, by0, bx1, by1 = probe.getbbox("\u2588")
        block_h = max(1, by1 - by0)
        # Size the font so the block glyph overflows the cell by about a pixel
        # on every side; the cell clips it, so edges are always fully covered
        # and block ramps have no seams. Text is positioned on whole pixels.
        font_size = PROBE_SIZE * (glyph_h + 2) / block_h
        font = _load_font(font_path, font_size)
        fx0, fy0, fx1, fy1 = font.getbbox("\u2588")
        fitted_w, fitted_h = fx1 - fx0, fy1 - fy0
        self.glyph_w = max(3, int(fitted_w) - 2)
        ox = int(round((self.glyph_w - fitted_w) / 2)) - fx0
        oy = int(round((glyph_h - fitted_h) / 2)) - fy0

        masks = np.zeros((len(chars), glyph_h, self.glyph_w), dtype=np.float32)
        for i, ch in enumerate(chars):
            img = Image.new("L", (self.glyph_w, glyph_h), 0)
            ImageDraw.Draw(img).text((ox, oy), ch, font=font, fill=255)
            masks[i] = np.asarray(img, dtype=np.float32) / 255.0
        self.coverage = masks


def measure_cell_aspect(font_path: str | None) -> float:
    """Width / height of a character cell for this font."""
    probe = _load_font(font_path, PROBE_SIZE)
    x0, y0, x1, y1 = probe.getbbox("\u2588")
    return max(0.2, min(1.0, (x1 - x0) / max(1, (y1 - y0))))


@dataclass
class RegionInfo:
    cols: int
    rows: int
    glyph_w: int
    glyph_h: int


class AsciiRenderer:
    def __init__(self, font_path: str | None = None, min_glyph_h: int = 6, max_glyph_h: int = 48):
        self.font_path = font_path
        self.cell_aspect = measure_cell_aspect(font_path)
        self.min_glyph_h = min_glyph_h
        self.max_glyph_h = max_glyph_h
        self._atlases: dict[tuple[str, int], GlyphAtlas] = {}

    def grid_for(self, quad, columns: int, frame_w: int, frame_h: int) -> tuple[int, int] | None:
        """Character grid (cols, rows) for a quad, or None if the quad is too small."""
        width, height = quad_size(quad)
        if width < frame_w * 0.03 or height < frame_h * 0.03:
            return None
        rows = int(round(columns * (height / width) * self.cell_aspect))
        return columns, max(1, min(MAX_ROWS, rows))

    def atlas(self, chars: list[str], glyph_h: int) -> GlyphAtlas:
        key = ("".join(chars), glyph_h)
        atlas = self._atlases.get(key)
        if atlas is None:
            if len(self._atlases) > 24:
                self._atlases.clear()
            atlas = GlyphAtlas(self.font_path, chars, glyph_h)
            self._atlases[key] = atlas
        return atlas

    def render(self, frame: np.ndarray, quad, settings: Settings) -> RegionInfo | None:
        """Replace the quad's interior in `frame` (BGR, modified in place) with ASCII.

        A shortcut for callers that only want the default lens; the pipeline
        goes through `lenses` so any lens can be active.
        """
        from .lenses import LensContext, render_lens
        from .lenses.ascii import AsciiLens

        ctx = LensContext(frame, 0, 0.0, self, lambda _seconds: None)
        drawn, region = render_lens(AsciiLens(), frame, quad, settings, ctx)
        return region if drawn else None
