# Design

## Context

`ds4_gpu_tp_init` starts `ds4_gpu_tp_keepalive_thread`: a loop that commits one `kernel_dsv4_tp_keepalive` dispatch (one threadgroup of 256 threads, 1.2M ALU iterations) on its own queue and waits for it, sleeping 200 us while `g_tp_keepalive_paused` is set. Upstream measured it as a decode win on the TP pair. On a single box it never starts. The decode critical path per layer (`132`, `210`): router batch end -> about 20 us to see the ids -> about 10 us of CPU work -> about 100-115 us from commit to the expert pass's GPU start; layers with a miss add about 1 ms of reads. `131` noted that a thread that does not sleep "also resumes on a warm core".

## Goals / Non-Goals

**Goals:** a higher sustained GPU and CPU clock across the gaps of a streaming decode token; no cost outside decode; output bitwise; one switch per step.

**Non-Goals:** keep-alive during prefill sweeps (the GPU is busy there), the TP keep-alive's tuning, Argodrive's wait-only mode 1 (it gained less than whole-token mode 2 in their measurements).

## Decisions

### D1. Gate

Before any code: a harness A/B cannot see a clock directly, so the gate reads the GPU active frequency the harness already records per run (`--min-freq-of-median` uses it) and `DS4_METAL_CB_TIMES` GPU spans of the expert-pass batches. Two short decode runs on the S1 prototype with and without the switch: if the expert pass's GPU span on all-hit layers and the median frequency do not move, close the change.

### D2. GPU keep-alive (S1)

Factor the thread start of `ds4_gpu_tp_init` into a helper that both TP and the single-box path call; the single box starts it lazily at the first decode token with `g_tp_keepalive_paused = 1`, unpauses at the token's start and pauses at its end (after the logits readback). TP keeps starting it as today. The thread is joined at cleanup.

### D3. CPU keep-alive (S2)

A thread created at the first decode token at `QOS_CLASS_USER_INTERACTIVE` that spins with `__builtin_arm_yield` while a flag is set and sleeps on a condition variable otherwise; the same token scope sets the flag. Measured on top of S1 as its own step.

### D4. Evidence

Each step: decode-switch bitwise test; harness `decode,append` with the long and cold guards, `--bitwise`; the per-step keep rule. Power is reported (Argodrive: about 4.5 W CPU) but not gated.

## Risks / Trade-offs

- Contention: the keep-alive queue competes with the decode queue -> one threadgroup, ALU-only, and the harness decides; pause outside decode.
- Power: more watts during decode -> reported; the switch turns it off.

## Migration Plan

Branch `perf/220-decode-keepalive`. Switches join `AGENTS.md`. Provenance in `docs/upstream-prs.md` and commit messages. No commit or push without a request.
