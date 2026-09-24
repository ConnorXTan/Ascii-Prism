"""Render every lens look into the same fingertip window on the sample photo
and write a contact sheet to docs/plans/, so the looks can be judged and
tuned on a still before they are wired into the pipeline.

    .venv/bin/python tools/lens_sheet.py [--columns 80] [--out docs/plans]

The photo is doubled to 1280 wide to match a webcam frame, and its exposure
is lifted to what a webcam does to a face in a lit room.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ascii_prism.ascii import AsciiRenderer, find_font  # noqa: E402
from ascii_prism.geometry import quad_size  # noqa: E402
from ascii_prism.lenses import looks  # noqa: E402
from ascii_prism.warp import paste_quad, sample_quad  # noqa: E402

PHOTO = REPO / "tests/.cache/hands.jpg"
QUAD_1X = np.array([[150, 370], [590, 400], [575, 700], [140, 670]], dtype=np.float64)
SCALE = 2
GAMMA = 0.72


def overlay(frame: np.ndarray, quad: np.ndarray) -> None:
    scale = max(1.0, frame.shape[1] / 640)
    thick = max(1, int(round(1.5 * scale)))
    pts = np.round(quad).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(frame, [pts], True, (255, 255, 255), thick, cv2.LINE_AA)
    for x, y in quad:
        c = (int(round(x)), int(round(y)))
        cv2.circle(frame, c, int(6 * scale), (0, 0, 0), -1, cv2.LINE_AA)
        cv2.circle(frame, c, int(6 * scale), (255, 255, 255), thick, cv2.LINE_AA)


def label(tile: np.ndarray, text: str, ms: float) -> np.ndarray:
    strip = np.full((44, tile.shape[1], 3), 18, dtype=np.uint8)
    cv2.putText(strip, text, (14, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (235, 235, 235), 2, cv2.LINE_AA)
    stamp = f"{ms:.1f} ms"
    (tw, _), _ = cv2.getTextSize(stamp, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
    cv2.putText(strip, stamp, (tile.shape[1] - tw - 14, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (140, 140, 140), 1, cv2.LINE_AA)
    return np.vstack([strip, tile])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--columns", type=int, default=80)
    ap.add_argument("--out", type=Path, default=REPO / "docs/plans")
    ap.add_argument("--tiles", action="store_true", help="also write each tile at full size")
    args = ap.parse_args()
    if not PHOTO.exists():
        sys.exit(f"sample photo missing: run the tests once to fetch {PHOTO}")

    photo = cv2.imread(str(PHOTO))
    frame = cv2.resize(photo, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_CUBIC)
    lut = (np.linspace(0, 1, 256) ** GAMMA * 255 + 0.5).astype(np.uint8)
    frame = cv2.LUT(frame, lut)
    H, W = frame.shape[:2]
    quad = QUAD_1X * SCALE
    qw, qh = quad_size(quad)
    pw, ph = int(round(qw)), int(round(qh))

    renderer = AsciiRenderer(find_font())
    grid = looks.grid_for(renderer, quad, args.columns, W, H)
    ss = grid.sample_size
    rng = np.random.default_rng(7)
    print(f"frame {W}x{H}  quad {pw}x{ph}  grid {grid.cols}x{grid.rows}  glyph {grid.glyph_w}x{grid.glyph_h}")

    # An "older" frame for echo: the subject has drifted a little.
    M = np.array([[1.04, 0.0, -70.0], [0.0, 1.04, 20.0]], dtype=np.float64)
    older = cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    older = cv2.resize(older, (640, 960), interpolation=cv2.INTER_AREA)  # history frames are stored small

    try:
        mask = looks.PersonMask(looks.ensure_segmenter())(frame)
    except OSError as err:
        print(f"person lens skipped: {err}")
        mask = None

    rain_chars, rain_font = looks.rain_glyphs(renderer.font_path)
    print(f"rain: {'katakana' if rain_font != renderer.font_path else 'latin'} from {rain_font}")

    def rain_sim(chars: str, font: str | None, seconds: float = 3.0):
        atlas = looks.FixedCellAtlas(font, list(chars), grid.glyph_h, grid.glyph_w)
        rain = looks.Rain(grid, chars, atlas.coverage, np.random.default_rng(3))
        sampled = sample_quad(frame, quad, *ss)
        for _ in range(int(seconds * 30)):
            rain.step(1 / 30)
        return rain.paint(sampled)

    tiles: list[np.ndarray] = []
    heroes: dict[str, np.ndarray] = {}

    def add(name: str, fn) -> None:
        f = frame.copy()
        t0 = time.perf_counter()
        paste_quad(f, quad, fn())
        ms = (time.perf_counter() - t0) * 1000
        overlay(f, quad)
        x0, y0 = int(quad[:, 0].min()) - 60, int(quad[:, 1].min()) - 60
        x1, y1 = int(quad[:, 0].max()) + 60, int(quad[:, 1].max()) + 60
        side = max(x1 - x0, y1 - y0)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        x0, y0 = max(0, cx - side // 2), max(0, cy - side // 2)
        tile = f[y0:y0 + side, x0:x0 + side]
        if args.tiles:
            cv2.imwrite(str(args.out / f"lens-tile-{len(tiles):02d}-{name.split()[0]}.png"), tile)
        tiles.append(label(tile, name, ms))
        heroes[name] = cv2.resize(f, (640, 960), interpolation=cv2.INTER_AREA)
        print(f"  {name:<24} {ms:6.1f} ms")

    live = lambda: sample_quad(frame, quad, *ss)  # noqa: E731
    pixels = lambda: sample_quad(frame, quad, pw, ph)  # noqa: E731

    add("ascii (today)", lambda: looks.ascii_look(live(), grid, renderer))
    add("thermal", lambda: looks.thermal(pixels()))
    add("echo · ascii", lambda: looks.ascii_look(sample_quad(older, quad, *ss, frame_shape=frame.shape), grid, renderer))
    add("echo · video", lambda: sample_quad(older, quad, pw, ph, frame_shape=frame.shape))
    if rain_font != renderer.font_path:
        add("rain · katakana", lambda: rain_sim(rain_chars, rain_font))
    add("rain · latin", lambda: rain_sim(looks.RAIN_LATIN, renderer.font_path))
    add("gameboy", lambda: looks.gameboy(pixels()))
    add("sketch", lambda: looks.sketch(pixels(), rng=rng))
    if mask is not None:
        add("person", lambda: looks.person_look(live(), sample_quad(mask, quad, *ss), grid, renderer))
        add("person · inverted", lambda: looks.person_look(live(), sample_quad(mask, quad, *ss), grid, renderer, invert_bg=True))
    add("night", lambda: looks.night(pixels(), rng))
    add("kaleido · 6 fold", lambda: looks.ascii_look(looks.kaleido_remap(live()), grid, renderer))
    add("kaleido · mirror", lambda: looks.ascii_look(looks.mirror_remap(live()), grid, renderer))
    add("kaleido · mirror video", lambda: looks.mirror_remap(pixels()))

    cols = 5
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    sheet = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
    sheet = cv2.resize(sheet, None, fx=0.4, fy=0.4, interpolation=cv2.INTER_AREA)
    args.out.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.out / "lenses-preview.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 82])
    picks = [k for k in ("thermal", "rain · katakana", "person", "sketch", "night") if k in heroes][:4]
    cv2.imwrite(str(args.out / "lenses-hero.jpg"), np.hstack([heroes[k] for k in picks]), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"wrote {args.out / 'lenses-preview.jpg'} and lenses-hero.jpg")


if __name__ == "__main__":
    main()
