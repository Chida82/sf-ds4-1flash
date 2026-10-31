import React from "react";
import { C, Draw, go, ink, mono } from "../anim";

export type Series = { pts: [number, number][]; color: string; label?: string; at?: number; dur?: number; dash?: string; live?: boolean };
export type Mark = { x: number; y: number; label: string; color: string; a?: number; dx?: number; dy?: number; anchor?: "start" | "middle" | "end" };
export type Region = { x0: number; x1: number; label: string; color: string };

/** Line chart with Stroke Draw-In. Frame-driven: `f` is the slide frame. */
export const LineChart: React.FC<{
  w: number; h: number; f: number; xr: [number, number]; yr: [number, number]; xlog?: boolean;
  xticks: number[]; yticks: number[]; xlabel: string; ylabel: string; xfmt?: (v: number) => string;
  series: Series[]; marks?: Mark[]; regions?: Region[]; at?: number;
}> = ({ w, h, f, xr, yr, xlog, xticks, yticks, xlabel, ylabel, xfmt = (v) => String(v), series, marks = [], regions = [], at = 0 }) => {
  const m = { l: 86, r: 30, t: 24, b: 70 };
  const iw = w - m.l - m.r, ih = h - m.t - m.b;
  const nx = (v: number) => (xlog ? (Math.log10(v) - Math.log10(xr[0])) / (Math.log10(xr[1]) - Math.log10(xr[0])) : (v - xr[0]) / (xr[1] - xr[0]));
  const X = (v: number) => m.l + nx(v) * iw;
  const Y = (v: number) => m.t + (1 - (v - yr[0]) / (yr[1] - yr[0])) * ih;
  const axisA = go(f, at, 16);
  const text = { fontFamily: mono, fontSize: 21, fill: C.dim } as const;
  return (
    <svg width={w} height={h} style={{ overflow: "visible" }}>
      <g opacity={axisA}>
        {regions.map((r, i) => (
          <g key={i}>
            <rect x={X(r.x0)} y={m.t} width={X(r.x1) - X(r.x0)} height={ih} fill={r.color} opacity={0.12} rx={10} />
            <text x={(X(r.x0) + X(r.x1)) / 2} y={m.t + 28} textAnchor="middle" {...text} fill={r.color}>{r.label}</text>
          </g>
        ))}
        {yticks.map((v) => (
          <g key={v}>
            <line x1={m.l} x2={m.l + iw} y1={Y(v)} y2={Y(v)} stroke={ink(0.08)} />
            <text x={m.l - 14} y={Y(v) + 7} textAnchor="end" {...text}>{v}</text>
          </g>
        ))}
        {xticks.map((v) => (
          <text key={v} x={X(v)} y={m.t + ih + 34} textAnchor="middle" {...text}>{xfmt(v)}</text>
        ))}
        <line x1={m.l} x2={m.l + iw} y1={m.t + ih} y2={m.t + ih} stroke={ink(0.4)} strokeWidth={2} />
        <line x1={m.l} x2={m.l} y1={m.t} y2={m.t + ih} stroke={ink(0.4)} strokeWidth={2} />
        <text x={m.l + iw / 2} y={h - 8} textAnchor="middle" {...text} fontSize={22}>{xlabel}</text>
        <text transform={`translate(22 ${m.t + ih / 2}) rotate(-90)`} textAnchor="middle" {...text} fontSize={22}>{ylabel}</text>
      </g>
      {series.map((s, i) => {
        const d = s.pts.map(([x, y], k) => `${k ? "L" : "M"}${X(x).toFixed(1)} ${Y(y).toFixed(1)}`).join(" ");
        const e = s.live ? 1 : go(f, s.at ?? at + 14, s.dur ?? 46);
        const end = s.pts[s.pts.length - 1];
        return (
          <g key={i}>
            <Draw d={d} e={e} color={s.color} width={5} dash={s.dash} />
            {s.label && e > 0.6 && (
              <text x={X(end[0]) - 8} y={Y(end[1]) - 14} textAnchor="end" {...text} fill={s.color} fontSize={23} opacity={go(f, (s.at ?? at + 14) + 30, 14)}>{s.label}</text>
            )}
          </g>
        );
      })}
      {marks.map((k, i) => {
        const a = k.a ?? 1;
        return a > 0 ? (
          <g key={i} opacity={a}>
            <circle cx={X(k.x)} cy={Y(k.y)} r={9} fill={k.color} />
            <circle cx={X(k.x)} cy={Y(k.y)} r={17} fill="none" stroke={k.color} strokeOpacity={0.5} strokeWidth={2} />
            <text x={X(k.x) + (k.dx ?? 18)} y={Y(k.y) + (k.dy ?? -16)} textAnchor={k.anchor ?? "start"} {...text} fill={k.color} fontSize={22}>{k.label}</text>
          </g>
        ) : null;
      })}
    </svg>
  );
};
