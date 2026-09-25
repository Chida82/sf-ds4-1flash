# Triage candidates, 2026-09-25

211 unmerged PRs that touch ds4.c, ds4_metal.m, metal/, Engram or the GPU headers, have patches not in main (0aaea5a), and are not dominated by GLM/Qwen/CUDA hits. One line per PR:

`<PR> <o|c> <created MM-DD> p<patches not in main> v<V4.1 hits> e<Engram hits> s<ssd/stream hits> g<GLM> q<Qwen> c<CUDA/ROCm> h<hunks in functions the child still has>/<hunks> | <title>`

Hits count changed diff lines matching the keyword (case-insensitive), csv/json/md/txt/svg/png excluded.

```text
1124 o 09-25 p2 v0 e0 s0 g0 q0 c0 h11/11 | Metal: parallelize fused FP8 KV max reduction
1123 o 09-25 p5 v0 e0 s0 g0 q0 c2 h21/22 | Metal: fix chunked-prefill SWA ring overflow and four latent kernel bugs
1121 o 09-25 p1 v65 e8 s7 g7 q0 c0 h19/50 | [Draft] Add resumable imatrix collection with isolated V4.1 prompt packing
1120 o 09-24 p5 v15 e0 s4 g78 q0 c3 h55/55 | Specialize resident M5 Metal decode shapes
1117 o 09-24 p1 v4 e73 s0 g0 q0 c0 h9/9 | Linux: read decode Engram rows in parallel, probing the page cache first
1116 o 09-24 p1 v6 e0 s0 g0 q0 c8 h2/3 | CUDA TP: lower the V4.1 layer-major prefill threshold to 32 rows
1090 o 09-19 p6 v638 e188 s93 g1138 q4 c16 h133/255 | metal: speed up GLM Flash over 28% and DeepSeek V4.1 Flash over 50% on M3 Ultra
1089 o 09-19 p1 v46 e2 s5 g9 q0 c0 h15/15 | v4.1: rewind live sessions instead of rebuilding them
1082 c 09-18 p28 v13 e48 s103 g2 q2 c237 h4/4 | CUDA SSD streaming: run the cached experts while the miss reads are in flight (+6 to +12 % deco
1073 o 09-18 p54 v811 e44 s53 g11 q0 c11 h414/445 | Speed up DeepSeek V4.1 Flash on Metal
1070 o 09-17 p19 v815 e102 s432 g18 q237 c1025 h169/205 | ROCm: add Qwen3.8 Flash Next support for Strix Halo (gfx1151)
1067 o 09-17 p5 v88 e117 s1 g0 q0 c0 h44/44 | Metal V4.1 decode: one command-buffer wait per token, Engram reads on threads
1064 c 09-16 p6 v3 e0 s172 g0 q0 c131 h9/9 | Nvidia dma streaming
1061 o 09-15 p1 v27 e0 s4 g4 q0 c0 h9/9 | metal: decode-shaped V4.1 indexer kernels for long contexts
1060 o 09-15 p1 v2 e0 s0 g0 q0 c0 h5/5 | metal: radix-select top-k for the V4.1 indexer
1056 o 09-15 p28 v6 e0 s512 g21 q1259 c18 h118/419 | Metal: optimize Qwen3.8 kernels, MTP state and SSD MoE scheduling (Up tp 40%)
1049 c 09-14 p3 v14 e8 s2 g0 q0 c0 h9/9 | perf(v41): reuse gathered KV across scalar reuse layers
1047 c 09-14 p3 v3 e0 s218 g2 q221 c8 h25/74 | Metal: add SSD expert streaming for Qwen3.8 Flash Next
1043 o 09-14 p1 v1 e0 s0 g0 q0 c0 h1/1 | metal: Q4_K group-6 expert table by default for DeepSeek V4.1 Flash (+2.3% decode on M3 Ultra, 
1042 o 09-14 p7 v252 e0 s3 g0 q0 c0 h37/39 | v41: fuse the single-box decode glue (HC, MoE, attention): +20% on M3 Ultra on top of #1041, bi
1041 o 09-14 p2 v10 e8 s1 g0 q0 c0 h8/8 | v41: queue single-box decode layers and commit each without waiting (+37% decode on M3 Ultra, b
1036 o 09-13 p6 v815 e101 s412 g18 q0 c875 h164/187 | ROCm: add DeepSeek V4.1 Flash support for Strix Halo (gfx1151)
1035 o 09-13 p3 v0 e47 s0 g0 q0 c0 h2/2 | engram: parallelize DeepSeek V4.1 Flash decode reads on macOS
1034 o 09-13 p2 v13 e0 s19 g0 q0 c0 h2/2 | metal: reduce decode synchronization for DeepSeek V4.1 Flash SSD streaming
1033 o 09-13 p3 v0 e0 s54 g0 q0 c0 h6/6 | metal: add opt-in slab residency for DeepSeek V4.1 Flash （M2 192GB 0.25tk/s -> 13tk/s)
1031 o 09-12 p4 v0 e0 s193 g0 q0 c87 h2/2 | CUDA: use selected expert cache for IQ2 SSD prefill
1027 o 09-11 p1 v0 e0 s1 g0 q0 c0 h2/2 | Make BPE merging O(n log n) for large CJK pieces
1020 o 09-10 p2 v0 e0 s0 g0 q0 c0 h2/2 | kvstore: stamp checkpoints with a behavioral tokenizer fingerprint
1018 o 09-10 p3 v2 e0 s23 g2 q0 c2 h1/1 | Add OdinLink (odl_tb5) TP transport: --transport odl
1011 o 09-09 p33 v815 e102 s448 g121 q239 c1129 h172/215 | ROCm: accelerate GLM 5.3 prefill and reduce MTP overhead on gfx1151
1010 o 09-09 p1 v0 e0 s1 g3 q0 c1 h24/29 | kv-cache: lazy-grow compressed KV caches instead of full-ctx up front
1005 o 09-09 p2 v0 e0 s1 g6 q3 c0 h2/3 | server: support live prefix rewind for GLM-5.3 and preserve common prefix on forks
1003 o 09-09 p2 v0 e0 s1 g1 q1 c0 h11/15 | Reuse DSpark snapshots for immediate session rewinds
1000 o 09-07 p2 v0 e0 s0 g0 q0 c0 h4/4 | server: avoid full prefix rewind when speculative decode stops
983 c 09-05 p2 v0 e0 s0 g0 q0 c0 h2/2 | kvstore: stamp checkpoints with a behavioral tokenizer fingerprint
977 o 09-04 p3 v0 e0 s0 g0 q0 c0 h22/24 | server: unify text and vision KV prefix reuse
970 o 09-04 p9 v0 e0 s77 g9 q0 c16 h51/72 | Steering: read GLP (GGUF Layer Projection) vectors
969 o 09-04 p1 v0 e0 s0 g6 q0 c0 h6/6 | Fix text tool observation path for non-GLM multimodal messages
965 o 09-03 p1 v0 e0 s0 g0 q0 c2 h1/5 | metal: bypass DSpark speculation once a request proves unprofitable
963 o 09-03 p1 v0 e0 s0 g0 q0 c0 h1/1 | ds4-agent: fix every tool call failing on DeepSeek without --vision (+ regression test)
961 o 09-03 p1 v0 e0 s0 g0 q0 c0 h19/21 | server: persist vision KV with exact conditioning provenance
960 o 09-03 p1 v0 e0 s5 g3 q0 c3 h1/2 | server: restore the prompt frontier after cancelled generation
959 o 09-03 p3 v0 e0 s0 g2 q0 c3 h10/10 | metal: prune top-k argsort merge rounds to top_k
957 o 09-03 p1 v0 e0 s0 g0 q0 c0 h11/11 | fix(metal): coalesce adjacent --layers model map spans
954 o 09-02 p21 v0 e0 s18 g3 q0 c4 h147/159 | metal: pre-M5 optimizations — +3.65% MXFP4 prefill on M3 Ultra
952 o 09-02 p83 v2056 e121 s1829 g49 q4 c5583 h581/654 | AProjQ4: imatrix-guided Q4_K attention and GPU runtime optimizations
947 c 09-02 p1 v0 e0 s1 g1 q0 c0 h4/4 | Withhold the automatic Metal 4 tensor enable on M5 until accumulate parity
942 o 09-01 p1 v0 e0 s1 g2 q2 c2 h8/10 | Detach tokenizer storage from model mmap
937 o 09-01 p2 v0 e0 s0 g2 q0 c2 h20/22 | Fix DeepSeek Vision-Exp image inference with SSD streaming on Metal
927 c 09-01 p1 v0 e0 s1 g0 q0 c1 h5/5 | server: reuse KV when tools append images
924 o 08-31 p1 v0 e0 s0 g0 q0 c0 h1/1 | agent, engine: restore text tool observation path for non-GLM models
919 o 08-31 p11 v0 e0 s5 g10 q2 c10 h6/9 | Add pipeline parallelism
915 o 08-30 p2 v0 e0 s0 g2 q0 c2 h2/3 | dspark: fix indexer sparse-threshold mismatch + skip batched verify for a bare draft_n==1 accep
902 o 08-30 p2 v0 e0 s0 g0 q0 c0 h2/2 | M2 Ultra benchmark + whitelist it for two pre-M5 fusion paths
883 o 08-27 p1 v0 e0 s4 g0 q0 c0 h1/1 | engine: clearer refusal when --ssd-streaming meets a single-GPU --gpu-vram budget (#880)
882 o 08-27 p2 v0 e0 s1 g0 q0 c0 h1/1 | kvstore: reject disk KV checkpoints written under different model weights (#805)
876 o 08-27 p1 v0 e0 s7 g0 q0 c5 h1/1 | cli: name only the backends the build actually has
874 o 08-27 p11 v0 e0 s0 g1 q0 c3 h38/39 | Tune the Metal backend for M3 Ultra
873 o 08-27 p1 v0 e0 s0 g0 q0 c0 h13/13 | tokenizer: fix bpe_emit_piece's O(n^2) merge loop (#853)
864 o 08-25 p1 v0 e0 s0 g0 q0 c0 h35/35 | metal: speed up IQ2_XXS MoE prefill with half LUT and split MPP
861 c 08-24 p19 v19 e6 s516 g42 q0 c832 h158/184 | Consolidate ROCm exactness, distributed v3, DSpark speculation, and NHI tensor parallelism for 
852 o 08-22 p1 v0 e0 s0 g0 q0 c0 h24/24 | metal: keep TP gate waits out of compute command buffers
850 o 08-22 p1 v0 e0 s0 g0 q0 c1 h2/5 | metal: scale default prefill chunk with prompt length
849 o 08-21 p2 v0 e0 s40 g0 q0 c0 h13/14 | ssd streaming: router-lookahead expert prefetch, +5.2% on top of #848 (output byte identical)
848 o 08-21 p1 v0 e0 s34 g0 q0 c0 h30/30 | ssd streaming: packed expert file, +10.7% on DeepSeek V4 Flash (output byte identical)
846 o 08-21 p1 v0 e0 s64 g0 q0 c3 h58/65 | metal: M1-class decode tuning, n-gram speculation, and batch-verifier groundwork
843 o 08-20 p1 v0 e0 s0 g0 q0 c0 h1/1 | engine: skip the single-instance lock for --inspect
841 o 08-20 p1 v0 e0 s3 g0 q0 c0 h16/16 | samplers: adds top-n-sigma sampler
835 o 08-19 p6 v0 e0 s27 g7 q0 c16 h18/24 | Distributed speculative decoding for the pipeline split (MTP + DSpark)
832 o 08-18 p9 v2 e0 s24 g0 q0 c2 h19/19 | metal: canonical top-k order + exact streaming top-512 selector
831 o 08-18 p5 v0 e0 s0 g0 q0 c3 h10/10 | metal: register-blocked, K-register-resident indexer prefill scorer (tiled4+tiled5)
830 o 08-18 p1 v0 e0 s0 g0 q0 c0 h8/8 | metal: wide-tile indexer prefill scorer over half-packed Q/K (bit-exact, +4.7% prefill at 64k)
828 o 08-18 p2 v33 e0 s2 g0 q0 c0 h21/23 | metal: non-blocking GPU stage timestamps behind DS4_METAL_GPU_STAGE_TIMESTAMPS
827 o 08-18 p1 v0 e0 s0 g2 q0 c0 h1/1 | server: idle prefill quantum follows the engine's prefill cap
822 o 08-17 p1 v0 e0 s42 g1 q0 c1 h1/6 | perf: optimize resumed streaming prefill boundaries
820 c 08-17 p1 v0 e0 s361 g15 q0 c515 h72/102 | distributed: descriptor-framed NHI transport, ROCm event timing, regression gates
817 c 08-16 p1 v0 e0 s0 g0 q0 c3 h5/5 | ROCm: env opt-in to keep the Q8->F16 weight cache in multi-model (MTP) setups
799 o 08-13 p2 v0 e0 s621 g36 q0 c0 h258/302 | Metal: per-stream command-queue overlap for batched session decode (~1.7x measured)
798 o 08-13 p3 v0 e0 s176 g4 q0 c16 h69/86 | fix DeepSeek SSD and DSpark integration
796 o 08-13 p1 v0 e0 s0 g0 q0 c0 h2/2 | Add AVX2 kernel for ds4_vec_dot_iq2_xxs_q8_K
795 o 08-13 p2 v0 e0 s283 g5 q0 c219 h18/20 | cuda: persistent expert cache + Q2Q4 mixed-size expert cache optimiza…
782 o 08-11 p1 v0 e0 s0 g0 q0 c0 h7/7 | metal: lightning-indexer-organized DS4 indexer scorer (llt)
778 o 08-11 p3 v0 e0 s10 g0 q0 c5 h45/97 | dspark: fold first-token forward into verify + bit-exact M5 Metal decode wins
777 o 08-11 p1 v0 e0 s0 g0 q0 c0 h1/1 | metal: fix staged B-tile tensor extents in the mm_id mpp kernel
770 o 08-10 p1 v0 e0 s0 g0 q0 c0 h15/15 | metal: gate the M3-class fusion whitelists on the pre-M5 predicate
767 o 08-10 p1 v0 e1 s1 g1 q0 c0 h20/23 | kv-cache: serialize only occupied compressor rows in checkpoints
758 o 08-09 p1 v0 e0 s0 g0 q0 c1 h16/16 | metal: accelerate M5 Max indexed prefill
752 o 08-09 p2 v0 e0 s8 g1 q0 c2 h8/9 | server: resolve Responses response ids to KV prefixes
749 o 08-08 p25 v0 e0 s126 g0 q0 c11 h23/29 | DSpark: bitwise first-divergence diagnostics for batched vs sequential decode
743 c 08-07 p1 v0 e0 s0 g0 q0 c0 h9/10 | metal: add optional polled release fence for the TP gate (~23% decode gain with `--tensor-paral
739 o 08-07 p3 v0 e0 s353 g0 q0 c207 h3/5 | cuda: retain routed experts in bounded cache
738 o 08-07 p2 v0 e0 s148 g0 q0 c91 h3/5 | cuda: overlap streamed expert uploads with compute
725 o 08-06 p1 v0 e0 s1 g0 q0 c0 h1/1 | ssd: enforce streaming cache floor at one-prefill minimum
720 c 08-06 p1 v0 e0 s2 g0 q0 c0 h1/1 | Fix misleading refusal message for --ssd-streaming
717 o 08-06 p1 v0 e0 s33 g69 q0 c60 h1/13 | glm: make GLM 5.2 work on CUDA with SSD streaming, including IQ2_XXS
715 c 08-06 p12 v0 e0 s151 g5 q0 c12 h59/65 | feat: support Apple RDMA in layer parallel distributed mode
704 o 08-05 p4 v0 e0 s0 g6 q0 c0 h8/8 | Fix reasoning_effort tier mapping and context-gate misreading
701 c 08-05 p1 v0 e0 s28 g43 q0 c47 h1/12 | glm: fix CUDA SSD-streaming, and refuse instead of wedging the host
686 o 08-04 p6 v0 e0 s1 g2 q0 c0 h11/12 | reasoning-effort: add a fourth tier so 0731's `max` is actually reachable
677 c 08-04 p1 v0 e0 s3 g0 q0 c2 h7/12 | DSpark: add byte-exact Metal verifier for lossless batching
664 o 08-03 p8 v0 e0 s2 g9 q0 c4 h15/24 | Community GGUF dialect compat for ds4f-mxfp4: dense BF16/F32/Q6_K load-time conversion
662 o 08-03 p4 v0 e0 s0 g0 q0 c0 h11/19 | Community GGUF dialect compat for ds4f-mxfp4: metadata derivation and tensor-name aliases
647 o 08-01 p4 v0 e0 s196 g0 q0 c250 h2/2 | cuda: implement real per-(layer,expert) LRU for --ssd-streaming-cache-experts
645 o 08-01 p1 v0 e0 s1 g0 q0 c4 h2/2 | fix(quantizer): support preserved MXFP4 in DSpark plans
631 o 07-30 p1 v0 e0 s0 g0 q0 c0 h5/5 | fix: keep distributed layer-slice HC on active tier
628 o 07-29 p2 v0 e0 s7276 g6339 q0 c6557 h191/528 | Add model-first provider boundary and split kernel implementations
621 c 07-28 p187 v0 e0 s5967 g423 q0 c7683 h751/1065 | Support AProjQ4 GGUFs: Q4_K dense attention projections; Metal, ROCm and CUDA performance impro
592 c 07-22 p1 v0 e0 s0 g0 q0 c0 h3/10 | fix(cuda): avoid null output-head dereference in distributed coordinators
590 c 07-21 p2 v0 e0 s2 g0 q0 c2 h9/27 | DSpark: replay-free partial accepts + encoder-batched captures (+40% greedy, byte-lossless)
589 o 07-21 p4 v0 e0 s458 g1 q0 c298 h50/85 | Support SSD streaming and MTP drafter when using two GPUs and caching of experts in VRAM
575 o 07-19 p1 v0 e0 s0 g0 q0 c0 h2/2 | Resolve Metal shader sources relative to the executable
571 o 07-17 p9 v0 e0 s2493 g3318 q0 c388 h1271/1515 | server: restore schema-declared argument types for GLM tool calls
570 o 07-17 p2 v0 e0 s46 g0 q0 c0 h10/10 | metal: pread pool dispatch stats and IO-tier pinning for streaming experts
568 o 07-16 p4 v0 e0 s458 g1 q0 c298 h50/85 | Support for Multi-GPU and --ssd-streaming
559 c 07-13 p1 v0 e0 s0 g0 q0 c0 h11/11 | Add opt-in fused Q2 down-sum kernel
557 o 07-13 p3 v0 e0 s906 g0 q0 c951 h4/4 | feat: implementing vulkan backend
555 c 07-12 p3 v0 e0 s2 g0 q0 c1 h227/240 | Optimize Metal prefill and decode on all Apple Silicon chips  
553 o 07-11 p9 v0 e0 s2501 g3314 q0 c386 h1225/1470 | glm5.2: streamed prefill fails when the boot model map does not cover routed experts
548 o 07-11 p1 v0 e0 s0 g0 q0 c0 h1/1 | Bound tokenizer merges count to INT32_MAX like the tokens table
545 c 07-11 p1 v0 e0 s0 g0 q0 c0 h2/2 | Bound GGUF metadata/tensor counts by file size before allocating (DoS)
535 o 07-11 p15 v0 e0 s2848 g3743 q0 c921 h1755/2043 | Hy3 (295B): CUDA backend support, GQA attention path
533 c 07-10 p3 v0 e0 s70 g0 q0 c0 h14/14 | metal: stop expert-miss readahead racing the pread pool (+13% GLM streaming decode)
530 c 07-10 p18 v0 e0 s458 g0 q0 c134 h403/508 | Batched decode: co-decode N live sessions in one GPU pass (opt-in)
529 o 07-10 p9 v0 e0 s2 g0 q0 c0 h71/71 | Enhance CPU performance with AVX512/AMX SIMD, TBB integration, and NUMA support
528 o 07-10 p11 v0 e0 s2503 g3316 q0 c386 h1284/1530 | glm: overlap the indexed full-layer prefill sweep with a pread prepare of the next layer
527 c 07-10 p9 v0 e0 s2493 g3314 q0 c386 h1271/1515 | Add GLM M3 Ultra implementation plans
523 o 07-09 p16 v0 e0 s95 g330 q0 c4 h285/321 | hy3: Metal decode path + shared gate/up fusion
520 o 07-08 p10 v0 e0 s2494 g3315 q0 c386 h1288/1532 | glm: fix streaming prefill failures for real-size prompts
517 o 07-07 p9 v0 e0 s2796 g3734 q0 c898 h1271/1515 | GLM 5.2: CUDA backend support
516 c 07-07 p3 v0 e0 s100 g0 q0 c16 h431/535 | Server: add --parallel N interleaved sessions (default 1)
515 c 07-07 p1 v0 e0 s9 g0 q0 c1 h431/535 | Engine: share prefill/decode work buffers across sessions
514 c 07-07 p10 v0 e0 s851 g1 q0 c8 h282/307 | Add sidecar for speed up ssd streaming
511 o 07-06 p1 v0 e0 s0 g0 q0 c0 h3/3 | Fix CPU backend abort on DeepSeek V4 PRO: use DS4_N_OUT_GROUP for attention-output grouping
508 o 07-06 p8 v0 e0 s284 g0 q0 c8 h11/13 | CPU backend: SSD streaming for routed experts (safe CPU inference on macOS)
502 o 07-05 p6 v0 e0 s16 g0 q1 c7 h8/15 | Add DeepSpec tests and training harnesses
499 o 07-04 p1 v0 e0 s2 g0 q0 c0 h2/2 | Opt-in mlock of non-routed weights for SSD streaming (DS4_MLOCK_NONROUTED)
492 c 07-03 p1 v0 e0 s0 g0 q0 c0 h2/2 | agent: resolve runtime assets from binary directory
489 o 07-02 p15 v0 e0 s121 g0 q0 c2 h1/1 | Server: fix agent-loop cache misses, add cancellation, observability, and robustness fixes
488 o 07-02 p1 v0 e0 s1 g0 q0 c6 h2/2 | cuda: enable streaming auto cache (implement recommended_working_set_size)
482 o 06-30 p9 v0 e0 s41 g0 q1 c8 h44/65 | DSpark B2 rejection sampling + adaptive block sizing
480 c 06-30 p167 v0 e0 s61 g0 q1 c18 h56/105 | Add DSpark speculative draft runtime
464 o 06-27 p2 v0 e0 s1 g0 q0 c0 h3/3 | Fix slow decodes "poisoning" sleep times when using power throttling
454 c 06-25 p1 v0 e0 s15 g0 q0 c0 h2/2 | Metal: keep selected-address SSD prefill opt-in by default
451 c 06-24 p1 v0 e0 s46 g0 q0 c39 h8/11 | Support SSD streaming for Q4_K routed experts on ROCm
443 c 06-21 p15 v0 e0 s4 g0 q0 c0 h7/7 | AGENTS.md rename (and server performance improvements?)
441 c 06-20 p9 v0 e0 s749 g0 q0 c2614 h8/8 | Major codebase refactor
420 o 06-16 p1 v0 e0 s0 g0 q0 c0 h8/8 | Metal: protect tensor alloc/free byte counters with a mutex
418 o 06-16 p1 v0 e0 s0 g0 q0 c0 h122/129 | Metal: FP8-packed compressed-KV cache + long-context memory optimizations
416 c 06-15 p1 v0 e0 s0 g0 q0 c0 h122/129 | Metal: FP8-packed compressed-KV cache + long-context memory optimizations
411 o 06-14 p1 v0 e0 s0 g0 q0 c0 h1/2 | Fix bug with impact on DeepSeek V4 Pro MTP Drafter usage
401 o 06-12 p4 v0 e0 s5 g0 q0 c0 h3/3 | Disaggregated Architecture for LLM Serving
399 o 06-11 p1 v0 e0 s0 g0 q0 c0 h7/7 | Add multi-column attn-out low projection kernel for small batches
396 o 06-11 p1 v0 e0 s2 g0 q0 c0 h10/11 | Add env-gated prompt-lookup speculative decoding for greedy generation
385 o 06-10 p1 v0 e0 s0 g0 q0 c0 h2/3 | Skip MTP probes while drafts go unused
383 o 06-10 p3 v0 e0 s1695 g0 q0 c1404 h149/152 | ds4_agent: fix rocm support
379 o 06-10 p3 v0 e0 s0 g0 q0 c2 h10/11 | feat: add runtime file discovery chain
371 o 06-09 p1 v0 e0 s0 g0 q0 c0 h5/8 | Add continuous depth-1 MTP speculation (DS4_MTP_CONTINUOUS)
363 c 06-08 p1 v0 e0 s0 g0 q0 c0 h7/7 | session payload: reject KV checkpoints saved against a different model/quant (v3 fingerprint)
353 c 06-07 p1 v0 e0 s0 g0 q0 c0 h1/1 | Avoid writing local KV cache payloads twice
351 c 06-07 p22 v0 e0 s3 g0 q0 c6 h31/33 | Add JACCL expert-parallel distributed inference
349 o 06-06 p1 v0 e0 s223 g0 q0 c226 h44/47 | Port CUDA SSD streaming support
347 o 06-06 p1 v0 e0 s0 g0 q0 c0 h6/6 | Remove hardcoded number of output groups and rank
343 c 06-06 p22 v0 e0 s1191 g0 q0 c1357 h36/37 | Local decode with distributed prefill
327 o 06-02 p3 v0 e0 s2 g0 q0 c0 h1/1 | checkpoint cache support with optional tail-cache
307 o 05-31 p1 v0 e0 s0 g0 q0 c0 h6/6 | bench: add routed expert locality profiler
306 c 05-31 p1 v0 e0 s0 g0 q0 c0 h19/19 | metal: simdgroup MMA mini-GEMM for decode MoE [experimental]
305 o 05-30 p1 v0 e0 s0 g0 q0 c4 h5/5 | cpu: add x86 AVX2/AVX512 SIMD fast paths for quantized MoE dot products
302 o 05-30 p13 v0 e2 s7 g8 q0 c4 h19/19 | Structured outputs (JSON etc.) via llguidance
295 c 05-30 p1 v0 e0 s0 g0 q0 c0 h6/6 | ds4: use shape macros for grouped attention output on the CPU path (fixes Pro on CPU)
292 c 05-30 p3 v0 e0 s2 g0 q0 c0 h1/1 | basic implementation of checkpoint based kv-cache
286 c 05-29 p1 v0 e0 s0 g0 q0 c1 h4/4 | metal: implement ds4_gpu_argmax_tensor (fix Metal build break)
282 o 05-28 p4 v0 e0 s17 g0 q0 c0 h45/54 | Teacher-Forced Directional Steering
281 o 05-28 p14 v0 e0 s9 g0 q0 c0 h92/100 | feat: add REAP-compact GGUF support
276 o 05-27 p2 v0 e0 s0 g0 q0 c6 h32/62 | Tune suffix decoding defaults for M5 Max Metal
274 o 05-27 p1 v0 e0 s0 g0 q0 c2 h2/2 | Add DS4_EMBED_KERNELS flag to embed Metal kernel sources into binary
265 o 05-27 p10 v0 e0 s0 g0 q0 c6 h93/99 | RFC: Planar3 KV-cache quantization for compressed attention (experimental)
261 o 05-26 p7 v0 e0 s0 g0 q0 c6 h32/76 | Add suffix-tree speculative decoding for repetitive/agentic generation patterns
241 o 05-24 p1 v0 e0 s0 g0 q0 c0 h2/2 | agent: resolve runtime assets from binary directory
239 c 05-24 p2 v0 e0 s0 g0 q0 c0 h22/22 | Add q4_K and AVX2 support for the CPU
218 c 05-21 p24 v0 e0 s0 g0 q0 c0 h60/68 | Add Q8 routed expert GGUF support
212 c 05-21 p1 v0 e0 s1 g0 q0 c0 h43/73 | [codex] Add bitlift sidecar runtime and eval tools
206 o 05-19 p1 v0 e0 s0 g0 q0 c0 h2/2 | mtp: make speculation disable skip draft work
203 c 05-19 p2 v0 e0 s0 g0 q0 c0 h20/27 | dir-steering: support up to 8 stacked direction vectors
195 o 05-19 p1 v0 e0 s0 g0 q0 c0 h1/1 | opt-in sampler-level repetition guard
187 o 05-18 p130 v0 e0 s481 g0 q0 c1713 h59/186 | Fast CUDA backend: vendored mmq matmul, VMM weight layout, speculative-decoding plumbing
184 c 05-18 p1 v0 e0 s0 g0 q0 c4 h24/30 | [codex] harden Metal failure recovery
181 c 05-17 p8 v0 e0 s2 g0 q0 c13 h10/10 | Add claude GitHub actions 1779008389951
169 c 05-16 p6 v0 e0 s0 g0 q0 c0 h26/32 | Metal: speed up M5 Max decode indexer
168 o 05-16 p2 v0 e0 s1 g0 q0 c2 h78/90 | Steering MoE LLMs via Expert (De)Activation
149 c 05-14 p2 v0 e0 s0 g0 q0 c0 h26/30 | Metal: correctness-gate M5 Max 4096 prefill (+5%)
148 o 05-14 p2 v0 e0 s0 g0 q0 c0 h7/7 | server: add tool-safe directional steering policy
124 c 05-14 p2 v0 e0 s13 g0 q0 c0 h53/57 | [codex] Add Metal TurboQuant KV cache
119 c 05-13 p1 v0 e0 s0 g0 q0 c0 h2/2 | flock: unlink lock file on release
111 c 05-13 p1 v0 e0 s0 g0 q0 c0 h8/15 | cancel prefill on client disconnect
106 c 05-12 p1 v0 e0 s0 g0 q0 c0 h9/9 | server: resolve asset paths relative to executable
92 o 05-12 p1 v0 e0 s0 g0 q0 c0 h1/1 | Fix Metal startup when default device is unavailable
83 o 05-12 p7 v0 e0 s16 g0 q0 c36 h87/107 | Pooling VRAM between Macs
82 c 05-11 p1 v0 e0 s0 g0 q0 c0 h2/2 | Fuse block-sum accumulation into `ds4_quantize_row_q8_K pass`
73 o 05-11 p1 v0 e0 s213 g0 q0 c0 h55/68 | fix(ds4): Implement MoE low-memory streaming to work around macOS's kernel bug.
72 o 05-11 p3 v0 e0 s0 g0 q0 c0 h45/47 | Sub 2bit iq1s down
67 c 05-11 p3 v0 e0 s19 g0 q0 c7 h4/12 | feat: multi-session pool with zero-wait switching between agents and context windows
66 c 05-10 p1 v0 e0 s0 g0 q0 c0 h1/1 | feat(server): cache system prompt as a reusable KV prefix
60 c 05-10 p4 v0 e0 s0 g0 q0 c2 h108/120 | feat(loader): support stock-recipe (Q8_0/F32) abliterated GGUFs end-to-end on Metal
59 c 05-10 p1 v0 e0 s0 g0 q0 c0 h7/7 | Fix external launcher startup paths
58 c 05-10 p2 v0 e0 s0 g0 q0 c0 h19/19 | fix(metal): infer model view overlap from tensors to support q4 on 192GB Macs
32 c 05-09 p1 v0 e0 s0 g0 q0 c0 h5/5 | Refactor SwiGLU kernel for improved clarity and stability
31 c 05-09 p1 v0 e0 s0 g0 q0 c0 h42/42 | Refactor FP8 quantization and related kernels
30 c 05-09 p1 v0 e0 s1 g0 q0 c0 h3/3 | Refactor concat kernel for improved readability
24 c 05-09 p11 v0 e0 s242 g0 q0 c0 h17/46 | Add experimental mlx-flash streaming mode
19 c 05-09 p1 v0 e0 s0 g0 q0 c0 h2/2 | feat: support quick instructions
15 c 05-08 p35 v0 e0 s0 g0 q0 c1 h209/227 | Add Metal 4 M5 prefill optimizations
```
