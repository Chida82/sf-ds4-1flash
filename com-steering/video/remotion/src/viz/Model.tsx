import React from "react";
import { C, go, hash, ink } from "../anim";

/**
 * The model as a mixture of experts: one column per layer, an expert grid on top
 * (a few cells light up per token, as the router picks them), the attention pill below,
 * and the residual stream running underneath like a highway. Pulses are tokens
 * travelling left to right; rings are things done to the residual stream.
 */
export const modelGeom = (x: number, y: number, w: number, h: number, n: number) => {
  const colW = w / n;
  const pad = colW * 0.14;
  return {
    colW, cw: colW - 2 * pad, x0: (l: number) => x + l * colW + pad, cx: (l: number) => x + l * colW + colW / 2,
    gridTop: y + h * 0.04, gridH: h * 0.58, attnY: y + h * 0.66, attnH: h * 0.09, hwY: y + h * 0.93, bottom: y + h,
  };
};

export type Pulse = { pos: number; color: string };
export type Band = { from: number; to: number; color: string; a: number };

export const ModelStack: React.FC<{
  x: number; y: number; w: number; h: number; n: number; f: number;
  start?: number;                       // frame at which the columns begin to rise
  cols?: number; rows?: number;
  pulses?: Pulse[];
  ring?: (l: number) => number;         // 0..1 progress of the ring on layer l
  ringColor?: string;
  bands?: Band[];
  calm?: boolean;                       // no flicker: the experts rest
}> = ({ x, y, w, h, n, f, start = 0, cols = 3, rows = 5, pulses = [], ring, ringColor = C.amber, bands = [], calm }) => {
  const g = modelGeom(x, y, w, h, n);
  const cells = cols * rows;
  const step = Math.floor(f / 4);
  const gap = Math.max(1.5, g.cw * 0.08);
  const cellW = (g.cw - gap * (cols + 1)) / cols;
  const cellH = (g.gridH - gap * (rows + 1)) / rows;
  const L = Array.from({ length: n }, (_, l) => l);

  return (
    <g>
      {bands.map((b, i) => (
        <rect key={i} x={g.x0(b.from) - g.colW * 0.1} y={y - h * 0.04} width={(b.to - b.from + 1) * g.colW} height={h * 1.1} rx={6}
          fill={b.color} opacity={0.14 * b.a} stroke={b.color} strokeOpacity={0.55 * b.a} />
      ))}
      {L.map((l) => {
        const a = go(f, start + l * (n > 24 ? 1 : 2), 16);
        // alive = how close the closest pulse is; the experts nearest it light up.
        const lit = pulses.map((p) => ({ p, k: Math.max(0, 1 - Math.abs(p.pos - l) / 1.6), passed: p.pos > l }));
        return (
          <g key={l} opacity={a} transform={`translate(0 ${(1 - a) * 26})`}>
            <rect x={g.x0(l)} y={y} width={g.cw} height={h * 0.8} rx={3} fill={C.card} stroke={ink(0.16)} />
            {Array.from({ length: cells }, (_, i) => {
              const cx = g.x0(l) + gap + (i % cols) * (cellW + gap);
              const cy = g.gridTop + gap + Math.floor(i / cols) * (cellH + gap);
              let fill = ink(0.09), op = 1;
              for (const { p, k, passed } of lit) {
                // two experts per layer lit by the pulse's passage, reshuffled every 4 frames
                const pick = [Math.floor(hash(l, step) * cells), Math.floor(hash(l + 7, step) * cells)];
                if (k > 0 && !calm && pick.includes(i)) { fill = p.color; op = 0.35 + 0.65 * k; }
                else if (passed && hash(l, i) > 0.82 && fill === ink(0.09)) { fill = p.color; op = 0.28; }
              }
              return <rect key={i} x={cx} y={cy} width={cellW} height={cellH} rx={Math.min(cellW, cellH) * 0.25} fill={fill} opacity={op} />;
            })}
            <rect x={g.x0(l) + g.cw * 0.08} y={g.attnY} width={g.cw * 0.84} height={g.attnH} rx={g.attnH * 0.5}
              fill={lit.some((q) => q.k > 0) ? lit.find((q) => q.k > 0)!.p.color : ink(0.2)}
              opacity={lit.some((q) => q.k > 0) ? 0.5 + 0.4 * Math.max(...lit.map((q) => q.k)) : 1} />
            <line x1={g.cx(l)} y1={g.attnY + g.attnH} x2={g.cx(l)} y2={g.hwY} stroke={ink(0.16)} strokeWidth={2} />
          </g>
        );
      })}
      <line x1={x} y1={g.hwY} x2={x + w} y2={g.hwY} stroke={ink(0.3)} strokeWidth={3} />
      {ring && L.map((l) => {
        const r = ring(l);
        return r > 0 ? <circle key={l} cx={g.cx(l)} cy={g.hwY} r={g.cw * (0.55 + 0.35 * (1 - r))} fill={ringColor} fillOpacity={0.25 * r} stroke={ringColor} strokeWidth={3} opacity={r} /> : null;
      })}
      {pulses.map((p, i) => p.pos >= -1 && p.pos <= n + 1 && (
        <g key={i}>
          <circle cx={x + (p.pos + 0.5) * g.colW} cy={g.hwY} r={g.cw * 1.1} fill={p.color} opacity={0.18} />
          <circle cx={x + (p.pos + 0.5) * g.colW} cy={g.hwY} r={g.cw * 0.45} fill={p.color} />
        </g>
      ))}
    </g>
  );
};
