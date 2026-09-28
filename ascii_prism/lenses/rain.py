"""Matrix rain that lights up wherever the window is bright."""

from __future__ import annotations

import numpy as np

from ..ascii import RegionInfo
from ..settings import Settings
from .ascii import region_of
from .base import Lens, LensContext
from .looks import FixedCellAtlas, Grid, Rain, grid_for, rain_glyphs


class RainLens(Lens):
    id = "rain"
    label = "Rain"
    blurb = "Falling code that glows wherever you are."

    def __init__(self) -> None:
        self._rain: Rain | None = None
        self._glyphs: tuple[str, str | None] | None = None  # (chars, font path)
        self._atlases: dict[tuple[int, int], FixedCellAtlas] = {}

    def grid(self, quad, settings: Settings, ctx: LensContext) -> Grid | None:
        w, h = ctx.frame_size
        return grid_for(ctx.renderer, quad, settings.columns, w, h)

    def sample_size(self, quad, settings: Settings, ctx: LensContext) -> tuple[int, int] | None:
        grid = self.grid(quad, settings, ctx)
        return None if grid is None else grid.sample_size

    def paint(self, sampled: np.ndarray, quad, settings: Settings, ctx: LensContext) -> tuple[np.ndarray, RegionInfo | None]:
        grid = self.grid(quad, settings, ctx)
        if self._glyphs is None:
            self._glyphs = rain_glyphs(ctx.renderer.font_path)
        chars, font = self._glyphs
        atlas = self._atlas(font, chars, grid)
        if self._rain is None:
            self._rain = Rain(grid, chars, atlas.coverage, np.random.default_rng())
        else:
            self._rain.resize(grid)
            self._rain.coverage = atlas.coverage
        self._rain.step(ctx.dt)
        return self._rain.paint(sampled), region_of(grid)

    def _atlas(self, font: str | None, chars: str, grid: Grid) -> FixedCellAtlas:
        key = (grid.glyph_h, grid.glyph_w)
        atlas = self._atlases.get(key)
        if atlas is None:
            if len(self._atlases) > 24:
                self._atlases.clear()
            atlas = self._atlases[key] = FixedCellAtlas(font, list(chars), grid.glyph_h, grid.glyph_w)
        return atlas

    def reset(self) -> None:
        self._rain = None
