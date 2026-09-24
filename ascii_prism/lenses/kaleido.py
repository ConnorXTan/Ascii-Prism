"""The window folds into itself."""

from __future__ import annotations

import numpy as np

from ..ascii import RegionInfo
from ..settings import Settings
from .base import Lens, LensContext
from .looks import mirror_remap


class KaleidoLens(Lens):
    id = "kaleido"
    label = "Kaleido"
    blurb = "The window mirrored into itself, four ways."

    def paint(self, sampled: np.ndarray, quad, settings: Settings, ctx: LensContext) -> tuple[np.ndarray, RegionInfo | None]:
        return mirror_remap(sampled), None
