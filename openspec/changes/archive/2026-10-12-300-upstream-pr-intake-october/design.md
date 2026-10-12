# Design

## Context

- **#1135** replaces a plain copy of the compressed-key selection mask, in `ds4_gpu_encode_flash_attention_decode_mixed_batch_heads` (`ds4_metal.m`), with `kernel_dsv4_causal_comp_mask`. A key is visible when it is selected and its index is below `(pos + 1) / ratio`.
  - The PR states that the normal text top-k path uses a separate indexed-attention implementation, and does not claim that text inference was affected.
  - Its test, `test_metal_compressed_selection_causality`, is analytic and runs under `--metal-kernels`.
- **#1192 and #1204** are performance PRs with claimed bit-identical output. `70` S4f already fused the one-row shared gate/up SwiGLU from #1073; its `_rows` and MMA forms were not taken.
- **#1073's three new commits** touch code that main partly holds from `60` and `70`: the wide index scorer, the radix top-k scratch, and the V4.1 matrix rows.

## Goals / Non-Goals

**Goals:**
- Every listed commit has a verdict line.
- #1135 is settled for this child: either not reachable, or fixed with its test.

**Non-Goals:**
- Porting DSpark or n-gram drafting (`310`-`350`).
- Reviewing PRs beyond the six named. The next full review follows the Method as usual.

## Decisions

### D1. Reachability by probe, not by name
Follow the child's rule 15. Each commit's site is proved reached or unreached, by a constant-false predicate, `nm`, or a runtime probe. A probe is a scratch counter at the call site, run once with a text prompt and once with an image prompt. It never lands.

### D2. #1135 is a correctness step
The test decides. If the analytic test fails against main's kernel, the leak exists in this child and the fix is ported.
- **Kept when** the test passes and text prompts stay token-identical and bitwise in the harness (`--bitwise`, kinds `decode,append`).
- **Image prompts** may change output. The change is reported as the fix's effect, with the first differing position on the PR's reproducer.
- **Verdict:** `adopt -> 300`. If upstream merges the PR first, the line becomes `next sync`.

The alternative, waiting for a sync, leaves a known leak in a live path for an open PR of unknown timing.

### D3. #1192 and #1204 follow the keep rule
- **A reachable commit is a step**, judged by the config's rule against the previous step. It runs in sections mode when its predicted end-to-end effect is below the harness's resolution.
- **#1204 against S4f.** It is compared site by site first. If it adds nothing S4f lacks for one row, it is `in main, modified`, with no run.

### D4. #1073 moves to its new head
The commit table is re-derived from `3d3c83b..cad7933`.
- The three new commits get lines.
- The nine DSpark commits get `open`, with "assigned by `310`" in the note.
- The "never" sentence in the Commits prose is replaced.

## Risks / Trade-offs

- **[#1135 is reachable from a text path too]** → The test and the probe both cover text. If text output changes, the step stops, and the first differing position and prompt go to the owner before anything is kept.
- **[A measured port is neutral]** → It is recorded as `history`, as usual. Nothing in `310`-`350` depends on it.
