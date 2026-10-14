# Design

## Context

Abliteration removes refusal by projecting the residual-*writing* matrices against a
refusal direction `r`: `W' = W − r (r^T W)`. The difference `ΔW = W_base − W_abliterated =
r (r^T W)` is therefore rank-one along `r`, so the left singular vector of `ΔW` recovers
`r` per edited matrix — from weights alone, no activations, no generation, no GPU.

Our base is `antirez/deepseek-v4.1-flash-gguf` `Q2` (340.6 GiB on disk). Three public
abliterated V4.1 checkpoints exist: `audreyt/DeepSeek-V4.1-Flash-Abliterated-GGUF` (Q2,
same ds4 project — a download is in progress), `distributedcognition/...-abliterated`
(reported strong decensoring, quant to confirm), and a domain variant
`drowzeys/...-Cybersecurity-Unleashed`. The `402` msuiche vector is an *activation*-derived
per-layer direction already validated; a weight-diff direction is a second, independent
derivation to compare against it and possibly improve on.

The runtime steering site is the per-layer residual fold
`v41_attn_input_weighted_fold_post_engram`. Both the `402` vector and a weight-diff `r`
are per-layer **residual-space** directions, so a per-layer cosine between them is
meaningful on the common layer mask.

## Goals / Non-Goals

**Goals**
- Recover a per-layer unit-norm f32 direction from an abliterated-vs-base weight diff, in
  the existing direction format, entirely offline.
- Gate the result on a base-match sanity check so a requantization artefact is never
  mistaken for an edit.
- Report geometry against the `402` vector; evaluate efficacy only through the `402`
  axis-A harness, user-run, against the msuiche baseline.

**Non-Goals**
- No runtime change and no new default direction in this change.
- No autonomous harmful-axis generation: axis-A stays user-run.
- No full dequantization of a 340 GiB file when the edited tensors are a small subset.

## Decisions

### D1 — Locate edits by a raw quantized-byte diff first (this is also the sanity check)
At equal quantization and shape, an un-edited tensor is byte-identical between the two
GGUFs, and an edited one is not. So the first pass compares raw tensor bytes — no dequant —
and yields both the edited-tensor map and the base-match sanity check for free: if tensors
the abliteration should not touch are byte-identical, the file is a clean per-tensor edit;
if everything differs, the file was fully requantized and the diff is requant noise, which
fails the check.

### D2 — Recover `r` as the left singular vector of `ΔW` at residual-writing sites
Dequantize only the edited tensors and take the SVD of `ΔW` per layer. The residual-writing
sites are the attention output projection and the shared-expert down projection (dense, one
per layer); routed-expert down projections (384 per layer) are used only in aggregate and
only if the dense sites are insufficient. Record each layer's leading singular-value share
as the rank-one quality; flag a layer that is not dominantly rank-one as low-confidence.

### D3 — Compare per-layer to the `402` vector, and diagnose a single global `r`
Report per-layer cosine to the `402` msuiche direction on the common mask. Abliteration
often applies one global `r` across layers; if so the recovered per-layer rows are mutually
near-identical — a diagnostic worth recording, and a reason the recovered direction may be
simpler (or coarser) than the per-layer `402` vector.

### D4 — Same-quant comparability; audreyt `Q2` first
`audreyt` `Q2` matches our base's quantization and project, so D1's byte-identity holds and
the edit is clean to read. `distributedcognition` and `drowzeys` are secondary: if their
quant differs or they are fully requantized, D1 falls back to a dequant-and-threshold diff
(an un-edited tensor must diff below a documented epsilon), which is noisier and weaker
evidence.

### D5 — Dequant with ds4's own reader if the GGUF type is custom
Inspect the GGUF tensor `ggml_type` first. A standard GGML quant dequantizes with a
standalone `gguf`+`numpy` reader in a disposable `/tmp` venv (host environment untouched,
SPEC §System integrity). A custom ds4 `Q2` needs a tiny ds4-backed dump of the dequantized
edited tensors; building that is the fallback, not the first move.

### D6 — Evaluation stays user-run; nothing adopted here
A recovered candidate is evaluated through `402` axis-A at a finishing cap against msuiche,
user-run. Malformed / not-comparable / no-better-than-msuiche are all valid recorded
completions. Adoption as a default, and any fusion with `402`, belong to `406`/`404`, not here.

## Risks / Trade-offs

- **Requantization noise.** If an abliterated file was fully requantized, un-edited tensors
  are not byte-identical and a small rank-one edit can be swamped. The D1 sanity check
  catches this; the mitigation is to prefer the same-project `Q2` file and, failing that, a
  higher-precision abliterated checkpoint — not to lower the threshold until it passes.
- **Basis mismatch.** The edit lives in the write matrices; our steering site reads the
  attention input. The directions share the residual space, but transfer is not guaranteed —
  only the user-run axis-A result settles efficacy, and geometry alone never does.
- **Expert aggregation ambiguity.** With 384 routed experts per layer, aggregating edited
  down-projections is ill-defined; the design leans on the dense sites and treats the expert
  aggregate as optional evidence.
- **SVD sign ambiguity.** The left singular vector is defined up to sign; fix the sign by
  aligning each layer to the `402` vector (or to a fixed +refusal reference) and record the
  convention, so a cosine sign is never read as disagreement.
