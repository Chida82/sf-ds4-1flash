import React from "react";
import { C, ink, CH, CW, Cap, Draw, Stream, Up, glass, go, hash, lin, mix, mono, sweep, useAnim } from "../anim";
import { LineChart } from "./charts";
import { ModelStack, modelGeom } from "./Model";

const Box: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ position: "relative", width: CW, height: CH }}>{children}</div>
);
const At: React.FC<{ x: number; y: number; w?: number; h?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ x, y, w, h, children, style }) => (
  <div style={{ position: "absolute", left: x, top: y, width: w, height: h, ...style }}>{children}</div>
);
const Pill: React.FC<{ f: number; at: number; color?: string; children: React.ReactNode }> = ({ f, at, children }) => (
  <Up f={f} at={at} y={16}>
    <div style={{ display: "inline-flex", alignItems: "center", gap: 14 }}>{children}</div>
  </Up>
);
const Step: React.FC<{ n: string; color?: string }> = ({ n, color = C.amber }) => (
  <span style={{ display: "inline-flex", width: 44, height: 44, borderRadius: 22, background: color, color: "#fff", fontFamily: mono, fontWeight: 700, fontSize: 26, alignItems: "center", justifyContent: "center" }}>{n}</span>
);

// ───────────────────────── S9.1: byte diff of two GGUFs ─────────────────────────
// Schematic: 6 tensor cells per layer, 3 edited (122 in all = 40 × 3 + 2); real number is 122.
const edited = (l: number): number[] => {
  const order = [0, 1, 2, 3, 4, 5].sort((a, b) => hash(l, a) - hash(l, b));
  return order.slice(0, l === 0 || l === 39 ? 4 : 3);
};
const EDITED = Array.from({ length: 40 }, (_, l) => edited(l));

export const Diff: React.FC = () => {
  const { f, t } = useAnim();
  const x0 = 170, cwid = (CW - x0) / 40, ch = 26, gap = 4;
  const S0 = t(0.32), SD = t(0.34);
  const sx = x0 + lin(f, S0, SD) * (CW - x0);
  const compared = (l: number) => x0 + (l + 1) * cwid <= sx;
  const count = EDITED.reduce((n, e, l) => n + (compared(l) ? e.length : 0), 0);
  const strip = (y: number, side: "a" | "b") => (
    <g>
      <g opacity={go(f, t(side === "a" ? 0.04 : 0.12))}>
        <rect x={0} y={y} width={140} height={6 * (ch + gap) - gap} rx={14} fill={C.cyan} fillOpacity={0.16} stroke={C.cyan} strokeOpacity={0.6} />
        <text x={70} y={y + 80} textAnchor="middle" fontFamily={mono} fontSize={19} fill={C.text}>token</text>
        <text x={70} y={y + 106} textAnchor="middle" fontFamily={mono} fontSize={19} fill={C.text}>embedding</text>
        {Array.from({ length: 40 }, (_, l) => (
          <g key={l}>
            {Array.from({ length: 6 }, (_, k) => {
              const ed = EDITED[l].includes(k);
              const hit = side === "b" && ed && compared(l);
              return <rect key={k} x={x0 + l * cwid + 2} y={y + k * (ch + gap)} width={cwid - 4} height={ch} rx={5}
                fill={hit ? C.amber : side === "b" && compared(l) ? C.mint : C.cyan} fillOpacity={hit ? 1 : side === "b" && compared(l) ? 0.28 : 0.3} />;
            })}
          </g>
        ))}
      </g>
    </g>
  );
  return (
    <Box>
      <svg width={CW} height={CH} style={{ position: "absolute", left: 0, top: 0 }}>
        <text x={0} y={30} fontSize={28} fontWeight={600} fill={C.text} opacity={go(f, t(0.04))}>base GGUF — ours</text>
        {strip(50, "a")}
        <text x={0} y={376} fontSize={28} fontWeight={600} fill={C.text} opacity={go(f, t(0.12))}>public abliterated GGUF — same quantisation</text>
        {strip(396, "b")}
        <text x={x0} y={290} fontFamily={mono} fontSize={23} fill={C.amber} opacity={go(f, S0 - 6)}>orange = bytes differ · green = identical</text>
        <text x={70} y={600} textAnchor="middle" fontFamily={mono} fontSize={21} fill={C.mint} opacity={go(f, S0 + SD)}>identical ✓</text>
        {f >= S0 && f <= S0 + SD + 4 && <line x1={sx} x2={sx} y1={44} y2={580} stroke={C.amber} strokeWidth={3} opacity={0.9} />}
      </svg>
      <At x={0} y={610} w={CW}>
        <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
          <Pill f={f} at={t(0.04)} color={C.cyan}><Step n="1" color={C.cyan} /><span style={{ fontSize: 30, color: C.text }}>two files</span></Pill>
          <Pill f={f} at={t(0.3)} color={C.amber}><Step n="2" /><span style={{ fontSize: 30, color: C.text }}>byte diff first</span></Pill>
          <div style={{ marginLeft: "auto", fontFamily: mono, fontSize: 56, fontWeight: 700, color: C.amber }}>{count}<span style={{ fontSize: 28, color: C.dim }}> tensors differ</span></div>
        </div>
      </At>
      <At x={0} y={690} w={CW}>
        <Cap f={f} at={t(0.62)} size={26}>The rest is identical, even the token embedding → an edit in place, not a re-quantisation. No GPU: the network is a library; one download, nothing dequantised yet.</Cap>
        <span style={{ display: "block", fontFamily: mono, fontSize: 19, color: C.dim, marginTop: 6 }}>(schematic layout: the number 122 is real)</span>
      </At>
    </Box>
  );
};

// ───────────────────────── S9.2: ΔW is rank one, SVD gives r ─────────────────────────
const heat = (v: number) => (v >= 0 ? `rgba(13,148,136,${Math.min(1, v)})` : `rgba(225,29,72,${Math.min(1, -v)})`);
const R = Array.from({ length: 14 }, (_, i) => Math.sin(i * 1.3 + 0.4) * 0.9);
const S = Array.from({ length: 14 }, (_, j) => Math.cos(j * 0.9 + 1.1) * 0.85 + 0.2 * Math.sin(j * 2.3));
const SIGMA = [0.9, 0.034, 0.026, 0.02, 0.015, 0.012, 0.01, 0.008, 0.006, 0.005];

export const RankOne: React.FC = () => {
  const { f, t } = useAnim();
  const c = 29, gx = 110, gy = 120;
  const arrow = go(f, t(0.7), 20);
  return (
    <Box>
      <At x={0} y={0}><Pill f={f} at={0} color={C.cyan}><Step n="3" color={C.cyan} /><span style={{ fontSize: 32, color: C.text }}>ΔW = W − W′ = r (rᵀW)</span></Pill></At>
      <svg width={800} height={CH} style={{ position: "absolute", left: 0, top: 0 }}>
        {R.map((v, i) => <rect key={i} x={30} y={gy + i * c} width={c - 3} height={c - 3} rx={5} fill={heat(v)} opacity={go(f, t(0.05) + i, 14)} />)}
        {S.map((v, j) => <rect key={j} x={gx + j * c} y={gy - 44} width={c - 3} height={c - 3} rx={5} fill={heat(v)} opacity={go(f, t(0.12) + j, 14)} />)}
        <text x={16} y={gy + 14 * c + 30} fontFamily={mono} fontSize={24} fill={C.cyan} opacity={go(f, t(0.06))}>r</text>
        <text x={gx} y={gy - 56} fontFamily={mono} fontSize={24} fill={C.cyan} opacity={go(f, t(0.13))}>rᵀW</text>
        {R.map((rv, i) => S.map((sv, j) => (
          <rect key={`${i}-${j}`} x={gx + j * c} y={gy + i * c} width={c - 3} height={c - 3} rx={5} fill={heat(rv * sv)}
            opacity={go(f, t(0.22) + ((i + j) / 26) * t(0.2), 14)} />
        )))}
        <text x={gx} y={gy + 14 * c + 30} fontFamily={mono} fontSize={24} fill={C.amber} opacity={go(f, t(0.3))}>ΔW</text>
      </svg>
      <At x={0} y={600} w={780}>
        <Cap f={f} at={t(0.44)} size={26}>Every row of ΔW is a multiple of one row: the edit has rank one, and its column space is the direction that was removed.</Cap>
      </At>
      <At x={850} y={0}><Pill f={f} at={t(0.4)} color={C.amber}><Step n="4" /><span style={{ fontSize: 32, color: C.text }}>SVD of ΔW</span></Pill></At>
      <svg width={880} height={CH} style={{ position: "absolute", left: 850, top: 0 }}>
        {SIGMA.map((v, i) => {
          const e = go(f, t(0.46) + i * 3, 18);
          return <rect key={i} x={20 + i * 52} y={470 - v * 400 * e} width={40} height={v * 400 * e} rx={6} fill={i === 0 ? C.amber : C.dim} opacity={i === 0 ? 1 : 0.7} />;
        })}
        <line x1={10} x2={550} y1={470} y2={470} stroke={ink(0.42)} strokeWidth={2} />
        <text x={20} y={506} fontFamily={mono} fontSize={21} fill={C.dim} opacity={go(f, t(0.5))}>singular values σ₁ … σ₁₀</text>
        <text x={78} y={150} fontFamily={mono} fontSize={26} fill={C.amber} opacity={go(f, t(0.58))}>σ₁: share 0.89–0.92</text>
        <text x={190} y={430} fontFamily={mono} fontSize={21} fill={C.dim} opacity={go(f, t(0.6))}>the rest: quantisation noise</text>
        <Draw d="M60 120 C 200 70, 420 70, 580 130" e={arrow} color={C.amber} width={5} />
        <polygon points="570,112 596,134 566,146" fill={C.amber} opacity={arrow > 0.9 ? 1 : 0} />
      </svg>
      <At x={1450} y={110} w={270}>
        <Up f={f} at={t(0.74)}>
          <div style={{ ...glass, borderTop: `6px solid ${C.amber}` }}>
            <div style={{ fontFamily: mono, fontSize: 34, fontWeight: 700, color: C.amber }}>u₁ = r̂</div>
            <div style={{ fontSize: 24, color: C.text, marginTop: 8 }}>the direction removed</div>
          </div>
        </Up>
        <Up f={f} at={t(0.84)} style={{ marginTop: 20 }}>
          <div style={{ ...glass, fontSize: 24, color: C.text }}>
            <b style={{ color: C.cyan }}>fix the sign</b><div style={{ color: C.dim, marginTop: 6 }}>so every layer agrees</div>
          </div>
        </Up>
      </At>
    </Box>
  );
};

// ───────────────────────── S9.3: 40 parallel directions → one file ─────────────────────────
export const Align: React.FC = () => {
  const { f, t } = useAnim();
  const cx = 330, cy = 360, L = 230;
  const base = (-32 * Math.PI) / 180;
  const fix = go(f, t(0.34), t(0.16));
  const flipped = (l: number) => hash(l, 9) > 0.5;
  return (
    <Box>
      <At x={0} y={0}><Pill f={f} at={0} color={C.cyan}><Step n="5" color={C.cyan} /><span style={{ fontSize: 32, color: C.text }}>40 layers, one direction</span></Pill></At>
      <svg width={700} height={CH} style={{ position: "absolute", left: 0, top: 0 }}>
        <circle cx={cx} cy={cy} r={L + 10} fill="none" stroke={ink(0.18)} strokeDasharray="6 8" opacity={go(f, t(0.04))} />
        {Array.from({ length: 40 }, (_, l) => {
          const a = base + (hash(l, 4) - 0.5) * 0.09 + (flipped(l) ? Math.PI * (1 - fix) : 0);
          const col = flipped(l) && fix < 0.98 ? C.coral : C.cyan;
          const e = go(f, t(0.05) + l * 2, 18);
          return <line key={l} x1={cx} y1={cy} x2={cx + Math.cos(a) * L * e} y2={cy + Math.sin(a) * L * e} stroke={col} strokeWidth={4} strokeLinecap="round" opacity={0.7} />;
        })}
        <circle cx={cx} cy={cy} r={9} fill={C.text} />
        <text x={cx} y={cy + L + 70} textAnchor="middle" fontFamily={mono} fontSize={26} fill={C.cyan} opacity={go(f, t(0.52))}>|cos| = 1.0 between layers</text>
        <text x={cx} y={cy - L - 24} textAnchor="middle" fontFamily={mono} fontSize={21} fill={C.dim} opacity={go(f, t(0.06))}>(schematic arrows)</text>
      </svg>
      <At x={760} y={0}><Pill f={f} at={t(0.55)} color={C.mint}><Step n="6" color={C.mint} /><span style={{ fontSize: 32, color: C.text }}>write 40 × 5120</span></Pill></At>
      <svg width={960} height={CH} style={{ position: "absolute", left: 760, top: 0 }}>
        {Array.from({ length: 40 }, (_, l) => {
          const e = go(f, t(0.58) + l * 2, 14);
          return l === 0
            ? <rect key={l} x={0} y={90} width={760 * e} height={11} rx={3} fill="none" stroke={C.dim} strokeDasharray="8 6" />
            : <rect key={l} x={0} y={90 + l * 13} width={760 * e} height={11} rx={3} fill={C.mint} fillOpacity={0.55 + 0.4 * hash(l, 2)} />;
        })}
        <text x={780} y={101} fontFamily={mono} fontSize={21} fill={C.dim} opacity={go(f, t(0.7))}>row 0: empty</text>
        <text x={0} y={70} fontFamily={mono} fontSize={22} fill={C.dim} opacity={go(f, t(0.6))}>5120 float32 per row · unit rows</text>
      </svg>
      <At x={760} y={640} w={960}>
        <Cap f={f} at={t(0.74)} size={26}>One throw-away Python environment, the shared Hugging Face cache, and no full dequantisation of 340 GiB.</Cap>
      </At>
    </Box>
  );
};

// ───────────────────────── S10.2: two nearly orthogonal directions ─────────────────────────
export const Orthogonal: React.FC = () => {
  const { f, t } = useAnim();
  const ox = 140, oy = 480, L = 380;
  const ang = Math.acos(0.105);
  const e1 = go(f, t(0.04), 30), e2 = go(f, t(0.22), 30);
  const bar = (label: string, v: number, color: string, y: number, at: number) => (
    <g opacity={go(f, at)}>
      <text x={0} y={y - 12} fontSize={26} fill={C.text}>{label}</text>
      <rect x={0} y={y} width={560 * (v / 12) * go(f, at + 6, 30)} height={40} rx={10} fill={color} />
      <text x={560 * (v / 12) * go(f, at + 6, 30) + 14} y={y + 30} fontFamily={mono} fontSize={28} fill={C.text}>{v}</text>
    </g>
  );
  return (
    <Box>
      <svg width={700} height={CH} style={{ position: "absolute", left: 0, top: 0 }}>
        <Draw d={`M${ox} ${oy} L${ox + L} ${oy}`} e={e1} color={C.amber} width={7} />
        <polygon points={`${ox + L - 4},${oy - 14} ${ox + L + 22},${oy} ${ox + L - 4},${oy + 14}`} fill={C.amber} opacity={e1 > 0.95 ? 1 : 0} />
        <text x={ox + L - 20} y={oy + 48} fontFamily={mono} fontSize={26} fill={C.amber} opacity={e1}>slot 1</text>
        <Draw d={`M${ox} ${oy} L${ox + L * Math.cos(ang)} ${oy - L * Math.sin(ang)}`} e={e2} color={C.cyan} width={7} />
        <polygon points={`${ox + L * Math.cos(ang) - 14},${oy - L * Math.sin(ang) + 6} ${ox + L * Math.cos(ang)},${oy - L * Math.sin(ang) - 24} ${ox + L * Math.cos(ang) + 14},${oy - L * Math.sin(ang) + 6}`} fill={C.cyan} opacity={e2 > 0.95 ? 1 : 0} />
        <text x={ox + L * Math.cos(ang) + 34} y={oy - L * Math.sin(ang) + 10} fontFamily={mono} fontSize={26} fill={C.cyan} opacity={e2}>slot 2 (q1)</text>
        <path d={`M${ox + 90} ${oy} A 90 90 0 0 0 ${ox + 90 * Math.cos(ang)} ${oy - 90 * Math.sin(ang)}`} fill="none" stroke={C.text} strokeWidth={3} opacity={go(f, t(0.4))} />
        <text x={ox + 110} y={oy - 70} fontFamily={mono} fontSize={26} fill={C.text} opacity={go(f, t(0.42))}>median |cos| 0.105</text>
        <text x={ox} y={oy + 110} fontSize={28} fill={C.dim} opacity={go(f, t(0.46))}>≈ orthogonal → a clean 2D removal</text>
      </svg>
      <svg width={760} height={420} style={{ position: "absolute", left: 900, top: 70 }}>
        <text x={0} y={24} fontFamily={mono} fontSize={22} fill={C.dim} opacity={go(f, t(0.5))}>score on a 12-id screen</text>
        {bar("slot 2 applied everywhere", 7.3, C.coral, 90, t(0.52))}
        {bar("slot 2 only in the reasoning", 11.3, C.mint, 215, t(0.64))}
      </svg>
      <At x={900} y={400} w={820}>
        <Up f={f} at={t(0.76)}>
          <div style={{ ...glass, fontSize: 32, color: C.text }}>Everywhere it <b style={{ color: C.coral }}>hurts</b>. Only in the reasoning it <b style={{ color: C.mint }}>helps</b>.</div>
        </Up>
      </At>
    </Box>
  );
};

// ───────────────────────── S10.3: the phase gate ─────────────────────────
export const Phase: React.FC = () => {
  const { f, t } = useAnim();
  const W = CW, split = W * 0.74;
  const e1 = go(f, t(0.12), t(0.22)), e2 = go(f, t(0.3), t(0.2));
  const head = lin(f, t(0.12), t(0.55)) * W;
  return (
    <Box>
      <svg width={W} height={CH} style={{ position: "absolute", left: 0, top: 0 }}>
        <rect x={0} y={60} width={split - 6} height={64} rx={16} fill={C.cyan} fillOpacity={0.14} stroke={C.cyan} strokeOpacity={0.6} opacity={go(f, t(0.02))} />
        <rect x={split + 6} y={60} width={W - split - 6} height={64} rx={16} fill={C.mint} fillOpacity={0.14} stroke={C.mint} strokeOpacity={0.6} opacity={go(f, t(0.06))} />
        <text x={30} y={103} fontFamily={mono} fontSize={28} fill={C.cyan} opacity={go(f, t(0.04))}>THINK</text>
        <text x={split + 36} y={103} fontFamily={mono} fontSize={28} fill={C.mint} opacity={go(f, t(0.08))}>ANSWER</text>
        <rect x={0} y={190} width={W * e1} height={70} rx={16} fill={C.amber} fillOpacity={0.85} />
        <text x={30} y={236} fontFamily={mono} fontSize={28} fill="#fff" opacity={e1 > 0.4 ? 1 : 0}>slot 1 · both phases</text>
        <rect x={0} y={290} width={split * e2} height={70} rx={16} fill={C.cyan} fillOpacity={0.85} />
        <text x={30} y={336} fontFamily={mono} fontSize={28} fill="#fff" opacity={e2 > 0.4 ? 1 : 0}>slot 2 · think only</text>
        <line x1={split} x2={split} y1={40} y2={390} stroke={C.text} strokeWidth={3} strokeDasharray="10 8" opacity={go(f, t(0.5))} />
        <text x={split - 14} y={420} textAnchor="end" fontFamily={mono} fontSize={24} fill={C.text} opacity={go(f, t(0.5))}>phase gate</text>
        {f > t(0.12) && f < t(0.67) && <line x1={head} x2={head} y1={50} y2={380} stroke={C.text} strokeWidth={3} opacity={0.6} />}
      </svg>
      <At x={0} y={470} w={W}>
        <Cap f={f} at={t(0.6)} size={40} style={{ color: C.text, fontWeight: 600 }}>What helps the thinking can hurt the answer.</Cap>
      </At>
      <At x={0} y={580} w={W}>
        <Up f={f} at={t(0.75)}>
          <div style={{ ...glass, borderLeft: `8px solid ${C.amber}`, fontSize: 32, color: C.text }}>
            <b style={{ color: C.amber }}>One fusion is never the fusion:</b> every combination must also restart from the original parents.
          </div>
        </Up>
      </At>
    </Box>
  );
};

// ───────────────────────── S12.1 / S12.2: the schedules ─────────────────────────
const smooth = (x: number) => { const c = Math.max(0, Math.min(1, x)); return c * c * (3 - 2 * c); };
const logGrid = Array.from({ length: 70 }, (_, i) => Math.pow(10, (i / 69) * 4));

export const DecayFail: React.FC = () => {
  const { f, t } = useAnim();
  const decay = logGrid.map((x) => [x, 7 * (1 - smooth(x / 30))] as [number, number]);
  const card = (v: string, l: string, color: string, at: number) => (
    <Up f={f} at={at} style={{ marginBottom: 24 }}>
      <div style={{ ...glass, borderTop: `6px solid ${color}` }}>
        <div style={{ fontFamily: mono, fontSize: 64, fontWeight: 700, color }}>{v}</div>
        <div style={{ fontSize: 28, color: C.text }}>{l}</div>
      </div>
    </Up>
  );
  return (
    <Box>
      <At x={0} y={10}>
        <Up f={f} at={0}>
          <div style={{ ...glass, padding: "10px 0 0 0" }}>
            <LineChart w={1060} h={600} f={f} xr={[1, 10000]} xlog yr={[0, 8]} xticks={[1, 10, 100, 1000, 10000]} yticks={[0, 2, 4, 6, 7]}
              xlabel="generated tokens (log) · schematic" ylabel="steering scale" at={t(0.04)}
              regions={[{ x0: 30, x1: 3000, label: "the reasoning: thousands of tokens", color: C.coral }, { x0: 3000, x1: 10000, label: "answer", color: C.amber }]}
              series={[{ pts: decay, color: C.cyan, at: t(0.1), dur: t(0.3) }]}
              marks={[{ x: 12, y: 7 * (1 - smooth(12 / 30)), label: "decay to ≈ 0 in 30 tokens", color: C.cyan, a: go(f, t(0.3)), dx: 22, dy: -6 },
                { x: 30, y: 0, label: "dose spent", color: C.coral, a: go(f, t(0.42)), dx: 12, dy: -26 },
                { x: 5000, y: 0, label: "answer at scale ≈ 0", color: C.amber, a: go(f, t(0.55)), dx: 0, dy: -26, anchor: "middle" }]} />
          </div>
        </Up>
      </At>
      <At x={1100} y={10} w={620}>
        {card("39.0 → 3.2", "think score · 38 of 44 refused", C.coral, t(0.5))}
        {card("41.6 → 34.0", "non-think score", C.amber, t(0.58))}
        <Up f={f} at={t(0.68)}><div style={{ fontSize: 26, color: C.dim }}>V4.1 reasons for thousands of tokens: a 30-token dose is spent inside the reasoning, and the answer starts at scale ≈ 0.</div></Up>
      </At>
    </Box>
  );
};

export const DecayKept: React.FC = () => {
  const { f, t } = useAnim();
  const xs = Array.from({ length: 80 }, (_, i) => (i / 79) * 300);
  const sch = (target: number) => xs.map((x) => [x, 7 - (7 - target) * smooth((x - 25) / 256)] as [number, number]);
  const items = ["Hold scale 7 for 25 tokens", "Then ease to 3.5 (reasoning) or 4 (answer) over 256 tokens", "Less vector once the censorship is passed", "Result: 41.3 non-think · 39.0 think"];
  return (
    <Box>
      <At x={0} y={10}>
        <Up f={f} at={0}>
          <div style={{ ...glass, padding: "10px 0 0 0" }}>
            <LineChart w={1060} h={600} f={f} xr={[0, 300]} yr={[0, 8]} xticks={[0, 50, 100, 150, 200, 250, 300]} yticks={[0, 2, 3.5, 4, 6, 7]}
              xlabel="generated tokens" ylabel="steering scale" at={t(0.04)}
              series={[{ pts: sch(3.5), color: C.cyan, at: t(0.1), dur: t(0.3), label: "reasoning → 3.5" }, { pts: sch(4), color: C.amber, at: t(0.16), dur: t(0.3), label: "answer → 4" }]}
              marks={[{ x: 25, y: 7, label: "hold 7 for 25 tokens", color: C.mint, a: go(f, t(0.12)), dx: 16, dy: -20 }]} />
          </div>
        </Up>
      </At>
      <At x={1100} y={10} w={620}>
        {items.map((s, i) => (
          <Up key={i} f={f} at={t(0.2 + 0.12 * i)} style={{ marginBottom: 20 }}>
            <div style={{ ...glass, fontSize: 31, color: C.text, padding: "20px 28px" }}>{s}</div>
          </Up>
        ))}
      </At>
    </Box>
  );
};

// ───────────────────────── S13.1: the gap to </think> ─────────────────────────
export const Gap: React.FC = () => {
  const { f, t } = useAnim();
  const card = (v: string, l: string, color: string, at: number) => (
    <Up f={f} at={at} style={{ marginBottom: 24 }}>
      <div style={{ ...glass, borderTop: `6px solid ${color}` }}>
        <div style={{ fontFamily: mono, fontSize: 64, fontWeight: 700, color }}>{v}</div>
        <div style={{ fontSize: 28, color: C.text }}>{l}</div>
      </div>
    </Up>
  );
  return (
    <Box>
      <At x={0} y={10}>
        <Up f={f} at={0}>
          <div style={{ ...glass, padding: "10px 0 0 0" }}>
            <LineChart w={1060} h={620} f={f} xr={[0, 8192]} yr={[0, 24]} xticks={[0, 2048, 4096, 6144, 8192]} yticks={[0, 5, 10, 15, 20]}
              xlabel="thinking tokens · schematic of measured values" ylabel="logit gap to </think>" at={t(0.04)}
              series={[{ pts: [[0, 22], [380, 16], [440, 0]], color: C.mint, at: t(0.1), dur: t(0.18) }, { pts: [[0, 20], [8192, 20]], color: C.coral, at: t(0.3), dur: t(0.4), label: "with steering" }]}
              marks={[{ x: 0, y: 22, label: "22", color: C.mint, a: go(f, t(0.12)), dx: 18, dy: -14 }, { x: 380, y: 16, label: "16", color: C.mint, a: go(f, t(0.2)), dx: 18, dy: -10 }, { x: 440, y: 0, label: "base model: 0 → it closes", color: C.mint, a: go(f, t(0.26)), dx: 22, dy: -22 }]} />
          </div>
        </Up>
      </At>
      <At x={1100} y={10} w={620}>
        {card("22 → 16 → 0", "base model: falls in one step", C.mint, t(0.28))}
        {card("≈ 20", "with steering: flat for 8192 tokens", C.coral, t(0.5))}
        {card("20 / 20", "loop-prone ids never close the think", C.amber, t(0.66))}
      </At>
    </Box>
  );
};

// ───────────────────────── S13.2: where the two things live ─────────────────────────
export const Bands: React.FC = () => {
  const { f, t } = useAnim();
  const n = 40, h = 300, y0 = 130;
  const g = modelGeom(0, y0, CW, h, n);
  const pos = sweep(f, t(0.1), t(0.5), n);
  const a1 = go(f, t(0.3), 24), a2 = go(f, t(0.5), 24);
  const mid = (a: number, b: number) => (g.x0(a) + g.x0(b) + g.cw) / 2;
  const card = (c: string, title: string, body: string, at: number) => (
    <Up f={f} at={at} style={{ flex: 1 }}>
      <div style={{ ...glass, borderTop: `6px solid ${c}`, height: 150 }}>
        <div style={{ fontFamily: mono, fontSize: 24, color: c }}>{title}</div>
        <div style={{ fontSize: 30, color: C.text, marginTop: 8 }}>{body}</div>
      </div>
    </Up>
  );
  return (
    <Box>
      <svg width={CW} height={CH} style={{ position: "absolute", left: 0, top: 0 }}>
        <ModelStack x={0} y={y0} w={CW} h={h} n={n} f={f} start={t(0.02)} pulses={[{ pos, color: C.cyan }]}
          bands={[{ from: 1, to: 9, color: C.coral, a: a1 }, { from: 30, to: 39, color: C.mint, a: a2 }]} />
        <text x={mid(1, 9)} y={60} textAnchor="middle" fontSize={30} fontWeight={700} fill={C.coral} opacity={a1}>layers 1–9</text>
        <text x={mid(1, 9)} y={96} textAnchor="middle" fontSize={24} fill={C.text} opacity={a1}>suppression of the closing · carried early</text>
        <text x={mid(30, 39)} y={60} textAnchor="middle" fontSize={30} fontWeight={700} fill={C.mint} opacity={a2}>layers 30–39</text>
        <text x={mid(30, 39)} y={96} textAnchor="middle" fontSize={24} fill={C.text} opacity={a2}>compliance · carried late</text>
      </svg>
      <At x={0} y={520} w={CW}>
        <div style={{ display: "flex", gap: 30 }}>
          {card(C.coral, "ZERO LAYERS 1–9", "loops halve", t(0.55))}
          {card(C.amber, "LOOPS ON 44 IDS", "17 (constant scale) → 13 (with schedule)", t(0.65))}
          {card(C.mint, "ZERO LAYERS 30–39", "compliance 12 → 2", t(0.75))}
        </div>
      </At>
      <At x={0} y={700} w={CW}>
        <Cap f={f} at={t(0.84)}>A logit bias would force the stop, not restore the decision. A clue, not a winner.</Cap>
      </At>
    </Box>
  );
};

// ───────────────────────── S14.2: the closure schedule ─────────────────────────
export const Schedule: React.FC = () => {
  const { f, t } = useAnim();
  const items = ["onset moves the exit one for one", "working dose ≈ 0.3", "late onset loses loops", "scale 1.0 is non-monotonic: fixes one prompt, breaks another"];
  return (
    <Box>
      <At x={0} y={10}>
        <Up f={f} at={0}>
          <div style={{ ...glass, padding: "10px 0 0 0" }}>
            <LineChart w={1060} h={620} f={f} xr={[0, 6500]} yr={[0, 1]} xticks={[0, 1000, 2000, 3000, 4000, 5000, 6000]} yticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
              xlabel="thinking tokens" ylabel="closure channel scale" at={t(0.04)}
              series={[{ pts: [[0, 0], [2989, 0], [2989, 0.4], [4989, 0.4], [5501, 0.9], [6500, 0.9]], color: C.violet, at: t(0.1), dur: t(0.5) }]}
              marks={[{ x: 2989, y: 0.4, label: "0.4 from onset ≈ 2989 (level 75)", color: C.amber, a: go(f, t(0.3)), dx: 20, dy: -24 },
                { x: 5501, y: 0.9, label: "0.9 from onset + 2000", color: C.coral, a: go(f, t(0.5)), dx: -18, dy: -22, anchor: "end" },
                { x: 800, y: 0, label: "0 until the onset", color: C.cyan, a: go(f, t(0.14)), dx: 0, dy: -24, anchor: "middle" }]} />
          </div>
        </Up>
      </At>
      <At x={1100} y={10} w={620}>
        {items.map((s, i) => (
          <Up key={i} f={f} at={t(0.4 + 0.1 * i)} style={{ marginBottom: 20 }}>
            <div style={{ ...glass, fontSize: 30, color: C.text, padding: "20px 28px" }}>{s}</div>
          </Up>
        ))}
      </At>
    </Box>
  );
};

// ───────────────────────── S16.1: terminal + the pieces of the service ─────────────────────────
type Span = { t: string; c?: string };
const LINES: Span[][] = [
  [{ t: "$ ", c: C.mint }, { t: "./sf-ds4-1flash-server --ssd-streaming \\" }],
  [{ t: "    --steering-profile-on-request " }, { t: "sf-ds4-1flash-candor", c: C.amber }],
  [{ t: "# the profile is loaded, steering is off", c: C.dim }],
  [{ t: "" }],
  [{ t: "$ ", c: C.mint }, { t: "curl localhost:8002/v1/chat/completions \\" }],
  [{ t: "    -d '{\"model\": \"" }, { t: "deepseek-v4.1-flash-steering", c: C.amber }, { t: "\", ...}'" }],
  [{ t: "# steering ON for this request", c: C.dim }],
  [{ t: "" }],
  [{ t: "$ ", c: C.mint }, { t: "curl ... -d '{\"model\": \"" }, { t: "deepseek-v4.1-flash", c: C.cyan }, { t: "\", ...}'" }],
  [{ t: "# steering OFF: bitwise the original model", c: C.dim }],
];
export const Terminal: React.FC = () => {
  const { f, t } = useAnim();
  const cps = 38, start = t(0.06);
  let left = Math.max(0, Math.floor(((f - start) * cps) / 30));
  const cards: [string, string, string, string][] = [
    [".sfsteer profile", "SFSTEER1 · JSON header · three 40×5120 matrices · 2.4 MB", C.amber, "0.18"],
    ["Session switch", "off = bitwise the original", C.cyan, "0.36"],
    ["Request", "the model id selects steering", C.mint, "0.54"],
    ["KV store", "separate steering/ cache on disk", C.coral, "0.72"],
  ];
  return (
    <Box>
      <At x={0} y={10} w={1000}>
        <Up f={f} at={0}>
          <div style={{ background: C.card, border: `1.5px solid ${ink(0.1)}`, boxShadow: glass.boxShadow, borderRadius: 14, overflow: "hidden", height: 640 }}>
            <div style={{ display: "flex", gap: 10, padding: "16px 20px", background: ink(0.09) }}>
              {[C.coral, C.amber, C.mint].map((c) => <div key={c} style={{ width: 16, height: 16, borderRadius: 8, background: c }} />)}
            </div>
            <div style={{ padding: "26px 30px", fontFamily: mono, fontSize: 25, lineHeight: 1.55, color: C.text, whiteSpace: "pre" }}>
              {LINES.map((line, i) => {
                const out = line.map((s, k) => {
                  const take = Math.min(left, s.t.length);
                  left -= take;
                  return <span key={k} style={{ color: s.c }}>{s.t.slice(0, take)}</span>;
                });
                return <div key={i} style={{ minHeight: 39 }}>{out}</div>;
              })}
              {left === 0 && Math.floor(f / 10) % 2 === 0 && <span style={{ color: C.cyan }}>▍</span>}
            </div>
          </div>
        </Up>
      </At>
      <At x={1050} y={10} w={670}>
        {cards.map(([ti, s, c, at], i) => (
          <Up key={i} f={f} at={t(+at)} style={{ marginBottom: 20 }}>
            <div style={{ ...glass, borderLeft: `8px solid ${c}`, padding: "18px 28px" }}>
              <div style={{ fontSize: 32, fontWeight: 700, color: C.text }}>{ti}</div>
              <div style={{ fontSize: 24, color: C.dim, marginTop: 4 }}>{s}</div>
            </div>
          </Up>
        ))}
        <Up f={f} at={t(0.84)}><div style={{ fontSize: 25, color: C.dim }}>Raw steering options removed: here steering exists only as a profile.</div></Up>
      </At>
    </Box>
  );
};
