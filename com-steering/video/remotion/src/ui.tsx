import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile } from "remotion";
import { C, CH, CW, Cap, Draw, Stream, TailCtx, Up, font, glass, go, ink, mono, tint, useAnim, type Tone } from "./anim";
import { scenes } from "./scenes";

export type { Tone };

// streamTitle: the title is a model prompt, so it is typed token by token; other titles slide up.
// dur: exact length in seconds (else the narration length, at least `min`); tail: seconds the
// finished animation stays up before the next slide (else the last 18 % of the slide).
type Base = { title: string; min?: number; dur?: number; tail?: number; streamTitle?: boolean };
export type Slide = Base &
  (
    | { kind: "image"; src: string; src2?: string; labels?: [string, string]; items?: string[]; caption?: string }
    | { kind: "bullets"; items: string[]; note?: string }
    | { kind: "stats"; stats: { v: string; l: string; tone?: Tone }[]; items?: string[]; note?: string }
    | { kind: "bars"; unit: string; aName: string; bName: string; rows: { l: string; a: number; b: number }[]; why?: [string, string]; caption?: string; note?: string }
    | { kind: "flow"; steps: { t: string; s?: string; tone?: Tone }[]; note?: string }
    | { kind: "table"; head: string[]; rows: string[][]; hl?: number; note?: string }
    | { kind: "score"; series: string[]; rows: { l: string; v: (number | null)[] }[]; max: number; hl?: number; items?: string[]; note?: string }
    | { kind: "scene"; id: string }
  );

const Note: React.FC<{ f: number; at: number; children?: string }> = ({ f, at, children }) =>
  children ? <Cap f={f} at={at} size={28} style={{ marginTop: 28 }}>{children}</Cap> : null;

const Bullets: React.FC<{ f: number; at: number; items: string[]; size?: number }> = ({ f, at, items, size = 38 }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
    {items.map((t, i) => (
      <Up key={i} f={f} at={at + i * 14} y={30}>
        <div style={{ ...glass, fontSize: size, color: C.text, padding: "20px 32px" }}>{t}</div>
      </Up>
    ))}
  </div>
);

const Body: React.FC<{ s: Slide }> = ({ s }) => {
  const { f, t } = useAnim();
  const col = (c?: Tone) => C[c ?? "cyan"];
  switch (s.kind) {
    case "bullets":
      return <><Bullets f={f} at={t(0.04)} items={s.items} /><Note f={f} at={t(0.5)}>{s.note}</Note></>;
    case "image":
      if (s.src2) {
        // two screenshots side by side (before / after), the items as chips underneath
        return (
          <>
            <div style={{ display: "flex", gap: 32 }}>
              {[s.src, s.src2].map((src, i) => (
                <Up key={i} f={f} at={t(0.02 + 0.08 * i)} style={{ flex: 1 }}>
                  <div style={{ ...glass, padding: 16, borderTop: `6px solid ${i ? C.mint : C.coral}` }}>
                    <div style={{ fontFamily: mono, fontSize: 26, color: i ? C.mint : C.coral, marginBottom: 10 }}>{s.labels?.[i]}</div>
                    <Img src={staticFile(src)} style={{ width: "100%", height: 470, objectFit: "contain", objectPosition: "top", borderRadius: 10 }} />
                  </div>
                </Up>
              ))}
            </div>
            {s.items && (
              <div style={{ display: "flex", gap: 24, marginTop: 28 }}>
                {s.items.map((x, i) => (
                  <Up key={i} f={f} at={t(0.3) + i * 14} style={{ flex: 1 }}>
                    <div style={{ ...glass, fontSize: 30, color: C.text, padding: "18px 26px", height: "100%" }}>{x}</div>
                  </Up>
                ))}
              </div>
            )}
          </>
        );
      }
      return (
        <div style={{ display: "flex", gap: 36, alignItems: "flex-start" }}>
          <Up f={f} at={t(0.02)} style={{ flex: s.items ? 1.7 : 1 }}>
            <div style={{ ...glass, padding: 16 }}>
              <Img src={staticFile(s.src)} style={{ width: "100%", maxHeight: 640, objectFit: "contain", borderRadius: 10 }} />
              {s.caption && <Cap f={f} at={t(0.15)} size={26} style={{ marginTop: 12 }}>{s.caption}</Cap>}
            </div>
          </Up>
          {s.items && <div style={{ flex: 1 }}><Bullets f={f} at={t(0.2)} items={s.items} size={32} /></div>}
        </div>
      );
    case "stats":
      return (
        <div style={{ minHeight: CH - 60, display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 28 }}>
            {s.stats.map((x, i) => (
              <Up key={i} f={f} at={t(0.03) + i * 12} style={{ flex: `1 1 ${s.stats.length > 3 ? 31 : 28}%`, maxWidth: s.stats.length > 3 ? "32%" : undefined }}>
                <div style={{ ...glass, textAlign: "center", borderTop: `6px solid ${col(x.tone)}` }}>
                  <div style={{ fontFamily: mono, fontSize: 70, fontWeight: 700, color: col(x.tone) }}>{x.v}</div>
                  <div style={{ fontSize: 28, color: C.text, marginTop: 8 }}>{x.l}</div>
                </div>
              </Up>
            ))}
          </div>
          {s.items && <div style={{ marginTop: 28 }}><Bullets f={f} at={t(0.4)} items={s.items} size={32} /></div>}
          <Note f={f} at={t(0.5)}>{s.note}</Note>
        </div>
      );
    case "bars": {
      // Red (ds4) bars first, all rows together, then the green (sf) ones; caption and note are
      // on screen from the start, the two explanations arrive after the bars they describe.
      const max = Math.max(...s.rows.flatMap((r) => [r.a, r.b]));
      const k = s.rows.length, G = 10, D = 50;
      const redAt = (i: number) => 14 + i * G;
      const greenAt = (i: number) => redAt(k - 1) + D + 10 + i * G;
      const bar = (v: number, color: string, at: number) => (
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 6 }}>
          <div style={{ width: `${(v / max) * 100 * go(f, at, D)}%`, maxWidth: "74%", height: 26, background: color, borderRadius: 6 }} />
          <div style={{ fontFamily: mono, fontSize: 26, color: C.text, opacity: go(f, at + 26, 12) }}>{v}</div>
        </div>
      );
      return (
        <>
          <div style={{ display: "flex", gap: 36, alignItems: "flex-start" }}>
            <div style={{ flex: s.why ? 1.1 : 1 }}>
              <Up f={f} at={0}>
                <div style={{ ...glass, display: "flex", gap: 40, marginBottom: 18, fontSize: 26, color: C.dim, padding: "16px 32px" }}>
                  <span><b style={{ color: C.coral }}>■</b> {s.aName}</span>
                  <span><b style={{ color: C.mint }}>■</b> {s.bName}</span>
                  <span style={{ marginLeft: "auto" }}>{s.unit}</span>
                </div>
              </Up>
              <Up f={f} at={4} y={20}>
                <div style={{ ...glass }}>
                  {s.rows.map((r, i) => (
                    <div key={i} style={{ display: "flex", gap: 20, alignItems: "center", marginBottom: i < k - 1 ? 18 : 0 }}>
                      <div style={{ width: s.why ? 190 : 300, fontSize: 26, color: C.text }}>{r.l}</div>
                      <div style={{ flex: 1 }}>{bar(r.a, C.coral, redAt(i))}{bar(r.b, C.mint, greenAt(i))}</div>
                    </div>
                  ))}
                </div>
              </Up>
              {s.caption && <Cap f={f} at={8} size={21} style={{ fontFamily: mono, marginTop: 14 }}>{s.caption}</Cap>}
            </div>
            {s.why && (
              <div style={{ flex: 1 }}>
                {s.why.map((w, i) => (
                  <Up key={i} f={f} at={i ? greenAt(0) + 30 : redAt(0) + 40} style={{ marginBottom: 24 }}>
                    <div style={{ ...glass, borderTop: `6px solid ${i ? C.mint : C.coral}` }}>
                      <div style={{ fontFamily: mono, fontSize: 26, color: i ? C.mint : C.coral, marginBottom: 8 }}>{i ? s.bName : s.aName}</div>
                      <div style={{ fontSize: 28, color: C.text }}>{w}</div>
                    </div>
                  </Up>
                ))}
              </div>
            )}
          </div>
          <Note f={f} at={10}>{s.note}</Note>
        </>
      );
    }
    case "flow":
      return (
        <div style={{ height: CH - 60, display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <div style={{ display: "flex", gap: 20, alignItems: "stretch" }}>
            {s.steps.map((x, i) => (
              <React.Fragment key={i}>
                {i > 0 && (
                  <svg width={70} height={20} style={{ alignSelf: "center", flex: "none" }}>
                    <Draw d="M0 10 L56 10" e={go(f, t(0.04) + i * 24, 16)} color={C.dim} width={4} />
                    <polygon points="52,2 68,10 52,18" fill={C.dim} opacity={go(f, t(0.04) + i * 24 + 12, 6)} />
                  </svg>
                )}
                <Up f={f} at={t(0.03) + i * 24} style={{ flex: 1 }}>
                  <div style={{ ...glass, height: "100%", borderTop: `6px solid ${col(x.tone)}` }}>
                    <div style={{ fontSize: 38, fontWeight: 600, color: C.text }}>{x.t}</div>
                    {x.s && <div style={{ fontSize: 27, color: C.dim, marginTop: 12 }}>{x.s}</div>}
                  </div>
                </Up>
              </React.Fragment>
            ))}
          </div>
          <Note f={f} at={t(0.55)}>{s.note}</Note>
        </div>
      );
    case "table":
      return (
        <>
          <Up f={f} at={0}>
            <div style={{ ...glass, padding: "12px 24px" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 32, color: C.text }}>
                <thead><tr>{s.head.map((h, i) => <th key={i} style={{ textAlign: "left", padding: "14px 12px", color: C.amber, fontFamily: mono, fontSize: 26 }}>{h}</th>)}</tr></thead>
                <tbody>
                  {s.rows.map((r, i) => {
                    const e = go(f, t(0.05) + i * 18, 16);
                    return (
                      <tr key={i} style={{ opacity: e, transform: `translateY(${(1 - e) * 20}px)`, background: i === s.hl ? tint(C.mint, 0.14) : undefined, fontWeight: i === s.hl ? 700 : 400 }}>
                        {r.map((c, k) => <td key={k} style={{ padding: "16px 12px", borderTop: `1px solid ${ink(0.1)}` }}>{c}</td>)}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Up>
          <Note f={f} at={t(0.6)}>{s.note}</Note>
        </>
      );
    case "score": {
      const cols = [C.cyan, C.violet];
      return (
        <>
          <Up f={f} at={0}>
            <div style={{ ...glass, display: "flex", gap: 36, marginBottom: 18, fontSize: 26, color: C.dim, padding: "14px 32px" }}>
              {s.series.map((n, k) => <span key={k}><b style={{ color: cols[k] }}>■</b> {n}</span>)}
              <span style={{ marginLeft: "auto" }}>score / {s.max}</span>
            </div>
          </Up>
          <div style={{ ...glass }}>
            {s.rows.map((r, i) => {
              const at = t(0.06) + i * 18;
              const hl = i === s.hl;
              return (
                <Up key={i} f={f} at={at - 6} y={20}>
                  <div style={{ display: "flex", gap: 24, alignItems: "center", marginBottom: 14, padding: "8px 12px", borderRadius: 10, background: hl ? tint(C.mint, 0.14) : undefined }}>
                    <div style={{ width: 380, fontSize: 28, color: C.text, fontWeight: hl ? 700 : 400 }}>{r.l}</div>
                    <div style={{ flex: 1 }}>
                      {r.v.map((v, k) => v === null ? null : (
                        <div key={k} style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 5 }}>
                          <div style={{ width: `${(v / s.max) * 100 * go(f, at + k * 6, 40)}%`, height: 24, background: cols[k], borderRadius: 6 }} />
                          <div style={{ fontFamily: mono, fontSize: 26, color: C.text, opacity: go(f, at + 28 + k * 6, 12) }}>{v.toFixed(1)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </Up>
              );
            })}
          </div>
          {s.items && <div style={{ marginTop: 22 }}><Bullets f={f} at={t(0.45)} items={s.items} size={28} /></div>}
          <Note f={f} at={t(0.6)}>{s.note}</Note>
        </>
      );
    }
    case "scene": {
      const Scene = scenes[s.id];
      return Scene ? <Scene /> : <div style={{ color: C.coral, fontSize: 40 }}>missing scene {s.id}</div>;
    }
  }
};

export const SlideView: React.FC<{ kicker: string; slide: Slide }> = ({ kicker, slide }) => {
  const { f } = useAnim();
  const o = interpolate(f, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ fontFamily: font, opacity: o }}>
      <div style={{ position: "absolute", left: 100, top: 52, width: CW }}>
        <div style={{ fontFamily: mono, fontSize: 24, color: C.amber, letterSpacing: 2, marginBottom: 8, fontWeight: 600 }}>{kicker}</div>
        <div style={{ fontSize: 60, fontWeight: 700, color: C.text, lineHeight: 1.1 }}>
          {slide.streamTitle ? <Stream text={slide.title} f={f} at={3} wps={4} /> : <Up f={f} at={2} y={20}>{slide.title}</Up>}
        </div>
      </div>
      <div style={{ position: "absolute", left: 100, top: 230, width: CW, height: CH }}>
        <TailCtx.Provider value={slide.tail}><Body s={slide} /></TailCtx.Provider>
      </div>
    </AbsoluteFill>
  );
};
