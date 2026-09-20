# ASCII Prism

Turn the space between your fingertips into live ASCII art.

Hold both hands up to your webcam with thumbs and index fingers extended. The
four fingertips become the corners of a window: inside it the video is
rendered as characters, outside it stays ordinary video. Move, tilt or skew
your hands and the character grid follows in perspective.

Built with Python, OpenCV, MediaPipe and NumPy. Everything runs locally; no
frames leave your machine.

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

Two windows open: the video and a small customizer panel. macOS will ask for
camera permission for your terminal the first time.

Useful options:

```bash
python -m ascii_prism --camera 1                 # a different camera
python -m ascii_prism --source clip.mp4          # a video or image file instead
python -m ascii_prism --source photo.jpg --snapshot out.png   # one frame, no windows
python -m ascii_prism --no-panel                 # keyboard controls only
python -m ascii_prism --font /path/to/Mono.ttf   # a different monospace font
```

Keys in the video window:

| Key | Action |
| --- | --- |
| `L` | Lock or unlock the current window so you can lower your hands |
| `H` | Show or hide the customizer panel |
| `T` | Toggle fingertip dots and outline |
| `M` | Toggle camera mirroring |
| `I` | Invert brightness |
| `-` / `=` | Fewer / more characters across |
| `F` | Fullscreen |
| `S` | Save the current frame as a PNG |
| `Q` or `Esc` | Quit |

## The gesture

Think of holding a sheet of paper by its corners: index fingers on top,
thumbs at the bottom. The app does not care which finger is which corner. It
takes the four fingertips, orders them clockwise and maps the character grid
onto that quadrilateral. If the four points cross over each other (a
non-convex shape) the window is hidden until you spread them out again.

When fewer than two hands are visible the window disappears and you see
plain video.

## Customizer

- **Characters.** Pick a preset ramp or type your own. Characters are ordered
  from darkest to brightest; each cell picks the character whose position in
  the ramp matches its brightness. Block characters work.
- **Invert brightness.** Flip the ramp, useful for light backgrounds.
- **Characters across.** How many character columns the window has, from 16
  to 200. Rows are derived from the window's shape so characters keep their
  natural proportions.
- **Colour.** *Video colours* tints each character with the average colour of
  the video it replaces. *Vivid* normalises those colours so dark cells still
  read clearly. *Single colour* uses one ink colour. The background colour
  applies in all modes.
- **Smoothing.** Damps fingertip jitter. Higher values are steadier but lag
  more.
- **Show fingertips and outline** and **Mirror camera** do what they say.

Settings are saved to `~/.config/ascii-prism/settings.json`.

## How it works

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
- `ascii_prism/pipeline.py` ties tracking, geometry and rendering together
  per frame and draws the fingertip overlay. It has no windows, so it can be
  tested and driven from files.
- `ascii_prism/app.py` handles the camera, the window, keys and the status
  bar. `ascii_prism/panel.py` is the Tkinter customizer.

On an Apple Silicon Mac, hand tracking takes about 19 ms per 720p frame and
the ASCII render about 7 ms, so the app runs at roughly 30 fps.

## Tests

```bash
python -m pytest
```

Geometry and rendering tests run offline. The pipeline test downloads a
sample photo of two hands and the hand model on first run, and is skipped if
they cannot be fetched. Screenshots and cached files land in `tests/.cache/`.
