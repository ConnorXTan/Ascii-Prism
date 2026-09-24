# Lenses: the window as a portal

Status: looks prototyped and tuned (see Preview findings at the end); pipeline work not started. Written 2026-09-24.

## Why

Today the fingertip window does one thing: it shows the live video as
characters. The border is the identity of the app; what is inside it does
not have to be ASCII of the live frame. A **lens** is what the window looks
into. Pick a lens and the same four fingertips frame a different world: the
room two seconds ago, Matrix rain, a thermal camera, a Game Boy, a pencil
sketch, or only the person in ASCII with the background left as video.

Lenses give the app a second verb (switch) and a reason to keep holding
the frame up. They also make good clips, which is how the app spreads.

## Design

### A lens is a strategy, the renderer keeps the scaffolding

`AsciiRenderer.render` in `ascii_prism/ascii.py` currently does five things
in a row: size the grid, sample the quad flat, turn samples into glyphs,
warp the flat image back into the quad, blend it over the frame. Steps 1, 2,
4 and 5 are the same for every lens. Only "turn samples into a picture"
changes, plus occasionally *which* frame is sampled.

Split it like this:

- `ascii_prism/warp.py` (new): `sample_quad(src, quad, w, h)` returns the
  quad's contents as a flat `(h, w, 3)` BGR image (the bilinear map plus
  `cv2.remap` that `render` does now). `paste_quad(frame, quad, flat, opacity)`
  warps a flat image back into the quad and blends it in, returning the
  valid mask (the inverse bilinear plus remap plus `blend` that `render` does
  now). If `src` has different dimensions from `frame`, scale the quad by the
  ratio before sampling, so history frames can be stored small.
- `ascii_prism/lenses/base.py` (new):

  ```python
  class Lens:
      id: str
      label: str
      blurb: str            # one line for the panel
      needs_history = False # pipeline keeps a frame ring buffer only if True

      def source(self, ctx) -> np.ndarray:            # default: ctx.frame
      def sample_size(self, quad, settings, ctx) -> tuple[int, int]
      def paint(self, sampled, quad, settings, ctx) -> tuple[np.ndarray, RegionInfo | None]
      def reset(self) -> None                          # on switch or mirror change
  ```

  `ctx` is a small `LensContext` dataclass: the live `frame`, `timestamp_ms`,
  `dt` since the last frame, a `history(seconds)` accessor, and the
  `AsciiRenderer` (for `grid_for`, `atlas` and `cell_aspect`). Lenses are
  stateful objects, one instance per session, because rain needs drop
  positions and echo needs a buffer.

- `ascii_prism/lenses/ascii.py`: the current glyph composition moved into
  `AsciiLens.paint` with no behaviour change. `AsciiRenderer` keeps the font,
  atlas cache and `grid_for`; it becomes the shared toolkit rather than the
  whole pipeline. `RegionInfo` still comes back for the grid readout.
- `ascii_prism/lenses/__init__.py`: `LENSES` registry (ordered list of
  classes), `by_id`, `DEFAULT_LENS_ID = "ascii"`.
- `Pipeline.process` in `ascii_prism/pipeline.py` replaces the single
  `self.renderer.render(frame, quad, s)` call with: pick the lens for
  `s.lens` (instantiate on change, call `reset` on the old one), build the
  context, `src = lens.source(ctx)`, `sampled = sample_quad(src, ...)`,
  `flat, region = lens.paint(...)`, `paste_quad(frame, quad, flat, s.opacity)`.
  The pipeline also owns the frame history ring buffer, filled only while
  the active lens has `needs_history`.

Everything in the existing test suite for geometry, twisted quads and the
locked window keeps working because the quad handling does not move.

### Settings and validation

Add to `Settings` in `ascii_prism/settings.py`:

| field | type | default | range | used by |
|---|---|---|---|---|
| `lens` | str | `"ascii"` | must be a registered id | all |
| `delay` | float | 1.5 | 0.2 to 3.0 s | echo |
| `person_invert` | bool | False | | person |

`clamp()` resets an unknown `lens` to the default so a stale localStorage
value or a hand-edited settings file cannot pick a lens that does not exist.
`apply_settings` in `server.py` already accepts str, float and bool fields by
type, so no change there beyond the `RANGES` entry for `delay`.

`/api/config` gains `"lenses": [{"id", "label", "blurb"}]` so the page and
the desktop panel build their lists from one source.

### Switching

Phase 1, keyboard and UI:

- Web: a **Lens** button in the dock opens a panel with one radio card per
  lens (same pattern as the charset presets in `app.js`). Lens-specific
  controls sit under the cards and show only for the lens that uses them
  (the delay slider for echo, the invert switch for person). `PANEL_KEYS.lens`
  lists the three fields so the panel's Reset works. Keys: `[` and `]` cycle
  lenses, `1` to `9` pick by position. The top readout shows the lens name
  for a second after a switch.
- Desktop: a combobox in `panel.py` next to the charset one, and the same
  `[` and `]` keys in `app.py`.

Phase 3, gesture. Two candidates, to be tried on camera before choosing:

- **Wipe** (recommended). Both hand centres move horizontally faster than
  about one frame-width per second for at least 100 ms, then a 700 ms
  cooldown. Direction picks next or previous. Only needs `hand.center`
  history, which `Pipeline` can keep from the `Hand` objects it already gets.
  Ordinary framing moves are far slower, but the thresholds need tuning
  against real footage so slow drifts never trigger it.
- **Pinky flag.** Extend the pinky of one hand for 300 ms. Needs `hands.py`
  to also return the pinky tip and pinky knuckle. Less likely to misfire but
  less discoverable and awkward while holding the frame.

When switching, run a 250 ms transition: keep the outgoing lens alive, paint
both, and wipe between them along the window's u axis in the gesture's
direction (crossfade for keyboard switches).

## Lens catalogue

Costs are rough extra milliseconds per 720p frame on an Apple Silicon Mac,
on top of the 10 to 30 ms the pipeline spends today.

### Ship first

| id | what you see | how | state | cost |
|---|---|---|---|---|
| `ascii` | today's behaviour | existing code, moved | atlas cache | 0 |
| `thermal` | false-colour heat camera, no glyphs | luminance, light blur, `cv2.applyColorMap` with INFERNO | none | ~1 |
| `echo` | the scene 1.5 s ago, as ASCII | `source()` returns the history frame nearest `now - delay`; then `AsciiLens.paint` | ring buffer in pipeline | ~1 |
| `rain` | Matrix rain that reveals your silhouette | per column a drop head falls at its own speed; a cell lights where a head passed and fades behind it; multiply by video luminance so rain is only visible on bright shapes; random half-width katakana per cell reshuffled every few frames; green ink, white head | head y and speed per column, glyph indices | ~2 |
| `gameboy` | four-tone green handheld | downscale to about 160 cells wide keeping aspect, 4x4 Bayer ordered dither to `#0f380f #306230 #8bac0f #9bbc0f`, nearest-neighbour upscale | none | ~1 |
| `sketch` | pencil drawing on paper | grey, invert, Gaussian blur, colour-dodge divide, slight paper tint | none | ~2 |

`thermal` goes in with the plumbing because it is the smallest possible
lens and proves the whole path end to end.

### Ship second

| id | what you see | how | state | cost |
|---|---|---|---|---|
| `person` | only the person is ASCII, background stays video (or inverted) | MediaPipe Image Segmenter (selfie model, about 250 KB) run on the quad's bounding box scaled to 256 px; threshold the confidence mask; sample the mask through the same warp; `AsciiLens.paint` then blend with the sampled video where the mask is off | segmenter per session | ~6 to 10 |
| `night` | night vision goggles | green tint, gain, grain, vignette, faint scanlines | noise seed | ~1 |
| `kaleido` | the window folds into itself | fold u and v before sampling (4- or 6-fold mirror), then ASCII | none | ~1 |

`person` needs `model.py` generalised from one hard-coded URL to a small
table of models (`hand_landmarker.task`, `selfie_segmenter.tflite`) with the
same cache and download-once behaviour, and the segmenter must be created
lazily on first use so sessions that never pick the lens pay nothing.

### Maybe later

CRT with barrel distortion and chromatic fringing, a "frozen" lens that shows
the frame captured at lock, and an "ASCII on top" toggle so thermal, gameboy
and night can be drawn as characters too (their `paint` would feed the
`AsciiLens` instead of returning pixels).

## Phases

**Phase 0, refactor.** `warp.py`, `lenses/base.py`, `lenses/ascii.py`,
registry, pipeline wiring. `lens` is not yet a setting. Done when the full
test suite passes unchanged and a desktop snapshot of the sample photo is
pixel-identical before and after. One commit.

**Phase 1, plumbing.** Settings fields, `clamp` validation, `/api/config`
lenses list, web Lens panel with keys, desktop combobox and keys, `thermal`
lens. Done when you can switch between ascii and thermal from both the
browser and the desktop window, a bad lens id over the WebSocket is ignored,
and the readout names the lens. One commit for backend, one for web, one
for desktop.

**Phase 2, the fun ones.** `echo` with the history buffer, then `rain`,
`gameboy`, `sketch`. One commit each. Done when each has a unit test and
holds the frame rate target below.

**Phase 3, person and gestures.** Model table in `model.py`, `person` lens,
wipe gesture with tuning, transitions, `night` and `kaleido` if there is
appetite. One commit each.

**Phase 4, polish.** README section under Controls, panel blurbs, a
`--lens` flag for desktop mode, and a lens name in the desktop status bar.

## Tests

Follow the existing pattern in `tests/test_pipeline.py`: a `FakeTracker`
with two hands, a synthetic frame, `show_tips=False`, `smoothing=0`.

- `test_warp.py`: `sample_quad` of a flat-colour frame returns that colour;
  `paste_quad` of a solid image lands inside the quad and nowhere else;
  round trip on an axis-aligned quad is within one pixel; a smaller `src`
  than `frame` samples the right region.
- `test_lenses.py`, one small test per lens: `echo` shows the older of two
  frames after the delay has elapsed and the live frame before it; `rain`
  changes between frames and is empty on a black source; `gameboy` output
  has at most four distinct colours; `sketch` on a flat frame is near white;
  `thermal` maps black to the colormap's first entry; `person` is skipped
  when the segmenter model cannot be fetched (a fixture like `hand_model` in
  `tests/conftest.py`).
- `test_settings.py` (or extend `test_server.py`): `clamp` resets an unknown
  lens id; `delay` is clamped; `/api/config` lists every registered lens.
- `test_pipeline.py`: switching `settings.lens` mid-stream swaps the lens
  and resets the old one; the history buffer is empty while the active lens
  does not need it; the locked window keeps working through a switch.

## Performance and memory

- Target: no cheap lens adds more than 5 ms per 720p frame; `person` no more
  than 12 ms. Measure with `python -m ascii_prism desktop --source clip.mp4
  --max-frames 300`, which already prints the average fps.
- History buffer: store frames at most 640 px wide and keep only
  `delay + 0.5` seconds. At 30 fps and 3 s that is about 60 MB per session,
  acceptable locally. If the site is ever hosted, cap `delay` lower there or
  make it a server option.
- Every lens runs on the server per viewer, so the README's "one core per
  viewer" note stands. `person` roughly doubles the per-viewer cost.

## Decisions taken in this plan

- One flat list of lenses, one active at a time. A "source × look" split
  (delay as an option on any lens) was considered and deferred; if it is
  wanted later, `Lens.source` is already the seam.
- Lenses may be pixels, not only characters. The border is the product; the
  ASCII look is one lens among several and remains the default.
- Lens-specific parameters are typed `Settings` fields with `RANGES`
  entries, not a free-form dict, so the existing validation keeps working.

## Open questions

1. Katakana or Latin glyphs for `rain`? Katakana is the recognisable look
   and Menlo has the half-width forms; check the Linux and Windows fallback
   fonts render them before committing.
2. Should `echo` be ASCII (as planned) or raw video? ASCII keeps the app's
   identity; raw video is spookier. Could be a toggle later.
3. Wipe or pinky flag for gesture switching, to be decided on camera.

## Preview findings

Written 2026-09-24, before Phase 0, from a prototype of every look rendered
into the same fingertip window on the sample photo (`tests/.cache/hands.jpg`,
doubled to 1280 wide and lifted to webcam exposure). `lenses-preview.jpg`
next to this file is the contact sheet and `lenses-hero.jpg` shows four of
the looks in the full frame. Both come from `tools/lens_sheet.py`, which can
be re-run whenever a look is retuned.

What exists already, all new files and nothing the pipeline imports yet:

- `ascii_prism/warp.py`: `sample_quad` and `paste_quad` exactly as specified
  above, lifted from `AsciiRenderer.render`, plus the scaled-quad path for
  small history frames. Phase 0 can make `render` call these.
- `ascii_prism/lenses/looks.py`: every look as a pure function on the flat
  image (`thermal`, `gameboy`, `sketch`, `night`, `kaleido_remap`,
  `mirror_remap`, `ascii_look`, `person_look`), the stateful `Rain`, the
  `FixedCellAtlas` the rain needs, `PersonMask` around the segmenter, and
  `grid_for`, which sizes the cell grid the way `render` does. The `Lens`
  classes wrap these; their `paint` bodies are one or two lines each.
- `tests/test_warp.py` and `tests/test_looks.py`: the tests listed under
  Tests above, model-free except for one segmenter test that skips offline.

Decisions the preview settles:

- **Rain glyphs (open question 1).** Menlo, Monaco and Courier New all draw
  half-width katakana as tofu. Hiragino Sans has them on macOS; Noto Sans
  CJK and MS Gothic are the Linux and Windows candidates. `rain_glyphs()`
  picks katakana when such a font exists and falls back to Latin in the
  renderer's own font. At 12 x 18 px glyphs katakana is unmistakably the
  Matrix; Latin reads as generic code. Ship katakana with the fallback.
- **Rain on a dark room.** Scaling the trail purely by luminance leaves a
  dark scene empty. `Rain.paint(lift=0.07)` keeps a faint drizzle
  everywhere and lets bright shapes glow through at full strength.
- **Thermal.** Luminance alone made a white jumper hotter than a face.
  Adding red-over-blue as warmth (`skin=0.5`) makes skin the hottest thing
  in the window, which is what a thermal camera looks like to people.
- **Echo (open question 2).** ASCII echo is just a darker ASCII on a still;
  raw video echo reads instantly as "the past" because the mismatch at the
  window edge is visible. Default echo to raw video, keep ASCII as a toggle
  later if wanted.
- **Kaleido.** A 6-fold ASCII fold is abstract and dim. The 4-way mirror on
  raw video (the four-eyed face) is the one everyone recognises. Make
  `kaleido` the 4-way mirror on video; `kaleido_remap` stays for a later
  variant.
- **Person.** The selfie segmenter returns one confidence mask (1 = person),
  about 5 ms at 256 px wide. Feathering the mask edge by 0.15 hides the
  256 px staircase. `looks.ensure_segmenter` caches the model next to the
  hand model; fold it into `model.py`'s table when the lens is wired in.
- **Sample sizes.** Pixel looks (thermal, gameboy, sketch, night, echo
  video, mirror) want the quad sampled at its own pixel size, capped around
  480 px wide; glyph looks keep today's cols x 3 by rows x 3 supersample.
- **Font.** `AsciiRenderer()` with no path uses Pillow's bitmap font; every
  caller must pass `find_font()` as `server.py` does, or glyphs come out
  3 px wide.

Cost of each look on an 877 x 601 quad in a 1280 x 1920 frame, Apple
Silicon, including `paste_quad` (about 10 ms of every figure is the
existing warp and paste; the ASCII look today costs 30 ms on this quad):

| look | ms | look | ms |
|---|---|---|---|
| thermal | 19 | person (plus 5 for the segmenter) | 24 |
| echo, video | 14 | night | 30 |
| rain, katakana | 25 | kaleido, 6 fold ASCII | 19 |
| gameboy | 17 | kaleido, mirror video | 14 |
| sketch | 28 | | |

Sketch and night are the heavy ones at full quad resolution; sampling them
at half size brings both under the 5 ms target from the Performance section.
