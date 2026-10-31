import narration from "./narration.generated.json";
import { slides } from "./slides";
import type { Slide } from "./ui";

export const FPS = 30;
const WPM = 150;

export type Segment = { scene: string; id: string; label: string; slide: Slide; from: number; frames: number; stop: boolean };

// shortcut: duration = words at 150 wpm (floor: the slide's `min` seconds) + 1 s; a draft
// pace, not a recorded voice. Replace with measured audio length when a voice exists.
// A slide with `dur` (seconds) takes exactly that long, whatever the narration length.
const frames = (words: number, min: number, dur?: number) =>
  dur ? Math.round(dur * FPS) : Math.max(Math.round(min * FPS), Math.round((words / WPM) * 60 * FPS)) + FPS;

let cursor = 0;
export const segments: Segment[] = narration.scenes.flatMap((sc) =>
  sc.chunks.map((c) => {
    const slide = slides[c.slide];
    if (!slide) throw new Error(`${c.slide}: narration section without a slide in slides.ts`);
    const seg: Segment = { scene: sc.id, id: c.slide, label: `${c.slide} · ${sc.title}`, slide, from: cursor, frames: frames(c.words, slide.min ?? 8, slide.dur), stop: c.stop };
    cursor += seg.frames;
    return seg;
  }),
);

const known = new Set(segments.map((s) => s.id));
for (const id of Object.keys(slides)) if (!known.has(id)) throw new Error(`${id}: slide without a narration section`);

export const totalFrames = cursor;
// Presenter stops: last frame of each segment that ends with [STOP].
export const stopFrames = segments.filter((s) => s.stop).map((s) => s.from + s.frames - 1);
