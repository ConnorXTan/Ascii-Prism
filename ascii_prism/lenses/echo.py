"""The window looks a moment into the past."""

from __future__ import annotations

import numpy as np

from ..ascii import RegionInfo
from ..settings import Settings
from .base import Lens, LensContext


class EchoLens(Lens):
    id = "echo"
    label = "Echo"
    blurb = "The window looks a moment into the past."
    needs_history = True
    uses = ("delay",)

    def source(self, ctx: LensContext, settings: Settings) -> np.ndarray:
        past = ctx.history(settings.delay)
        return ctx.frame if past is None else past

    def paint(self, sampled: np.ndarray, quad, settings: Settings, ctx: LensContext) -> tuple[np.ndarray, RegionInfo | None]:
        return sampled, None
