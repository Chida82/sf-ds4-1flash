# Tasks

## 1. Gate: memory accounting

- [x] 1.1 Read the timeline, curve and ranking of `225-mac-memory-evidence` (memory during decode and at the prefill peak, the prefill-only buffers' state, the misses removed at +770 slots). Verify `225` is complete.
- [x] 1.2 From those tables decide the S1 size (770 slots or less) and whether S2 is admissible (prefill-only buffers resident, not compressed, during decode). Record the table and the decision in `speed-bench/perf-record.md`.

## 2. S1: growth into the reserve

- [x] 2.1 Lent slabs (D2): after the explicit buffers are freed, allocate the slabs, register them, push their slots on the free list; behind `DS4_METAL_DISABLE_V41_CACHE_GROWTH` read per call; time one or two slabs and keep the faster shape. Verify `make test` and a CLI decode printing `cache growth: +N slots` in the streaming summary.
- [x] 2.2 Shrink before a sweep (D3): drain, evict the lent slabs' entries, release, then the explicit buffers allocate as today; the mmap fallback on a failed release, counted. Verify `make test`, `test-metal-ssd-experts`, `--stream-decode-queue-parity`, `test-metal-command-memory`, and a CLI run with two prompts printing one shrink and no fallback.
- [x] 2.3 Harness A/B `decode,append` with `guard-16896,guard-decode`, `--bitwise --cache-policy-change`, against the previous kept tree, with memory and swapouts sampled. Verify the keep rule on decode with append and the guards bounded; record the row, the hit rates, the miss counts and the first token after the sweep. Remove the code if not kept.

## 3. Hotness decay

- [x] 3.1 Environment override of the decay interval (D4), read per call. Verify the decode-switch test passes with the override set to 16, then A/B 8 and 32 against 16 in one session with `--cache-policy-change`; keep a value only with a CI above zero on decode; record the rows. Done 2026-10-09 with 128 against 16 instead of 8 and 32 (the `225` replay screen: 8 is worse than 16 and 32 is too close to it): decode 8192 below zero, so 16 stays; the override is kept.

## 4. S2: prefill-only context buffers (only if 1.2 admits it and 2.3 kept S1)

Not run: 2.3 dropped S1 (2026-10-09).

- [x] 4.1 (Not run: 2.3 dropped S1, and S2 builds on it.) Split `ds41_graph_alloc` into static and per-sweep parts (D5); release after a sweep, reallocate at the next; extend the growth by their bytes. Verify `make test`, the model-backed prefill tests (`test-deepseek41-prefill-*`), and `DS4_METAL_CB_TIMES` showing the allocation time per sweep.
- [x] 4.2 (Not run: 2.3 dropped S1.) Harness A/B against S1, same kinds and flags, with ttft and first token reported. Verify the keep rule; record the row. Remove S2 if not kept.

## 5. Integration

- [x] 5.1 Review the touched regions against `AGENT.md`; add the switches to `AGENTS.md` and update its memory figures; `make`, `make cpu`, `make test`, the model-backed checks and `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`; `openspec validate 230-expert-cache-growth --strict`. The segment-start A/B joins the end-of-batch measurement. No commit or push without a request. Done 2026-10-09 for what stayed (the decay override): `make`, `make cpu`, `make test`, the decode-switch test bitwise, parity OK (10 prompts), `ds4_test` with streaming OK on every group but `--tool-call-quality` (hours-long `--quality` streaming branch, not touched).
