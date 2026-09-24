"""Lenses: what the fingertip window looks into.

`LENSES` is the ordered registry the settings, the page and the desktop
panel all read from. The looks themselves live in `looks.py` as pure
functions; each lens class here is a thin wrapper that plugs one into the
pipeline (see `base.py`).
"""

from __future__ import annotations

from .ascii import AsciiLens
from .base import Lens, LensContext, render_lens

LENSES: list[type[Lens]] = [AsciiLens]
DEFAULT_LENS_ID = AsciiLens.id


def by_id(lens_id: str) -> type[Lens] | None:
    for lens in LENSES:
        if lens.id == lens_id:
            return lens
    return None


def lens_ids() -> list[str]:
    return [lens.id for lens in LENSES]


__all__ = ["DEFAULT_LENS_ID", "LENSES", "Lens", "LensContext", "by_id", "lens_ids", "render_lens"]
