# ASCII Prism

Turn the space between your fingertips into live ASCII art.

Hold both hands up to your webcam with thumbs and index fingers extended. The
four fingertips become the corners of a window: inside it the video is
rendered as characters, outside it stays ordinary video. Move, tilt or skew
your hands and the character grid follows in perspective.

It is a website with a Python backend. The page in your browser captures the
webcam and streams frames to a FastAPI server; Python does all the computer
vision (MediaPipe hand tracking, OpenCV and NumPy rendering) and streams the
result back. Nothing leaves your machine when you run it locally.

## Setup

MediaPipe's current 1.x release crashes at start-up on macOS
([google-ai-edge/mediapipe#6356](https://github.com/google-ai-edge/mediapipe/issues/6356)),
so this project pins MediaPipe 0.10, which needs **Python 3.10 to 3.12**.
The easiest way to get one is [uv](https://docs.astral.sh/uv/):

```bash
cd "Ascii Prism"
uv venv --python 3.12          # downloads Python 3.12 if you do not have it
source .venv/bin/activate
uv pip install -r requirements.txt
```

Without uv, any Python 3.12 works the same way:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The hand-tracking model (about 8 MB) is downloaded once on first run into
`~/.cache/ascii-prism/`.

## Run it

```bash
python -m ascii_prism
```

This starts the server at <http://localhost:8000/> and opens it in your
browser. The page first shows the gesture and asks to turn on the camera;
allow access when the browser asks. Once the camera has been allowed, later
visits go straight to the video. Options:

```bash
python -m ascii_prism --port 9000            # another port
python -m ascii_prism --no-open              # do not open a browser tab
python -m ascii_prism --host 0.0.0.0         # reachable from other devices (see below)
```

Keys on the page: `L` locks or unlocks the current window so you can lower
your hands, `H` hides the controls, `F` goes fullscreen, `Esc` closes an
open panel.

Browsers only allow camera access on `localhost` or over HTTPS. To use the
site from a phone or another computer on your network, put it behind an
HTTPS reverse proxy such as Caddy, or use a tunnel like `ngrok`.

### Desktop mode

The same pipeline also runs as a native window without a browser:

```bash
python -m ascii_prism desktop                     # webcam
python -m ascii_prism desktop --source clip.mp4   # a video or image file
python -m ascii_prism desktop --help              # all options
```

## The gesture

Think of holding a sheet of paper by its corners: index fingers on top,
thumbs at the bottom. The app does not care which finger is which corner. It
takes the four fingertips, orders them clockwise and maps the character grid
onto that quadrilateral. If the four points cross over each other (a
non-convex shape) the window is hidden until you spread them out again.

When fewer than two hands are visible the window disappears and you see
plain video.

## Controls

The video fills the page. The dock at the bottom opens one panel at a time:

- **Characters.** Pick a preset ramp or type your own. Characters are ordered
  from darkest to brightest; each cell picks the character whose position in
  the ramp matches its brightness. Block characters work. *Invert* flips the
  ramp, useful for light backgrounds.
- **Grid.** How many character columns the window has, from 16 to 200. Rows
  are derived from the window's shape so characters keep their natural
  proportions.
- **Colour.** Every character takes the average colour of the video it
  replaces, then goes through the colour wheel: the angle of the handle
  rotates hue and its distance from the centre sets saturation (the thin
  ring marks the video as-is, the centre is greyscale). *Opacity* blends the
  characters over the live video, *Brightness* is a gain on the sampled
  colours, and *Backdrop* is the colour behind the characters.
- **Tracking.** *Smoothing* damps fingertip jitter; higher values are
  steadier but lag more. *Fingertips* draws the four points and the
  outline. *Mirror* flips the camera like a mirror.

**Lock** freezes the current window so you can lower your hands, and
**Fullscreen** does what it says.

Settings are kept in the browser's `localStorage` and sent to the server on
every change.

## How it works

- `ascii_prism/web/` is the page: `app.js` captures the webcam and sends
  small JPEG frames (480 pixels wide) over a WebSocket for hand tracking,
  keeping two in flight so the network overlaps the server's work. The
  server answers with where the window is, and `render.js` draws the video
  and the ASCII window from the full-size camera feed on the visitor's own
  machine: it samples the average colour under every cell, grades it, picks
  a glyph by brightness, composes the character grid on a canvas and warps
  it into the window with the same bilinear map the Python renderer uses.
- `ascii_prism/server.py` is the FastAPI app. Each connection gets its own
  hand tracker, geometry state and settings; frames are processed in a
  thread pool so the event loop stays responsive.
- `ascii_prism/pipeline.py` ties tracking and geometry together per frame.
  `track()` returns the window in normalized coordinates for the website;
  `process()` also renders it and draws the fingertip overlay for desktop
  mode. It has no I/O, so it is easy to test from files.
- `ascii_prism/hands.py` wraps MediaPipe's Hand Landmarker and returns the
  thumb and index fingertips of up to two hands.
- `ascii_prism/geometry.py` orders the four points, checks convexity, sizes
  the quad, smooths it over time, and builds the perspective maps with
  OpenCV.
- `ascii_prism/ascii.py` renders the characters. Pillow rasterises the ramp
  into a glyph atlas from a monospace font, sized so a block character fills
  a cell exactly. Each frame, the quad is warped flat and shrunk to one pixel
  per cell to get average cell colours, luminance picks a glyph per cell,
  NumPy composes the flat character image, and OpenCV warps it back into the
  quad over the live frame.
- `ascii_prism/app.py` and `panel.py` are desktop mode: OpenCV window, keys,
  status bar and a Tkinter customizer.

Hand tracking costs the server about 10 ms per frame on an Apple Silicon Mac
and about 30 ms on a Vercel function. The browser draws at the camera's frame
rate regardless; only the window's position updates at the tracking rate.

## Tests

```bash
python -m pytest
```

Geometry, rendering and server-validation tests run offline. The pipeline and
WebSocket tests download a sample photo of two hands and the hand model on
first run, and are skipped if they cannot be fetched. Cached files land in
`tests/.cache/`.

## Deploying

Every visitor's hand tracking runs on the server, about 30 ms per frame on
one Vercel vCPU, so plan CPU accordingly; the rendering happens in the
visitor's browser. Any host that runs a persistent Python process works: run
`python -m ascii_prism --host 0.0.0.0` behind HTTPS.

### Vercel

`Dockerfile.vercel` builds the server as a container image, which Vercel
runs as a function with WebSocket support. The image installs the OpenGL
and GLib libraries MediaPipe needs, a monospace font for the renderer, and
bakes the hand model in so cold starts never download it. With the
[Vercel CLI](https://vercel.com/docs/cli) installed and logged in:

```bash
vercel link --yes --project ascii-prism   # once
vercel deploy                             # preview URL
vercel deploy --prod                      # production
```

Two things to expect on Vercel: the function is put to sleep after a few
idle minutes, so the first visit after a quiet spell waits on a cold start,
and each WebSocket is closed when the function reaches its time limit (five
minutes on the Hobby plan). The page reconnects on its own, so that shows up
as a short pause rather than a dead stream.
