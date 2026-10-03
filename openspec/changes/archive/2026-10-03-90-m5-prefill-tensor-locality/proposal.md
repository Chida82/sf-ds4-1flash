# Proposal

## Why

The M5 Neural Accelerators are already active in V4.1 prefill, but `kernel_mul_mm_id_mpp_packed` still stages custom-dequantized weights through threadgroup memory and uses a direct work-list/grid traversal. After `80`, improve data delivery to the existing TensorOps kernels rather than replacing the model or counting Apple's advertised acceleration twice.

## What Changes

- Start from the resolved `60`/`70`/`80` baseline and measure the routed-FFN section on the actual prompt shapes.
- Evaluate an expert-local output-tile traversal that changes ownership order, not each tile's math.
- Independently try feeding the same dequantized half values through cooperative-tensor inputs, retaining the existing matmul descriptor and K accumulation order.
- Only if register headroom permits, evaluate paired gate/up MPP with two independent accumulators and the exact current activation/rounding epilogue.
- Reject a stage independently on bit drift, no measurable benefit, or regressions. Do not retain scaffolding for a hypothetical later stage.

## Capabilities

### New Capabilities
None. Output and configuration behavior are unchanged (`skip_specs: true`).

### Modified Capabilities
None. Reuse the existing harness and the sections mode introduced by `60`.

## Impact

- `metal/moe.metal`, its dispatch/resource bindings in `ds4_metal.m`, existing MoE/Metal tests, and performance documentation.
- No GGUF conversion, activation/KV quantization, SDK installation, model scheduling change, or new general-purpose GEMM layer.
- Respect `60`'s measured #864 half-LUT outcome; do not reintroduce its rejected split-MPP accumulation. #947 is not a reason to disable the already-used TensorOps path.
- Locality and register-pressure claims are hypotheses until on-device measurement; SDK availability is already established in `docs/MacM5.md`.
