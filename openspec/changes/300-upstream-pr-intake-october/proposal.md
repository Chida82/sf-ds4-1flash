# Proposal

## Why

`docs/upstream-prs.md` was last reviewed on 2026-09-26. Since then, five open upstream PRs touch code that V4.1 Flash reaches on Metal, and #1073 has moved:

- **#1073** moved its head from `3d3c83b` to `cad7933`. The three new commits are `4f80638`, `ff95f53` and `cad7933`: the wide index scorer kept exact, the radix top-k scratch reset, and the V4.1 rows and DSpark checks kept off other models. Its nine DSpark commits are recorded as "never" only because the registry said "spec-dec: none". `310` reopens that question.
- **#1135** fixes future compressed keys that become visible in batched attention when fewer than `top_k` causal keys exist. The selection mask overwrote the causal mask. The PR's reproducer is a visual prefill, and this child keeps vision.
- **#1192** sorts the non-causal top-k blocks with a shuffle network. It claims bit-identical results and about -20% on that kernel.
- **#1204** fuses the V4.1 shared expert's gate, up and SwiGLU. Main already has a one-row fusion of that site from #1073 (`70` S4f).
- **#1167 and #1168** add an n-gram prompt-lookup drafter and an exponential back-off for speculative drafting, written for V4 Flash. Their ideas serve `330` and `350`.

The DSpark changes `310`-`350` need the registry to say which commits they take. #1135 is a correctness question for this child's vision prefill, and it should not wait for a performance branch.

## What Changes

- **Registry.**
  - Rows and commit lines for #1135, #1167, #1168, #1192 and #1204, with verdicts by the Method.
  - The #1073 row and its commit table move to `cad7933`, and the three new commits get verdicts.
  - The DSpark commits change from "never" to `open`. `310`'s decision assigns them.
- **#1135.**
  - Reachability in this child: which callers reach the batched-attention wrapper with a compressed selection mask (vision prefill; text prefill is expected to use the indexed path).
  - The PR's analytic test runs against main's kernel. If it fails there, the fix and its test are ported as a correctness step.
  - That is the one step of this change allowed to change output, and only where future keys leaked.
- **#1192 and #1204.**
  - Reachability first.
  - A reachable commit is measured and kept by the usual rule.
  - #1204 is compared with main's S4f before any run. If it is the same work, it is recorded `in main, modified`.
- **#1167 and #1168.** `idea` lines pointing at `350` and `330`. No code is taken here.

## Capabilities

### New Capabilities
None (`skip_specs: true`): registry, one correctness fix, and possible performance ports with unchanged output.

### Modified Capabilities
None.

## Impact

- `docs/upstream-prs.md`.
- If ported: `ds4_metal.m`, `metal/dsv4_misc.metal` and `tests/ds4_test.c` (#1135); the top-k sort kernel (#1192); the shared-expert site (#1204).
- `speed-bench/perf-record.md` rows for any measured step.
- Independent of `310`-`350`, which only read its registry lines.
