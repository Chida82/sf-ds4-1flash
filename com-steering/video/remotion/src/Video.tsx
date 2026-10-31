import React from "react";
import { AbsoluteFill, Sequence, useCurrentFrame } from "remotion";
import { C, ink, tint } from "./anim";
import { segments, totalFrames } from "./timeline";
import { SlideView } from "./ui";

// Wireframe isometric backdrop: a drifting isometric grid, a few wireframe cubes and a stack
// of layer plates (the model's layers) at the lower right. It sits outside the sequences,
// so it does not blink between slides.
const K = Math.tan(Math.PI / 6); // 30° isometric slope
const STEP = 120;

const cube = (cx: number, cy: number, s: number, color: string, key: number) => {
  const v = [90, 30, -30, -90, -150, 150].map((a) => [cx + s * Math.cos((a * Math.PI) / 180), cy - s * Math.sin((a * Math.PI) / 180)]);
  const hex = v.map((p) => p.join(",")).join(" ");
  return (
    <g key={key} fill="none" stroke={color} strokeWidth={1.6}>
      <polygon points={hex} />
      <polyline points={`${v[1].join(",")} ${cx},${cy} ${v[5].join(",")}`} />
      <line x1={cx} y1={cy} x2={v[3][0]} y2={v[3][1]} />
    </g>
  );
};

const plate = (cx: number, cy: number, s: number, key: number, lit: number) => {
  const p = [[cx, cy - s], [cx + s * 0.866, cy - s / 2], [cx, cy], [cx - s * 0.866, cy - s / 2]];
  return (
    <g key={key}>
      <polygon points={p.map((q) => q.join(",")).join(" ")} fill={tint(C.cyan, 0.05)} stroke={C.cyan} strokeWidth={1.4} />
      <polygon points={[[cx, cy - s * 0.7], [cx + s * 0.3, cy - s * 0.55], [cx, cy - s * 0.4], [cx - s * 0.3, cy - s * 0.55]].map((q) => q.join(",")).join(" ")}
        fill={C.cyan} opacity={0.15 + 0.35 * lit} />
    </g>
  );
};

const Backdrop: React.FC = () => {
  const f = useCurrentFrame();
  const drift = (f * 0.35) % STEP;
  const W = 1920, H = 1080;
  const lines: React.ReactNode[] = [];
  for (let c = -W * K - STEP; c < H + STEP; c += STEP) {
    const o = c + drift;
    lines.push(<line key={`a${c}`} x1={0} y1={o} x2={W} y2={o + W * K} />);
    lines.push(<line key={`b${c}`} x1={0} y1={o + W * K} x2={W} y2={o} />);
  }
  for (let x = 0; x < W + STEP * 2; x += STEP * 1.1547) lines.push(<line key={`v${x}`} x1={x - drift * 0.5} y1={0} x2={x - drift * 0.5} y2={H} />);
  const bob = (ph: number, amp = 10) => Math.sin(f / 90 + ph) * amp;
  return (
    <AbsoluteFill style={{ background: `linear-gradient(160deg,#F8FAFC 0%,${C.bg} 55%,#E2E8F0 100%)` }}>
      <svg width={W} height={H} style={{ position: "absolute", inset: 0 }}>
        <g stroke="#64748B" strokeOpacity={0.14} strokeWidth={1}>{lines}</g>
        <g opacity={0.6}>
          {cube(1790, 150 + bob(0), 70, C.cyan, 0)}
          {cube(50, 1030 + bob(2), 34, C.amber, 1)}
          {cube(60, 150 + bob(1), 34, C.cyan, 3)}
        </g>
        <g opacity={0.3}>
          {[0, 1, 2, 3].map((i) => plate(1810, 1070 - i * 28 + bob(i * 0.5, 3), 100, i, 0.5 + 0.5 * Math.sin(f / 18 + i * 1.4)))}
        </g>
      </svg>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 45%, rgba(241,245,249,0.8) 0%, rgba(241,245,249,0.35) 70%, rgba(241,245,249,0) 100%)" }} />
    </AbsoluteFill>
  );
};

const Progress: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <div style={{ position: "absolute", left: 100, bottom: 26, width: 1720, height: 4, background: ink(0.1) }}>
      <div style={{ width: `${(f / totalFrames) * 100}%`, height: "100%", background: C.cyan }} />
      {segments.filter((s, i) => i === 0 || s.scene !== segments[i - 1].scene).map((s) => (
        <div key={s.from} style={{ position: "absolute", left: `${(s.from / totalFrames) * 100}%`, top: -5, width: 2, height: 14, background: ink(0.3) }} />
      ))}
    </div>
  );
};

export const Video: React.FC = () => (
  <AbsoluteFill>
    <Backdrop />
    {segments.map((s) => (
      <Sequence key={s.id} from={s.from} durationInFrames={s.frames}>
        <SlideView kicker={s.label} slide={s.slide} />
      </Sequence>
    ))}
    <Progress />
  </AbsoluteFill>
);
