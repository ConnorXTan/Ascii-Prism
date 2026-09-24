"""Web front end.

The browser captures the webcam and streams small JPEG frames over a
WebSocket. This server runs hand tracking and the window geometry on each
frame and answers with where the window is, in normalized coordinates. The
page draws the video and the ASCII window itself from its own full-size
camera feed, so the computer vision stays in Python while the pixels never
have to come back over the network.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, fields
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .charsets import CHARSETS
from .hands import HandTracker
from .model import ensure_model
from .pipeline import Pipeline
from .settings import RANGES, Settings

WEB_DIR = Path(__file__).parent / "web"
MAX_CHARSET_LENGTH = 256

app = FastAPI(title="ASCII Prism", version=__version__)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.middleware("http")
async def no_stale_assets(request, call_next):
    """Make browsers revalidate every response. Without this, Chrome keeps a
    cached script or stylesheet for hours after an update and runs the old
    one against the new page, which breaks it silently."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache"
    return response

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="prism")
_model_path: Path | None = None
_model_lock = threading.Lock()


def get_model() -> Path:
    global _model_path
    with _model_lock:
        if _model_path is None:
            _model_path = ensure_model()
        return _model_path


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/healthz")
async def health() -> dict:
    return {"ok": True, "version": __version__}


@app.get("/api/config")
async def config() -> dict:
    """Presets, defaults and ranges, so the page has a single source of truth."""
    return {
        "charsets": [{"id": cs.id, "label": cs.label, "chars": cs.chars} for cs in CHARSETS],
        "defaults": asdict(Settings()),
        "ranges": {name: list(bounds) for name, bounds in RANGES.items()},
        "version": __version__,
    }


def apply_settings(settings: Settings, data: dict) -> None:
    """Copy known fields from an untrusted JSON object into settings."""
    for f in fields(Settings):
        if f.name not in data:
            continue
        value = data[f.name]
        expected = type(f.default)
        if expected is bool:
            if not isinstance(value, bool):
                continue
        elif expected is int:
            if isinstance(value, bool) or not isinstance(value, int):
                continue
        elif expected is float:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            value = float(value)
        elif expected is str:
            if not isinstance(value, str):
                continue
            if f.name == "charset":
                value = value[:MAX_CHARSET_LENGTH]
        setattr(settings, f.name, value)
    settings.clamp()


class Session:
    """One browser connection: its own tracker, geometry state and settings.

    The page renders the ASCII window itself; the server only says where it is.
    """

    def __init__(self) -> None:
        self.settings = Settings()
        self.tracker = HandTracker(get_model())
        self.pipeline = Pipeline(self.tracker, None, self.settings)
        self.started = time.monotonic()

    def track(self, data: bytes) -> dict | None:
        if not data:
            return None  # OpenCV raises on an empty buffer; treat it like any undecodable frame
        frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return None
        timestamp_ms = int((time.monotonic() - self.started) * 1000)
        t0 = time.perf_counter()
        result = self.pipeline.track(frame, timestamp_ms)
        return {
            "type": "track",
            "hands": result.hands,
            "tips": [[round(float(x), 4), round(float(y), 4)] for x, y in result.tips],
            "quad": [[round(float(x), 4), round(float(y), 4)] for x, y in result.quad]
            if result.quad is not None
            else None,
            "twisted": result.twisted,
            "hint": result.hint,
            "locked": result.locked,
            "ms": round((time.perf_counter() - t0) * 1000, 1),
        }

    def close(self) -> None:
        self.tracker.close()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    loop = asyncio.get_running_loop()
    try:
        session = await loop.run_in_executor(_executor, Session)
    except Exception as err:  # noqa: BLE001 - report start-up failures to the page
        await ws.send_json({"type": "error", "message": f"Hand tracking could not start: {err}"})
        await ws.close()
        return
    await ws.send_json({"type": "ready"})
    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                out = await loop.run_in_executor(_executor, session.track, message["bytes"])
                if out is None:
                    # The page keeps a fixed number of frames in flight, so a frame
                    # that cannot be decoded must still be answered or the stream stalls.
                    await ws.send_json({"type": "dropped"})
                    continue
                await ws.send_json(out)
            elif message.get("text"):
                try:
                    data = json.loads(message["text"])
                except ValueError:
                    continue
                kind = data.get("type") if isinstance(data, dict) else None
                if kind == "settings" and isinstance(data.get("settings"), dict):
                    was_mirrored = session.settings.mirror
                    apply_settings(session.settings, data["settings"])
                    if session.settings.mirror != was_mirrored:
                        session.pipeline.reset_tracking()
                elif kind == "lock":
                    locked = session.pipeline.toggle_lock()
                    await ws.send_json({"type": "lock", "locked": locked})
    except Exception:  # noqa: BLE001 - client went away mid-frame
        pass
    finally:
        await loop.run_in_executor(_executor, session.close)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ascii-prism serve", description="Serve ASCII Prism as a website.")
    p.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=8000, help="port (default 8000)")
    p.add_argument("--no-open", action="store_true", help="do not open the page in a browser")
    args = p.parse_args(argv)

    import uvicorn

    get_model()
    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}/"
    print(f"ASCII Prism is running at {url}  (Ctrl+C to stop)")
    if not args.no_open:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0
