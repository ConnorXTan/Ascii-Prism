"""A heat camera, no characters."""

from __future__ import annotations

import numpy as np

from ..ascii import RegionInfo
from ..settings import Settings
from .base import Lens, LensContext
from .looks import thermal


class ThermalLens(Lens):
    id = "thermal"
    label = "Thermal"
    blurb = "A heat camera: skin glows, the room goes cold."

    def paint(self, sampled: np.ndarray, quad, settings: Settings, ctx: LensContext) -> tuple[np.ndarray, RegionInfo | None]:
        return thermal(sampled), None
