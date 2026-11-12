# Proposal

## Why

A survey of 22 open System One projects (`docs/system-one.md`, section 11)
found that most do what `800` already does (state once, a suffix per
question, softmax over label logits). It also found a short list of
techniques this repository has not tried, and a longer list it should never
spend time on. This change writes both lists down as decisions, and probes the
three techniques that are cheap to test here.

## What the survey settles without any run

**Already covered by an existing change** (no new work):

| Technique seen elsewhere | Where it lives here |
|---|---|
| label prior from a content-free state, divided out (AnyJev L0) | `a020` |
| reasoning only when the margin is low, capped (AnyJev "cot") | `a035`; its design should also offer the cap: at most 20% of a request's questions escalate |
| `label_mass` as a health or abstain signal (vLLM, SGLang) | legal mass, `800`; `820` measured it as an abstain signal (AUROC 0.833, against 0.974 for an explicit option) |
| cached and cold answers differ (vLLM, SGLang: up to 0.07) | `830`: exact hits bitwise, extensions change 1 top in 20 |
| exact prefix tree with an ancestor mask (open-jev-fast) | `a045` |
| questions cached before the state (decider "schema-first") | `a015`; decider reports an accuracy cost without training: `a015`'s gate must be applied strictly |
| multi-token label tries (jevmlx) | `a040` |

**Discarded, with the reason** (do not propose again without new facts):

| Technique | Reason |
|---|---|
| trained heads, LoRA, pointer heads, self-distilled checkpoints, embedding models (Kev, decider, Nimble, NeoHorse, Tacit, JevEmbed, Laya) | no training stack for this model; cost in section 10 |
| verbalized probabilities in JSON, grammar fallbacks, readout ladders | they generate tokens at 31 ms each and exist for servers that hide logits; this one reads raw logits |
| batching suffixes or requests across sessions (Flide, simple-jev, vLLM) | refused under SSD streaming (`ds41_sessions_batch_supported`); revisit only with resident weights (`915`) |
| diffusion canvas (djev) | another architecture |
| NLI or embedding zero-shot models, small-model cascades | another model; a cascade is a client-side pattern |
| query-independent state compression (edge-jev) | no public accuracy measurement; changes the state the caller sent |
| prompt policies that repeat the state | double the dominant cost |

## What Changes (the three probes)

1. **Rotation averaging, offline.** Answer each low-margin `choice` again with
   the options rotated and average. A first look at `820`'s saved results says
   accuracy does not move (0.680 to 0.693 on 150 items) and calibrated NLL
   barely does; the probe confirms it on the full set and closes the
   question.
2. **Chained questions** (`so1`'s packed layout, without a new kernel): the
   questions of one request asked one after another in the same conversation,
   a placeholder as each earlier answer, no snapshot restore. It measures
   what packing costs in accuracy before anyone writes a multi-row readout.
3. **Graded `noul`** (simple-jev): read yes/no as a 1-9 rating instead of two
   letters. `820` fitted a `noul` temperature of 8, the edge of its search:
   the two-letter readout is badly over-confident.

Each probe ends with a keep-or-drop rule.

## Non-goals

- No engine edit. No multi-row sweep readout: that is a later change, written
  only if probe 2 says packing keeps accuracy.

## Impact

- `sf_sysone.c/.h`: a chained answer function, a graded `noul` suffix; both
  behind request options. `ds4_server.c`: two `sf` options.
- `sysone-bench/`: `rotation_avg.py`, runs, record.
- `openspec/changes/a035-sys1-confidence-escalation/design.md`: the 20% cap.
