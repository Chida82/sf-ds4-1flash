// GLM-5.3 Flash vision operations not covered by the shared BF16 matmuls.

struct glm53_vision_rows_args {
    uint width;
    uint rows;
    float eps;
};

struct glm53_vision_qkv_args {
    uint rows;
    uint grid_h;
    uint grid_w;
    float eps;
};

struct glm53_vision_attention_args {
    uint rows;
    float scale;
};

struct glm53_vision_scatter_args {
    uint dst_row;
    uint image_row;
    uint rows;
    uint total_rows;
    uint width;
    uint hc;
};

kernel void kernel_glm53_vision_add_bias(
        constant glm53_vision_rows_args &args,
        device float                    *x,
        device const ushort             *bias,
        uint2 gid [[thread_position_in_grid]]) {
    if (gid.x >= args.width || gid.y >= args.rows) return;
    x[(ulong)gid.y * args.width + gid.x] += glm53_bf16_to_f32(bias[gid.x]);
}

kernel void kernel_glm53_vision_rms_bf16(
        constant glm53_vision_rows_args &args,
        device const float              *x,
        device const ushort             *weight,
        device float                    *out,
        threadgroup float               *partial,
        uint row [[threadgroup_position_in_grid]],
        uint tid [[thread_index_in_threadgroup]],
        ushort lane [[thread_index_in_simdgroup]],
        ushort sg [[simdgroup_index_in_threadgroup]],
        ushort nsg [[simdgroups_per_threadgroup]]) {
    if (row >= args.rows) return;
    device const float *xr = x + (ulong)row * args.width;
    device float *yr = out + (ulong)row * args.width;
    float sum = 0.0f;
    for (uint d = tid; d < args.width; d += 256u) sum = fma(xr[d], xr[d], sum);
    sum = simd_sum(sum);
    if (lane == 0u) partial[sg] = sum;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (sg == 0u) {
        float v = lane < nsg ? partial[lane] : 0.0f;
        v = simd_sum(v);
        if (lane == 0u) partial[0] = rsqrt(v / (float)args.width + args.eps);
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    const float inv = partial[0];
    for (uint d = tid; d < args.width; d += 256u) {
        yr[d] = xr[d] * inv * glm53_bf16_to_f32(weight[d]);
    }
}

/* A simdgroup owns one query/head and keeps its 64 output values in registers.
 * This is quadratic in compute, as the model graph requires, but linear in
 * memory and never materializes the attention matrix. */
kernel void kernel_glm53_vision_attention(
        constant glm53_vision_attention_args &args,
        device const float                   *q,
        device const float                   *k,
        device const float                   *v,
        device float                         *out,
        uint2 group [[threadgroup_position_in_grid]],
        ushort lane [[thread_index_in_simdgroup]]) {
    const uint row = group.x;
    const uint head = group.y;
    if (row >= args.rows || head >= 16u) return;
    const ulong base = (ulong)row * 1024u + (ulong)head * 64u;
    const float q0 = q[base + lane];
    const float q1 = q[base + lane + 32u];
    float acc0 = 0.0f, acc1 = 0.0f;
    float max_score = -INFINITY;
    float denom = 0.0f;
    for (uint key_row = 0; key_row < args.rows; key_row++) {
        const ulong kb = (ulong)key_row * 1024u + (ulong)head * 64u;
        float score = simd_sum(q0 * k[kb + lane] + q1 * k[kb + lane + 32u]);
        score *= args.scale;
        const float next_max = max(max_score, score);
        const float old_scale = max_score == -INFINITY ? 0.0f : exp(max_score - next_max);
        const float new_scale = exp(score - next_max);
        denom = denom * old_scale + new_scale;
        acc0 = acc0 * old_scale + new_scale * v[kb + lane];
        acc1 = acc1 * old_scale + new_scale * v[kb + lane + 32u];
        max_score = next_max;
    }
    out[base + lane] = acc0 / denom;
    out[base + lane + 32u] = acc1 / denom;
}

kernel void kernel_glm53_vision_bias_residual(
        constant glm53_vision_rows_args &args,
        device float                    *x,
        device const ushort             *bias,
        device const float              *residual,
        uint2 gid [[thread_position_in_grid]]) {
    if (gid.x >= args.width || gid.y >= args.rows) return;
    const ulong off = (ulong)gid.y * args.width + gid.x;
    x[off] += glm53_bf16_to_f32(bias[gid.x]) + residual[off];
}

