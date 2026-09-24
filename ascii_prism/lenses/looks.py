"""Lens looks: what the fingertip window can show instead of live ASCII.

Every look is a pure function of a flat image: the window's contents as a
(h, w, 3) BGR uint8 array in (from `warp.sample_quad`), a flat BGR uint8
array out (for `warp.paste_quad`). The looks know nothing about the quad,
the pipeline or the settings, which keeps them easy to tune on a still with
tools/lens_sheet.py. The `Lens` classes from docs/plans/lenses.md wrap them.

Pixel looks (thermal, gameboy, sketch, night) want the quad sampled at about
its own pixel size, capped around 480 px wide; glyph looks want the
supersampled cell grid from `Grid.sample_size`.
"""

from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..ascii import AsciiRenderer
from ..geometry import quad_size

LUMA = np.array([0.0722, 0.7152, 0.2126], dtype=np.float32)  # BGR weights
SUPERSAMPLE = 3  # video samples per cell edge when averaging cell colours
DEFAULT_CHARS = " .:-=+*#%@"


def luminance(flat: np.ndarray) -> np.ndarray:
    """Per-pixel luminance in 0..1 of a BGR uint8 image."""
    return (flat.astype(np.float32) / 255.0) @ LUMA


def to_u8(x: np.ndarray) -> np.ndarray:
    return (np.clip(x, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


# --------------------------------------------------------------- grid

@dataclass
class Grid:
    cols: int
    rows: int
    glyph_w: int
    glyph_h: int

    @property
    def sample_size(self) -> tuple[int, int]:
        """(w, h) to sample the quad at for a glyph look."""
        return self.cols * SUPERSAMPLE, self.rows * SUPERSAMPLE


def grid_for(renderer: AsciiRenderer, quad, columns: int, frame_w: int, frame_h: int) -> Grid | None:
    """Cell grid and glyph size for a quad, sized as `AsciiRenderer.render` does."""
    grid = renderer.grid_for(quad, columns, frame_w, frame_h)
    if grid is None:
        return None
    cols, rows = grid
    _, height = quad_size(quad)
    glyph_h = int(min(renderer.max_glyph_h, max(renderer.min_glyph_h, round(height / rows))))
    return Grid(cols, rows, renderer.atlas([" "], glyph_h).glyph_w, glyph_h)


def cells_from(sampled: np.ndarray, grid: Grid) -> np.ndarray:
    """Average colour per cell, (rows, cols, 3) float32 in 0..1."""
    return cv2.resize(sampled, (grid.cols, grid.rows), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def compose(coverage: np.ndarray, idx: np.ndarray, ink: np.ndarray, background) -> np.ndarray:
    """Paint one glyph per cell from an atlas' coverage masks.

    `idx` (rows, cols) picks each cell's glyph, `ink` (rows, cols, 3) gives
    its colour in 0..1, `background` is a BGR triple in 0..255.
    """
    rows, cols = idx.shape
    gh, gw = coverage.shape[1:]
    cov = coverage[idx].transpose(0, 2, 1, 3).reshape(rows * gh, cols * gw, 1)
    ink_big = np.repeat(np.repeat(ink, gh, axis=0), gw, axis=1)
    bg = np.asarray(background, dtype=np.float32) / 255.0
    return to_u8(bg + (ink_big - bg) * cov)


# -------------------------------------------------------------- ascii

def ascii_glyphs(cells: np.ndarray, grid: Grid, renderer: AsciiRenderer, chars: str = DEFAULT_CHARS,
                 ink: np.ndarray | None = None, invert: bool = False, background=(0, 0, 0)) -> np.ndarray:
    """Today's look from precomputed cells: a glyph per cell picked by
    luminance, drawn in `ink` (default: the cell's own colour)."""
    lum = cells @ LUMA
    if invert:
        lum = 1.0 - lum
    n = max(1, len(chars))
    idx = np.clip((lum * n).astype(np.int32), 0, n - 1)
    atlas = renderer.atlas(list(chars) or [" "], grid.glyph_h)
    return compose(atlas.coverage, idx, cells if ink is None else ink, background)


def ascii_look(sampled: np.ndarray, grid: Grid, renderer: AsciiRenderer, chars: str = DEFAULT_CHARS,
               invert: bool = False, background=(0, 0, 0)) -> np.ndarray:
    return ascii_glyphs(cells_from(sampled, grid), grid, renderer, chars, None, invert, background)


# ------------------------------------------------------------ thermal

def thermal(flat: np.ndarray, sensor_w: int = 160, skin: float = 0.5) -> np.ndarray:
    """False-colour heat camera.

    Heat is luminance pushed by red-over-blue, so skin reads hotter than a
    white shirt. A low-resolution sensor pass (downscale, blur, upscale)
    gives the soft thermal-camera blur, then the INFERNO colormap.
    """
    h, w = flat.shape[:2]
    f = flat.astype(np.float32) / 255.0
    warmth = np.clip(f[..., 2] - f[..., 0], 0.0, 1.0)
    heat = (f @ LUMA) * (1.0 - skin) + warmth * skin * 2.0
    sw = min(w, sensor_w)
    sh = max(1, int(round(h * sw / w)))
    small = cv2.resize(heat, (sw, sh), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), 0.8)
    small = np.clip((small - 0.05) / 0.75, 0.0, 1.0)
    big = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
    return cv2.applyColorMap(to_u8(big), cv2.COLORMAP_INFERNO)


# ------------------------------------------------------------ gameboy

GB_PALETTE = np.array([[15, 56, 15], [48, 98, 48], [139, 172, 15], [155, 188, 15]], dtype=np.uint8)[:, ::-1]  # BGR
BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32) / 16.0


def gameboy(flat: np.ndarray, screen_w: int = 160) -> np.ndarray:
    """Four-tone handheld: 160 px wide, 4x4 ordered dither, chunky pixels."""
    h, w = flat.shape[:2]
    sw = min(w, screen_w)
    sh = max(1, int(round(h * sw / w)))
    lum = cv2.resize(luminance(flat), (sw, sh), interpolation=cv2.INTER_AREA)
    lum = np.clip((lum - 0.04) / 0.85, 0.0, 1.0) ** 0.9
    thresh = np.tile(BAYER4, (sh // 4 + 1, sw // 4 + 1))[:sh, :sw]
    level = np.clip(np.floor(lum * 3.0 + thresh), 0, 3).astype(np.int32)
    return cv2.resize(GB_PALETTE[level], (w, h), interpolation=cv2.INTER_NEAREST)


# ------------------------------------------------------------- sketch

SKETCH_PAPER = np.array([0.86, 0.92, 0.96], dtype=np.float32)  # BGR, warm white
SKETCH_GRAPHITE = np.array([0.20, 0.19, 0.18], dtype=np.float32)


def sketch(flat: np.ndarray, sigma_frac: float = 0.018, grain: float = 0.04, rng=None) -> np.ndarray:
    """Pencil on paper: colour-dodge of grey over its blurred inverse, deepened,
    on a warm paper tint with a little grain so flat areas are not dead white."""
    h, w = flat.shape[:2]
    grey = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(255 - grey, (0, 0), max(1.0, sigma_frac * w))
    dodge = cv2.divide(grey, 255 - blur, scale=256).astype(np.float32) / 255.0
    strokes = np.clip(dodge, 0.0, 1.0) ** 2.8
    if rng is not None and grain > 0:
        strokes = strokes + rng.normal(0.0, grain, strokes.shape).astype(np.float32)
    mix = np.clip(strokes, 0.0, 1.0)[..., None]
    return to_u8(SKETCH_GRAPHITE + (SKETCH_PAPER - SKETCH_GRAPHITE) * mix)


# -------------------------------------------------------------- night

NIGHT_PHOSPHOR = np.array([0.28, 1.0, 0.42], dtype=np.float32)  # BGR


def night(flat: np.ndarray, rng, gain: float = 2.2, grain: float = 0.07) -> np.ndarray:
    """Night-vision goggles: soft-knee gain, phosphor green, grain, a
    vignette, faint scanlines and a white bloom on the brightest spots."""
    h, w = flat.shape[:2]
    lum = 1.0 - np.exp(-luminance(flat) * gain)
    lum = lum + rng.normal(0.0, grain, lum.shape).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
    lum = lum * np.clip(1.0 - 0.6 * r ** 2.4, 0.0, 1.0)
    lum[1::3] *= 0.82
    lum = np.clip(lum, 0.0, 1.0)
    out = lum[..., None] * NIGHT_PHOSPHOR
    bloom = cv2.GaussianBlur(lum ** 4, (0, 0), max(1.0, 0.01 * w))
    return to_u8(out + bloom[..., None] * 0.6)


# ------------------------------------------------------------ kaleido

def kaleido_remap(flat: np.ndarray, folds: int = 6, aim: float = -2.35) -> np.ndarray:
    """Fold the window into `folds` mirrored wedges around its centre.

    `aim` is the direction (radians, y down) of the source wedge. The default
    points up and left, where an eye tends to be when the window is held in
    front of a face.
    """
    h, w = flat.shape[:2]
    u = (np.arange(w, dtype=np.float32) + 0.5) / w - 0.5
    v = (np.arange(h, dtype=np.float32) + 0.5) / h - 0.5
    x, y = np.meshgrid(u, v)
    r = np.hypot(x, y)
    a = np.arctan2(y, x)
    sector = 2.0 * np.pi / folds
    a = np.mod(a, sector)
    a = np.where(a > sector / 2, sector - a, a) + aim
    xs = (0.5 + r * np.cos(a)) * w - 0.5
    ys = (0.5 + r * np.sin(a)) * h - 0.5
    return cv2.remap(flat, xs.astype(np.float32), ys.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def mirror_remap(flat: np.ndarray) -> np.ndarray:
    """The window's top-left quarter reflected into all four quarters."""
    h, w = flat.shape[:2]
    x = np.arange(w, dtype=np.float32)
    y = np.arange(h, dtype=np.float32)
    xs = np.minimum(x, (w - 1) - x)[None, :].repeat(h, 0)
    ys = np.minimum(y, (h - 1) - y)[:, None].repeat(w, 1)
    return cv2.remap(flat, xs, ys, cv2.INTER_LINEAR)


# --------------------------------------------------------------- rain

HALFWIDTH_KATAKANA = "".join(chr(c) for c in range(0xFF71, 0xFF9E)) + "0123456789"
RAIN_LATIN = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ:=*+-<>|"
RAIN_GREEN = np.array([0.30, 1.0, 0.45], dtype=np.float32)  # BGR
RAIN_WHITE = np.array([0.85, 1.0, 0.90], dtype=np.float32)

# Menlo, Monaco and Courier New draw half-width katakana as tofu, so the
# rain look needs a CJK font of its own.
RAIN_FONT_CANDIDATES = [
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    r"C:\Windows\Fonts\msgothic.ttc",
    r"C:\Windows\Fonts\meiryo.ttc",
]


def find_rain_font() -> str | None:
    for path in RAIN_FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def rain_glyphs(fallback_font: str | None) -> tuple[str, str | None]:
    """(chars, font path) for the rain: katakana when a font can draw it,
    otherwise Latin in the renderer's own font."""
    font = find_rain_font()
    return (HALFWIDTH_KATAKANA, font) if font else (RAIN_LATIN, fallback_font)


class FixedCellAtlas:
    """Coverage masks for characters drawn into a cell of a given size.

    `GlyphAtlas` sizes the cell from the font's block glyph, which is right
    for monospace fonts. CJK fonts have a full-width block, so this atlas
    takes the cell size from outside and scales the glyphs to fill `fill` of
    its height instead.
    """

    def __init__(self, font_path: str | None, chars: list[str], glyph_h: int, glyph_w: int, fill: float = 0.78):
        self.glyph_h, self.glyph_w = glyph_h, glyph_w
        font = self._font(font_path, 100)
        x0, y0, x1, y1 = font.getbbox("".join(chars[:8]))
        font = self._font(font_path, 100 * (glyph_h * fill) / max(1, y1 - y0))
        masks = np.zeros((len(chars), glyph_h, glyph_w), dtype=np.float32)
        for i, ch in enumerate(chars):
            bx0, by0, bx1, by1 = font.getbbox(ch)
            ox = (glyph_w - (bx1 - bx0)) / 2 - bx0
            oy = (glyph_h - (by1 - by0)) / 2 - by0
            img = Image.new("L", (glyph_w, glyph_h), 0)
            ImageDraw.Draw(img).text((ox, oy), ch, font=font, fill=255)
            masks[i] = np.asarray(img, dtype=np.float32) / 255.0
        self.coverage = masks

    @staticmethod
    def _font(path: str | None, size: float):
        size = max(1, int(round(size)))
        if path:
            return ImageFont.truetype(path, size)
        try:
            return ImageFont.load_default(size)
        except TypeError:  # older Pillow
            return ImageFont.load_default()


class Rain:
    """Matrix rain over a cell grid.

    One drop head per column falls at its own speed and leaves a trail that
    fades over `fade` seconds. When painted, the trail is scaled by the
    video's luminance so whatever is bright in the window glows through the
    code; `lift` is how much shows on black so a dark room is not empty.
    """

    def __init__(self, grid: Grid, chars: str, coverage: np.ndarray, rng, fade: float = 0.8):
        self.grid = grid
        self.chars = chars
        self.coverage = coverage
        self.rng = rng
        self.fade = fade
        cols, rows = grid.cols, grid.rows
        self.head = rng.uniform(-rows * 0.7, rows, cols)
        self.speed = rng.uniform(rows * 0.4, rows * 1.0, cols)  # cells per second
        self.trail = np.zeros((rows, cols), dtype=np.float32)
        self.glyph = rng.integers(0, len(chars), (rows, cols))

    def step(self, dt: float) -> None:
        cols, rows = self.grid.cols, self.grid.rows
        rng = self.rng
        self.trail *= np.float32(np.exp(-dt / self.fade))
        prev = self.head.copy()
        self.head += self.speed * dt
        lo = np.clip(np.ceil(prev), 0, rows).astype(int)
        hi = np.clip(np.floor(self.head), -1, rows - 1).astype(int)
        for c in np.nonzero(hi >= lo)[0]:
            self.trail[lo[c]:hi[c] + 1, c] = 1.0
        done = self.head >= rows + 2
        n_done = int(done.sum())
        if n_done:
            self.head[done] = rng.uniform(-rows * 0.7, -1, n_done)
            self.speed[done] = rng.uniform(rows * 0.4, rows * 1.0, n_done)
        shuffle = rng.random((rows, cols)) < min(1.0, dt * 1.5)
        self.glyph[shuffle] = rng.integers(0, len(self.chars), int(shuffle.sum()))

    def paint(self, sampled: np.ndarray, floor: float = 0.05, lift: float = 0.07) -> np.ndarray:
        cols, rows = self.grid.cols, self.grid.rows
        lum = cells_from(sampled, self.grid) @ LUMA
        reveal = np.clip((lum - floor) / (0.55 - floor), 0.0, 1.0) ** 0.7
        light = np.clip(self.trail * (lift + (1.0 - lift) * reveal), 0.0, 1.0)
        head_row = np.floor(self.head).astype(int)
        ok = (head_row >= 0) & (head_row < rows)
        is_head = np.zeros((rows, cols), dtype=bool)
        is_head[head_row[ok], np.nonzero(ok)[0]] = True
        head_lift = min(1.0, lift * 2.0)
        ink = light[..., None] * RAIN_GREEN
        ink = np.where(is_head[..., None], (head_lift + (1.0 - head_lift) * reveal)[..., None] * RAIN_WHITE, ink)
        idx = np.clip(self.glyph, 0, len(self.chars) - 1)
        return compose(self.coverage, idx, ink, (0, 0, 0))


# ------------------------------------------------------------- person

SEGMENTER_URL = (
    "https://storage.googleapis.com/mediapipe-models/image_segmenter/"
    "selfie_segmenter/float16/latest/selfie_segmenter.tflite"
)


def segmenter_path() -> Path:
    """Where the selfie segmenter lives, next to the hand model. To be folded
    into model.py's model table when the person lens is wired in."""
    override = os.environ.get("ASCII_PRISM_SEGMENTER")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "ascii-prism" / "selfie_segmenter.tflite"


def ensure_segmenter(log=print) -> Path:
    path = segmenter_path()
    if path.exists() and path.stat().st_size > 100_000:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    log(f"Downloading segmentation model to {path} ...")
    tmp = path.with_suffix(".part")
    urllib.request.urlretrieve(SEGMENTER_URL, tmp)
    tmp.replace(path)
    return path


class PersonMask:
    """MediaPipe selfie segmentation on a whole frame. Calling it returns a
    float32 mask in 0..1 at the frame's size, 1 where there is a person.
    About 5 ms at the default working width."""

    def __init__(self, model: Path | str):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        options = vision.ImageSegmenterOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model)),
            running_mode=vision.RunningMode.IMAGE,
            output_confidence_masks=True,
            output_category_mask=False,
        )
        self._seg = vision.ImageSegmenter.create_from_options(options)

    def __call__(self, frame_bgr: np.ndarray, work_w: int = 256) -> np.ndarray:
        h, w = frame_bgr.shape[:2]
        sw = min(w, work_w)
        sh = max(1, int(round(h * sw / w)))
        small = cv2.resize(frame_bgr, (sw, sh), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        masks = self._seg.segment(image).confidence_masks
        m = np.asarray(masks[-1].numpy_view(), dtype=np.float32).reshape(sh, sw)
        return cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)

    def close(self) -> None:
        self._seg.close()


def person_look(sampled: np.ndarray, mask_flat: np.ndarray, grid: Grid, renderer: AsciiRenderer,
                chars: str = DEFAULT_CHARS, invert_bg: bool = False, feather: float = 0.15) -> np.ndarray:
    """ASCII where the mask says person, the video (or its negative) elsewhere.

    `mask_flat` is the person mask sampled through the same warp as `sampled`.
    """
    glyphs = ascii_look(sampled, grid, renderer, chars)
    h, w = glyphs.shape[:2]
    video = cv2.resize(sampled, (w, h), interpolation=cv2.INTER_LINEAR)
    if invert_bg:
        video = 255 - video
    m = cv2.resize(mask_flat, (w, h), interpolation=cv2.INTER_LINEAR)
    m = np.clip((m - 0.5 + feather) / (2 * feather), 0.0, 1.0)[..., None]
    return to_u8(video.astype(np.float32) / 255.0 * (1 - m) + glyphs.astype(np.float32) / 255.0 * m)
