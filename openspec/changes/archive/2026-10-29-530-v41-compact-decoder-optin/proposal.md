# Proposal

> **Status 2026-10-29: no-go after the go/no-go, never implemented.** Under SSD streaming each decoder layer's expert read is paid whatever the row count, so the ceiling on time to first token is 0 on `cold-2500` and `cold-5000` and about 3% on `cold-10000`; the typical mix gains well under 1%. That does not justify the one exception to identical output. Re-evaluate without SSD streaming (main weights resident on a 256 GB or larger machine, or two boxes with TP/RDMA): there the prefill is compute-bound and the read-free ceiling, 19 / 9 / 23% of ttft on the same shapes, is the relevant one (`speed-bench/perf-record.md`, "Approximate decoder prefill ceiling").

## Why

V4.1's decoder layers (20-39) take their compressed KV from layer 20's input. In prefill they are only needed for two things:
- each layer's sliding-window (SWA) ring for the last 128 positions;
- the last token's logits.

This child computes both exactly.
- **Wide sweeps.** `ds41_graph_prefill_sweep` runs a shrinking suffix of `1 + (39 - il) * 127` rows per decoder layer, 2541 at layer 20, plus 127-128 warm rows.
- **Batched sweeps of 2048 rows or fewer.** Every row goes through every decoder layer.

DeepInfer's YOCO prefill truncation (`DEEPINFER_YOCO_PREFILL_TRUNCATION_MODE=compact`, off by default) trades that exactness for time. The layers after the first ratio-1 layer process only the last K rows of the prompt, with attention truncated to that segment: the query at i sees keys from `max(s, i - 127)` to i. Its notes call this "nearly halving total prefill computation" on GPU (`doc/inference_deployment_qa.md`). The result is approximate.

A rough estimate on `speed-bench/perf-record.md`'s decomposition puts the gain at 10-25% of time to first token for cold prompts of 2K-10K tokens. The estimate is not measured:
- `cold-10000` spends about 4 s in the decoder suffix and 10.3 s in its final 1808-row sweep, out of 41.4 s;
- a 2048-row sweep spends 9.1-10.2 s in stages.

Expert reads bound part of it: 128 rows already touch about 85% of a layer's experts, and a layer's experts must be read whatever the row count.

The project's rule forbids this: "no prefill schedule or kernel that alters bits". This change is the owner-approved exception to that rule. It is valid only behind an opt-in flag that is off by default. With the flag off, nothing changes, bitwise.

## What Changes

- **Go/no-go first, without code.**
  - Today's binary runs `cold-2500`, `cold-5000` and `cold-10000` under `DS4_METAL_V41_STAGE_PROFILE=1` and `DS4_METAL_GRAPH_PREFILL_PROFILE=1`.
  - From the per-layer stage and read times, it computes the ceiling of the saving: per decoder layer and sweep, today's `max(read, compute)` against `max(read, compute * K / rows)`.
  - If the ceiling on time to first token is under the harness's resolution, the change stops there and is archived as history.
- **An opt-in flag, `--approx-decoder-prefill`,** in the CLI, the server and the bench. It is off by default, with K = 128, DeepInfer's window. With it, in every batched V4.1 prefill sweep:
  - **layers 0-20 run as today.** Layer 20 still publishes the decoder's compressed KV for every row, so that KV stays exact;
  - **layers 21-39 process only the sweep's last K rows,** with their SWA attention starting at the segment, and no warm rows.

  Decode, token-major tails and appends under the 1024-token batch threshold are unchanged.
- **Flag off, nothing changes.** The default path is the same code path with the same arguments, proven three ways:
  - `make test` and the model-backed tests pass bitwise;
  - `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` passes;
  - a harness A/B with the flag off is bitwise and neutral.
- **Persistence refused.** A session prefilled with the flag holds approximate SWA state. It refuses payload saves and loads and snapshots, as a steered session does (`ds41_steering_refuses_persistence`). The server with the flag does not open `--kv-disk-dir`, and says so. Approximate state never reaches disk, and never reaches a session without the flag.
- **Steering refused.** The flag and any active steering refuse each other at engine open. Steering and quality measurements always run with the flag off.
- **Harness tool step.** `ab_bench.py` gets a mode that lets B's tokens differ. It reports the first differing position instead of failing the run, because the flag changes output by design.
- **Quality, measured and reported.**
  - Flag on against flag off: first-token agreement and first divergence on the parity prompts;
  - the eval `core` suite;
  - a long-context recall check.

  The owner then knows what the flag costs before enabling it.
- **The exception is recorded where readers look:**
  - the `AGENTS.md` Identity table;
  - `README.md` (the flag, the measured gain and the measured quality cost);
  - the `prefill-schedule` spec.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `prefill-schedule`: an opt-in approximate decoder prefill. It is:
  - off by default and bitwise when off;
  - refused with steering, and refusing persistence;
  - documented as the one exception to identical output.

## Impact

- **`ds4.c`:**
  - `ds41_graph_prefill_sweep`, the decoder part of the sweep;
  - `ds41_attention_batch`, a segment start for the ring copy that today uses `min(start, 127)`;
  - the persistence refusal next to steering's;
  - engine options.
- **Frontends and env.**
  - `ds4.h`, `ds4_cli.c`, `ds4_server.c`, `ds4_bench.c`: the flag;
  - `ds4_env.def` only if a switch is added.
- **No Metal kernel change expected.** The attention kernels derive the window start from the first raw position passed in. The design names the evidence and the task that confirms it.
- **Harness and docs.** `speed-bench/ab_bench.py` (the approximate mode), `speed-bench/perf-record.md`, `README.md`, `AGENTS.md`.
- **Output.** None with the flag off. With it on, prompt-dependent drift from the first generated token on, which the quality task measures.
