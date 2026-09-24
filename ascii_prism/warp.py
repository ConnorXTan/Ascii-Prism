"""The two halves of the fingertip window's warp.

`sample_quad` pulls the quad's contents out of a frame as a flat image, and
`paste_quad` puts a flat image back into the quad. Between the two, a lens
decides what the flat image looks like. Both use the bilinear map from
`geometry`, so a twisted quad (one hand flipped) folds the same way it does
today.
"""

from __future__ import annotations

import cv2
import numpy as np

from .geometry import bilinear_map, inverse_bilinear


def sample_quad(src: np.ndarray, quad, w: int, h: int, frame_shape=None) -> np.ndarray:
    """The quad's contents as a flat (h, w, 3) image.

    `quad` is in the pixel space of the frame it was found in. If `src` is a
    different size (a history frame stored small), pass that frame's shape as
    `frame_shape` and the quad is scaled to match.
    """
    q = np.asarray(quad, dtype=np.float64).reshape(4, 2)
    if frame_shape is not None and tuple(frame_shape[:2]) != src.shape[:2]:
        q = q * [src.shape[1] / frame_shape[1], src.shape[0] / frame_shape[0]]
    us = (np.arange(w, dtype=np.float64) + 0.5) / w
    vs = (np.arange(h, dtype=np.float64) + 0.5) / h
    sx, sy = bilinear_map(q, us[None, :], vs[:, None])
    return cv2.remap(src, sx.astype(np.float32), sy.astype(np.float32), cv2.INTER_LINEAR)


def paste_quad(frame: np.ndarray, quad, flat: np.ndarray, opacity: float = 1.0) -> np.ndarray | None:
    """Warp `flat` into the quad and blend it over `frame` in place.

    Only the quad's bounding box is touched, and inside it only pixels that
    lie on the (possibly folded) surface. Returns the valid mask for that
    bounding box, or None if the quad lies entirely off the frame.
    """
    frame_h, frame_w = frame.shape[:2]
    fh, fw = flat.shape[:2]
    q = np.asarray(quad, dtype=np.float64).reshape(4, 2)
    x0 = int(max(0, np.floor(q[:, 0].min())))
    y0 = int(max(0, np.floor(q[:, 1].min())))
    x1 = int(min(frame_w, np.ceil(q[:, 0].max()) + 1))
    y1 = int(min(frame_h, np.ceil(q[:, 1].max()) + 1))
    if x1 <= x0 or y1 <= y0:
        return None
    px = np.arange(x0, x1, dtype=np.float64) + 0.5
    py = np.arange(y0, y1, dtype=np.float64) + 0.5
    u, v, valid = inverse_bilinear(q, px[None, :], py[:, None])
    map_x = (np.nan_to_num(u) * fw - 0.5).astype(np.float32)
    map_y = (np.nan_to_num(v) * fh - 0.5).astype(np.float32)
    warped = cv2.remap(flat, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    region = frame[y0:y1, x0:x1]
    if opacity < 1.0:
        warped = cv2.addWeighted(region, 1.0 - opacity, warped, opacity, 0.0)
    np.copyto(region, warped, where=valid[:, :, None])
    return valid
