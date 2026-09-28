"""A pencil drawing on paper."""

from __future__ import annotations

import numpy as np

from ..ascii import RegionInfo
from ..settings import Settings
from .base import Lens, LensContext
from .looks import sketch


class SketchLens(Lens):
    id = "sketch"
    label = "Sketch"
    blurb = "A pencil drawing on warm paper."

    def __init__(self) -> None:
        self._rng = np.random.default_rng()

    def paint(self, sampled: np.ndarray, quad, settings: Settings, ctx: LensContext) -> tuple[np.ndarray, RegionInfo | None]:
        return sketch(sampled, rng=self._rng), None
