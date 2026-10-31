import React from "react";
import { C } from "./anim";
import { Ablation, Contrast, Layer, Scale, Site } from "./viz/scenes1";
import { Align, Bands, DecayFail, DecayKept, Diff, Gap, Orthogonal, Phase, RankOne, Schedule, Terminal } from "./viz/scenes2";

// Scene ids used by `{ kind: "scene", id }` slides in slides.ts.
export const scenes: Record<string, React.FC> = {
  extract: () => (
    <Contrast
      a={{ name: "good", sub: "the model answers", text: "“Here is what happened…”", color: C.cyan }}
      b={{ name: "bad", sub: "the model refuses", text: "“I can't help with that.”", color: C.coral }}
      formula="mean(good) − mean(bad)" resultLabel="refusal direction d" resultSub="one unit row of ~5000 numbers per layer"
      note="Teacher-forced: measured while the model is already entering the answer we want." />
  ),
  closure: () => (
    <Contrast
      a={{ name: "last 10 forwards", sub: "before a natural </think>", text: "“…so the answer is… </think>”", color: C.mint }}
      b={{ name: "mid-reasoning", sub: "the same prompt, earlier", text: "“…let me check this again…”", color: C.violet }}
      formula="mean(closing) − mean(mid)" resultLabel="closure-satisfied" resultSub="additive · think only · 20 benign prompts"
      note="Teacher-forced on the model's own reasoning: the state right before it decides to stop." />
  ),
  ablation: Ablation, scale: Scale, site: Site, layer: Layer, diff: Diff, rank1: RankOne, align: Align,
  orthogonal: Orthogonal, phase: Phase, decayFail: DecayFail, decayKept: DecayKept, gap: Gap, bands: Bands,
  schedule: Schedule, terminal: Terminal,
};
