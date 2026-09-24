# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: people evaluating Connor's computer vision work, such as recruiters
and hiring managers reading his CV or portfolio. They open the link on a
laptop with a webcam, give it about a minute, and judge whether it works and
whether it was built with care. They have no instructions and will not read
a README first.

Secondary: anyone who lands on the public link (friends, social followers,
strangers). Same situation: a webcam, a first visit, no guidance, a short
attention span.

Connor himself uses it locally while developing and demoing. Desktop mode
(`python -m ascii_prism desktop`) exists for him and for file-based testing;
the browser is the product.

## Product Purpose

Hold both hands up to the webcam with thumbs and index fingers extended, and
the space between the four fingertips becomes a live ASCII-art window that
follows the hands in perspective as they move, tilt, or twist. Outside the
window the video stays ordinary.

Success is a first-time visitor getting the window up within seconds and
feeling that it is responding to their hands, then staying to play with the
characters and colour. A second measure is that the visitor comes away
believing the underlying vision work is real and well made.

## Positioning

The gesture is the product. Ordinary ASCII webcam filters convert the whole
frame; ASCII Prism converts only the region the visitor frames with their own
fingertips, in perspective, with the border tracking every tilt and twist
(a flipped hand folds the window like a ribbon rather than breaking it).
That direct, physical control is the thing a neighbouring filter cannot
truthfully claim, and every feature has to serve it rather than compete
with it.

Secondary claim: all the vision work (hand tracking, warping, rendering) is
real Python on the server, not a browser shader, which is why the project
exists in this stack.

## Operating Context

- Runs in a browser with webcam access. Browsers only grant the camera on
  `localhost` or HTTPS, so any hosted deployment must be HTTPS.
- The browser streams JPEG frames over a WebSocket to a FastAPI server, which
  does all the tracking and rendering and streams frames back. One frame is
  in flight at a time, so frame rate follows server speed (roughly 10 to
  30 ms per 720p frame on Apple Silicon).
- Every viewer's video is processed on the server: about one CPU core per
  viewer at full rate. Hosting needs a long-lived process (Fly, Railway,
  Render, a VPS), not serverless functions.
- Locally nothing leaves the machine. On a hosted demo, video does go to the
  server; the product must say so honestly and never claim otherwise.
- Connor builds the project with several Claude Code sessions at once; one
  session commits for the others. UI and pipeline changes are often
  in-flight in the working tree at the same time.

## Capabilities and Constraints

Shipped:

- Two-hand fingertip framing with exponential smoothing; window hides when
  fewer than two hands are visible or the four points cross. Lock (`L`)
  freezes the window so hands can be lowered.
- Character ramps: presets (Standard, Detailed, Blocks, Dots, Binary,
  Minimal, Prism) or a custom string, dark to bright, with Invert.
- Grid width from 16 to 200 columns; rows follow the window's shape.
- Colour: every character takes the average colour of the video it replaces,
  then hue rotation and saturation via a wheel, plus opacity, brightness,
  and backdrop colour.
- Tracking panel: smoothing, fingertip and outline overlay, mirror.
- Fullscreen (`F`), hide controls (`H`), close panel (`Esc`).
- Settings persist in the browser's localStorage and are sent to the server
  on every change; `/api/config` is the single source of truth for presets,
  defaults, and ranges.

Planned, not started (see `docs/plans/lenses.md`): **lenses**, where the
window shows something other than live ASCII (the room two seconds ago,
Matrix rain, thermal, Game Boy, pencil sketch, person-only ASCII), switched
by keys first and a hand gesture later. Parked ideas from the same
discussion: snapshot and copy-as-text export; hand-seal gestures that cast
effects. None of these are commitments yet.

Technical constraints:

- Python 3.10 to 3.12 with MediaPipe 0.10.x. MediaPipe 1.x crashes at
  start-up on macOS (google-ai-edge/mediapipe#6356); do not bump.
- Block-character ramps need a TrueType monospace font on the server (Menlo,
  DejaVu Sans Mono, or Consolas).
- Not deployed anywhere yet. Hosting is the next step (see Users), so
  per-viewer CPU cost and HTTPS are live constraints on any new feature.

Terminology: **window** (the fingertip quad and what it shows), **ramp**
(the character set, dark to bright), **dock** (the bottom toolbar),
**panel** (one popover open at a time), **lock**, **fingertips**,
**lens** (planned: what the window looks into).

## Brand Commitments

- Name: **ASCII Prism**. Tagline in use: "Turn the space between your
  fingertips into live ASCII art."
- Existing mark: a triangle with a red, yellow, blue gradient on black, used
  as favicon and in the top bar. An existing asset, not yet confirmed as
  binding.
- Voice in the README and UI copy: plain, second person, no hype, explains
  the mechanism in one sentence.
- Layout constraints Connor set on 2026-09-24 and wants kept: the video
  fills the page; controls live in a bottom dock that opens one popover at a
  time; no sidebar or single column of stacked controls; a single neutral
  accent; no single-colour ink mode; prefer removing a marginal feature over
  adding one.

## Evidence on Hand

- Working software: the pipeline and web front end run locally with a
  webcam. Tests in `tests/` cover geometry, rendering, grading, and server
  validation offline, plus pipeline and WebSocket tests against a cached
  sample photo of two hands.
- UI screenshots from a review pass, desktop and phone, in
  `tests/.cache/ui-review/` (cache, not committed).
- Lens look references: `docs/plans/lenses-hero.jpg` and
  `docs/plans/lenses-preview.jpg`.
- Repository: https://github.com/ConnorXTan/Ascii-Prism

Absent, do not fabricate: no users, usage numbers, testimonials, press,
shared clips, or public deployment yet.

## Product Principles

1. **The hands are the interface.** A feature earns its place by making the
   fingertip window feel more immediate and responsive, never by adding a
   control that competes with it.
2. **Succeed in the first ten seconds.** A first-time visitor with no
   instructions must discover the gesture and see the window appear.
   Hints, empty states, and the connecting state are product surfaces, not
   afterthoughts.
3. **Latency beats detail.** Frame rate and responsiveness win over
   resolution or extra passes; anything that adds server time per frame must
   justify itself against the per-viewer cost of hosting.
4. **Read as considered, not generated.** Fewer, better controls; remove
   before adding; one accent, one dock, one open panel.
5. **Be honest about the camera.** Say where the video goes, locally and
   hosted, and never imply privacy the deployment does not provide.

## Accessibility & Inclusion

No standard has been set. Known facts: the core interaction requires two
visible hands with thumb and index finger extended, which is inherent to the
product and should be stated rather than hidden. Controls are reachable by
keyboard with ARIA labels and shortcuts, and the colour wheel supports arrow
keys. Any hosted version should keep those working.
