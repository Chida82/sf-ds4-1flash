# Proposal

## Why

The source names 557 distinct `DS4_*` variables, and they have no inventory. Nobody, owner or agent, can tell which ones are probes that slow a run, which turn a speed-up off, which are operational settings, and which are left over from code this child removed. A variable exported in a shell profile, or left over from a measurement session, silently changes the next run: a stray `DS4_METAL_DISABLE_V41_READBACK_MAILBOX` costs about 6% of decode, a profiler switch adds per-batch timing and logs. Today the only guard is the A/B harness, which strips inherited `DS4_*` from its own runs; normal CLI, server, bench and eval launches have none.

The engine also reads its switches with `getenv()` at the point of use, every time, and `130-m5-decode-submission` S0 measured `getenv` at 0.5% of decode wall time on the main thread (`speed-bench/perf-record.md`, Decode submission after 120). A snapshot read once per process was this change's first step; the harness measured no gain and it was dropped (design D1).

## What Changes

- **A classification file.** `ds4_env.def`, one `DS4_ENV(...)` line per variable the code reads: name, category (`operational`, `tuning`, `disable`, `enable`, `probe`, `test`), the normal-use state (`unset` or `any`), and a one-line description of what it does, taken from the code at its read site.
- **A startup report.** At engine open (CLI, server, bench, eval) the engine prints, only when there is something to say:
  - every `DS4_*` variable that is set although its normal-use state is `unset`, with its category and description;
  - every `DS4_*` variable that is set but that this build never reads (a typo, or a feature this child removed).

  Variables at their normal-use state are not shown. In a clean terminal it prints nothing.
- **A build check.** `make test` lists the `DS4_*` names the sources read and fails, naming them, on any that `ds4_env.def` does not classify. A sync that brings a new upstream switch stops there until it is classified; a classified name the code no longer reads is reported for removal.
- **Dead switches go.** A switch whose every read is unreachable in this child (no caller, or a guard on a shape V4.1 never has), and that no test reaches, is removed with the code only it guards, each cut marked `sf-ablate`. Pipeline, TP and CPU-reference paths count as live.
- Switches are still read with `getenv` where upstream reads them.
- Docs: `AGENTS.md`, the `DS4_*` paragraph under "Child-specific values".

## Expected effect

None on speed: the change claims no gain and must not make any phase slower (harness against `main`, bitwise, no metric with its CI wholly below zero). Its value is the runs it protects: a leftover switch can cost more than any step of a segment gains.

## Capabilities

### New Capabilities
- `env-switches`: how every `DS4_*` environment switch is classified, and what the engine reports at startup about switches that are set.

### Modified Capabilities
None. `perf-harness` keeps stripping inherited `DS4_*` from its runs; with the report, the variables it passes explicitly will be printed by each run's engine as well, which the harness ignores.

## Impact

- New: `ds4_env.h` (the table and the report), `ds4_env.def`, `tests/env_check.pl`.
- `Makefile`: the name check `env-check` first in `test`, and the objects that compile `ds4.c` depend on the header and the `.def`.
- `ds4.c`: the include and one call at engine open, the only lines added to an upstream file.
- No upstream PR in `docs/upstream-prs.md` owns this zone (`#1027` and `d1738d2` mention `getenv` only in passing).
- Output: unchanged, bitwise.
- `ds4.c`, `ds4_metal.m`, `ds4_cli.c`, `metal/*.metal`: the dead-switch cuts, deletions only.
- Runtime lines added: about 40 (the `.def` is data, not runtime code).
