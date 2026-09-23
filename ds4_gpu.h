#ifndef DS4_GPU_H
#define DS4_GPU_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* =========================================================================
 * GPU Tensor and Command Lifetime.
 * =========================================================================
 *
 * Opaque device tensor used by the DS4-specific GPU executor.
 *
 * The public GPU API is tensor-resident: activations, KV state, and scratch
 * buffers stay device-owned across the whole prefill/decode command sequence.
 */
#ifndef DS4_GPU_TENSOR_DEFINED
#define DS4_GPU_TENSOR_DEFINED
typedef struct ds4_gpu_tensor ds4_gpu_tensor;
#endif

#ifndef DS4_GPU_ATTENTION_DECODE_ROW_DEFINED
#define DS4_GPU_ATTENTION_DECODE_ROW_DEFINED
#define DS4_GPU_ATTENTION_DECODE_BATCH_MAX 32u
#endif

int ds4_gpu_init(void);
void ds4_gpu_cleanup(void);

ds4_gpu_tensor *ds4_gpu_tensor_alloc(uint64_t bytes);
ds4_gpu_tensor *ds4_gpu_tensor_alloc_managed(uint64_t bytes);
ds4_gpu_tensor *ds4_gpu_tensor_view(const ds4_gpu_tensor *base, uint64_t offset, uint64_t bytes);
void ds4_gpu_tensor_free(ds4_gpu_tensor *tensor);
uint64_t ds4_gpu_tensor_bytes(const ds4_gpu_tensor *tensor);
void *ds4_gpu_tensor_contents(ds4_gpu_tensor *tensor);
int ds4_gpu_tensor_fill_f32(ds4_gpu_tensor *tensor, float value, uint64_t count);
int ds4_gpu_tensor_write(ds4_gpu_tensor *tensor, uint64_t offset, const void *data, uint64_t bytes);
int ds4_gpu_tensor_read(const ds4_gpu_tensor *tensor, uint64_t offset, void *data, uint64_t bytes);
int ds4_gpu_tensor_copy(ds4_gpu_tensor *dst, uint64_t dst_offset,
                          const ds4_gpu_tensor *src, uint64_t src_offset,
                          uint64_t bytes);
int ds4_gpu_tensor_copy_f32_to_f16(ds4_gpu_tensor *dst, uint64_t dst_offset,
                                   const ds4_gpu_tensor *src, uint64_t src_offset,
                                   uint64_t count);
int ds4_gpu_pack_slot_rows_f32_tensor(
        ds4_gpu_tensor       *out,
        const ds4_gpu_tensor *slots,
        uint32_t                n_rows,
        uint32_t                width,
        uint32_t                n_slots,
        uint32_t                slot_cap);

int ds4_gpu_begin_commands(void);
int ds4_gpu_flush_commands(void);
int ds4_gpu_commands_active(void);
#include "ds4_deepseek41_gpu.h"
int ds4_gpu_parallel_ffn_finish(void);
void ds4_gpu_parallel_ffn_abort(void);
int ds4_gpu_parallel_ffn_start(
        ds4_gpu_tensor       *gate,
        ds4_gpu_tensor       *up,
        ds4_gpu_tensor       *mid,
        ds4_gpu_tensor       *shared_out,
        const void           *model_map,
        uint64_t              model_size,
        uint64_t              gate_offset,
        uint64_t              up_offset,
        uint64_t              down_offset,
        uint32_t              model_dim,
        uint32_t              shared_dim,
        const ds4_gpu_tensor *x,
        float                 clamp);
int ds4_gpu_parallel_ffn_start_sliced(
        ds4_gpu_tensor       *gate,
        ds4_gpu_tensor       *up,
        ds4_gpu_tensor       *mid,
        ds4_gpu_tensor       *shared_out,
        const void           *model_map,
        uint64_t              model_size,
        uint64_t              gate_offset,
        uint64_t              up_offset,
        uint64_t              down_offset,
        uint32_t              model_dim,
        uint32_t              shared_dim,
        uint32_t              shared_lane_offset,
        uint32_t              shared_lane_count,
        const ds4_gpu_tensor *x,
        float                 clamp);

/* GPU-decided shared-expert lane split for two-rank TP decode: the split
 * kernels read the selected expert ids and take complementary lane ranges
 * sized to balance the bytes each rank streams (shift_q16 = routed expert
 * bytes / (2 * shared expert bytes) in Q16; 0 reproduces static halves). */
int ds4_gpu_parallel_ffn_start_split(
        ds4_gpu_tensor       *gate,
        ds4_gpu_tensor       *up,
        ds4_gpu_tensor       *mid,
        ds4_gpu_tensor       *shared_out,
        const void           *model_map,
        uint64_t              model_size,
        uint64_t              gate_offset,
        uint64_t              up_offset,
        uint64_t              down_offset,
        uint32_t              model_dim,
        uint32_t              shared_dim,
        const ds4_gpu_tensor *x,
        float                 clamp,
        const ds4_gpu_tensor *selected,
        uint32_t              tp_rank,
        uint32_t              tp_world,
        uint32_t              n_expert,
        uint32_t              n_expert_used,
        uint32_t              shift_q16);

/* out = a + b into this rank's TP slab slot for (layer, gate), publishing the
 * gate's checked flag from the same kernel; falls back to ds4_gpu_add_tensor
 * when the fold does not apply.  Call right before ds4_gpu_tp_gate_encode. */
int ds4_gpu_add_tensor_tp_flag(
        ds4_gpu_tensor       *out,
        const ds4_gpu_tensor *a,
        const ds4_gpu_tensor *b,
        uint32_t              n,
        uint32_t              layer,
        uint32_t              gate);

/* Register that the next TP partial producer for (layer, gate) may publish
 * the gate's checked flag itself (taken by the attention output K-slice
 * matvec when its output is that slot; otherwise ignored). */
void ds4_gpu_tp_flag_fold_request(uint32_t layer, uint32_t gate);

/* Deferred kv norm task: call before ds4_gpu_dsv4_qkv_rms_norm_kv_rope_fp8_store_tensor
 * to run only its q task now and fold the kv task into the KV staging
 * kernel of the same layer; flush runs it standalone if nothing consumed it. */
void ds4_gpu_dsv4_qkv_norm_defer_kv_next(void);
int ds4_gpu_kv_norm_task_flush(void);
int ds4_gpu_kv_norm_task_begin_concurrent(void);
void ds4_gpu_kv_norm_task_end_concurrent(void);
int ds4_gpu_signal_selected_readback_ready(uint64_t *event_value);
int ds4_gpu_commit_and_wait_selected_readback(uint64_t event_value, const char *label);
int ds4_gpu_wait_selected_readback_ready(uint64_t event_value, const char *label);
int ds4_gpu_end_commands(void);
int ds4_gpu_synchronize(void);

int ds4_gpu_set_model_map(const void *model_map, uint64_t model_size);
int ds4_gpu_set_model_fd(int fd);
/* Two-rank expert-only artifacts; never build or cache the unowned half.
 * file_size includes any disk-only tail outside the model mapping. */
int ds4_gpu_set_model_map_range(const void *model_map, uint64_t model_size, uint64_t map_offset, uint64_t map_size, uint64_t max_tensor_bytes);
/* Add a secondary GGUF mapping without replacing the primary model mapping. */
int ds4_gpu_set_model_map_spans(const void *model_map, uint64_t model_size, const uint64_t *offsets, const uint64_t *sizes, uint32_t count, uint64_t max_tensor_bytes);

/* Model-file ranges assigned to CUDA devices by the multi-GPU placement
 * planner. Metal keeps these declarations for the shared engine interface. */
#ifndef DS4_MAX_GPUS
#define DS4_MAX_GPUS 16
#endif

int ds4_gpu_pro_q4_expert_table_auto_available(void);
void ds4_gpu_set_quality(bool quality);
void ds4_gpu_set_ssd_streaming(bool enabled);
int ds4_gpu_device_is_pre_m5_apple_silicon(void);
int ds4_gpu_device_is_m5_apple_silicon(void);
int ds4_gpu_set_decode_pipeline_fast_lookup(int enabled);
/* Strict test oracle for the fixed decode mul_mv pipeline lookup cache. */
int ds4_gpu_test_decode_pipeline_fast_lookup(void);
/* Strict test oracle for the extended decode mul_mv_ext (nsg + nxpsg) cache. */
int ds4_gpu_test_decode_pipeline_fast_lookup_ext(void);
/* Strict test oracle for the generated resident-prefill MXFP4 half LUT. */
int ds4_gpu_test_mxfp4_down_half_lut(uint16_t *legacy_bits,
                                     uint16_t *lut_bits);
enum {
    DS4_GPU_TEST_MXFP4_PAIR_TAIL_CULL = 1u << 0,
    DS4_GPU_TEST_MXFP4_PAIR_COMPACT_TILE = 1u << 1,
    DS4_GPU_TEST_MXFP4_MAP_SCATTER = 1u << 2,
    DS4_GPU_TEST_MXFP4_DOWN_TAIL_CULL = 1u << 3,
    DS4_GPU_TEST_MXFP4_DOWN_HALF_LUT = 1u << 4,
    DS4_GPU_TEST_OUTPUT_HC_WEIGHTS4 = 1u << 5,
    DS4_GPU_TEST_HC_RMS_SCALE_PROJ = 1u << 6,
};
void ds4_gpu_test_set_flags(uint32_t flags);
void ds4_gpu_release_zero_prefix_prefill_mask_cache(void);
void ds4_gpu_set_streaming_expert_cache_budget(uint32_t experts);
void ds4_gpu_set_streaming_expert_cache_expert_bytes(uint64_t bytes);
/* One row of a Qwen3.8 decode batch for the attention rows kernels: the
 * session's caches for the layer, its rope positions, its token position and
 * whether it attends through the block selection or densely. */
#define DS4_GPU_QWEN4_ATTN_ROW_BYTES 64u   /* one staged table entry */
/* One session of a decode batch for the GDN rows kernels: its state and
 * history, optional snapshots of both after its first token, its first row
 * and its row count (one or two). */
#define DS4_GPU_QWEN4_GDN_ROW_BYTES 48u
uint64_t ds4_gpu_recommended_working_set_size(void);
uint32_t ds4_gpu_stream_expert_cache_configured_count(void);
uint32_t ds4_gpu_stream_expert_cache_current_count(void);
typedef struct ds4_gpu_stream_expert_table {
    const void *model_map;
    uint64_t    model_size;
    uint32_t    layer;
    uint32_t    n_total_expert;
    uint64_t    gate_offset;
    uint64_t    up_offset;
    uint64_t    down_offset;
    uint64_t    gate_expert_bytes;
    uint64_t    down_expert_bytes;
} ds4_gpu_stream_expert_table;
/* Reset only the prompt-local eviction heuristic.  The resident SSD expert
 * cache itself is intentionally kept warm across sessions. */
void ds4_gpu_stream_expert_cache_reset_route_hotness(void);
uint32_t ds4_gpu_stream_expert_cache_budget_for_expert_size(
        uint64_t gate_expert_bytes,
        uint64_t down_expert_bytes);
int ds4_gpu_stream_expert_cache_seed_selected(
        const ds4_gpu_stream_expert_table *table,
        const int32_t                     *selected_ids,
        uint32_t                           n_selected);
int ds4_gpu_stream_expert_cache_begin_selected_load(
        const ds4_gpu_stream_expert_table *table,
        const int32_t                     *selected_ids,
        uint32_t                           n_selected);
/* The async selected-load worker registers itself so Metal cache paths never
 * wait on command buffers from that thread (they fail the load instead and
 * the caller retries synchronously). */
void ds4_gpu_stream_expert_cache_note_service_thread(void);
int ds4_gpu_stream_expert_cache_seed_experts(
        const ds4_gpu_stream_expert_table *table,
        const int32_t                     *expert_ids,
        const uint32_t                    *expert_priorities,
        uint32_t                           n_experts);
/* Seed from mapped weights with blits appended to the active command buffer. */
int ds4_gpu_stream_expert_cache_seed_experts_gpu_copy(
        const ds4_gpu_stream_expert_table *table,
        const int32_t                     *expert_ids,
        const uint32_t                    *expert_priorities,
        uint32_t                           n_experts);
void ds4_gpu_print_memory_report(const char *label);

#include "ds4_gpu_tp.h"
/* Skip the whole-file model residency set (TP sharding: only the
 * owned ranges are warmed; the rest must never be paged in). Call before
 * the model is mapped. */
void ds4_gpu_model_residency_skip(int skip);
/* Submit one trivial command buffer (first-submission costs paid at load). */
int ds4_gpu_warm_command_queue(void);

/* Tensor-parallel sliced projections (Metal decode path only).
 *
 * ds4_gpu_matmul_q8_0_kslice_tensor computes a k-range partial matvec:
 * out[out_dim] = W[:, k_off : k_off + k_cnt] @ x[x_elem_off : +k_cnt] where
 * W rows span full_in_dim quantized Q8_0 elements.  k offsets/counts must be
 * multiples of 32 (Q8_0 block).  Partial results from both ranks sum to the
 * full projection.
 *
 * ds4_gpu_attention_output_q8_tp_tensor is the group-sliced attention output
 * pair: low projection for groups [group0, group0+group_cnt) plus the
 * matching k-slice of the expand projection, producing this rank's partial
 * attention block output (n_tokens == 1 only). */
int ds4_gpu_matmul_q8_0_kslice_tensor(
        ds4_gpu_tensor       *out,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_offset,
        uint64_t                full_in_dim,
        uint64_t                k_off,
        uint64_t                k_cnt,
        uint64_t                out_dim,
        const ds4_gpu_tensor *x,
        uint64_t                x_elem_off);
/* CUDA input rows contain only the owned contiguous K slice. Metal input
 * rows span full_in_dim and the kernel reads the slice at k_off within them.
 * Both backends produce full-width output rows. */
int ds4_gpu_matmul_quant_kslice_tensor(
        ds4_gpu_tensor       *out,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_offset,
        uint32_t                weight_type,
        uint64_t                full_in_dim,
        uint64_t                k_off,
        uint64_t                k_cnt,
        uint64_t                out_dim,
        const ds4_gpu_tensor *x,
        uint64_t                x_elem_off);
int ds4_gpu_attention_output_q8_tp_tensor(
        ds4_gpu_tensor       *out,
        ds4_gpu_tensor       *low,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                out_a_offset,
        uint64_t                out_b_offset,
        uint64_t                group_dim,
        uint64_t                rank,
        uint32_t                n_groups_total,
        uint32_t                group0,
        uint32_t                group_cnt,
        uint64_t                out_dim,
        const ds4_gpu_tensor *heads);

/* =========================================================================
 * Embeddings and Indexer Helpers.
 * =========================================================================
 *
 * These kernels seed HC state from token embeddings and implement the ratio-4
 * compressed-attention indexer that chooses visible compressed rows.
 */

int ds4_gpu_embed_token_hc_tensor(
        ds4_gpu_tensor *out_hc,
        const void       *model_map,
        uint64_t          model_size,
        uint64_t          weight_offset,
        uint32_t          n_vocab,
        uint32_t          token,
        uint32_t          n_embd,
        uint32_t          n_hc);

int ds4_gpu_embed_tokens_hc_tensor(
        ds4_gpu_tensor       *out_hc,
        const ds4_gpu_tensor *tokens,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_offset,
        uint32_t                n_vocab,
        uint32_t                n_tokens,
        uint32_t                n_embd,
        uint32_t                n_hc);

int ds4_gpu_indexer_score_one_tensor(
        ds4_gpu_tensor       *scores,
        const ds4_gpu_tensor *q,
        const ds4_gpu_tensor *weights,
        const ds4_gpu_tensor *index_comp,
        uint32_t                n_comp,
        uint32_t                n_head,
        uint32_t                head_dim,
        float                   scale);

int ds4_gpu_indexer_scores_prefill_tensor(
        ds4_gpu_tensor       *scores,
        const ds4_gpu_tensor *q,
        const ds4_gpu_tensor *weights,
        const ds4_gpu_tensor *index_comp,
        uint32_t                n_comp,
        uint32_t                n_tokens,
        uint32_t                n_head,
        uint32_t                head_dim,
        uint32_t                ratio,
        float                   scale);

int ds4_gpu_indexer_scores_decode_batch_tensor(
        ds4_gpu_tensor       *scores,
        const ds4_gpu_tensor *q,
        const ds4_gpu_tensor *weights,
        const ds4_gpu_tensor *index_comp,
        uint32_t                n_comp,
        uint32_t                n_tokens,
        uint32_t                pos0,
        uint32_t                n_head,
        uint32_t                head_dim,
        uint32_t                ratio,
        float                   scale);

int ds4_gpu_indexer_topk_tensor(
        ds4_gpu_tensor       *selected,
        const ds4_gpu_tensor *scores,
        uint32_t                n_comp,
        uint32_t                n_tokens,
        uint32_t                top_k);

/* GPU argmax over n_vocab F32 logits. Writes the winning index as int32 at
 * out_idx[0]. Tie-break: lower index wins (matches host sample_argmax). */

int ds4_gpu_dsv4_topk_mask_tensor(
        ds4_gpu_tensor       *mask,
        const ds4_gpu_tensor *topk,
        uint32_t                n_comp,
        uint32_t                n_tokens,
        uint32_t                top_k);

/* =========================================================================
 * Dense Projections, Norms, RoPE, and KV Rounding.
 * =========================================================================
 *
 * The graph uses these primitives for Q/KV projections, HC/output projections,
 * attention output projections, and DS4's tail-only RoPE.
 */

int ds4_gpu_matmul_q8_0_tensor(
        ds4_gpu_tensor       *out,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_offset,
        uint64_t                in_dim,
        uint64_t                out_dim,
        const ds4_gpu_tensor *x,
        uint64_t                n_tok);
/* Qwen projections preserve FP32 activations on both GPU backends. */

int ds4_gpu_matmul_q8_0_decode_mpp_tensor(
        ds4_gpu_tensor       *out,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_offset,
        uint64_t                in_dim,
        uint64_t                out_dim,
        const ds4_gpu_tensor *x,
        uint64_t                n_tok);

int ds4_gpu_matmul_quant_tensor(
        ds4_gpu_tensor       *out,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_offset,
        uint32_t                weight_type,
        uint64_t                in_dim,
        uint64_t                out_dim,
        const ds4_gpu_tensor *x,
        uint64_t                n_tok);

/* Optional fused GPU operations.
 *
 * These are acceleration hooks, not required backend primitives.  A backend
 * that does not provide the fused kernel must still define the symbol and
 * return 0.  Callers then use the portable sequence of required primitives.
 * Backends that return nonzero from a fused half-output operation must also
 * implement the matching half-input HC expansion helpers below.
 */
int ds4_gpu_matmul_q8_0_pair_tensor(
        ds4_gpu_tensor       *out0,
        ds4_gpu_tensor       *out1,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight0_offset,
        uint64_t                weight1_offset,
        uint64_t                in_dim,
        uint64_t                out0_dim,
        uint64_t                out1_dim,
        const ds4_gpu_tensor *x,
        uint64_t                n_tok);

/* Multi-row decode projections that preserve the one-row reduction order. */
int ds4_gpu_matmul_q8_0_decode_rows_exact_tensor(
        ds4_gpu_tensor       *out,
        const void           *model_map,
        uint64_t              model_size,
        uint64_t              weight_offset,
        uint64_t              in_dim,
        uint64_t              out_dim,
        const ds4_gpu_tensor *x,
        uint32_t              n_rows);


int ds4_gpu_shared_gate_up_swiglu_q8_0_tensor(
        ds4_gpu_tensor       *gate,
        ds4_gpu_tensor       *up,
        ds4_gpu_tensor       *mid,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                gate_offset,
        uint64_t                up_offset,
        uint64_t                in_dim,
        uint64_t                out_dim,
        const ds4_gpu_tensor *x,
        float                   clamp);

int ds4_gpu_router_shared_gate_up_q8_0_tensor(
        ds4_gpu_tensor       *router_logits,
        ds4_gpu_tensor       *gate,
        ds4_gpu_tensor       *up,
        ds4_gpu_tensor       *mid,
        const void           *model_map,
        uint64_t              model_size,
        uint64_t              router_weight_offset,
        uint64_t              gate_offset,
        uint64_t              up_offset,
        uint64_t              in_dim,
        uint64_t              router_out_dim,
        uint64_t              out_dim,
        const ds4_gpu_tensor *x,
        float                 clamp,
        bool                  router_only);
int ds4_gpu_router_project_select_fused_tensor(
        ds4_gpu_tensor       *router_logits,
        ds4_gpu_tensor       *probs,
        ds4_gpu_tensor       *selected,
        ds4_gpu_tensor       *weights,
        const void           *model_map,
        uint64_t              model_size,
        uint64_t              router_weight_offset,
        uint64_t              bias_offset,
        bool                  has_bias,
        const ds4_gpu_tensor *x);

int ds4_gpu_matmul_f16_tensor(
        ds4_gpu_tensor       *out,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_offset,
        uint64_t                in_dim,
        uint64_t                out_dim,
        const ds4_gpu_tensor *x,
        uint64_t                n_tok);

/* Exact multi-row form of the DeepSeek 4096x256 F16 router projection. */

int ds4_gpu_matmul_f16_pair_tensor(
        ds4_gpu_tensor       *out_a,
        ds4_gpu_tensor       *out_b,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_a_offset,
        uint64_t                weight_b_offset,
        uint64_t                in_dim,
        uint64_t                out_dim,
        const ds4_gpu_tensor *x,
        uint64_t                n_tok);

/* Optional Metal decode fusion. Returns 1 when the paired projection and
 * recurrent compressor-state store were encoded, 0 when the optimized path
 * is unavailable, and -1 on an attempted-path error. */
int ds4_gpu_matmul_f16_pair_compressor_store_tensor(
        ds4_gpu_tensor       *out_kv,
        ds4_gpu_tensor       *out_score,
        ds4_gpu_tensor       *state_kv,
        ds4_gpu_tensor       *state_score,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_kv_offset,
        uint64_t                weight_score_offset,
        uint64_t                ape_offset,
        uint32_t                ape_type,
        uint64_t                in_dim,
        uint32_t                width,
        const ds4_gpu_tensor *x,
        uint32_t                ratio,
        uint32_t                pos);

int ds4_gpu_matmul_f16_quad_compressor_store_tensor(
        ds4_gpu_tensor       *out0_kv,
        ds4_gpu_tensor       *out0_score,
        ds4_gpu_tensor       *out1_kv,
        ds4_gpu_tensor       *out1_score,
        ds4_gpu_tensor       *state0_kv,
        ds4_gpu_tensor       *state0_score,
        ds4_gpu_tensor       *state1_kv,
        ds4_gpu_tensor       *state1_score,
        const void           *model_map,
        uint64_t              model_size,
        uint64_t              weight0_kv_offset,
        uint64_t              weight0_score_offset,
        uint64_t              weight1_kv_offset,
        uint64_t              weight1_score_offset,
        uint64_t              ape0_offset,
        uint32_t              ape0_type,
        uint64_t              ape1_offset,
        uint32_t              ape1_type,
        uint64_t              in_dim,
        uint32_t              width0,
        uint32_t              width1,
        const ds4_gpu_tensor *x,
        uint32_t              ratio,
        uint32_t              pos);

/* Decode-only M5 fusion: emit-path compressor row finalize (norm + rope +
 * fp8/commit + indexer qat) in one dispatch.  Bit-exact vs the separate
 * dispatches.  Returns 1 when fused, 0 to fall back. */
int ds4_gpu_dsv4_comp_row_finalize_tensor(
        ds4_gpu_tensor       *attn_stage,
        ds4_gpu_tensor       *attn_cache,
        uint32_t              attn_comp_row,
        uint64_t              attn_norm_offset,
        ds4_gpu_tensor       *index_cache,
        uint32_t              index_comp_row,
        uint64_t              index_norm_offset,
        ds4_gpu_tensor       *attn_state_kv,
        ds4_gpu_tensor       *attn_state_score,
        ds4_gpu_tensor       *index_state_kv,
        ds4_gpu_tensor       *index_state_score,
        const void           *model_map,
        uint64_t              model_size,
        uint32_t              pos,
        uint32_t              n_rot,
        uint32_t              n_ctx_orig,
        float                 freq_base,
        float                 freq_scale,
        float                 ext_factor,
        float                 attn_factor,
        float                 beta_fast,
        float                 beta_slow,
        float                 rms_eps);

/* Decode-only M5 fusion: q_a/kv Q8 pair projection + F16 quad compressor
 * projection/store in one dispatch.  Bit-exact vs the separate dispatches.
 * Returns 1 when fused, 0 to fall back, -1 on error. */

int ds4_gpu_matmul_f32_tensor(
        ds4_gpu_tensor       *out,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_offset,
        uint64_t                in_dim,
        uint64_t                out_dim,
        const ds4_gpu_tensor *x,
        uint64_t                n_tok);

int ds4_gpu_repeat_hc_tensor(
        ds4_gpu_tensor       *out,
        const ds4_gpu_tensor *row,
        uint32_t                n_embd,
        uint32_t                n_hc);

int ds4_gpu_rms_norm_plain_tensor(
        ds4_gpu_tensor       *out,
        const ds4_gpu_tensor *x,
        uint32_t                n,
        float                   eps);

int ds4_gpu_rms_norm_plain_rows_tensor(
        ds4_gpu_tensor       *out,
        const ds4_gpu_tensor *x,
        uint32_t                n,
        uint32_t                rows,
        float                   eps);

int ds4_gpu_rms_norm_weight_tensor(
        ds4_gpu_tensor       *out,
        const ds4_gpu_tensor *x,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_offset,
        uint32_t                n,
        float                   eps);

int ds4_gpu_rms_norm_weight_rows_tensor(
        ds4_gpu_tensor       *out,
        const ds4_gpu_tensor *x,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_offset,
        uint32_t                n,
        uint32_t                rows,
        float                   eps);

int ds4_gpu_dsv4_qkv_rms_norm_rows_tensor(
        ds4_gpu_tensor       *q_out,
        const ds4_gpu_tensor *q,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                q_weight_offset,
        uint32_t                q_n,
        ds4_gpu_tensor       *kv_out,
        const ds4_gpu_tensor *kv,
        uint64_t                kv_weight_offset,
        uint32_t                kv_n,
        uint32_t                rows,
        float                   eps);

int ds4_gpu_dsv4_qkv_rms_norm_kv_rope_fp8_store_tensor(
        ds4_gpu_tensor       *q_out,
        const ds4_gpu_tensor *q,
        const void           *model_map,
        uint64_t              model_size,
        uint64_t              q_weight_offset,
        uint32_t              q_n,
        ds4_gpu_tensor       *kv_out,
        const ds4_gpu_tensor *kv,
        uint64_t              kv_weight_offset,
        uint32_t              kv_n,
        ds4_gpu_tensor       *raw_cache,
        uint64_t              raw_cap,
        uint32_t              raw_row,
        uint32_t              n_rot,
        uint32_t              pos0,
        uint32_t              n_ctx_orig,
        float                 freq_base,
        float                 freq_scale,
        float                 ext_factor,
        float                 attn_factor,
        float                 beta_fast,
        float                 beta_slow,
        float                 eps);

int ds4_gpu_head_rms_norm_tensor(
        ds4_gpu_tensor *x,
        uint32_t          n_tok,
        uint32_t          n_head,
        uint32_t          head_dim,
        float             eps);

int ds4_gpu_head_rms_norm_rope_tail_tensor(
        ds4_gpu_tensor *x,
        uint32_t          n_tok,
        uint32_t          n_head,
        uint32_t          head_dim,
        uint32_t          n_rot,
        uint32_t          pos0,
        uint32_t          n_ctx_orig,
        bool              inverse,
        float             freq_base,
        float             freq_scale,
        float             ext_factor,
        float             attn_factor,
        float             beta_fast,
        float             beta_slow,
        float             eps);


int ds4_gpu_dsv4_fp8_kv_quantize_tensor(
        ds4_gpu_tensor *x,
        uint32_t          n_tok,
        uint32_t          head_dim,
        uint32_t          n_rot);

int ds4_gpu_dsv4_indexer_qat_tensor(
        ds4_gpu_tensor *x,
        uint32_t          n_rows,
        uint32_t          head_dim);

int ds4_gpu_rope_tail_tensor(
        ds4_gpu_tensor *x,
        uint32_t          n_tok,
        uint32_t          n_head,
        uint32_t          head_dim,
        uint32_t          n_rot,
        uint32_t          pos0,
        uint32_t          n_ctx_orig,
        bool              inverse,
        float             freq_base,
        float             freq_scale,
        float             ext_factor,
        float             attn_factor,
        float             beta_fast,
        float             beta_slow);

/* GLM-5.3 pools four normalized indexer keys with a learned, per-channel
 * softmax. Partial pools are retained in tail_k/tail_gate across calls. */

int ds4_gpu_glm_indexer_score_one_tensor(
        ds4_gpu_tensor       *scores,
        const ds4_gpu_tensor *q,
        const ds4_gpu_tensor *weights,
        const ds4_gpu_tensor *indexer_key_cache,
        uint32_t              n_rows,
        uint32_t              n_head,
        uint32_t              head_dim,
        float                 scale,
        bool                  cache_f16);

/* Release decode fused KV finalizer: after the standalone RoPE kernel, this
 * performs DS4's FP8 non-RoPE KV round trip and writes the F16-rounded raw
 * attention cache row in one dispatch. */
int ds4_gpu_kv_fp8_store_raw_tensor(
        ds4_gpu_tensor *kv,
        ds4_gpu_tensor *raw_cache,
        uint32_t          raw_cap,
        uint32_t          row,
        uint32_t          head_dim,
        uint32_t          n_rot);

/* Reference/raw-cache primitive kept for prefill and diagnostics.  Decode uses
 * ds4_gpu_kv_fp8_store_raw_tensor unless a diagnostic reference path is
 * explicitly selected by the graph driver. */
int ds4_gpu_store_raw_kv_tensor(
        ds4_gpu_tensor       *raw_cache,
        const ds4_gpu_tensor *kv,
        uint32_t                raw_cap,
        uint32_t                row,
        uint32_t                head_dim);

int ds4_gpu_store_raw_kv_batch_tensor(
        ds4_gpu_tensor       *raw_cache,
        const ds4_gpu_tensor *kv,
        uint32_t                raw_cap,
        uint32_t                pos0,
        uint32_t                n_tokens,
        uint32_t                head_dim);

/* =========================================================================
 * KV Compression and Attention.
 * =========================================================================
 *
 * Compressed layers maintain rolling score/KV state and append pooled rows at
 * ratio boundaries.  Attention kernels consume raw SWA rows, compressed rows,
 * and optional indexer masks.
 */

int ds4_gpu_compressor_update_tensor(
        const ds4_gpu_tensor *kv_cur,
        const ds4_gpu_tensor *sc_cur,
        ds4_gpu_tensor       *state_kv,
        ds4_gpu_tensor       *state_score,
        ds4_gpu_tensor       *comp_cache,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                ape_offset,
        uint32_t                ape_type,
        uint64_t                norm_offset,
        uint32_t                norm_type,
        uint32_t                head_dim,
        uint32_t                ratio,
        uint32_t                pos,
        uint32_t                comp_row,
        uint32_t                n_rot,
        uint32_t                n_ctx_orig,
        float                   freq_base,
        float                   freq_scale,
        float                   ext_factor,
        float                   attn_factor,
        float                   beta_fast,
        float                   beta_slow,
        float                   rms_eps,
        bool                    state_already_stored,
        bool                    decode_one_token,
        bool                    defer_finalize);

int ds4_gpu_compressor_store_batch_tensor(
        const ds4_gpu_tensor *kv,
        const ds4_gpu_tensor *sc,
        ds4_gpu_tensor       *state_kv,
        ds4_gpu_tensor       *state_score,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                ape_offset,
        uint32_t                ape_type,
        uint32_t                head_dim,
        uint32_t                ratio,
        uint32_t                pos0,
        uint32_t                n_tokens);

int ds4_gpu_compressor_prefill_tensor(
        ds4_gpu_tensor       *comp_cache,
        ds4_gpu_tensor       *state_kv,
        ds4_gpu_tensor       *state_score,
        const ds4_gpu_tensor *kv,
        const ds4_gpu_tensor *sc,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                ape_offset,
        uint32_t                ape_type,
        uint64_t                norm_offset,
        uint32_t                norm_type,
        uint32_t                head_dim,
        uint32_t                ratio,
        uint32_t                pos0,
        uint32_t                n_tokens,
        uint32_t                n_rot,
        uint32_t                n_ctx_orig,
        bool                    quantize_fp8,
        float                   freq_base,
        float                   freq_scale,
        float                   ext_factor,
        float                   attn_factor,
        float                   beta_fast,
        float                   beta_slow,
        float                   rms_eps);

int ds4_gpu_compressor_prefill_ratio4_replay_tensor(
        ds4_gpu_tensor       *comp_cache,
        ds4_gpu_tensor       *state_kv,
        ds4_gpu_tensor       *state_score,
        const ds4_gpu_tensor *kv,
        const ds4_gpu_tensor *sc,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                ape_offset,
        uint32_t                ape_type,
        uint64_t                norm_offset,
        uint32_t                norm_type,
        uint32_t                head_dim,
        uint32_t                pos0,
        uint32_t                n_tokens,
        uint32_t                n_rot,
        uint32_t                n_ctx_orig,
        bool                    quantize_fp8,
        float                   freq_base,
        float                   freq_scale,
        float                   ext_factor,
        float                   attn_factor,
        float                   beta_fast,
        float                   beta_slow,
        float                   rms_eps);

int ds4_gpu_compressor_prefill_state_ratio4_tensor(
        ds4_gpu_tensor       *state_kv,
        ds4_gpu_tensor       *state_score,
        const ds4_gpu_tensor *kv_tail,
        const ds4_gpu_tensor *sc_tail,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                ape_offset,
        uint32_t                ape_type,
        uint32_t                head_dim,
        uint32_t                pos0);

int ds4_gpu_attention_decode_heads_tensor(
        ds4_gpu_tensor       *heads,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                sinks_offset,
        const ds4_gpu_tensor *q,
        const ds4_gpu_tensor *raw_kv,
        uint32_t                n_raw,
        uint32_t                raw_cap,
        uint32_t                raw_start,
        const ds4_gpu_tensor *comp_kv,
        uint32_t                comp_kv_f16,
        uint32_t                n_comp,
        const ds4_gpu_tensor *comp_mask,
        uint32_t                use_mask,
        uint32_t                n_head,
        uint32_t                head_dim);

/* Diagnostic/public form of the dk=512 gathered decode-attention KV staging
 * step. The compressed source must be F16; dst writes chronological raw-ring
 * rows followed by compressed rows and must not overlap either source. */
int ds4_gpu_flash_kv_stage_f16_tensor(
        ds4_gpu_tensor       *dst,
        const ds4_gpu_tensor *raw,
        uint32_t                raw_cap,
        uint32_t                raw_start,
        uint32_t                n_raw,
        const ds4_gpu_tensor *comp,
        uint32_t                comp_is_f16,
        uint32_t                n_comp,
        uint32_t                head_dim);

int ds4_gpu_attention_prefill_raw_heads_tensor(
        ds4_gpu_tensor       *heads,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                sinks_offset,
        const ds4_gpu_tensor *q,
        const ds4_gpu_tensor *raw_kv,
        uint32_t                n_tokens,
        uint32_t                window,
        uint32_t                n_head,
        uint32_t                head_dim);

/* Rectangular raw prefill attention: q is a view of the n_q query rows at
 * token positions [q_row0, q_row0 + n_q) of the chunk, raw_kv keeps all
 * n_kv rows, heads receives n_q output rows.  Used by the TP prefill row
 * split; the square entry above is the q_row0 = 0, n_q = n_kv case. */
int ds4_gpu_attention_prefill_raw_heads_range_tensor(
        ds4_gpu_tensor       *heads,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                sinks_offset,
        const ds4_gpu_tensor *q,
        const ds4_gpu_tensor *raw_kv,
        uint32_t                q_row0,
        uint32_t                n_q,
        uint32_t                n_kv,
        uint32_t                window,
        uint32_t                n_head,
        uint32_t                head_dim);

int ds4_gpu_attention_decode_raw_batch_heads_tensor(
        ds4_gpu_tensor       *heads,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                sinks_offset,
        const ds4_gpu_tensor *q,
        const ds4_gpu_tensor *raw_kv,
        uint32_t                n_tokens,
        uint32_t                pos0,
        uint32_t                n_raw,
        uint32_t                raw_cap,
        uint32_t                raw_start,
        uint32_t                window,
        uint32_t                n_head,
        uint32_t                head_dim);

int ds4_gpu_attention_decode_mixed_batch_heads_tensor(
        ds4_gpu_tensor       *heads,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                sinks_offset,
        const ds4_gpu_tensor *q,
        const ds4_gpu_tensor *raw_kv,
        const ds4_gpu_tensor *comp_kv,
        uint32_t                comp_kv_f16,
        const ds4_gpu_tensor *comp_mask,
        uint32_t                use_comp_mask,
        uint32_t                n_tokens,
        uint32_t                pos0,
        uint32_t                n_raw,
        uint32_t                raw_cap,
        uint32_t                raw_start,
        uint32_t                n_comp,
        uint32_t                window,
        uint32_t                ratio,
        uint32_t                n_head,
        uint32_t                head_dim);

int ds4_gpu_attention_indexed_mixed_batch_heads_tensor(
        ds4_gpu_tensor       *heads,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                sinks_offset,
        const ds4_gpu_tensor *q,
        const ds4_gpu_tensor *raw_kv,
        const ds4_gpu_tensor *comp_kv,
        uint32_t                comp_kv_f16,
        const ds4_gpu_tensor *topk,
        uint32_t                n_tokens,
        uint32_t                pos0,
        uint32_t                n_raw,
        uint32_t                raw_cap,
        uint32_t                raw_start,
        uint32_t                n_comp,
        uint32_t                top_k,
        uint32_t                window,
        uint32_t                ratio,
        uint32_t                n_head,
        uint32_t                head_dim);

int ds4_gpu_attention_prefill_static_mixed_heads_tensor(
        ds4_gpu_tensor       *heads,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                sinks_offset,
        const ds4_gpu_tensor *q,
        const ds4_gpu_tensor *raw_kv,
        const ds4_gpu_tensor *comp_kv,
        uint32_t                comp_kv_f16,
        uint32_t                n_tokens,
        uint32_t                n_comp,
        uint32_t                window,
        uint32_t                ratio,
        uint32_t                n_head,
        uint32_t                head_dim);

/* Rectangular static-mixed prefill attention: q is a view of the n_q query
 * rows at token positions [q_row0, q_row0 + n_q) of the chunk, while raw_kv
 * keeps all n_tokens rows and comp_kv all n_comp compressed keys.  Used by
 * the TP prefill row split; the square entry above is q_row0 = 0,
 * n_q = n_tokens. */
int ds4_gpu_attention_prefill_static_mixed_heads_range_tensor(
        ds4_gpu_tensor       *heads,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                sinks_offset,
        const ds4_gpu_tensor *q,
        const ds4_gpu_tensor *raw_kv,
        const ds4_gpu_tensor *comp_kv,
        uint32_t                comp_kv_f16,
        uint32_t                q_row0,
        uint32_t                n_q,
        uint32_t                n_tokens,
        uint32_t                n_comp,
        uint32_t                window,
        uint32_t                ratio,
        uint32_t                n_head,
        uint32_t                head_dim);

int ds4_gpu_attention_prefill_masked_mixed_heads_tensor(
        ds4_gpu_tensor       *heads,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                sinks_offset,
        const ds4_gpu_tensor *q,
        const ds4_gpu_tensor *raw_kv,
        const ds4_gpu_tensor *comp_kv,
        uint32_t                comp_kv_f16,
        const ds4_gpu_tensor *comp_mask,
        uint32_t                n_tokens,
        uint32_t                n_comp,
        uint32_t                window,
        uint32_t                ratio,
        uint32_t                n_head,
        uint32_t                head_dim);

/* DeepSeek Vision-Exp attention over the current prefill chunk. The raw cache
 * is chronological from raw_start and may include the preceding SWA rows.
 * Synthetic image spans in tokens are made bidirectional as specified by the
 * checkpoint; text and compressed keys retain the normal causal masks. */
int ds4_gpu_attention_visual_mixed_batch_heads_tensor(
        ds4_gpu_tensor       *heads,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                sinks_offset,
        const ds4_gpu_tensor *q,
        const ds4_gpu_tensor *raw_kv,
        const ds4_gpu_tensor *comp_kv,
        uint32_t                comp_kv_f16,
        const ds4_gpu_tensor *comp_mask,
        uint32_t                use_comp_mask,
        const int32_t          *tokens,
        uint32_t                vocab_size,
        uint32_t                n_tokens,
        uint32_t                pos0,
        uint32_t                n_raw,
        uint32_t                raw_cap,
        uint32_t                raw_start,
        uint32_t                n_comp,
        uint32_t                window,
        uint32_t                ratio,
        uint32_t                n_head,
        uint32_t                head_dim);

int ds4_gpu_attention_output_q8_batch_tensor(
        ds4_gpu_tensor       *out,
        ds4_gpu_tensor       *low,
        ds4_gpu_tensor       *group_tmp,
        ds4_gpu_tensor       *low_tmp,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                out_a_offset,
        uint64_t                out_b_offset,
        uint64_t                group_dim,
        uint64_t                rank,
        uint32_t                n_groups,
        uint64_t                out_dim,
        const ds4_gpu_tensor *heads,
        uint32_t                n_tokens);
int ds4_gpu_attention_output_q4_K_batch_tensor(
        ds4_gpu_tensor       *out,
        ds4_gpu_tensor       *low,
        ds4_gpu_tensor       *group_tmp,
        ds4_gpu_tensor       *low_tmp,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                out_a_offset,
        uint64_t                out_b_offset,
        uint32_t                out_b_type,
        uint64_t                group_dim,
        uint64_t                rank,
        uint32_t                n_groups,
        uint64_t                out_dim,
        const ds4_gpu_tensor *heads,
        uint32_t                n_tokens);


int ds4_gpu_attention_output_low_q8_tensor(
        ds4_gpu_tensor       *low,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                out_a_offset,
        uint64_t                group_dim,
        uint64_t                rank,
        uint32_t                n_groups,
        const ds4_gpu_tensor *heads);
int ds4_gpu_attention_output_low_q4_K_slice_tensor(
        ds4_gpu_tensor       *low,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                out_a_offset,
        uint64_t                group_dim,
        uint64_t                rank,
        uint32_t                group0,
        uint32_t                group_cnt,
        const ds4_gpu_tensor *heads);

int ds4_gpu_attention_output_q8_tp_tensor(
        ds4_gpu_tensor       *out,
        ds4_gpu_tensor       *low,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                out_a_offset,
        uint64_t                out_b_offset,
        uint64_t                group_dim,
        uint64_t                rank,
        uint32_t                n_groups_total,
        uint32_t                group0,
        uint32_t                group_cnt,
        uint64_t                out_dim,
        const ds4_gpu_tensor *heads);

/* =========================================================================
 * Router, Shared Expert, and Routed MoE.
 * =========================================================================
 *
 * These kernels implement the FFN body: router probabilities/top-k or hash
 * routing, shared SwiGLU, and the IQ2_XXS/Q2_K/Q4_K routed experts.
 */

int ds4_gpu_swiglu_tensor(
        ds4_gpu_tensor       *out,
        const ds4_gpu_tensor *gate,
        const ds4_gpu_tensor *up,
        uint32_t                n,
        float                   clamp,
        float                   weight);

int ds4_gpu_add_tensor(
        ds4_gpu_tensor       *out,
        const ds4_gpu_tensor *a,
        const ds4_gpu_tensor *b,
        uint32_t                n);

int ds4_gpu_directional_steering_project_tensor(
        ds4_gpu_tensor       *x,
        const ds4_gpu_tensor *directions,
        uint32_t                layer,
        uint32_t                width,
        uint32_t                rows,
        float                   scale);

int ds4_gpu_router_select_tensor(
        ds4_gpu_tensor       *selected,
        ds4_gpu_tensor       *weights,
        ds4_gpu_tensor       *probs,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                bias_offset,
        uint64_t                hash_offset,
        uint32_t                hash_rows,
        uint32_t                token,
        uint32_t                n_expert,
        uint32_t                n_expert_used,
        float                   expert_weight_scale,
        uint32_t                n_expert_groups,
        uint32_t                n_group_used,
        bool                    has_bias,
        bool                    hash_mode,
        const ds4_gpu_tensor *logits);

int ds4_gpu_router_select_batch_tensor(
        ds4_gpu_tensor       *selected,
        ds4_gpu_tensor       *weights,
        ds4_gpu_tensor       *probs,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                bias_offset,
        uint64_t                hash_offset,
        uint32_t                hash_rows,
        uint32_t                n_expert_groups,
        uint32_t                n_group_used,
        bool                    has_bias,
        bool                    hash_mode,
        const ds4_gpu_tensor *logits,
        const ds4_gpu_tensor *tokens,
        uint32_t                n_expert,
        uint32_t                n_expert_used,
        float                   expert_weight_scale,
        uint32_t                n_tokens);

/* DeepSeek Vision-Exp prefill may mix ordinary vocabulary IDs and synthetic
 * image IDs in one batch. Text rows keep the normal/hash route; image rows use
 * the checkpoint's visual selection bias. Routing weights always come from
 * the original, unbiased scores. */
int ds4_gpu_router_select_batch_visual_tensor(
        ds4_gpu_tensor       *selected,
        ds4_gpu_tensor       *weights,
        ds4_gpu_tensor       *probs,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                bias_offset,
        uint64_t                hash_offset,
        uint32_t                hash_rows,
        bool                    has_bias,
        bool                    hash_mode,
        const void             *vision_map,
        uint64_t                vision_size,
        uint64_t                visual_bias_offset,
        const ds4_gpu_tensor *logits,
        const ds4_gpu_tensor *tokens,
        uint32_t                vocab_size,
        uint32_t                n_expert,
        uint32_t                n_expert_used,
        float                   expert_weight_scale,
        uint32_t                n_tokens);

int ds4_gpu_routed_moe_set_selected_override(const int32_t *selected, uint32_t n_selected);

int ds4_gpu_routed_moe_one_tensor(
        ds4_gpu_tensor       *out,
        ds4_gpu_tensor       *gate,
        ds4_gpu_tensor       *up,
        ds4_gpu_tensor       *mid,
        ds4_gpu_tensor       *experts,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                gate_offset,
        uint64_t                up_offset,
        uint64_t                down_offset,
        uint32_t                gate_type,
        uint32_t                down_type,
        uint64_t                gate_expert_bytes,
        uint64_t                gate_row_bytes,
        uint64_t                down_expert_bytes,
        uint64_t                down_row_bytes,
        uint32_t                expert_in_dim,
        uint32_t                expert_mid_dim,
        uint32_t                out_dim,
        const ds4_gpu_tensor *selected,
        const ds4_gpu_tensor *weights,
        uint32_t                n_total_expert,
        uint32_t                n_expert,
        float                   clamp,
        const ds4_gpu_tensor *x,
        const ds4_gpu_tensor *add_in,
        uint32_t                layer_index,
        bool                    force_resident);

int ds4_gpu_routed_moe_batch_tensor(
        ds4_gpu_tensor       *out,
        ds4_gpu_tensor       *gate,
        ds4_gpu_tensor       *up,
        ds4_gpu_tensor       *mid,
        ds4_gpu_tensor       *experts,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                gate_offset,
        uint64_t                up_offset,
        uint64_t                down_offset,
        uint32_t                gate_type,
        uint32_t                down_type,
        uint64_t                gate_expert_bytes,
        uint64_t                gate_row_bytes,
        uint64_t                down_expert_bytes,
        uint64_t                down_row_bytes,
        uint32_t                expert_in_dim,
        uint32_t                expert_mid_dim,
        uint32_t                out_dim,
        const ds4_gpu_tensor *selected,
        const ds4_gpu_tensor *weights,
        uint32_t                n_total_expert,
        uint32_t                n_expert,
        float                   clamp,
        const ds4_gpu_tensor *x,
        uint32_t                layer_index,
        uint32_t                n_tokens,
        bool                   *mid_is_f16,
        bool                    force_resident);

/* =========================================================================
 * Hyper-Connection Kernels.
 * =========================================================================
 *
 * HC kernels reduce four residual streams before a sublayer and expand the
 * sublayer output back into four streams afterward.
 */

int ds4_gpu_hc_split_sinkhorn_tensor(
        ds4_gpu_tensor       *out,
        const ds4_gpu_tensor *mix,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                scale_offset,
        uint64_t                base_offset,
        uint32_t                n_hc,
        uint32_t                sinkhorn_iters,
        float                   eps);

int ds4_gpu_hc_weighted_sum_tensor(
        ds4_gpu_tensor       *out,
        const ds4_gpu_tensor *residual_hc,
        const ds4_gpu_tensor *weights,
        uint32_t                n_embd,
        uint32_t                n_hc);

int ds4_gpu_hc_weighted_sum_split_tensor(
        ds4_gpu_tensor       *out,
        const ds4_gpu_tensor *residual_hc,
        const ds4_gpu_tensor *split,
        uint32_t                n_embd,
        uint32_t                n_hc);

/* Release decode fused HC pre-sublayer operation: split the HC mixer and
 * immediately reduce four HC streams into the active 4096-wide sublayer row. */
int ds4_gpu_hc_split_weighted_sum_tensor(
        ds4_gpu_tensor       *out,
        ds4_gpu_tensor       *split,
        const ds4_gpu_tensor *mix,
        const ds4_gpu_tensor *residual_hc,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                scale_offset,
        uint64_t                base_offset,
        uint32_t                n_embd,
        uint32_t                n_hc,
        uint32_t                sinkhorn_iters,
        float                   eps);

int ds4_gpu_hc_split_weighted_sum_norm_tensor(
        ds4_gpu_tensor       *out,
        ds4_gpu_tensor       *norm_out,
        ds4_gpu_tensor       *split,
        const ds4_gpu_tensor *mix,
        const ds4_gpu_tensor *residual_hc,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                scale_offset,
        uint64_t                base_offset,
        uint64_t                norm_weight_offset,
        uint32_t                n_embd,
        uint32_t                n_hc,
        uint32_t                sinkhorn_iters,
        float                   eps,
        float                   norm_eps);

int ds4_gpu_hc_rms_norm_mix_f16_available(void);
int ds4_gpu_hc_rms_norm_mix_f16_tensor(
        ds4_gpu_tensor       *out,
        const ds4_gpu_tensor *x,
        const void           *model_map,
        uint64_t              model_size,
        uint64_t              weight_offset,
        uint32_t              n,
        uint32_t              out_dim,
        float                 eps);

/* Batched HC RMSNorm followed by its narrow F16 mixer projection. On the
 * tuned Metal path, scale_scratch stores one float per row instead of the
 * full normalized HC tensor; other shapes retain the established fallback. */
int ds4_gpu_hc_rms_scale_project_f16_tensor(
        ds4_gpu_tensor       *out,
        ds4_gpu_tensor       *scale_scratch,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_offset,
        uint32_t                in_dim,
        uint32_t                out_dim,
        const ds4_gpu_tensor *x,
        uint32_t                n_rows,
        float                   eps);

int ds4_gpu_hc_rms_norm_mix_split_norm_f16_tensor(
        ds4_gpu_tensor       *mix,
        ds4_gpu_tensor       *out,
        ds4_gpu_tensor       *norm_out,
        ds4_gpu_tensor       *split,
        const ds4_gpu_tensor *residual_hc,
        const void           *model_map,
        uint64_t              model_size,
        uint64_t              mix_weight_offset,
        uint64_t              scale_offset,
        uint64_t              base_offset,
        uint64_t              norm_weight_offset,
        uint32_t              n,
        uint32_t              mix_dim,
        uint32_t              n_embd,
        uint32_t              n_hc,
        uint32_t              sinkhorn_iters,
        float                 eps,
        float                 hc_eps,
        float                 norm_eps);
int ds4_gpu_hc_expand_add_rms_norm_mix_split_norm_f16_tensor(
        ds4_gpu_tensor       *mix,
        ds4_gpu_tensor       *out,
        ds4_gpu_tensor       *norm_out,
        ds4_gpu_tensor       *split,
        const ds4_gpu_tensor *residual_hc,
        const ds4_gpu_tensor *block_out,
        const ds4_gpu_tensor *block_add,
        const ds4_gpu_tensor *residual_prev,
        const ds4_gpu_tensor *post,
        const ds4_gpu_tensor *comb,
        const void           *model_map,
        uint64_t              model_size,
        uint64_t              mix_weight_offset,
        uint64_t              scale_offset,
        uint64_t              base_offset,
        uint64_t              norm_weight_offset,
        uint32_t              n,
        uint32_t              mix_dim,
        uint32_t              n_embd,
        uint32_t              n_hc,
        uint32_t              sinkhorn_iters,
        float                 eps,
        float                 hc_eps,
        float                 norm_eps);

int ds4_gpu_output_hc_weights_tensor(
        ds4_gpu_tensor       *out,
        const ds4_gpu_tensor *pre,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                scale_offset,
        uint64_t                base_offset,
        uint32_t                n_hc,
        float                   eps);

int ds4_gpu_hc_expand_tensor(
        ds4_gpu_tensor       *out_hc,
        const ds4_gpu_tensor *block_out,
        const ds4_gpu_tensor *residual_hc,
        const ds4_gpu_tensor *post,
        const ds4_gpu_tensor *comb,
        uint32_t                n_embd,
        uint32_t                n_hc);
int ds4_gpu_hc_expand_add_tensor(
        ds4_gpu_tensor       *out_hc,
        const ds4_gpu_tensor *block_out,
        const ds4_gpu_tensor *block_add,
        const ds4_gpu_tensor *residual_hc,
        const ds4_gpu_tensor *post,
        const ds4_gpu_tensor *comb,
        uint32_t                n_embd,
        uint32_t                n_hc);

int ds4_gpu_hc_expand_add_tensor(
        ds4_gpu_tensor       *out_hc,
        const ds4_gpu_tensor *block_out,
        const ds4_gpu_tensor *block_add,
        const ds4_gpu_tensor *residual_hc,
        const ds4_gpu_tensor *post,
        const ds4_gpu_tensor *comb,
        uint32_t                n_embd,
        uint32_t                n_hc);

int ds4_gpu_hc_expand_split_tensor(
        ds4_gpu_tensor       *out_hc,
        const ds4_gpu_tensor *block_out,
        const ds4_gpu_tensor *residual_hc,
        const ds4_gpu_tensor *split,
        uint32_t                n_embd,
        uint32_t                n_hc);


int ds4_gpu_hc_expand_add_split_tensor(
        ds4_gpu_tensor       *out_hc,
        const ds4_gpu_tensor *block_out,
        const ds4_gpu_tensor *block_add,
        const ds4_gpu_tensor *residual_hc,
        const ds4_gpu_tensor *split,
        uint32_t                n_embd,
        uint32_t                n_hc);


int ds4_gpu_shared_down_hc_expand_q8_0_tensor(
        ds4_gpu_tensor       *out_hc,
        ds4_gpu_tensor       *shared_out,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_offset,
        uint64_t                in_dim,
        uint64_t                out_dim,
        const ds4_gpu_tensor *shared_mid,
        const ds4_gpu_tensor *routed_out,
        const ds4_gpu_tensor *residual_hc,
        const ds4_gpu_tensor *split,
        uint32_t                n_embd,
        uint32_t                n_hc);

int ds4_gpu_matmul_q8_0_hc_expand_tensor(
        ds4_gpu_tensor       *out_hc,
        ds4_gpu_tensor       *block_out,
        const void             *model_map,
        uint64_t                model_size,
        uint64_t                weight_offset,
        uint64_t                in_dim,
        uint64_t                out_dim,
        const ds4_gpu_tensor *x,
        const ds4_gpu_tensor *residual_hc,
        const ds4_gpu_tensor *split,
        uint32_t                n_embd,
        uint32_t                n_hc);

int ds4_gpu_glm53_matmul_bf16(
        ds4_gpu_tensor       *out,
        const void           *model_map,
        uint64_t              model_size,
        uint64_t              weight_offset,
        uint32_t              in_dim,
        uint32_t              out_dim,
        const ds4_gpu_tensor *x,
        uint32_t              n_rows);

/* Encode normalized, block-major image patches into 4096-wide language-model
 * embeddings. GPU implementations keep every intermediate on device. */

#ifndef DS4_DEEPSEEK4_VISION_TYPES_DEFINED
#define DS4_DEEPSEEK4_VISION_TYPES_DEFINED
#define DS4_DEEPSEEK4_VISION_LAYERS 32u
#define DS4_DEEPSEEK4_LANGUAGE_LAYERS 43u
#define DS4_DEEPSEEK4_MTP_LAYERS 3u

typedef struct {
    uint64_t norm1;
    uint64_t qkv_weight;
    uint64_t qkv_bias;
    uint64_t attn_proj_weight;
    uint64_t attn_proj_bias;
    uint64_t norm2;
    uint64_t mlp_w1;
    uint64_t mlp_w2;
} ds4_deepseek4_vision_layer_weights;

typedef struct {
    uint64_t patch_weight;
    uint64_t patch_bias;
    uint64_t post_norm;
    uint64_t aligner_w1;
    uint64_t aligner_w1_bias;
    uint64_t aligner_w2;
    uint64_t aligner_w2_bias;
    uint64_t image_start;
    uint64_t image_pad;
    uint64_t image_newline;
    uint64_t image_end;
    uint64_t visual_router_bias[DS4_DEEPSEEK4_LANGUAGE_LAYERS];
    uint64_t mtp_visual_router_bias[DS4_DEEPSEEK4_MTP_LAYERS];
    uint64_t hash_router_bias[3];
    ds4_deepseek4_vision_layer_weights layer[DS4_DEEPSEEK4_VISION_LAYERS];
    uint32_t projection_dim;
} ds4_deepseek4_vision_weights;
#endif

/* Encode row-major normalized 14x14 RGB patches. The output is the natural
 * row-major 3x3-aligned grid; N-layout permutation and sentinels are applied
 * by the prompt layer once the image's token position is known. */
int ds4_gpu_deepseek4_vision_encode(
        float                              *out,
        const float                        *patches,
        uint32_t                            grid_h,
        uint32_t                            grid_w,
        const void                         *model_map,
        uint64_t                            model_size,
        const ds4_deepseek4_vision_weights *weights);

#ifdef __cplusplus
}
#endif

#endif
