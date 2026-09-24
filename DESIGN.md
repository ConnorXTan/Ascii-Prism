---
name: ASCII Prism
description: A viewfinder over live video. Smoked-glass instruments that recede so the fingertip window can lead.
colors:
  lens-black: "#000000"
  smoked-glass: "rgba(18, 18, 20, 0.84)"
  glass-hover: "rgba(255, 255, 255, 0.06)"
  glass-active: "rgba(255, 255, 255, 0.11)"
  hairline: "rgba(255, 255, 255, 0.10)"
  hairline-strong: "rgba(255, 255, 255, 0.22)"
  ink-well: "rgba(0, 0, 0, 0.35)"
  hint-glass: "rgba(0, 0, 0, 0.50)"
  bright-zinc: "#f4f4f5"
  zinc-ash: "#a1a1aa"
  zinc-smoke: "#6b6b74"
  pure-white: "#ffffff"
  signal-green: "#4ade80"
  lock-amber: "#fbbf24"
  fault-red: "#f87171"
  fault-glass: "rgba(60, 14, 20, 0.85)"
  fault-text: "#fecaca"
  mark-yellow: "#facc15"
  mark-blue: "#60a5fa"
typography:
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, 'Segoe UI', system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, 'Segoe UI', system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.45
  brand:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, 'Segoe UI', system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    letterSpacing: "0.01em"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, 'Segoe UI', system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
  tool:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, 'Segoe UI', system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 500
    letterSpacing: "0.01em"
  readout:
    fontFamily: "ui-monospace, 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1
  value:
    fontFamily: "ui-monospace, 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace"
    fontSize: "12px"
    fontWeight: 400
  input:
    fontFamily: "ui-monospace, 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace"
    fontSize: "13px"
    fontWeight: 400
    letterSpacing: "0.04em"
rounded:
  control: "6px"
  input: "8px"
  tool: "10px"
  glass: "14px"
  pill: "999px"
  round: "50%"
spacing:
  hair: "2px"
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "14px"
  xl: "18px"
  dock-gap: "20px"
  dock-height: "60px"
components:
  dock:
    backgroundColor: "{colors.smoked-glass}"
    rounded: "{rounded.glass}"
    padding: "4px"
    height: "{spacing.dock-height}"
  tool:
    textColor: "{colors.zinc-ash}"
    typography: "{typography.tool}"
    rounded: "{rounded.tool}"
    padding: "0 12px"
    width: "74px"
  tool-hover:
    backgroundColor: "{colors.glass-hover}"
    textColor: "{colors.bright-zinc}"
  tool-open:
    backgroundColor: "{colors.glass-active}"
    textColor: "{colors.bright-zinc}"
  tool-pressed:
    textColor: "{colors.lock-amber}"
  panel:
    backgroundColor: "{colors.smoked-glass}"
    textColor: "{colors.bright-zinc}"
    rounded: "{rounded.glass}"
    padding: "14px 18px 18px"
    width: "min(380px, calc(100vw - 24px))"
  chip:
    backgroundColor: "{colors.glass-hover}"
    textColor: "{colors.zinc-ash}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "5px 10px"
  chip-hover:
    backgroundColor: "{colors.glass-active}"
    textColor: "{colors.bright-zinc}"
  chip-selected:
    backgroundColor: "{colors.bright-zinc}"
    textColor: "{colors.lens-black}"
  input-text:
    backgroundColor: "{colors.ink-well}"
    textColor: "{colors.bright-zinc}"
    typography: "{typography.input}"
    rounded: "{rounded.input}"
    padding: "8px 10px"
  reset:
    textColor: "{colors.zinc-ash}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "2px 6px"
  pill-hint:
    backgroundColor: "{colors.hint-glass}"
    textColor: "{colors.bright-zinc}"
    rounded: "{rounded.pill}"
    padding: "9px 16px"
  pill-notice:
    backgroundColor: "{colors.fault-glass}"
    textColor: "{colors.fault-text}"
    rounded: "{rounded.pill}"
    padding: "9px 16px"
---

# Design System: ASCII Prism

## Overview

**Creative North Star: "The Viewfinder"**

ASCII Prism's interface is camera glass. The live video fills the viewport edge to edge and is the only source of colour and light; every piece of chrome is a translucent instrument laid over it, the way a camera's HUD sits over the scene. The picture leads. Controls recede into smoked glass at the top and bottom edges, brighten only when touched, and never occupy the middle of the frame, because the middle belongs to the visitor's hands.

The mood is quiet, precise and camera-like. Density is low: one slim readout bar, one dock of six tools, one panel open at a time, one transient pill for a hint or an error. Text is small and calm; anything the machine measured is set in monospace so numbers read as readouts rather than copy. Depth is ambient rather than structural: the glass floats on blur and a single soft shadow, it is not stacked.

Confirmed rejections: no sidebar or single column of stacked controls next to the video; no neon or brand-coloured accent in the chrome; no opaque panels.

**Key Characteristics:**
- Full-bleed video on a black stage; chrome is overlaid, never beside.
- Smoked glass (dark, 84% opaque, blurred) for every persistent surface.
- Colour in the chrome means status and nothing else: green connected, amber locked, red failed.
- Zinc text ramp in three steps; brightness, not hue, signals hierarchy and state.
- System sans for words, system mono for measurements.
- Pills for anything transient or selectable; rounded rectangles for anything that stays.

## Colors

A near-monochrome palette of black, smoked glass and zinc, with three status colours that appear only when they are true.

### Primary
- **Bright Zinc** (#f4f4f5): the primary text colour and the only solid fill in the chrome. A selected preset chip inverts to Bright Zinc with black text. Slider thumbs and switch knobs are **Pure White** (#ffffff) so they read as touchable.

### Neutral
- **Lens Black** (#000000): the stage behind the video and the letterbox around it. The page's base.
- **Smoked Glass** (rgba(18, 18, 20, 0.84)): the dock and every panel. Always paired with a backdrop blur and a hairline border.
- **Glass Hover** (rgba(255, 255, 255, 0.06)) and **Glass Active** (rgba(255, 255, 255, 0.11)): the two fills that show hover and open state on tools and chips. Hierarchy by brightness, never by hue.
- **Hairline** (rgba(255, 255, 255, 0.10)): the 1px border on every glass surface, input and chip. **Hairline Strong** (rgba(255, 255, 255, 0.22)) for dividers, slider tracks and the off state of switches.
- **Ink Well** (rgba(0, 0, 0, 0.35)): the recessed field behind the ramp text input. **Hint Glass** (rgba(0, 0, 0, 0.50)): the hint pill's fill.
- **Zinc Ash** (#a1a1aa): secondary text, tool labels, field labels and the readout. **Zinc Smoke** (#6b6b74): notes, dim readout items and the idle connection dot.

### Status
- **Signal Green** (#4ade80): the connection dot while tracking, and a switch that is on.
- **Lock Amber** (#fbbf24): the Lock tool while the window is frozen, the warning state of the connection dot, and the window outline drawn into the video while locked (the server draws it as BGR (0, 196, 255), the same hue).
- **Fault Red** (#f87171): the connection dot on error, and the border of the notice pill at 40% alpha. The notice fills with **Fault Glass** (rgba(60, 14, 20, 0.85)) and sets its text in **Fault Text** (#fecaca).

### Mark
- The prism mark is a triangle on black filled with a diagonal gradient from Fault Red's hex (#f87171) through **Mark Yellow** (#facc15) to **Mark Blue** (#60a5fa). It appears in the favicon and the top bar, and nowhere else.

### Named Rules
**The Status-Only Colour Rule.** The chrome is colourless. If a hue appears on a control, it is because something is true right now: connected, locked, or failed. Decorative colour comes from the video, never from the interface, and the prism gradient stays inside the mark.

**The Brightness Ladder Rule.** State and hierarchy are shown by stepping up the zinc ramp or the glass fills (Smoke, Ash, Bright; Hover, Active, Selected), not by changing hue.

## Typography

**Display Font:** none. There is no display scale; the largest type in the interface is 14px.
**Body Font:** the system sans (SF Pro Text on Apple platforms, then Inter, Segoe UI, system-ui).
**Label/Mono Font:** the system mono (SF Mono, Menlo, Consolas, DejaVu Sans Mono).

**Character:** small, calm and native. The sans disappears into the platform; the mono makes any measured value look like a camera readout. Three weights only: 400 for reading, 500 for tool captions, 600 for the brand and panel titles.

### Hierarchy
- **Title** (600, 13px): panel headings and the brand wordmark. The brand adds 0.01em tracking and a 1px black text shadow so it survives over video.
- **Body** (400, 14px, 1.45): the base size. Switch labels and the hint and notice pills use it at 13px.
- **Label** (400, 12px, Zinc Ash): field labels, wheel value names, reset buttons and chips. Notes drop to Zinc Smoke.
- **Tool** (500, 11px, 0.01em; 10px under 560px): the caption under each dock icon.
- **Readout** (mono, 12px, line-height 1; 11px under 560px): the top bar's status line, Zinc Ash with dim items in Zinc Smoke.
- **Value** (mono, 12px, Bright Zinc): every live number next to a control, such as `80`, `100%`, `+0°`, `10 levels`.
- **Input** (mono, 13px, 0.04em): the ramp text field, tracked out so individual characters can be told apart.

### Named Rules
**The Mono Means Measured Rule.** Anything the machine produced (a percentage, a count, a frame time, a hex code, a character ramp) is set in the mono face. Anything a person reads as language is set in the sans. Never mix the two inside one string.

## Layout

The stage is a fixed, full-viewport canvas on Lens Black with `object-fit: contain`, so the video is letterboxed rather than cropped. Every other element is `position: fixed` and layered over it; nothing scrolls except the inside of an open panel.

- **Top bar:** full width, 14px top and 20px side padding (the top respects the safe-area inset), with a 26px-deep gradient scrim from 55% black to transparent. Brand at the left, readout at the right, 16px gap. The bar ignores pointer events except on its children so it never blocks the stage.
- **Dock:** centred at the bottom, 20px up or the safe-area inset if larger, 60px tall, 4px inner padding, 2px between tools. Six tools with a 1px divider between the four panel tools and the two actions. On narrow screens tools shrink from 74px to 58px minimum width.
- **Panel:** centred above the dock with a 12px gap, `min(380px, 100vw - 24px)` wide, max-height set so it never reaches the top bar, scrolling internally. Padding 14px top, 18px sides and bottom. Fields stack 14px apart; a field's label row and its control sit 8px apart.
- **Hint and notice pills:** top-centre at 56px plus the safe-area inset, max width `min(520px, 100vw - 32px)`. A visible notice hides the hint.
- **Unhide:** a small pill at bottom-right, 16px in, shown only while the chrome is hidden with `H`.
- **Z-order:** stage 0, top bar 5, pills 6, panel 7, dock and unhide 8.
- **Breakpoint:** one, at 560px. Below it the readout tightens and hides frame time, tools shrink, and the colour wheel stacks above its values and grows to 180px.

### Named Rules
**The Clear Stage Rule.** Chrome lives on the top and bottom edges. Nothing persistent is placed in the middle band of the viewport; that band belongs to the hands. Only the transient hint may approach it, and only from the top.

**The One Panel Rule.** At most one panel is open, and it always opens from the dock, centred. There is no second column, no drawer, no sidebar.

## Elevation & Depth

Depth is ambient. Surfaces float on blur rather than sit on shelves. Every persistent surface is Smoked Glass with `backdrop-filter: blur(20px) saturate(140%)` (24px on panels, 12px on pills), a Hairline border, and one shared shadow. Text placed directly on video gets a 1px, 2px-blur black text shadow instead of a background.

### Shadow Vocabulary
- **Glass shadow** (`box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45), 0 1px 0 rgba(255, 255, 255, 0.04) inset`): the dock and panels. The inset hairline is the glass's top edge catching light.
- **Thumb shadow** (`box-shadow: 0 1px 4px rgba(0, 0, 0, 0.5)`): slider thumbs, so a white dot separates from a white track end.
- **Dot ring** (`box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.35)`): the connection dot's halo over video.
- **Scrim** (`linear-gradient(rgba(0, 0, 0, 0.55), rgba(0, 0, 0, 0))`): the top bar's only background.

### Named Rules
**The One Shadow Rule.** There is one shadow for glass and it does not change with state or importance. Hover, focus and open are shown with fill and text brightness, never with a bigger shadow or a lift.

## Shapes

Soft rounded rectangles for anything that stays, pills for anything transient or selectable, circles for anything that is a point.

- **Glass** (14px): the dock and panels.
- **Tool** (10px): the buttons inside the dock, nested 4px inside the 14px glass.
- **Input** (8px): the ramp text field.
- **Control** (6px): reset buttons and the backdrop colour swatch, 5px on the inner swatch.
- **Pill** (999px): hint, notice, preset chips, the unhide button and the switch track.
- **Round** (50%): the connection dot, slider thumbs, the switch knob, the colour wheel and its handle.
- **Borders:** 1px Hairline on every glass surface, chip and input; Hairline Strong on the dock divider and the colour input. No 2px borders anywhere in the chrome.
- **Icons:** 18px line icons, 1.5px stroke, round caps and joins, drawn in `currentColor` so they follow the text ramp.
- **In-video overlay:** the fingertip window is a thin white outline (Lock Amber when locked), with a white ring around a black core at each fingertip and hand labels in white with a heavy black stroke. The overlay is the one place a heavier stroke is allowed, because it sits on video rather than glass.

## Components

Refined and restrained: hairline borders, translucent fills, and states shown by brightness rather than colour. Hit areas are generous but the drawing is light.

### Dock and Tools
- **Shape:** the dock is Smoked Glass at 14px; each tool is a 10px rounded rectangle, an 18px icon over an 11px caption, minimum 74px wide, 5px between icon and caption.
- **Rest:** transparent fill, Zinc Ash icon and caption.
- **Hover:** Glass Hover fill, Bright Zinc text, 120ms ease on both.
- **Open** (`aria-expanded="true"`): Glass Active fill, Bright Zinc.
- **Pressed** (`aria-pressed="true"`, the Lock tool): icon and caption turn Lock Amber, the caption reads "Locked", and the padlock's shackle rotates open.
- **Divider:** 1px Hairline Strong with a 10px vertical inset.

### Panel
- **Shape:** 14px Smoked Glass with the glass shadow and a 24px blur.
- **Header:** 13px semibold title on the left; a 12px Zinc Ash "Reset" text button on the right that gains Glass Hover and Bright Zinc on hover.
- **Motion:** rises 6px and fades in over 140ms ease-out; none under reduced motion.
- **Content:** fields stacked 14px apart. Each field is a label row (label left in Zinc Ash, mono value right in Bright Zinc) over its control.

### Chips (preset ramps)
- **Style:** pill, Glass Hover fill, Hairline border, 12px Zinc Ash text, 5px by 10px padding, 6px apart.
- **Hover:** Glass Active fill, Bright Zinc text.
- **Selected** (`aria-checked="true"`): inverted to a Bright Zinc fill and border with black text. The only solid fill in the chrome.

### Range Slider
- **Track:** 3px tall, 2px radius, Hairline Strong.
- **Thumb:** 14px Pure White circle with the thumb shadow.
- **Focus:** a 3px halo of 35% white replaces the outline.
- **Value:** always paired with a mono readout in the field's label row.

### Switch
- **Track:** 30px by 18px pill, Hairline Strong when off, Signal Green when on, 150ms ease.
- **Knob:** 14px Pure White circle inset 2px, sliding 12px.
- **Focus:** a 2px halo of 50% white on the track.

### Text Input (ramp)
- **Style:** 8px radius, Ink Well fill, Hairline border, 13px mono tracked 0.04em, 8px by 10px padding.
- **Focus:** border steps up to Hairline Strong; no outline.

### Colour Swatch
- **Style:** a 30px by 22px native colour input with a 6px radius and a Hairline Strong border, followed by the hex in 12px mono Zinc Ash.

### Hint and Notice Pills
- **Hint:** pill, Hint Glass fill, Hairline border, 12px blur, 13px Bright Zinc text, centred. Transient guidance such as "Show both hands".
- **Notice:** the same pill in Fault Glass with a 40% Fault Red border and Fault Text. It is the only error surface and it takes priority over the hint.

### Readout (signature)
The top-right status line: a 7px connection dot (Zinc Smoke idle, Signal Green tracking, Lock Amber warning, Fault Red error) with its ring, then the connection word in Bright Zinc, then mono items in Zinc Ash 14px apart, with secondary items such as handedness in Zinc Smoke. It reads like a camera's top display: `● Tracking  2 hands  R back · L back  80 × 5 · twisted  43 fps · 10.3 ms`.

### Colour Wheel (signature)
A 160px hue and saturation wheel (180px on narrow screens). Hue runs around the ring starting at the top, saturation runs from grey at the centre outward, and a thin 55% white ring at 70% radius marks the video as-is. The handle is a 16px ring with a 2px Pure White border and 1px black halos inside and out. Drag, arrow keys, or double-click to reset. The two values sit beside it as a two-row definition list with Hairline rules between rows.

### Fingertip Overlay (signature, in-video)
Drawn by the server into the frame, not by CSS. A thin white outline joins the four fingertips; each tip is a white ring with a black core; each hand is labelled ("R back", "L back") in white with a black stroke. When locked the outline turns Lock Amber and the Lock tool matches it, so the same hue means the same thing on glass and on video.

## Do's and Don'ts

### Do:
- **Do** keep the video full-bleed on Lens Black and lay every control over it as Smoked Glass with a Hairline border and backdrop blur.
- **Do** add new controls as a tool in the dock that opens one centred panel, following the field pattern: label left, mono value right, control beneath.
- **Do** show hover, open and selected by stepping up the glass fills and the zinc ramp; reserve Signal Green, Lock Amber and Fault Red for states that are true right now.
- **Do** set every measured value, count and code in the mono face at 12px.
- **Do** keep pills for the transient (hints, notices) and the selectable (chips), and 14px and 10px rounded rectangles for the persistent.
- **Do** respect safe-area insets at the top and bottom and honour `prefers-reduced-motion` by removing the panel rise and all transitions.

### Don't:
- **Don't** add a sidebar, a drawer, or a column of stacked controls beside the video.
- **Don't** put a persistent element in the middle band of the viewport; that space is for the hands.
- **Don't** introduce a decorative or brand accent colour into the chrome, including the prism gradient outside the mark and any neon green.
- **Don't** use opaque panels, hard or coloured shadows, or shadows that grow on hover.
- **Don't** open two panels at once or let a panel push the dock.
- **Don't** reintroduce a single-colour ink mode for the rendered characters; colour comes from the video through the wheel.
