"""ASCII rendering of a warped region.

The flat character grid is composed with NumPy from a glyph atlas (coverage
masks rendered with Pillow from a monospace font), then mapped with a
bilinear warp into the fingertip quadrilateral and pasted over the live
frame. A bilinear map, unlike a perspective one, also handles a twisted quad
(edges crossing when one hand is flipped), which renders as a folded ribbon.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .geometry import bilinear_map, inverse_bilinear, quad_size
from .grading import blend, grade
from .settings import Settings, hex_to_bgr

MAX_ROWS = 400
SUPERSAMPLE = 3  # video samples per cell edge when averaging cell colours
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
        """Replace the quad's interior in `frame` (BGR, modified in place) with ASCII."""
        frame_h, frame_w = frame.shape[:2]
        grid = self.grid_for(quad, settings.columns, frame_w, frame_h)
        if grid is None:
            return None
        cols, rows = grid
        _, height = quad_size(quad)
        glyph_h = int(min(self.max_glyph_h, max(self.min_glyph_h, round(height / rows))))
        chars = settings.chars()
        atlas = self.atlas(chars, glyph_h)
        glyph_w = atlas.glyph_w

        # Average video colour per cell: sample the quad onto a small flat image.
        sw, sh = cols * SUPERSAMPLE, rows * SUPERSAMPLE
        us = (np.arange(sw, dtype=np.float64) + 0.5) / sw
        vs = (np.arange(sh, dtype=np.float64) + 0.5) / sh
        sx, sy = bilinear_map(quad, us[None, :], vs[:, None])
        small = cv2.remap(frame, sx.astype(np.float32), sy.astype(np.float32), cv2.INTER_LINEAR)
        cells = cv2.resize(small, (cols, rows), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0

        lum = cells[..., 0] * 0.0722 + cells[..., 1] * 0.7152 + cells[..., 2] * 0.2126
        if settings.invert:
            lum = 1.0 - lum
        n = len(chars)
        idx = np.clip((lum * n).astype(np.int32), 0, n - 1)

        ink = grade(cells, settings)
        background = np.array(hex_to_bgr(settings.background), dtype=np.float32) / 255.0

        # Compose the flat character image.
        cov = atlas.coverage[idx]  # (rows, cols, gh, gw)
        cov = cov.transpose(0, 2, 1, 3).reshape(rows * glyph_h, cols * glyph_w, 1)
        ink_big = np.repeat(np.repeat(ink, glyph_h, axis=0), glyph_w, axis=1)
        flat = background + (ink_big - background) * cov
        flat = (flat * 255.0 + 0.5).astype(np.uint8)

        # Warp it into the quad and paste over the frame. Only the quad's
        # bounding box is touched; pixels outside the (possibly twisted)
        # surface are left alone.
        fh, fw = flat.shape[:2]
        q = np.asarray(quad, dtype=np.float64)
        x0 = int(max(0, np.floor(q[:, 0].min())))
        y0 = int(max(0, np.floor(q[:, 1].min())))
        x1 = int(min(frame_w, np.ceil(q[:, 0].max()) + 1))
        y1 = int(min(frame_h, np.ceil(q[:, 1].max()) + 1))
        if x1 <= x0 or y1 <= y0:
            return None
        px = np.arange(x0, x1, dtype=np.float64) + 0.5
        py = np.arange(y0, y1, dtype=np.float64) + 0.5
        u, v, valid = inverse_bilinear(quad, px[None, :], py[:, None])
        map_x = (np.nan_to_num(u) * fw - 0.5).astype(np.float32)
        map_y = (np.nan_to_num(v) * fh - 0.5).astype(np.float32)
        warped = cv2.remap(flat, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        region = frame[y0:y1, x0:x1]
        np.copyto(region, blend(region, warped, settings.opacity), where=valid[:, :, None])
        return RegionInfo(cols, rows, glyph_w, glyph_h)
