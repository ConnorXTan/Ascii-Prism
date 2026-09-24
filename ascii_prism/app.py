"""Command-line entry point: camera, window, keys, status bar, panel."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from . import __version__
from .ascii import AsciiRenderer, find_font
from .hands import HandTracker
from .model import ensure_model
from .pipeline import FrameResult, Pipeline
from .settings import Settings

WINDOW = "ASCII Prism"


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="ascii-prism", description="Live ASCII art between your fingertips.")
    p.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    p.add_argument("--source", type=Path, help="image or video file to use instead of the camera")
    p.add_argument("--width", type=int, default=1280, help="requested camera width")
    p.add_argument("--height", type=int, default=720, help="requested camera height")
    p.add_argument("--font", type=Path, help="path to a monospace TrueType font")
    p.add_argument("--no-panel", action="store_true", help="do not open the customizer window")
    p.add_argument("--snapshot", type=Path, help="process one frame, write it to this PNG and exit")
    p.add_argument("--max-frames", type=int, default=0, help="exit after this many frames (0 = run until quit)")
    p.add_argument("--version", action="version", version=f"ascii-prism {__version__}")
    return p.parse_args(argv)


class FrameSource:
    """A camera, a video file, or a still image (repeated forever)."""

    def __init__(self, args: argparse.Namespace):
        self.still: np.ndarray | None = None
        self.capture: cv2.VideoCapture | None = None
        if args.source is not None:
            if not args.source.exists():
                raise SystemExit(f"Source not found: {args.source}")
            image = cv2.imread(str(args.source))
            if image is not None:
                self.still = image
                return
            self.capture = cv2.VideoCapture(str(args.source))
            if not self.capture.isOpened():
                raise SystemExit(f"Could not open {args.source} as an image or video.")
            return
        self.capture = cv2.VideoCapture(args.camera)
        if not self.capture.isOpened():
            raise SystemExit(
                f"Could not open camera {args.camera}. Check camera permissions for your terminal "
                "in System Settings > Privacy & Security > Camera, or pass --camera N."
            )
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    def read(self) -> np.ndarray | None:
        if self.still is not None:
            return self.still.copy()
        ok, frame = self.capture.read()
        if not ok:
            # Loop video files.
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.capture.read()
        return frame if ok else None

    def release(self) -> None:
        if self.capture is not None:
            self.capture.release()


def draw_status(frame: np.ndarray, result: FrameResult, fps: float) -> None:
    h, w = frame.shape[:2]
    scale = max(0.45, w / 1600)
    bar_h = int(34 * scale * 1.6)
    bar = frame[h - bar_h : h]
    cv2.addWeighted(bar, 0.35, np.zeros_like(bar), 0.65, 0, bar)
    grid = f"{result.region.cols} x {result.region.rows}" if result.region else "-"
    lock = "  LOCKED" if result.locked else ""
    twist = "  twisted" if result.twisted else ""
    text = f"{fps:4.0f} fps   hands {result.hands}   grid {grid}{twist}{lock}"
    cv2.putText(frame, text, (12, h - int(bar_h * 0.35)), cv2.FONT_HERSHEY_SIMPLEX, 0.55 * scale * 1.3,
                (235, 235, 235), 1, cv2.LINE_AA)
    if result.hint:
        font_scale = 0.6 * scale * 1.3
        (tw, th), _ = cv2.getTextSize(result.hint, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        x = max(8, (w - tw) // 2)
        y = h - bar_h - int(18 * scale)
        cv2.rectangle(frame, (x - 10, y - th - 10), (x + tw + 10, y + 10), (0, 0, 0), -1)
        cv2.putText(frame, result.hint, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1, cv2.LINE_AA)


def main(argv=None) -> int:
    args = parse_args(argv)
    settings = Settings.load()
    font = find_font(str(args.font) if args.font else None)
    if font is None:
        print("Warning: no monospace TrueType font found; block characters may not render. Use --font.", file=sys.stderr)
    renderer = AsciiRenderer(font)

    try:
        tracker = HandTracker(ensure_model())
    except Exception as err:  # noqa: BLE001 - surface any model/runtime failure plainly
        print(f"Hand tracking could not start: {err}", file=sys.stderr)
        return 1

    pipeline = Pipeline(tracker, renderer, settings)
    source = FrameSource(args)

    if args.snapshot:
        frame = source.read()
        if frame is None:
            print("No frame available.", file=sys.stderr)
            return 1
        result = pipeline.process(frame, 0)
        draw_status(result.frame, result, 0)
        cv2.imwrite(str(args.snapshot), result.frame)
        print(f"hands={result.hands} grid={result.region.cols}x{result.region.rows}" if result.region
              else f"hands={result.hands} grid=-")
        source.release()
        tracker.close()
        return 0

    panel = None
    if not args.no_panel:
        try:
            from .panel import Panel

            panel = Panel(settings, on_change=settings.save, on_lock=pipeline.toggle_lock,
                          on_reset=lambda: (settings.reset(), settings.save(), pipeline.reset_tracking()))
        except Exception as err:  # noqa: BLE001 - Tk may be unavailable; keyboard still works
            print(f"Customizer panel unavailable ({err}); keyboard controls still work.", file=sys.stderr)

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    fullscreen = False
    start = time.perf_counter()
    frames = 0
    total_frames = 0
    fps = 0.0
    fps_window = start
    try:
        while True:
            if args.max_frames and total_frames >= args.max_frames:
                break
            frame = source.read()
            if frame is None:
                break
            now_ms = int((time.perf_counter() - start) * 1000)
            result = pipeline.process(frame, now_ms)

            frames += 1
            total_frames += 1
            elapsed = time.perf_counter() - fps_window
            if elapsed >= 0.5:
                fps = frames / elapsed
                frames = 0
                fps_window = time.perf_counter()
                if panel is not None:
                    grid = f"{result.region.cols} x {result.region.rows}" if result.region else "-"
                    panel.set_status(f"{fps:.0f} fps   hands {result.hands}   grid {grid}")

            draw_status(result.frame, result, fps)
            cv2.imshow(WINDOW, result.frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            elif key == ord("l"):
                locked = pipeline.toggle_lock()
                if panel is not None:
                    panel.set_locked(locked)
            elif key == ord("h") and panel is not None:
                panel.toggle()
            elif key == ord("t"):
                settings.show_tips = not settings.show_tips
                settings.save()
                if panel is not None:
                    panel.sync()
            elif key == ord("m"):
                settings.mirror = not settings.mirror
                pipeline.reset_tracking()
                settings.save()
                if panel is not None:
                    panel.sync()
            elif key == ord("i"):
                settings.invert = not settings.invert
                settings.save()
                if panel is not None:
                    panel.sync()
            elif key in (ord("-"), ord("=")):
                settings.columns += 4 if key == ord("=") else -4
                settings.clamp()
                settings.save()
                if panel is not None:
                    panel.sync()
            elif key == ord("f"):
                fullscreen = not fullscreen
                cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN,
                                      cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL)
            elif key == ord("s"):
                out = Path(f"ascii-prism-{time.strftime('%Y%m%d-%H%M%S')}.png")
                cv2.imwrite(str(out), result.frame)
                print(f"Saved {out}")

            if panel is not None:
                try:
                    panel.pump()
                except Exception:  # noqa: BLE001 - panel destroyed
                    panel = None
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        source.release()
        tracker.close()
        cv2.destroyAllWindows()
        if panel is not None:
            panel.close()
    elapsed = time.perf_counter() - start
    if total_frames:
        print(f"Processed {total_frames} frames in {elapsed:.1f} s ({total_frames / elapsed:.1f} fps)")
    return 0
