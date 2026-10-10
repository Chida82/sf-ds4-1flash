# Proposal

## Why

The engine reads its `DS4_*` switches with `getenv()` at the point of use, every time. The source names 557 distinct `DS4_*` variables; `ds4_metal.m` has 361 `getenv` sites (about 276 not cached in a `static`) and `ds4.c` 162 (about 114). Many sit on per-batch and per-layer paths: `DS4_METAL_CB_TIMES` is read three times per command batch, the router select up to six times per layer, the routed MoE dozens of times behind `&&` chains. With nothing set, each call still scans the whole process environment (52 variables in the owner's shell) to find nothing. `130-m5-decode-submission` S0 measured `getenv` at **0.5% of decode wall time** on the main thread, which sits on the critical path between the selected-id readback and the encode of the next batch (`speed-bench/perf-record.md`, Decode submission after 120).

The same 557 variables have no inventory. Nobody, owner or agent, can tell which ones are probes that slow a run, which turn a speed-up off, which are operational settings, and which are left over from code this child removed. A variable exported in a shell profile, or left over from a measurement session, silently changes the next run: a stray `DS4_METAL_DISABLE_V41_READBACK_MAILBOX` costs about 6% of decode, a profiler switch adds per-batch timing and logs. Today the only guard is the A/B harness, which strips inherited `DS4_*` from its own runs; normal CLI, server, bench and eval launches have none.

## What Changes

- **Read once.** Every `getenv` in the engine's objects goes through a snapshot of the `DS4_*` variables taken once per process. With no `DS4_*` set, a lookup is a four-byte prefix compare and an empty-list check. Call sites do not change: a child-owned header force-included by the Makefile redirects `getenv`, so no upstream line is touched. Non-`DS4_*` names pass through to the C library.
- **Tests keep toggling.** The forced header also wraps `setenv`/`unsetenv` in test builds so that each change refreshes the snapshot; the 188 in-process `setenv`/`unsetenv` calls in `tests/` keep working unchanged.
- **A classification file.** `ds4_env.tsv`, one line per variable the code reads: name, category (`operational`, `tuning`, `disable`, `enable`, `probe`, `test`), the normal-use state (`unset` or `any`), and a one-line description of what it does, taken from the code at its read site.
- **A startup report.** At engine open (CLI, server, bench, eval) the engine prints, only when there is something to say:
  - every `DS4_*` variable that is set although its normal-use state is `unset`, with its category and description;
  - every `DS4_*` variable that is set but that this build never reads (a typo, or a feature this child removed).

  Variables at their normal-use state are not shown. In a clean terminal it prints nothing.
- **A build check.** `make test` lists the `DS4_*` names the sources read and fails, naming them, on any that `ds4_env.tsv` does not classify. A sync that brings a new upstream switch stops there until it is classified; a classified name the code no longer reads is reported for removal.
- Docs: `AGENTS.md`, the `DS4_*` paragraph under "Child-specific values".

## Expected effect, by phase

Estimates from the `130` profile and the call structure; the harness decides.

| Phase | Mechanism | Estimate |
|---|---|---|
| Decode (steady) | removes about 0.2 ms of `getenv` per token on the main thread, part of it on the critical path | **+0.2% to +0.5%** |
| Token-by-token prompt work: appends under 1024 tokens, the tail of a sweep (e.g. 904 of the 5000-token prompt's tokens) | same path as decode | +0.2% to +0.5% on that part: `append +300` about +0.3%, `ttft 5000` about +0.2% |
| Prefill sweeps (ttft 2500/3500/7500/10000, `append +1500`) | a few hundred lookups per layer against 0.5-2 s of GPU and SSD time per layer | none measurable |
| First token after a prefill | a handful of lookups | none |
| Typical mix (e2e estimate) | decode is most of a 200-2000-token answer | about +0.1% to +0.3% |

The report and the check claim no speed. Their value is the runs they protect: a leftover switch can cost more than this change gains.

## Capabilities

### New Capabilities
- `env-switches`: how the engine reads its `DS4_*` environment switches (once per process, refreshable by tests), how every switch is classified, and what the engine reports at startup about switches that are set.

### Modified Capabilities
None. `perf-harness` keeps stripping inherited `DS4_*` from its runs; with the report, the variables it passes explicitly will be printed by each run's engine as well, which the harness ignores.

## Impact

- New: `ds4_env.h` (force-included), `ds4_env.c`, `ds4_env.tsv`, a generated header from the TSV (build output, not committed).
- `Makefile`: `-include ds4_env.h` for the engine objects and the tests, the TSV-to-header rule, the name check in `test`.
- `ds4.c`: one call at engine open for the report, the only line added to an upstream file.
- No upstream PR in `docs/upstream-prs.md` owns this zone (`#1027` and `d1738d2` mention `getenv` only in passing).
- Output: unchanged, bitwise. The snapshot returns the same values `getenv` would, for the engine's whole life, because the engine never calls `setenv`.
- Runtime lines: well under 800 (the TSV is data, not runtime code).
