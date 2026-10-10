# Tasks

## 1. Code

- [x] 1.1 D1 in `ds41_prefill_expert_pread`. Verify `make` (no warnings) and `make test` (output names the V4.1 explicit-read tests).

## 2. Evidence

- [x] 2.1 Residency runs without the copy, `main` and this change alternated, two each: statics, model routed up, page-ins, first token after 8192.
  - Done 2026-10-10. 8192 segment, main / 268: prefill 341 and 312 / 574 and 532 tok/s; first token 984 and 725 / 102 and 353 ms; page-ins 1.72 M / 0.14 M; statics minimum 6.64 / 8.01 GiB. The 2048 segment depends on the previous process's page cache, so single runs cannot judge it.
  - Requests after a full memory, two repetitions: an 8192 prompt and 64 tokens, then two appends of 1100 tokens (each a sweep), 64 tokens after each.
    - `main`: prefill 135-146 then 119-129 tok/s; first token 177-240 then 539-597 ms.
    - `268`: prefill 168-169 then 160-161 tok/s; first token 105-137 then 132-139 ms.
    - Appends of 1000 tokens run token by token, under the 1024 warm minimum. They are equal: 24-25 tok/s and 40-48 ms both.
- [x] 2.2 Harness `cold,append,decode`, `--bitwise`, 3600 s, A = `main`, B = this change, without the copy. Verify bitwise.
  - Done 2026-10-10, 38 pairs, Heavy, bitwise. First token 8192: 1230 -> 150 ms. First token 10000: 295 -> 110 ms. ttft 10000 +5.7% (+2.9..+7.4). Append +1500 +12.5% (+10.0..+29.6). Decode 2048 +3.3% (-0.0..+8.4). Decode 8192 -0.6% (-16.0..+0.3, 4 pairs). The rest within +-0.6% across zero; e2e +1.0%.
- [x] 2.3 With the copy on APFS: the same harness with `--env DS4_METAL_PREFILL_REPLICA=<copy>`. Verify bitwise.
  - Done 2026-10-10, 32 pairs, Heavy/Moderate, bitwise. First token 8192: 1049 -> 132 ms. ttft 10000 +2.2% (+0.8..+4.7). Append +1500 +16.6% (+14.5..+18.3). Prefill 5000 +2.3% (+0.2..+3.4). Decode 2048 +2.3% (-1.4..+6.4). Decode 8192 -1.2% (-1.8..-0.7), CI below zero. The rest within 1.3% across zero; e2e +1.1%.
- [x] 2.4 Trace the decode 8192 row of 2.3: single runs with the timing summary, then the harness on `decode` and on `guard-decode`, copy on both.
  - Done 2026-10-10. Miss reads are equal over 2500 tokens. `decode`, 14 pairs: decode 8192 -1.6% (-2.1..-0.7), first token 844 -> 150 ms. In that window the GPU runs at 1099 MHz with `main` and 1077 MHz with this change: `main`'s first token idles and cools the GPU. `guard-decode`, 10 pairs, with no pause on either side: -0.1% (-0.4..+0.4), equal clocks.

## 3. Decision and documentation

- [x] 3.1 Apply the keep rule (design D3). Record the probe, the residency runs and the harness rows in `speed-bench/perf-record.md`. Point the `200` row in Rejected ideas to this change. If kept, update the first-token figures in `AGENTS.md` and the README, run `make cpu`, the model-backed checks and the parity oracle, and `openspec validate 268-aligned-uncached-reads --strict`. No commit or push without a request.
  - Done 2026-10-10. Kept: only decode 8192 with the copy fails the rule, and 2.4 traces it to the GPU clock. `perf-record.md` has Uncached reads from a page boundary; the `200` row points to it; `AGENTS.md` and the README carry the 0.15 s first token. On the main tree, together with `265`:
    - `make` has no warnings, and `make test` names its tests;
    - `make cpu` builds, and `make test-deepseek41-prefill-replica` passes bitwise;
    - `make test-deepseek41-metal` passes;
    - `ds4_test` with streaming passes every entry except `tool-call-quality`'s exact path, which was stopped after 45 min of `--quality` paging (it runs no code this change touches);
    - the parity oracle is token-identical on 10 prompts.
