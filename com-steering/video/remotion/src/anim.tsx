import React from "react";
import { Easing, useCurrentFrame, useVideoConfig } from "remotion";

// Light palette, 60-30-10: slate-ice background and white cards, deep slate text, three
// tech accents. The tone names are kept from the first draft; read them by role:
// cyan = teal (the model, core data), amber = orange (steering, highlight), mint = lime
// (positive), coral = crimson (refusal, failure), violet = magenta (think phase).
export const C = {
  cyan: "#0D9488", amber: "#EA580C", mint: "#65A30D", coral: "#E11D48", violet: "#B1289C",
  text: "#0F172A", dim: "#64748B", bg: "#F1F5F9", card: "#FFFFFF",
};
export type Tone = "cyan" | "amber" | "coral" | "mint" | "violet";
/** Slate ink at alpha `a`: hairlines, grid rules and empty cells on the light background. */
export const ink = (a: number) => `rgba(15,23,42,${a})`;
/** Tint of a palette colour (#rrggbb) at alpha `a`, for soft fills. */
export const tint = (hex: string, a: number) =>
  `rgba(${[1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(",")},${a})`;

/**
 * Colour of series `i`: the three base accents first, then vivid HSL colours that walk the
 * hue wheel by the golden ratio and skip the blue and violet arc (200°–280°).
 */
export const accent = (i: number) => {
  const base = [C.cyan, C.amber, C.mint];
  if (i < base.length) return base[i];
  const u = (((i - base.length) * 0.618034 + 0.08) % 1) * 280; // position in the 280° of allowed hues
  return `hsl(${Math.round(u < 200 ? u : u + 80)} 78% 42%)`;
};

export const font = "Inter, -apple-system, 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif";
export const mono = "'JetBrains Mono', 'SF Mono', Menlo, monospace";

// Content area under the title: 1920×1080 canvas minus 100 px side padding.
export const CW = 1720;
export const CH = 790;

// Smooth, no bounce: the motion rule of DESIGN.md.
export const ease = Easing.bezier(0.4, 0, 0.2, 1);
export const clamp = (x: number) => Math.max(0, Math.min(1, x));
/** Eased 0..1 progress of a `dur`-frame transition that starts at frame `start`. */
export const go = (f: number, start: number, dur = 18) => ease(clamp((f - start) / dur));
/** Linear 0..1 progress, for sweeps. */
export const lin = (f: number, start: number, dur: number) => clamp((f - start) / dur);
export const mix = (a: number, b: number, t: number) => a + (b - a) * t;

/**
 * Animation clock of a slide. `win` is the span in which the story unfolds (82 % of the
 * slide, at most 45 s), so the end state holds before the next slide or a presenter stop;
 * `t(0.3)` is the frame at 30 % of that span.
 */
export const TailCtx = React.createContext<number | undefined>(undefined);

export const useAnim = () => {
  const f = useCurrentFrame();
  const { durationInFrames: n } = useVideoConfig();
  const tail = React.useContext(TailCtx); // seconds the finished slide stays up, when the slide sets it
  const win = tail === undefined ? Math.min(n * 0.82, 45 * 30) : n - tail * 30;
  return { f, n, win, t: (frac: number) => frac * win };
};

/** Deterministic noise in 0..1, so renders are repeatable. */
export const hash = (a: number, b = 0) => {
  const s = Math.sin(a * 127.1 + b * 311.7) * 43758.5453;
  return s - Math.floor(s);
};

/** Staggered Slide-Up: fades in while rising `y` px. */
export const Up: React.FC<{ f: number; at: number; y?: number; dur?: number; style?: React.CSSProperties; children?: React.ReactNode }> =
  ({ f, at, y = 36, dur = 20, style, children }) => {
    const e = go(f, at, dur);
    return <div style={{ opacity: e, transform: `translateY(${(1 - e) * y}px)`, ...style }}>{children}</div>;
  };

/** Token-by-Token Stream: words appear one at a time, with a cursor while streaming. */
export const Stream: React.FC<{ text: string; f: number; at: number; wps?: number; cursor?: boolean; style?: React.CSSProperties }> =
  ({ text, f, at, wps = 7, cursor = true, style }) => {
    const toks = text.split(/(\s+)/);
    const words = toks.filter((t) => t.trim() !== "").length;
    const shown = Math.max(0, Math.floor(((f - at) * wps) / 30));
    let seen = 0;
    const streaming = f >= at && shown < words;
    return (
      <span style={style}>
        {toks.map((t, i) => {
          if (t.trim() === "") return <span key={i}>{t}</span>;
          seen += 1;
          return <span key={i} style={{ opacity: seen <= shown ? 1 : 0 }}>{t}</span>;
        })}
        {cursor && streaming && Math.floor(f / 8) % 2 === 0 && <span style={{ color: C.cyan }}>▍</span>}
      </span>
    );
  };

/** Stroke Draw-In for any SVG path/line: dashoffset from 1 to 0 over the eased progress `e`. */
export const Draw: React.FC<{ d: string; e: number; color: string; width?: number; arrow?: boolean; dash?: string }> =
  ({ d, e, color, width = 4, dash }) => (
    <path d={d} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round"
      pathLength={1} strokeDasharray={dash ?? "1"} strokeDashoffset={dash ? 0 : 1 - e} opacity={dash ? e : 1} />
  );

/**
 * Card: white, one radius, a slate hairline and a soft two-layer shadow that lifts it off
 * the ice background. Every panel of the video uses it.
 */
export const R = 14;
export const glass: React.CSSProperties = {
  background: C.card,
  border: `1.5px solid ${ink(0.1)}`,
  borderRadius: R,
  boxShadow: `0 1px 2px ${ink(0.06)}, 0 10px 28px ${ink(0.09)}`,
  padding: "24px 32px",
};

/** Caption / note: appears whole (a slide-up), never typed. */
export const Cap: React.FC<{ f: number; at: number; size?: number; style?: React.CSSProperties; children?: React.ReactNode }> =
  ({ f, at, size = 27, style, children }) => (
    <Up f={f} at={at} y={18}><div style={{ fontSize: size, color: C.dim, ...style }}>{children}</div></Up>
  );

/** Token position along n layers for a sweep; far off-screen outside it, so the pulse vanishes when done. */
export const sweep = (f: number, start: number, dur: number, n: number) =>
  f < start || f >= start + dur ? -99 : lin(f, start, dur) * (n + 1) - 0.5;

export const fmt = (n: number, d = 0) => n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
