"""The default lens: the live video as characters."""

from __future__ import annotations

import numpy as np

from ..ascii import AsciiRenderer, RegionInfo
from ..grading import grade
from ..settings import Settings, hex_to_bgr
from .base import Lens, LensContext
from .looks import Grid, ascii_glyphs, cells_from, grid_for


def paint_ascii(sampled: np.ndarray, grid: Grid, settings: Settings, renderer: AsciiRenderer) -> np.ndarray:
    """Cells, colour grading, glyphs: shared by every lens that draws characters."""
    cells = cells_from(sampled, grid)
    ink = grade(cells, settings)
    return ascii_glyphs(cells, grid, renderer, settings.charset, ink, settings.invert, hex_to_bgr(settings.background))


def region_of(grid: Grid) -> RegionInfo:
    return RegionInfo(grid.cols, grid.rows, grid.glyph_w, grid.glyph_h)


class AsciiLens(Lens):
    id = "ascii"
    label = "ASCII"
    blurb = "The live video as characters."

    def grid(self, quad, settings: Settings, ctx: LensContext) -> Grid | None:
        w, h = ctx.frame_size
        return grid_for(ctx.renderer, quad, settings.columns, w, h)

    def sample_size(self, quad, settings: Settings, ctx: LensContext) -> tuple[int, int] | None:
        grid = self.grid(quad, settings, ctx)
        return None if grid is None else grid.sample_size

    def paint(self, sampled: np.ndarray, quad, settings: Settings, ctx: LensContext) -> tuple[np.ndarray, RegionInfo | None]:
        grid = self.grid(quad, settings, ctx)
        return paint_ascii(sampled, grid, settings, ctx.renderer), region_of(grid)
