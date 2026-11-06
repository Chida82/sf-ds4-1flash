# Design

## Context

- `ds4_gpu_model_resource_options` (`ds4_metal.m`) returns untracked options
  when `DS4_METAL_MODEL_UNTRACKED` is set (presence only). It is used by the
  two places that wrap the model mmap without copying
  (`newBufferWithBytesNoCopy`): the model views and the exact owned, transient
  and cached views. The 9.37 GiB of static weights live in those views.
- The narrow copies are allocated in `ds4.c` through `ds4_gpu_tensor_alloc`,
  tracked whatever the environment says.
- The expert cache slabs, the explicit prefill buffers and the address tables
  are allocated with their own options in `ds4_metal.m`, always tracked.
- Upstream `b3f5018`: `g_model_untracked_default` with a setter called after
  `config_validate_model`, opt-out `DS4_METAL_MODEL_TRACKED` through
  `ds4_gpu_v41_on`, and `ds4_gpu_tensor_alloc_weights` for the copies. This
  child opens only V4.1 (`config_validate_model` refuses anything else), so the
  per-model setter and its ordering fix are not needed.

## Goals / Non-Goals

**Goals:**
- Upstream's default and switch name, bitwise output.
- One A/B to decide whether the default stays.

**Non-Goals:**
- Untracking any buffer the GPU writes.
- Upstream's per-model policy machinery.

## Decisions

- **Default untracked, upstream's opt-out name.** `DS4_METAL_MODEL_TRACKED=1`
  restores tracking; `DS4_METAL_MODEL_UNTRACKED` goes, since it would be the
  default. *Alternative:* keep the opt-in and only measure it. That leaves the
  child unlike upstream for no reason if the measure is neutral.
- **Copies through a weights allocation entry.** A small
  `ds4_gpu_tensor_alloc_weights` beside `ds4_gpu_tensor_alloc`, used only by
  the narrow copies, as upstream does.
- **Bitwise check in two processes.** The views are created at engine open,
  after which the switch is not read again. A CLI run with
  `--dump-frontier-logits-dir` through the bench (or `DS4_GLM_LOGIT_DUMP`) in
  two processes compares the bits. Reopening in one process is limited to
  32 GiB of cache (AGENTS.md), so separate processes are simpler.
- **Measurement.** `ab_bench.py --kinds all --bitwise` with
  `--b-env DS4_METAL_MODEL_TRACKED=1` on one tree, so A is the new default and
  B restores tracking. Keep the default if no metric favours tracking.

## Risks / Trade-offs

- **[A future writer]** A later change could pass a weight view as a kernel
  output and race without tracking. -> The requirement says untracked buffers
  are never outputs; the copies' fill stays CPU-only before first use.
- **[Below resolution]** Likely, in streaming. -> A neutral A/B still keeps the
  default, matching upstream, since the output is identical; a loss reverts it.
