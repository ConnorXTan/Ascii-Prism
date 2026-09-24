"""Night-vision goggles."""

from __future__ import annotations

import numpy as np

from ..ascii import RegionInfo
from ..settings import Settings
from .base import Lens, LensContext
from .looks import night


class NightLens(Lens):
    id = "night"
    label = "Night vision"
    blurb = "Phosphor green, grain and a vignette."

    def __init__(self) -> None:
        self._rng = np.random.default_rng()

    def paint(self, sampled: np.ndarray, quad, settings: Settings, ctx: LensContext) -> tuple[np.ndarray, RegionInfo | None]:
        return night(sampled, self._rng), None
