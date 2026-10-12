# Tasks

## 1. Registry

- [x] 1.1 Fetch the heads of #1073 (`cad7933`), #1135 (`e5b19e2`), #1167 (`7217598`), #1168 (`8f60f7d`), #1192 (`d851854`) and #1204 (`4203d5f`) as read-only refs in the upstream mirror. Verify that each head SHA matches `gh pr view`. (Done 2026-10-11: fetched as `refs/remotes/upstream-pr/<N>`; every head matches `gh pr view`. `upstream/main` is at `fc80bd6`, nine commits past `0aaea5a`.)
- [ ] 1.2 `docs/upstream-prs.md`:
  - the #1073 row and its commit table moved to `cad7933`, with lines for `4f80638`, `ff95f53` and `cad7933`;
  - the nine DSpark commits set to `open` ("assigned by `310`"), and the Commits prose updated;
  - new rows for #1135, #1167, #1168, #1192 and #1204, with #1167 and #1168 as `idea -> 350` and `idea -> 330`.

  Verify that every commit a later change acts on has a line, and that the PR count in Method is updated.

## 2. #1135

- [x] 2.1 Reachability by D1: a scratch counter at the compressed-mask copy, run once with a text prompt and once with an image prompt. Verify the result on the PR line (reached by text, by vision, or not reached). (Done 2026-10-12: not reached. Counters at the entry of `ds4_gpu_encode_flash_attention_decode_mixed_batch_heads` and at the copy, 20GB cache. V4.1's compress ratios are 2 and 1, so `ds41_attention_batch` takes the mixed path only below 512 compressed rows: an 821-token text prompt and a 547-token image prompt (`tests/vision-fixtures/glm53/diagram.png`, 493 image tokens) each reached the encoder with `use_comp_mask=0`, and the copy never ran. A 5038-token prompt takes the indexed path only. Statically, only `metal_graph_encode_layer_attention_batch` sets the flag. The probe was reverted.)
- [x] 2.2 (Not reached by 2.1, so nothing to run.) If reached: run the PR's analytic test against main's kernel. If it fails, port `kernel_dsv4_causal_comp_mask`, the encode change and the test. Verify all of these:
  - the test passes;
  - harness `--kinds decode,append --bitwise` A = main, B = step: text output bitwise;
  - the image reproducer's first differing position is recorded.

  Set the line to `adopt -> 300`.

## 3. #1192 and #1204

- [x] 3.1 #1204 against `70` S4f, site by site. If it adds nothing for one row, the verdict is `in main, modified` with the reason. Otherwise it is a step for 3.2. (Done 2026-10-11: `in main, modified`. S4f's `ds4_gpu_dsv41_shared_swiglu` already runs the one-row gate, up and SwiGLU in one dispatch with the same BF16 rounding, without storing gate and up; no run.)
- [ ] 3.2 Each reachable remaining commit is ported as a step and judged by the keep rule (sections mode when its predicted effect is below the harness's resolution). Verify the rows in `perf-record.md` and the verdict on its line. (2026-10-12: #1192 pre-screened with a scratch micro-bench of one decode token's top-k calls, loading the patched `argsort.metal` through `DS4_METAL_ARGSORT_SOURCE`: -59..-67 us/token at ctx 2048-32768, identical indices, about +0.13% decode. The harness A/B is still open, deferred to a later combined run.)

## 4. Integration

- [ ] 4.1 `make test` (read the names of the tests that ran) and `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` from the StarForge checkout when code changed. Then `openspec validate 300-upstream-pr-intake-october --strict`. No commit or push without a request.
