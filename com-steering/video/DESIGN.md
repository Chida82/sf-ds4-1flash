# DESIGN — video "Candor"

Format and style rules for the Remotion project. The scenes are in
[`STORYMAP.md`](STORYMAP.md), the text in [`NARRATION.md`](NARRATION.md).

## Format

| | |
|---|---|
| Canvas | 1920 × 1080 landscape, 30 fps |
| Slides language | English |
| Narration | Italian, in `NARRATION.md`, with the slide text in English and its Italian translation |
| Voice | none for now: the text is read by the presenter |
| Length | about 17.5 min, at most 20 |
| Outputs | **presenter** (`npm run presenter`, pauses at every `[STOP]`) and **distribution** (`npm run render` → `out/candor.mp4`) |

## Style: light wireframe isometric, 60-30-10

Version 1 was Glassmorphism, version 2 a dark wireframe-isometric blueprint. Version 3 keeps
the isometric wireframe but on a light, premium base (rule 60-30-10):

- 60 %, background (`src/Video.tsx`): slate-ice `#F1F5F9` with a slowly drifting isometric
  grid (30° lines and verticals), a few wireframe cubes in the corners and a stack of layer
  plates at the lower right (the model's layers), all faint so they never fight the content.
- Cards (`glass` in `src/anim.tsx`): white `#FFFFFF`, one radius (14 px), a slate hairline and
  a soft two-layer shadow. The model drawing, charts and terminal use the same card language.
- 30 %, text: deep slate `#0F172A` for titles and text, `#64748B` for labels and captions.
- 10 %, accents with a fixed meaning: teal `#0D9488` = the model / core data, orange
  `#EA580C` = steering vector / highlight, lime `#65A30D` = comply / positive, crimson
  `#E11D48` = refusal / failure / removed, magenta `#B1289C` = think phase. The tone names in
  the code (`cyan`, `amber`, `mint`, `coral`, `violet`) are kept from version 1: read them by role.
- More than three series: `accent(i)` in `src/anim.tsx` gives the three base accents, then
  vivid HSL colours that walk the hue wheel by the golden ratio and skip 200°–280° (no blue,
  no violet). The line-count treemap of S4.1 uses it.
- Type: system sans for text, monospace for tokens, numbers and code.

## The model as a mixture of experts

Whenever the video animates the model it draws the same object (`src/viz/Model.tsx`):
one column per layer, an **expert grid** on top (two cells per layer light up as a token
passes, as the router picks them), the **attention** pill below, and the **residual
stream** as a highway at the bottom. A token is a glowing pulse travelling left to right.
Things done *to* the model are drawn on the highway: an amber ring is steering, a coloured
band is a group of layers. What is not touched keeps the neutral grey.

## Motion rules

| Element | Effect | Where |
|---|---|---|
| Text a model would produce: the prompt of S1, quoted answers, the terminal | **Token-by-token stream**, blinking cursor | `Stream` in `src/anim.tsx` |
| Titles, captions and notes | appear whole, with a slide-up | `Up`, `Cap` |
| Vectors, arrows, curves, chart lines | **Stroke draw-in**, `cubic-bezier(0.4, 0, 0.2, 1)`, no bounce | `Draw`, `LineChart` |
| Boxes, cards, rows | **Staggered slide-up** (fade + 20–40 px) | `Up` |
| Bars | grow with the same easing | `ui.tsx` |

Animations start at fractions of the slide's duration and finish at 82 % of it (at most
45 s), so the end state is on screen when the presenter stops. Slide duration comes from
the narration length (150 words per minute) with a per-slide minimum. A slide in
`src/slides.ts` can set `dur` (exact seconds) and `tail` (seconds the finished animation
stays up before the next slide): the animation then fills `dur − tail`.

## Honesty marks on screen

Charts that are not plotted from a series say so: "schematic" (S9.1, S9.3, S12.1, S13.1).
The numbers are real; only the layout is illustrative. S4.1 line counts come from
`src/data/ablation.json` (tracked text files, ds4 at `ee7e840` against this tree).

## Stops

A narration section that contains `[STOP]` is a stop: the presenter player pauses on its last
frame; Space plays, Right arrow jumps to the next slide. The distribution render ignores stops.

## Build

- Remotion 4 project in `com-steering/video/remotion/`; local install only (no global
  install, npm cache redirected to a temporary directory); the headless browser is downloaded
  by Remotion on first render.
- `npm run prep` parses `NARRATION.md` into `src/narration.generated.json` (ignored by git).
- `npm run stills -- S4.1@0.5 S6.1` renders PNG stills to `out/stills/` to check a slide.
- Remotion needs a paid company licence for larger for-profit teams: check before
  distributing outside personal use.
