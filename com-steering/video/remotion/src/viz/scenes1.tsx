import React from "react";
import { C, accent, ink, tint, CH, CW, Cap, Draw, Stream, Up, glass, go, hash, mix, mono, fmt, sweep, useAnim } from "../anim";
import { LineChart } from "./charts";
import { ModelStack, modelGeom } from "./Model";
import { treemap, type Rect } from "./treemap";
import ablation from "../data/ablation.json";

const Box: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ position: "relative", width: CW, height: CH }}>{children}</div>
);
const At: React.FC<{ x: number; y: number; w?: number; h?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ x, y, w, h, children, style }) => (
  <div style={{ position: "absolute", left: x, top: y, width: w, height: h, ...style }}>{children}</div>
);
const Head: React.FC<{ f: number; at: number; children: string }> = ({ f, at, children }) => (
  <Up f={f} at={at} y={16}><div style={{ fontFamily: mono, fontSize: 26, color: C.amber, letterSpacing: 1 }}>{children}</div></Up>
);

// ───────────────────────── Contrast: how a direction is extracted ─────────────────────────
type Side = { name: string; sub: string; text: string; color: string };

export const Contrast: React.FC<{ a: Side; b: Side; formula: string; resultLabel: string; resultSub: string; note: string; headers?: [string, string, string] }> =
  ({ a, b, formula, resultLabel, resultSub, note, headers = ["1 · Pairs", "2 · Read the model", "3 · Subtract"] }) => {
    const { f, t } = useAnim();
    const n = 10;
    const mw = 800, mh = 300;
    const g = modelGeom(0, 10, mw, mh, n);
    const A0 = t(0.14), B0 = t(0.28), SW = t(0.12);
    const posA = sweep(f, A0, SW, n), posB = sweep(f, B0, SW, n);
    const val = (l: number) => 0.3 + 0.4 * hash(l, 3);
    const hA = (l: number) => (val(l) + 0.16 + 0.12 * hash(l, 5)) * 120;
    const hB = (l: number) => val(l) * 120;
    const dif = (l: number) => (hA(l) - hB(l)) * 1.6;
    const passA = (l: number) => A0 + (l / (n + 1)) * SW;
    const passB = (l: number) => B0 + (l / (n + 1)) * SW;
    // the difference is computed under each layer, then carried to the chart on the right
    const D0 = t(0.46), T0 = t(0.6);
    const baseY = 470, difY = 640, chartX = 880, chartW = 360, chartY = 420;
    const slot = chartW / n;
    const arrow = go(f, t(0.82), 18);
    return (
      <Box>
        <At x={0} y={0}><Head f={f} at={0}>{headers[0]}</Head></At>
        {[a, b].map((s, i) => (
          <At key={i} x={0} y={60 + i * 215} w={440}>
            <Up f={f} at={t(0.02 + 0.04 * i)}>
              <div style={{ ...glass, borderLeft: `8px solid ${s.color}`, height: 160 }}>
                <div style={{ fontSize: 34, fontWeight: 700, color: s.color }}>{s.name}</div>
                <div style={{ fontSize: 23, color: C.dim, marginBottom: 10 }}>{s.sub}</div>
                <Stream text={s.text} f={f} at={t(0.04 + 0.04 * i)} wps={5} style={{ fontFamily: mono, fontSize: 21, color: C.text }} />
              </div>
            </Up>
          </At>
        ))}
        <At x={480} y={0}><Head f={f} at={t(0.08)}>{headers[1]}</Head></At>
        <At x={1330} y={0}><Head f={f} at={t(0.58)}>{headers[2]}</Head></At>
        <At x={480} y={50}>
          <svg width={1240} height={700} style={{ overflow: "visible" }}>
            <ModelStack x={0} y={10} w={mw} h={mh} n={n} f={f} start={t(0.08)} cols={4} rows={5} pulses={[{ pos: posA, color: a.color }, { pos: posB, color: b.color }]} />
            <text x={0} y={g.hwY + 38} fontFamily={mono} fontSize={21} fill={C.dim} opacity={go(f, t(0.2))}>same site, every layer</text>
            {Array.from({ length: n }, (_, l) => {
              const ea = go(f, passA(l), 14), eb = go(f, passB(l), 14);
              const bw = g.cw * 0.4, x0 = g.x0(l) + g.cw * 0.1;
              return (
                <g key={l}>
                  <rect x={x0} y={baseY - hA(l) * ea} width={bw} height={hA(l) * ea} rx={2} fill={a.color} opacity={0.9} />
                  <rect x={x0 + bw + 4} y={baseY - hB(l) * eb} width={bw} height={hB(l) * eb} rx={2} fill={b.color} opacity={0.9} />
                </g>
              );
            })}
            <line x1={0} x2={mw} y1={baseY} y2={baseY} stroke={ink(0.36)} strokeWidth={2} />
            <g opacity={go(f, D0 - 10) * (1 - go(f, T0 + n * 3 + 8, 14))}>
              <text x={mw - 4} y={baseY + 30} textAnchor="end" fontFamily={mono} fontSize={21} fill={C.dim}>difference, layer by layer</text>
              <line x1={0} x2={mw} y1={difY} y2={difY} stroke={ink(0.36)} strokeWidth={2} />
            </g>
            <text x={chartX} y={30} fontFamily={mono} fontSize={26} fill={C.text} opacity={go(f, D0)}>{formula}</text>
            <line x1={chartX} x2={chartX + chartW} y1={chartY} y2={chartY} stroke={ink(0.36)} strokeWidth={2} opacity={go(f, T0)} />
            {Array.from({ length: n }, (_, l) => {
              const grow = go(f, D0 + l * 3, 16);
              const fly = go(f, T0 + l * 3, 26);
              const x = mix(g.x0(l) + g.cw * 0.1, chartX + l * slot + slot * 0.2, fly);
              const yb = mix(difY, chartY, fly);
              const w = mix(g.cw * 0.8, slot * 0.6, fly);
              const h = dif(l) * grow;
              return <rect key={l} x={x} y={yb - h} width={w} height={h} rx={2} fill={C.amber} />;
            })}
            <Draw d={`M${chartX + chartW / 2} ${chartY + 14} L${chartX + chartW / 2} ${chartY + 56}`} e={arrow} color={C.amber} width={5} />
            <polygon points={`${chartX + chartW / 2 - 12},${chartY + 48} ${chartX + chartW / 2},${chartY + 68} ${chartX + chartW / 2 + 12},${chartY + 48}`} fill={C.amber} opacity={arrow > 0.9 ? 1 : 0} />
          </svg>
        </At>
        <At x={1330} y={540} w={390}>
          <Up f={f} at={t(0.84)}>
            <div style={{ ...glass, borderTop: `6px solid ${C.amber}` }}>
              <div style={{ fontSize: 34, fontWeight: 700, color: C.amber }}>{resultLabel}</div>
              <div style={{ fontSize: 22, color: C.dim, marginTop: 6 }}>{resultSub}</div>
            </div>
          </Up>
        </At>
        <At x={0} y={720} w={1300}><Cap f={f} at={t(0.1)}>{note}</Cap></At>
      </Box>
    );
  };

// ───────────────────────── Ablation: ds4 cut down to this tree ─────────────────────────
const KIND: Record<string, { name: string; short: string; color: string }> = {
  Core: { name: "ds4.c · engine core", short: "ds4.c", color: accent(0) }, Metal: { name: "ds4_metal.m · Metal backend", short: "Metal", color: accent(2) },
  Kernels: { name: "metal/ · GPU kernels", short: "kernels", color: accent(3) }, Server: { name: "ds4_server.c", short: "server", color: accent(4) },
  Tests: { name: "tests", short: "tests", color: accent(5) }, CUDA: { name: "CUDA", short: "CUDA", color: C.coral }, ROCm: { name: "ROCm", short: "ROCm", color: C.coral },
  Agent: { name: "ds4-agent + web", short: "agent", color: C.coral }, Hotlists: { name: "other-model hotlists", short: "hotlists", color: C.coral },
  TP: { name: "TP · RDMA", short: "TP", color: accent(1) }, Frontends: { name: "CLI · eval · bench", short: "CLI", color: accent(6) },
  Docs: { name: "docs", short: "docs", color: C.dim }, Other: { name: "libs · KV · image", short: "libs", color: C.dim },
};
// Widest label that fits the cell (≈ 15 px per char at 26 px + padding), or none.
const cellLabel = (k: { name: string; short: string }, w: number) => (w > k.name.length * 15 + 44 ? k.name : w > k.short.length * 15 + 44 ? k.short : "");
const TW = CW, TH = 620;
const groups = ablation.groups;
const upTotal = groups.reduce((n, g) => n + g.up, 0), chTotal = groups.reduce((n, g) => n + g.ch, 0);
const layA = treemap(groups.map((g) => ({ id: g.id, v: g.up })), TW, TH);
const s = Math.sqrt(chTotal / upTotal);
const layB0 = treemap(groups.filter((g) => g.ch > 0).map((g) => ({ id: g.id, v: g.ch })), TW * s, TH * s);
const offB = { x: (TW - TW * s) / 2, y: (TH - TH * s) / 2 };
const layB: Record<string, Rect> = Object.fromEntries(groups.map((g) => {
  const a = layA[g.id];
  const b = layB0[g.id];
  return [g.id, b ? { x: b.x + offB.x, y: b.y + offB.y, w: b.w, h: b.h } : { x: a.x + a.w / 2, y: a.y + a.h / 2, w: 0, h: 0 }];
}));

export const Ablation: React.FC = () => {
  const { f, t } = useAnim();
  const m = go(f, t(0.34), t(0.2));
  const lines = mix(upTotal, chTotal, m);
  return (
    <Box>
      <At x={0} y={0}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 24 }}>
          <div style={{ fontFamily: mono, fontSize: 64, fontWeight: 700, color: m < 0.5 ? C.text : C.mint }}>{fmt(Math.round(lines))}</div>
          <div style={{ fontSize: 28, color: C.dim }}>lines · {m < 0.5 ? `ds4 at ${ablation.upstream}` : "sf-ds4-1flash"}</div>
          <div style={{ fontFamily: mono, fontSize: 40, color: C.mint, opacity: go(f, t(0.56)) }}>−{Math.round((1 - chTotal / upTotal) * 100)}%</div>
        </div>
      </At>
      <At x={0} y={92}>
        <svg width={TW} height={TH}>
          {groups.map((gr, i) => {
            const A = layA[gr.id], B = layB[gr.id];
            const r = { x: mix(A.x, B.x, m), y: mix(A.y, B.y, m), w: mix(A.w, B.w, m), h: mix(A.h, B.h, m) };
            const k = KIND[gr.id];
            const removed = gr.ch === 0;
            const cut = removed ? 1 : 1 - gr.ch / gr.up;
            const appear = go(f, i * 2, 14);
            const mark = go(f, t(0.08) + i * 2, 12);               // red flag on removed cells
            const part = go(f, t(0.2) + i * 2, 14);                // hatched cut on partly cut cells
            const pulse = 0.5 + 0.5 * Math.sin(f / 6 + i);
            const fill = removed ? k.color : k.color;
            const showCut = !removed && cut > 0.02;
            const name = r.h > 54 ? cellLabel(k, r.w) : "";
            const label = name !== "";
            return (
              <g key={gr.id} opacity={appear * (removed ? 1 - Math.max(0, (m - 0.7) / 0.3) : 1)}>
                <rect x={r.x + 3} y={r.y + 3} width={Math.max(0, r.w - 6)} height={Math.max(0, r.h - 6)} rx={5}
                  fill={fill} fillOpacity={removed ? 0.2 + 0.25 * mark * (0.7 + 0.3 * pulse) : 0.2} stroke={removed ? C.coral : fill} strokeWidth={2} strokeOpacity={removed ? 0.5 + 0.5 * mark : 0.7} />
                {showCut && (
                  <rect x={r.x + 3 + (r.w - 6) * (1 - cut * part)} y={r.y + 3} width={Math.max(0, (r.w - 6) * cut * part)} height={Math.max(0, r.h - 6)}
                    rx={5} fill={C.coral} fillOpacity={0.45 * (1 - m)} />
                )}
                {label && (
                  <g>
                    <text x={r.x + 22} y={r.y + 42} fontSize={26} fontWeight={600} fill={C.text} textDecoration={removed && mark > 0.5 ? "line-through" : undefined}>{name}</text>
                    <text x={r.x + 22} y={r.y + 76} fontSize={22} fontFamily={mono} fill={removed ? C.coral : C.dim}>
                      {removed ? `${fmt(gr.up / 1000, 1)}k${r.w > 230 ? "  removed" : ""}` :m > 0.9 ? `${fmt(gr.ch / 1000, 1)}k` : `${fmt(gr.up / 1000, 1)}k`}
                    </text>
                    {showCut && part > 0.6 && m < 0.5 && (
                      <text x={r.x + 22} y={r.y + 108} fontSize={21} fontFamily={mono} fill={C.coral}>−{Math.round(cut * 100)}%</text>
                    )}
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </At>
      <At x={0} y={730} w={CW}>
        <Cap f={f} at={t(0.04)} size={26}>Lines of code, kernels, tests and docs: ds4 at ee7e840 vs this tree. Red = removed or cut.</Cap>
      </At>
    </Box>
  );
};

// ───────────────────────── Scale: what F does to the component along d ─────────────────────────
export const Scale: React.FC = () => {
  const { f, t } = useAnim();
  const kf: [number, number][] = [[0.2, 1], [0.42, 2], [0.66, 7]];
  let prev = 0, F = 0;
  for (const [a, v] of kf) { F = mix(prev, v, go(f, t(a - 0.1), t(0.1))); if (f < t(a)) break; prev = v; }
  const u = 58, ox = 440, oy = 330, hx = 0.9, hy = 1.3;
  const tipH = [ox + hx * u, oy - hy * u], tipS = [ox + (1 - F) * hx * u, oy - hy * u];
  const arrow = (x2: number, y2: number, color: string, w = 5) => {
    const a = Math.atan2(y2 - oy, x2 - ox), L = 16;
    const p = [[x2, y2], [x2 - L * Math.cos(a - 0.4), y2 - L * Math.sin(a - 0.4)], [x2 - L * Math.cos(a + 0.4), y2 - L * Math.sin(a + 0.4)]];
    return <g><line x1={ox} y1={oy} x2={x2 - 10 * Math.cos(a)} y2={y2 - 10 * Math.sin(a)} stroke={color} strokeWidth={w} strokeLinecap="round" /><polygon points={p.map((q) => q.join(",")).join(" ")} fill={color} /></g>;
  };
  const markA = (x: number) => Math.max(0, Math.min(1, (F - x + 0.3) / 0.3));
  const lbl = { fontFamily: mono, fontSize: 25 } as const;
  const text = [
    ["d", C.cyan, "a unit direction: what “refusal” looks like inside the model"],
    ["c = d·h", C.text, "how much of the state h points along d"],
    ["h′ = h − F·c·d", C.amber, "steering subtracts F·c along d: what is left is (1 − F)·c"],
  ];
  return (
    <Box>
      <At x={CW / 2 - 480} y={0} w={960}>
        <Up f={f} at={0}><div style={{ ...glass, textAlign: "center", fontFamily: mono, fontSize: 56, color: C.amber, padding: "16px 24px" }}>h ← h − F · d · (d·h)</div></Up>
      </At>
      <At x={0} y={140} w={520}>
        {text.map(([sym, col, txt], i) => (
          <Up key={i} f={f} at={t(0.04 + 0.06 * i)} style={{ marginBottom: 18 }}>
            <div style={{ ...glass, padding: "16px 24px" }}>
              <div style={{ fontFamily: mono, fontSize: 30, fontWeight: 700, color: col }}>{sym}</div>
              <div style={{ fontSize: 26, color: C.text, marginTop: 4 }}>{txt}</div>
            </div>
          </Up>
        ))}
      </At>
      <At x={560} y={140}>
        <Up f={f} at={t(0.02)}>
          <div style={{ ...glass, padding: 0 }}>
            <svg width={540} height={560}>
              <Draw d={`M${ox - 6.3 * u} ${oy} L${ox + 1.7 * u} ${oy}`} e={go(f, t(0.02), 24)} color={ink(0.48)} width={3} />
              <text x={ox + 1.7 * u - 24} y={oy + 34} {...lbl} fill={C.cyan}>d</text>
              <line x1={tipH[0]} y1={tipH[1]} x2={tipH[0]} y2={oy} stroke={ink(0.36)} strokeDasharray="6 6" />
              <line x1={tipS[0]} y1={tipS[1]} x2={tipS[0]} y2={oy} stroke={C.amber} strokeOpacity={0.5} strokeDasharray="6 6" />
              {arrow(tipH[0], tipH[1], C.text, 4)}
              {arrow(tipS[0], tipS[1], C.amber, 6)}
              <text x={tipH[0] + 12} y={tipH[1] - 10} {...lbl} fill={C.text}>h</text>
              <text x={tipS[0] + (F > 1.2 ? -40 : 12)} y={tipS[1] - 12} {...lbl} fill={C.amber}>h′</text>
              <text x={26} y={52} {...lbl} fontSize={34} fill={C.amber}>F = {F.toFixed(1)}</text>
              <text x={26} y={92} {...lbl} fontSize={24} fill={C.dim}>component along d: {(1 - F).toFixed(1)}·c</text>
            </svg>
          </div>
        </Up>
      </At>
      <At x={1130} y={140}>
        <Up f={f} at={t(0.02)}>
          <div style={{ ...glass, padding: "10px 0 0 0" }}>
            <LineChart w={590} h={560} f={f} xr={[0, 8]} yr={[-7.5, 1.5]} xticks={[0, 1, 2, 3, 4, 5, 6, 7, 8]} yticks={[1, 0, -1, -3, -6]}
              xlabel="scale F" ylabel="component left: 1 − F" at={t(0.02)}
              series={[{ pts: [[0, 1], [F, 1 - F]], color: C.amber, live: true }]}
              marks={[
                { x: 1, y: 0, label: "F=1 projected away", color: C.cyan, a: markA(1), dx: 16, dy: -18 },
                { x: 2, y: -1, label: "F=2 reflected", color: C.mint, a: markA(2), dx: -22, dy: 8, anchor: "end" },
                { x: 7, y: -6, label: "F=7 ×(−6): ours", color: C.coral, a: markA(7), dx: -16, dy: -22, anchor: "end" },
              ]} />
          </div>
        </Up>
      </At>
    </Box>
  );
};

// ───────────────────────── Site: where steering acts in the whole model ─────────────────────────
export const Site: React.FC = () => {
  const { f, t } = useAnim();
  const n = 40, w = CW, h = 340, y0 = 70;
  const g = modelGeom(0, y0, w, h, n);
  const P0 = t(0.2), PD = t(0.34);
  const pos = sweep(f, P0, PD, n);
  const ring = (l: number) => (l === 0 ? 0 : go(f, P0 + (l / (n + 1)) * PD, 14));
  const br = go(f, t(0.58), 26);
  return (
    <Box>
      <At x={0} y={0} w={CW}>
        <Cap f={f} at={t(0.02)} size={28}>40 layers · each one: attention + 384 experts (6 active per token)</Cap>
      </At>
      <svg width={w} height={CH} style={{ position: "absolute", left: 0, top: 0 }}>
        <ModelStack x={0} y={y0} w={w} h={h} n={n} f={f} start={t(0.06)} pulses={[{ pos, color: C.cyan }]} ring={ring} />
        <text x={g.cx(0) - 14} y={g.hwY + 40} fontFamily={mono} fontSize={20} fill={C.dim} opacity={go(f, t(0.6))}>layer 0</text>
        <Draw d={`M${g.x0(1)} ${g.hwY + 62} L${g.x0(39) + g.cw} ${g.hwY + 62}`} e={br} color={C.amber} width={4} />
        <text x={(g.x0(1) + g.x0(39)) / 2} y={g.hwY + 100} textAnchor="middle" fontFamily={mono} fontSize={24} fill={C.amber} opacity={br}>layers 1–39 · one site, on the residual stream</text>
      </svg>
      <At x={0} y={510} w={840}>
        <Up f={f} at={t(0.66)}>
          <div style={{ ...glass, borderTop: `6px solid ${C.amber}`, height: 150 }}>
            <div style={{ fontFamily: mono, fontSize: 26, color: C.amber }}>ACTS HERE</div>
            <div style={{ fontSize: 31, color: C.text, marginTop: 8 }}>the residual stream, at the attention input · h −= F·d·(d·h)</div>
          </div>
        </Up>
      </At>
      <At x={880} y={510} w={840}>
        <Up f={f} at={t(0.74)}>
          <div style={{ ...glass, borderTop: `6px solid ${C.dim}`, height: 150 }}>
            <div style={{ fontFamily: mono, fontSize: 26, color: C.dim }}>NOT TOUCHED</div>
            <div style={{ fontSize: 31, color: C.text, marginTop: 8 }}>weights · experts · router · attention · KV cache</div>
          </div>
        </Up>
      </At>
      <At x={0} y={700} w={CW}>
        <Up f={f} at={t(0.84)}><div style={{ fontFamily: mono, fontSize: 25, color: C.dim }}>file: 40 × 5120 float32 · row 0 empty (layer 0 is never steered)</div></Up>
      </At>
    </Box>
  );
};

// ───────────────────────── Layer: zoom on one layer ─────────────────────────
const BLOCKS: { t: string; s?: string; steer?: boolean; moe?: boolean }[] = [
  { t: "Residual streams" }, { t: "Weighted fold" }, { t: "Engram", s: "layers 1 and 14" },
  { t: "STEERING", s: "h −= F·d·(d·h)", steer: true }, { t: "Attention norm" }, { t: "Attention" },
  { t: "MoE experts", s: "384 · 6 active", moe: true }, { t: "Residual add" },
];
export const Layer: React.FC = () => {
  const { f, t } = useAnim();
  const bw = 172, gap = 48, y = 90, bh = 150;
  const bx = (i: number) => i * (bw + gap);
  const glow = go(f, t(0.5), 20);
  return (
    <Box>
      <svg width={CW} height={CH} style={{ position: "absolute", left: 0, top: 0 }}>
        {BLOCKS.slice(1).map((_, i) => {
          const e = go(f, t(0.05 + 0.065 * (i + 1)) - 6, 16);
          const x1 = bx(i) + bw + 4, x2 = bx(i + 1) - 6, yy = y + bh / 2;
          return (
            <g key={i}>
              <Draw d={`M${x1} ${yy} L${x2} ${yy}`} e={e} color={ink(0.59)} width={4} />
              <polygon points={`${x2 - 2},${yy - 9} ${x2 + 14},${yy} ${x2 - 2},${yy + 9}`} fill={ink(0.59)} opacity={e > 0.9 ? 1 : 0} />
            </g>
          );
        })}
      </svg>
      {BLOCKS.map((b, i) => {
        const col = b.steer ? C.amber : C.dim;
        const lift = b.steer ? -18 * glow : 0;
        return (
          <At key={i} x={bx(i)} y={y + lift} w={bw}>
            <Up f={f} at={t(0.05 + 0.065 * i)}>
              <div style={{ ...glass, padding: "18px 16px", height: bh + (b.steer ? 36 * glow : 0), textAlign: "center",
                borderTop: `6px solid ${col}`, boxShadow: b.steer ? `0 0 ${50 * glow}px ${C.amber}55` : undefined,
                background: b.steer ? tint(C.amber, 0.1) : glass.background }}>
                <div style={{ fontSize: b.steer ? 30 : 26, fontWeight: 700, color: b.steer ? C.amber : C.text }}>{b.t}</div>
                {b.s && <div style={{ fontFamily: mono, fontSize: 20, color: b.steer ? C.text : C.dim, marginTop: 10 }}>{b.s}</div>}
              </div>
            </Up>
          </At>
        );
      })}
      {BLOCKS.map((b, i) => !b.steer && (
        <At key={`u${i}`} x={bx(i)} y={y + bh + 18} w={bw} style={{ textAlign: "center" }}>
          <div style={{ fontFamily: mono, fontSize: 19, color: C.dim, opacity: go(f, t(0.7)) }}>untouched</div>
        </At>
      ))}
      <svg width={CW} height={CH} style={{ position: "absolute", left: 0, top: 0 }}>
        {Array.from({ length: 24 }, (_, i) => {
          const step = Math.floor(f / 5);
          const lit = [0, 1, 2, 3, 4, 5].map((k) => Math.floor(hash(k + 3, step) * 24)).includes(i);
          const cx = bx(6) + 8 + (i % 6) * 26, cy = y + bh + 70 + Math.floor(i / 6) * 26;
          return <rect key={i} x={cx} y={cy} width={20} height={20} rx={5} fill={lit ? C.mint : ink(0.13)} opacity={go(f, t(0.5))} />;
        })}
      </svg>
      <At x={bx(3) - 150} y={y + bh + 90} w={500}>
        <Up f={f} at={t(0.58)}>
          <div style={{ ...glass, borderLeft: `8px solid ${C.amber}`, fontSize: 30, color: C.text }}>
            <b style={{ color: C.amber }}>after Engram, before the norm</b>
            <div style={{ fontSize: 24, color: C.dim, marginTop: 6 }}>one row d[l] of the file per layer</div>
          </div>
        </Up>
      </At>
      <At x={0} y={620} w={CW}>
        <Up f={f} at={t(0.8)}>
          <div style={{ ...glass, display: "flex", gap: 36, alignItems: "center", fontFamily: mono, fontSize: 34 }}>
            <span style={{ color: C.text }}>h</span><span style={{ color: C.dim }}>→</span>
            <span style={{ color: C.amber }}>h − F·d·(d·h)</span><span style={{ color: C.dim }}>→</span>
            <span style={{ color: C.text }}>the rest of the layer, as always</span>
          </div>
        </Up>
      </At>
    </Box>
  );
};
