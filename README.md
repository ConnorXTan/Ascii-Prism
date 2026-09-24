# ASCII Prism

Turn the space between your fingertips into live ASCII art.

Hold both hands up to your webcam with thumbs and index fingers extended. The
four fingertips become the corners of a window: inside it the video is
rendered as characters, outside it stays ordinary video. Move, tilt or skew
your hands and the character grid follows in perspective.

The window is a portal. Pick a **lens** and the same four fingertips frame
a thermal camera, the room a moment ago, Matrix rain, a Game Boy, a pencil
sketch, night vision, a kaleidoscope, or only you as characters with the
room left as video.

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
browser. Allow camera access when asked. Options:

```bash
python -m ascii_prism --port 9000            # another port
python -m ascii_prism --no-open              # do not open a browser tab
python -m ascii_prism --host 0.0.0.0         # reachable from other devices (see below)
```

Keys on the page: `[` and `]` cycle lenses and `1` to `9` pick one, `L`
locks or unlocks the current window so you can lower your hands, `H` hides
the controls, `F` goes fullscreen, `Esc` closes an open panel.

Browsers only allow camera access on `localhost` or over HTTPS. To use the
site from a phone or another computer on your network, put it behind an
HTTPS reverse proxy such as Caddy, or use a tunnel like `ngrok`.

### Desktop mode

The same pipeline also runs as a native window without a browser:

```bash
python -m ascii_prism desktop                     # webcam
python -m ascii_prism desktop --source clip.mp4   # a video or image file
python -m ascii_prism desktop --lens thermal      # start with a lens
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

- **Lens.** What the window looks into. *ASCII* is the live video as
  characters. *Thermal* is a heat camera where skin glows and the room goes
  cold. *Echo* looks a moment into the past; the delay slider sets how far,
  up to three seconds. *Rain* is falling Matrix code that lights up
  wherever you are. *Game Boy* is four shades of green at 160 pixels wide.
  *Sketch* is a pencil drawing on paper. *Night vision* is green goggles
  with grain. *Kaleido* mirrors the window into itself. *Person* keeps only
  you as characters and leaves the room as video, or as its negative with
  *Invert the background*. The panels below apply to the lenses that draw
  characters.
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

- `ascii_prism/web/` is the page: `app.js` captures the webcam, sends one
  JPEG frame at a time over a WebSocket and draws the frame that comes back.
  Only one frame is in flight, so the stream runs at whatever rate the server
  can process.
- `ascii_prism/server.py` is the FastAPI app. Each connection gets its own
  hand tracker, renderer and settings; frames are processed in a thread pool
  so the event loop stays responsive.
- `ascii_prism/pipeline.py` ties tracking, geometry and the active lens
  together per frame and draws the fingertip overlay. It has no I/O, so it
  is shared by the website and desktop mode and is easy to test from files.
  It also keeps the short frame history the echo lens looks into.
- `ascii_prism/lenses/` is the portal. `base.py` defines what a lens is
  (pick a source frame, say how big to sample the window, paint the flat
  image), `looks.py` holds every look as a pure function of that flat
  image, and each other file wraps one look as a lens. The registry in
  `__init__.py` is what the settings, the page and the desktop panel read.
- `ascii_prism/warp.py` samples the window out of a frame as a flat image
  and pastes a flat image back, through a bilinear map that also handles a
  twisted window when one hand is flipped.
- `ascii_prism/hands.py` wraps MediaPipe's Hand Landmarker and returns the
  thumb and index fingertips of up to two hands.
- `ascii_prism/geometry.py` orders the four points, checks convexity, sizes
  the quad, smooths it over time, and builds the perspective maps with
  OpenCV.
- `ascii_prism/ascii.py` owns the glyph atlas and grid sizing. Pillow
  rasterises the ramp from a monospace font, sized so a block character
  fills a cell exactly. The ASCII lens shrinks the sampled window to one
  pixel per cell for average colours, luminance picks a glyph per cell, and
  NumPy composes the flat character image.
- `ascii_prism/app.py` and `panel.py` are desktop mode: OpenCV window, keys,
  status bar and a Tkinter customizer.

On an Apple Silicon Mac the server spends roughly 10 to 30 ms per 720p frame
(hand tracking dominates), which gives 30 fps or better in the browser. The
lenses add a few milliseconds each; the person lens also runs a selfie
segmenter (a 250 KB model fetched on first use, next to the hand model) on
the window's surroundings, about 5 ms more.

## Tests

```bash
python -m pytest
```

Geometry, rendering, lens and server-validation tests run offline. The
pipeline, WebSocket and person-lens tests download a sample photo of two
hands and the models on first run, and are skipped if they cannot be
fetched. Cached files land in `tests/.cache/` and `~/.cache/ascii-prism/`.

## Deploying

The server needs long-lived WebSocket connections, so it fits hosts that run
a persistent Python process (Fly.io, Railway, Render, a VPS), not serverless
platforms such as Vercel functions. Run it with `--host 0.0.0.0` behind
HTTPS. Note that every visitor's video is processed on the server, so plan
CPU accordingly; one core handles roughly one viewer at full frame rate.
