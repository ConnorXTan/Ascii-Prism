"""A four-tone handheld screen."""

from __future__ import annotations

import numpy as np

from ..ascii import RegionInfo
from ..settings import Settings
from .base import Lens, LensContext
from .looks import gameboy


class GameboyLens(Lens):
    id = "gameboy"
    label = "Game Boy"
    blurb = "Four shades of green, 160 pixels wide."

    def paint(self, sampled: np.ndarray, quad, settings: Settings, ctx: LensContext) -> tuple[np.ndarray, RegionInfo | None]:
        return gameboy(sampled), None
