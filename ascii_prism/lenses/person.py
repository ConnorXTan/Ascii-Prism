"""Only the person becomes characters; the room stays video."""

from __future__ import annotations

import sys

import numpy as np

from ..ascii import RegionInfo
from ..settings import Settings
from ..warp import sample_quad
from .ascii import paint_ascii, region_of
from .base import Lens, LensContext, pixel_sample_size
from .looks import Grid, PersonMask, ensure_segmenter, grid_for, person_blend

ROI_MARGIN = 0.1  # of the quad's bounding box, on every side


class PersonLens(Lens):
    id = "person"
    label = "Person"
    blurb = "Only you become characters; the room stays video."
    uses = ("person_invert",)

    def __init__(self) -> None:
        self._mask: PersonMask | None = None
        self._unavailable = False

    def grid(self, quad, settings: Settings, ctx: LensContext) -> Grid | None:
        w, h = ctx.frame_size
        return grid_for(ctx.renderer, quad, settings.columns, w, h)

    def sample_size(self, quad, settings: Settings, ctx: LensContext) -> tuple[int, int] | None:
        grid = self.grid(quad, settings, ctx)
        if grid is None:
            return None
        gw, gh = grid.sample_size
        pw, ph = pixel_sample_size(quad)
        return max(gw, pw), max(gh, ph)  # cells still average; the video behind stays sharp

    def paint(self, sampled: np.ndarray, quad, settings: Settings, ctx: LensContext) -> tuple[np.ndarray, RegionInfo | None]:
        grid = self.grid(quad, settings, ctx)
        glyphs = paint_ascii(sampled, grid, settings, ctx.renderer)
        mask = self._segment(ctx.frame, quad)
        if mask is None:
            return glyphs, region_of(grid)
        mask_flat = sample_quad(mask, quad, sampled.shape[1], sampled.shape[0])
        return person_blend(glyphs, sampled, mask_flat, settings.person_invert), region_of(grid)

    def _segment(self, frame: np.ndarray, quad) -> np.ndarray | None:
        """A person mask the size of the frame, computed on the quad's
        surroundings only. None when the segmenter cannot be had, in which
        case the lens shows plain characters."""
        if self._unavailable:
            return None
        if self._mask is None:
            try:
                self._mask = PersonMask(ensure_segmenter(log=lambda *_: None))
            except Exception as err:  # noqa: BLE001 - no model, no MediaPipe: stay usable
                print(f"Person lens unavailable ({err}); showing characters instead.", file=sys.stderr)
                self._unavailable = True
                return None
        h, w = frame.shape[:2]
        q = np.asarray(quad, dtype=np.float64).reshape(4, 2)
        mx = (q[:, 0].max() - q[:, 0].min()) * ROI_MARGIN
        my = (q[:, 1].max() - q[:, 1].min()) * ROI_MARGIN
        x0 = int(max(0, np.floor(q[:, 0].min() - mx)))
        y0 = int(max(0, np.floor(q[:, 1].min() - my)))
        x1 = int(min(w, np.ceil(q[:, 0].max() + mx)))
        y1 = int(min(h, np.ceil(q[:, 1].max() + my)))
        if x1 - x0 < 8 or y1 - y0 < 8:
            return None
        return self._mask(frame, roi=(x0, y0, x1, y1))

    def reset(self) -> None:
        if self._mask is not None:
            self._mask.close()
            self._mask = None
