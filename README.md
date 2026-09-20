# ASCII Prism

Turn the space between your fingertips into live ASCII art.

Hold both hands up to your webcam with thumbs and index fingers extended. The
four fingertips become the corners of a window: inside it the video is
rendered as characters, outside it stays ordinary video. Move, tilt or skew
your hands and the character grid follows in perspective.

Everything runs locally in the browser. No frames leave your machine.

## Run it

You need a browser with WebGL2 and camera access (Chrome, Edge, Safari 17+ or
Firefox). The hand-tracking model is fetched from Google's CDN on first load,
so an internet connection is needed the first time.

```bash
npm start
```

Then open <http://localhost:5173> and allow camera access. Any static file
server works, for example `python3 -m http.server 5173`. Opening `index.html`
directly from disk will not work because the app uses ES modules.

## The gesture

Think of holding a sheet of paper by its corners: index fingers on top,
thumbs at the bottom. The app does not care which finger is which corner. It
takes the four fingertips, orders them clockwise and maps the character grid
onto that quadrilateral. If the four points cross over each other (a
non-convex shape) the window is hidden until you spread them out again.

When fewer than two hands are visible the window disappears and you see
plain video. Press <kbd>L</kbd> or click **Lock region** to freeze the
current window so you can lower your hands.

## Customizer

The panel on the right (toggle with <kbd>H</kbd>) controls:

- **Characters.** Pick a preset ramp or type your own. Characters are ordered
  from darkest to brightest; each cell picks the character whose position in
  the ramp matches its brightness. Emoji and block characters work.
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
- **Show fingertips and outline.** Draws the tracked fingertips and the
  window outline.
- **Mirror camera.** Selfie-style mirroring, on by default.
- **Preview region without hands.** Shows a fixed window so you can tune the
  look without holding your hands up.

Settings persist in `localStorage`.

## How it works

- `src/hands.js` wraps MediaPipe's Hand Landmarker (tasks-vision) and
  returns the thumb and index fingertips of up to two hands.
- `src/geometry.js` orders the four points, checks convexity, and builds the
  projective map (homography) from the unit square to the quadrilateral, plus
  its inverse.
- `src/renderer.js` is a WebGL2 renderer. Pass one draws the camera frame.
  Pass two is a full-screen fragment shader: each pixel is mapped through the
  inverse homography into the unit square (pixels outside are discarded so
  the video shows through), assigned to a character cell, and coloured from
  the average of nine video samples across that cell. Luminance selects a
  glyph from a font atlas that is rebuilt whenever the character ramp
  changes.
- `src/main.js` runs the camera, the per-frame loop, the overlay and the UI.

There is no build step and no framework.

## Tests

```bash
npm test           # unit tests for the geometry (node:test)
npm run test:browser
```

The browser test needs Google Chrome installed and `npm install` (for
`playwright-core`). It drives the app headlessly with Chrome's fake camera,
checks the model loads and the customizer works, then feeds Chrome a sample
photo of two hands and checks that fingertips are tracked and a window
appears. Screenshots land in `tests/browser/.cache/`.

## Deploying

The app is static, so any static host works. Camera access requires HTTPS
(or localhost), which hosts like Vercel, Netlify and GitHub Pages provide.
For Vercel, `vercel` from this directory is enough; there is nothing to build.
