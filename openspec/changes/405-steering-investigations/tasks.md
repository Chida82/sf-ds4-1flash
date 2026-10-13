# Tasks

Depends on `401` (residual hook), `403` (the decay it guards), `402` (the judge).
Every item is kept only if `402` shows axis A up with B/C/D flat (config CI rule), or
is recorded as a finding. Model/eval runs share the lock `/tmp/sf-ds4-1flash.lock`.

## 1. Per-layer scale

- [ ] 1.1 Measure the per-layer good-vs-bad separation of `dot(d[L], y)` on a harmful
  contrast set; emit a per-layer scale/mask (layers below the null gate zeroed).
  Verify the separation profile matches msuiche's shape (rising through the mid
  layers, weak at L1-6).
- [ ] 1.2 Apply the per-layer scale in the steering edit (`ds4.c`), gated on a file;
  no file means a flat scale. Verify OFF is bitwise via
  `make test-deepseek41-decode-switch SWITCH=<the per-layer disable env>`.
- [ ] 1.3 Measure with `402`: the masked vector vs the flat vector at the same knee.
  Verify axis A holds while B/C/D improve or hold; keep only on a win, else record the
  profile as a finding.

## 2. Event-based decay

- [ ] 2.1 Add an opt-in event-decay mode: lower the scale when `dot(d[L], y)` returns
  to the comply range, clamped non-increasing within a phase, falling back to `403`'s
  schedule on a noisy projection. Verify OFF is bitwise.
- [ ] 2.2 Measure with `402` against `403`'s fixed schedule on the typical mix. Verify
  it beats or holds A with no B/C/D loss; keep only on a win.

## 3. Projection log

- [ ] 3.1 A `probe` env that prints `dot(d[L], y)` per layer per token without
  touching the activation. Classify it in `ds4_env.def`. Verify output is bitwise
  identical with the env set and unset, and decode tokens/s is unchanged.

## 4. Attention second channel (conditional)

- [ ] 4.1 Sweep residual-small + attn-tiny vs residual alone (3x3) and measure with
  `402`. Verify a win before shipping any attn knob; otherwise record it as a dropped
  idea in the registry.

## 5. Findings

- [ ] 5.1 Generalization map: run `402`'s per-category axis for one broad vector across
  domains (refusal, cyber, geopolitical, benign). Verify the per-domain breadth is
  recorded in `speed-bench/perf-record.md`/the registry with n and resolution.
- [ ] 5.2 Breaking-point map: run a scale x decay grid and record where the text
  degrades (code-switching, repetition) on V4.1's non-monotone response. Verify the
  map names the first failure per decay and cites the completions read.

## 6. Integration

- [ ] 6.1 `make test` (incl. env-check), parity on the disabled path token-identical,
  `openspec validate 405-steering-investigations --strict`. No commit or push without
  a request.

## 7. Rigor upgrades to the first-token screen (added 2026-10-13)

401's scale window (4-8), sign and index decisions rest on n=5 sweeps run from the
session scratchpad. Firm them up; the screen itself becomes a repo tool in `402` 7.1.

- [ ] 7.1 Re-run the scale sweep {1,2,4,8,16} and the index probe {orig,+1,-1} at n=25
  (the full elicit set), with per-prompt variance or a bootstrap CI beside each mean.
  Verify the n=5 conclusions (4-8 window; keep `direction[il]`) hold, or revise them
  with the numbers cited.
- [ ] 7.2 Lexicon-free metric: Jensen-Shannon divergence between the base and steered
  top-20 first-token distributions, reported as a second column beside the lexicon
  mass. Verify it ranks the scales in the same order as the mass, or explain the
  disagreement.
- [ ] 7.3 Benign coherence at scale 16 (the mass plateaus at 16 vs 8: possible early
  regression). One invocation per benign prompt; verify whether 16 is inside or past
  the usable window.
