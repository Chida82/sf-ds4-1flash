# Proposal

> **Status 2026-10-28: stopped by `310`.** One verify row costs about 0.6 of a decode token under streaming (bitwise configuration); main projects under 1x on code. Reopen only if a verify row can cost at most 0.3 of a decode token on main (`310` "Margin verdict", `speed-bench/perf-record.md` "DSpark verify cost under streaming").

## Why

After `320`, drafting works only in the CLI and the bench, and only greedy. The owner's real requests reach the server, where most decoding samples: the DeepSeek thinking defaults set a temperature. Only tool-call syntax decodes greedily (`greedy_tool_syntax`). Without sampling support, drafting would help the server only inside tool calls.

#1073's cycle already holds exact speculative sampling, which keeps each token's distribution equal to ordinary sampling. This change enables it and brings drafting to the server for a single request.

## What Changes

- **Exact sampling with drafting.** At a temperature above zero, drafts are accepted with the target probability, and a rejection is resampled from the remaining distribution (#1073's `exact` branch).
  - The default threshold is upstream's for exact mode (0.8), unless measurement here says otherwise.
  - `320`'s "no drafting when sampling" notice goes.
  - Upstream's opportunistic mode, which accepts matching greedy drafts directly, is not ported. It changes the sampling distribution.
- **Server.**
  - `--dspark`, `--mtp-model` and `--dspark-confidence` are added to `sf-ds4-1flash-server`.
  - A request drafts when it is the only active decode. When more are pending, decoding is plain.
  - Live KV reuse and disk KV checkpoints work with drafting on.
- **Mode boundaries.** When a verified block crosses a change of sampling mode (into or out of tool-call syntax, or out of thinking), the accepted prefix stops at the boundary token. Rows after it are rolled back like rejected rows, and the next token is sampled in the new mode. No context rebuild is needed.
  - Upstream's `fc80bd6` solves the same problem for V4 Flash with snapshots.
- **Measurement.**
  - One client of `serve_concurrency_bench.py` on code, chat and tool requests with the thinking defaults, plain against `--dspark`.
  - A statistical check that exact sampling keeps the distribution.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `dspark-drafting`: sampled decoding drafts with exact sampling instead of turning drafting off; the server takes the flags; mode boundaries cut the accepted prefix.

## Impact

- `ds4_server.c`: flags, the single-request condition, the boundary cut.
- `ds4.c`: the exact branch enabled, and the accepted-prefix cut at a caller's boundary.
- `tests/`: the distribution check, and a boundary test.
- `README.md`, `docs/SERVER.md`, `docs/upstream-prs.md` (`fc80bd6`: `idea -> 340`).
