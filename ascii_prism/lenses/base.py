"""What a lens is.

A lens decides what the fingertip window shows. The pipeline does the same
four things for every lens: pick a source frame, sample the quad out of it
as a flat image, ask the lens to paint that flat image, and paste the result
back into the quad. Lenses are objects, one per session, because some keep
state between frames (rain has drop positions, echo has a delay).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from ..ascii import AsciiRenderer, RegionInfo
from ..geometry import quad_size
from ..settings import Settings
from ..warp import paste_quad, sample_quad

MIN_QUAD_FRACTION = 0.03  # of the frame's width and height, as AsciiRenderer.grid_for
PIXEL_CAP = 480  # the widest a pixel lens samples the window at


@dataclass
class LensContext:
    """Everything a lens may need for one frame."""

    frame: np.ndarray  # the live frame (already mirrored), BGR
    timestamp_ms: int
    dt: float  # seconds since the previous frame
    renderer: AsciiRenderer  # font, atlas cache and grid sizing
    history: Callable[[float], np.ndarray | None]  # frame nearest this many seconds ago, or None

    @property
    def frame_size(self) -> tuple[int, int]:
        h, w = self.frame.shape[:2]
        return w, h


def quad_usable(quad, frame_w: int, frame_h: int) -> bool:
    """False when the window is too small to be worth rendering."""
    width, height = quad_size(quad)
    return width >= frame_w * MIN_QUAD_FRACTION and height >= frame_h * MIN_QUAD_FRACTION


def pixel_sample_size(quad, cap: int = PIXEL_CAP) -> tuple[int, int]:
    """The quad's own pixel size, scaled down so it is at most `cap` wide."""
    width, height = quad_size(quad)
    scale = min(1.0, cap / max(1.0, width))
    return max(1, int(round(width * scale))), max(1, int(round(height * scale)))


class Lens:
    id = ""
    label = ""
    blurb = ""  # one line for the panel
    needs_history = False  # the pipeline keeps a frame ring buffer only if True
    uses: tuple[str, ...] = ()  # lens-specific Settings fields, shown in the panel only for this lens

    def source(self, ctx: LensContext, settings: Settings) -> np.ndarray:
        """Which frame the quad is sampled from. Default: the live one."""
        return ctx.frame

    def sample_size(self, quad, settings: Settings, ctx: LensContext) -> tuple[int, int] | None:
        """(w, h) to sample the quad at, or None if the quad is too small.
        Default: the quad's own pixel size, capped, for pixel lenses."""
        w, h = ctx.frame_size
        return pixel_sample_size(quad) if quad_usable(quad, w, h) else None

    def paint(self, sampled: np.ndarray, quad, settings: Settings, ctx: LensContext) -> tuple[np.ndarray, RegionInfo | None]:
        """Turn the sampled flat image into the flat image to paste back.
        Returns it with the character grid it used, if any."""
        raise NotImplementedError

    def reset(self) -> None:
        """Forget state: called when the lens is switched away or the camera is mirrored."""


def render_lens(lens: Lens, frame: np.ndarray, quad, settings: Settings, ctx: LensContext) -> tuple[bool, RegionInfo | None]:
    """Run one lens over the quad and paste the result into `frame` in place.

    Returns whether anything was drawn (False when the quad is too small or
    off the frame) and the character grid the lens used, if it used one.
    """
    size = lens.sample_size(quad, settings, ctx)
    if size is None:
        return False, None
    sampled = sample_quad(lens.source(ctx, settings), quad, *size, frame_shape=frame.shape)
    flat, region = lens.paint(sampled, quad, settings, ctx)
    if paste_quad(frame, quad, flat, settings.opacity) is None:
        return False, None
    return True, region
