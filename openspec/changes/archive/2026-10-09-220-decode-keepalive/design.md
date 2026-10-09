# Design

## Context

`ds4_gpu_tp_init` starts `ds4_gpu_tp_keepalive_thread`. The thread loops:
- it commits one `kernel_dsv4_tp_keepalive` dispatch (one threadgroup of 256 threads by default, ALU only, no memory traffic) on its own queue;
- it waits for that dispatch to finish;
- while `g_tp_keepalive_paused` is set, it sleeps 200 us instead.

The S1 prototype starts the same thread on a single streaming box at the first decode token, unpauses it for the token and gives it a 1 ms period with a duty cycle. The burst is calibrated from the fastest of the first three dispatches, about 22 iterations per us under decode. S1 lost in both regimes (proposal; `perf-record.md`, Decode keep-alive after 210).

The decode critical path per layer (`132`, `210`):
1. the router batch ends;
2. about 20 us later the CPU sees the ids;
3. about 10 us of CPU work follows;
4. about 100 us pass from the commit to the expert pass's GPU start.

A layer with missing experts takes the split-deferred path (`145`):
- the resident experts are committed as their own stage;
- `ds4_gpu_stream_expert_cache_load_selected_missing` reads the misses on the pread pool and blocks in `ds4_gpu_stream_expert_pread_pool_wait`, about 1 ms;
- the missing stage is committed after the resident one finishes.

The resident stage is about 30 us per expert, so the GPU idles for most of the read. A decode token takes 40-45 ms at Heavy, 31 ms at Nominal. The decode hit rate is 0.90 at the harness's cache.

Thermal regimes, from the `210` A/B mactop logs and the S1 gate:
- **Nominal:** the GPU at 1620 MHz and 100% active inside a decode window. The 13-20% idle share in the `210` logs is the whole run's (load, prefill, gaps).
- **Heavy:** about 1000-1125 MHz, the GPU 92-100% active at 15-20 W and 65-70 C.

CPU clusters during decode (S1 gate, Nominal):
- **Super:** 4.6 GHz, its top step, 95% active.
- **Performance:** 2.2-2.3 GHz, 46% active; 2.9 GHz is seen elsewhere in the log.

## Goals / Non-Goals

**Goals:**
- know, per thermal regime, whether a keep-alive during the miss reads (S1b) or a CPU spinner (S2) raises decode throughput, and at what power and temperature;
- if either pays somewhere, a launch-time policy (`off`/`auto`/`on`) with a default that never loses at Heavy;
- output bitwise; no cost outside decode.

**Non-Goals:**
- keep-alive during prefill sweeps;
- the TP keep-alive's tuning;
- a keep-alive for the whole decode token (S1, dropped);
- changing the harness's Nominal preflight.

## Decisions

### D1. Gate in two regimes, before the policy code

Each candidate (S1, S1b, S2) is gated the same way, behind its environment switch only. Every run logs mactop.

1. **Nominal, short.** Wait for pressure Nominal and the GPU below 50 C, then run one decode (2048 context, 256 tokens), alternating off and on, 6 pairs. Report steady tok/s, GPU MHz, GPU W, CPU W, cluster clocks, max temperature and the pressure at the run's end. This is the interactive case.
2. **Heavy, sustained.** Harness A/B `decode` with B on (`--b-env`), 30 minutes, 300 s preheat, `--bitwise`. Same metrics. This is the agent and back-to-back case.

| Nominal | Heavy | Result |
|---|---|---|
| gain | gain or flat | keep, default `on` |
| gain | loss | keep, default `auto` |
| flat or loss | gain | keep, default `on` if Nominal is flat, `auto` with the opposite gate otherwise |
| flat or loss | flat or loss | drop: Rejected ideas row, code removed |

A gain is a CI above zero by the harness rule (pair ratios with a bootstrap 95% CI for the Nominal pairs). S1 fell in the last row at duty 100. The duty sweep was skipped because the GPU was 100% active.

### D2. S1b: keep-alive during the miss reads

- **Scope:** the thread runs only while a decode token is in `ds4_gpu_stream_expert_pread_pool_wait`. The token scope stays at `ds41_graph_step` with logits on a single streaming box, and the wait unpauses and re-pauses the thread around itself. Prefill reads do not wake it.
- **Bursts:** short and back to back, with no duty cycle. A dispatch cannot be cut short, so a burst that starts near the end of the read delays the missing stage by up to one burst. The length, `DS4_METAL_V41_DECODE_KEEPALIVE_BURST_US`, is calibrated as in S1.
- **Sweep:** threadgroups 1 and 8 (`DS4_TP_KEEPALIVE_TGS`; Argodrive used 8) at a 200 us burst. Then bursts of 100 and 500 us at the better width, in the regime that gained.
- **Duty cycle:** S1's is deleted.
- **Logging:** in the cache report next to the mailbox line, the number of waits per token and their total time, so the gate can tell how much of the token the keep-alive covers.

### D3. Policy and parameter

S1b gained at Nominal and was flat at Heavy; S2 lost. The owner chose an opt-in flag:
- `--boost` sets `ds4_engine_options.boost` in the CLI, server and bench, off by default. The engine passes it to Metal with `ds4_gpu_set_decode_keepalive` at open.
- `DS4_METAL_V41_DECODE_KEEPALIVE=0|1` overrides it per token, for the harness and the decode-switch test.
- No `auto`: the keep-alive never loses at Heavy, so a pressure read would buy nothing.
- If the fan sessions (task group 5) pay, `--boost` also drives the request-scoped fan hint.
- The thread starts lazily at the first decode token, paused, and is joined at cleanup. TP keeps starting its own as today. If the keep-alive is kept, the paused thread waits on a condition variable instead of polling every 200 us, so an idle server does not wake it 5000 times a second.

### D4. S2: CPU spinner, gated on its own

One thread at `QOS_CLASS_USER_INTERACTIVE` spins with `yield` while a decode token runs and blocks on a condition variable between tokens. It is behind `DS4_METAL_V41_DECODE_CPU_KEEPALIVE=1` and is gated by D1 independently of S1b.

The decode thread already spins on the Super cluster at its top clock, so a gain would have to come from the Performance cluster or the Metal driver's threads. The gate reports both clusters' clocks, with the spinner on and off, to tell which. If the spinner lands on the Super cluster and nothing moves, that is recorded as the reason.

### D5. Evidence

- each switch: the decode-switch bitwise test (switch set against unset) and `make test`;
- each gate's two tables and the sweeps go in `perf-record.md`, with watts, temperatures and cluster clocks;
- if kept, the harness A/B at the chosen default against the previous kept tree, `decode,append` with the guards, `--bitwise`, keep rule.

## Risks / Trade-offs

- **A burst outlives the read and delays the missing stage** -> short bursts, and a sweep of the burst length.
- **At Heavy the keep-alive spends the power budget the decode kernels need** -> `auto` gates on pressure, and the default follows D1.
- **Contention with the decode queue** -> ALU only, active only while the decode queue has nothing to run.
- **The spinner adds CPU heat to a shared thermal budget** -> it is measured at Heavy too, with CPU W.
- **Pressure is a system-wide signal: another app's heat moves it** -> that is the point. The budget is shared, so the keep-alive yields when the machine is hot for any reason.
- **Nominal measurements need cooldown between runs (35-70 s each in the S1 gate)** -> run them unattended.

## Migration Plan

Branch `perf/220-decode-keepalive`. The flag and switches join `AGENTS.md` and the README's everyday-use section, and only if kept. Provenance goes in `docs/upstream-prs.md` and the commit message. No commit or push without a request.
