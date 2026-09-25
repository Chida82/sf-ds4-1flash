# Upstream PR registry

This file records which unmerged [antirez/ds4](https://github.com/antirez/ds4)
pull requests were reviewed for this child, up to which head commit, and the
verdict on their commits. A later review reads it to pick out only new PRs and
new commits on PRs already judged. The head SHAs record what was reviewed; they
are not a sync base. The base stays in git: the `sync-*` tags and
`git merge-base HEAD upstream/main`.

Last review: 2026-09-26

## Finding what changed

```sh
# new commits on a PR already analyzed (recorded head .. current head)
gh api repos/antirez/ds4/compare/<recorded-sha>...$(gh pr view <N> -R antirez/ds4 --json headRefOid -q .headRefOid) -q '.commits[] | .sha[0:7] + " " + (.commit.message | split("\n")[0])'
# PRs created or updated on or after the last review date
gh pr list -R antirez/ds4 --state all --limit 200 --search "updated:>=<YYYY-MM-DD>" --json number,title,state,headRefOid,updatedAt
```

If `compare` fails because the recorded head is gone (force push), list the
current commits and diff them by subject against the lines below:

```sh
gh pr view <N> -R antirez/ds4 --json commits -q '.commits[] | .oid[0:7] + " " + .messageHeadline'
```

Whether a commit already reached upstream is decided by patch, then by subject:

```sh
git fetch upstream && git fetch upstream pull/<N>/head
git cherry -v upstream/main FETCH_HEAD   # "-" = same patch in upstream/main
git log upstream/main --format=%s | grep -F "<subject>"   # "+" with a match = in main, modified
```

## Verdicts

| Verdict | Meaning |
|---|---|
| `adopt -> <change>` | the commit is ported in that change |
| `idea -> <change>` | the idea is used in that change, not the code |
| `drop` | not taken; the reason is recorded |
| `drop: output` | not taken because it changes output; the benefit given up is recorded |
| `history: <tag>` | no measurable effect on this machine today; the tag names the condition that would make it relevant |
| `next sync` | a correctness fix, taken at the next upstream sync, not in a perf branch |
| `superseded by <sha>` | another commit does the same thing |
| `already in main` | the same patch is already in main |
| `in main, modified` | the same work is in main as a different patch |
| `not reachable from V4.1` | the code is not reached by V4.1 on Metal |
| `docs` | documentation only |
| `merge` | a merge commit |
| `open` | useful, not yet assigned to a change |

`history` tags, combined with `+` when more than one applies:

| Tag | Condition that makes the work relevant |
|---|---|
| `disks` | more disks, or much faster I/O |
| `resident` | enough RAM to keep the main weights resident |
| `two-macs` | a second Mac (a TP pair or a pipeline split) |
| `chip` | a chip other than the M5 Max |
| `quant` | a Q4_K or MXFP4 GGUF |
| `long` | contexts of 128K tokens and above |
| `zone` | the code zone belongs to another PR; relevant if that PR is dropped |

A change that adopts or rejects a commit updates that commit's line in the same
branch. Effects written as "estimated" come from reading the code, not from a
measurement; the measuring change replaces them with its numbers.

Rejection rule: a commit that changes greedy output, or quantizes the KV cache
or activations, is `drop: output`, and its line records the benefit given up.

A PR gets a commit line for every commit that a later change, sync or review
acts on: `adopt`, `idea`, `drop: output`, `history`, `next sync` and `open`.
A PR whose single verdict covers every commit carries it in its row. All other
commits are summarized in their PR's row.

## Method

The 2026-09-25 review started from every PR ref of the repository:

| Stage | PRs | How |
|---|---|---|
| PR refs | 708 | `refs/pull/*/head` fetched into a scratch clone |
| unmerged | 669 | 440 open, 229 closed without merge (`merged_at == null`) |
| patches not in main (`0aaea5a`) | 664 | `git cherry main <head>` prints at least one `+` |
| touch engine files | 307 | the diff touches `ds4.c`, `ds4_metal.m`, `metal/*`, `ds4_engram.[ch]`, `ds4_deepseek41_gpu.h` or `ds4_gpu.h` |
| not dominated by other models or CUDA | 211 | `GLM + Qwen + CUDA <= 4 x (V4.1 + Engram + SSD + 2)`, hits as below |
| read commit by commit | 69 | chosen by hand from the 211, plus #1083 (CUDA-dominated, read as the successor of #1082) |

Hits count the changed lines of `git diff -U0 <merge-base> <head>` that match
`^[+-][^+-]`, with `*.csv *.json *.md *.txt *.svg *.png` left out, against each
pattern, ignoring case:

| Hit | Pattern |
|---|---|
| V4.1 | `ds41\|deepseek41\|dsv41\|flash41\|v4\.1\|v41` |
| Engram | `engram` |
| SSD | `stream\|ssd` |
| GLM | `glm` |
| Qwen | `qwen` |
| CUDA | `cuda\|\.cu\b\|hip\|rocm` |

Reachability was decided by two oracles: the pruned child itself (the function
named in each hunk header is looked up among the identifiers of the child's
`ds4*` and `metal/*` sources; a hunk in a function the child no longer has is
unreachable for V4.1) and call-site reading.

Sources of the columns below: the head analyzed is the one the review read;
title and state are from `gh pr view`; the commit count is
`gh api repos/antirez/ds4/compare/0aaea5a...<head> -q .ahead_by`, the commits
not in `0aaea5a`, merges included.

The re-triage of 2026-09-26 saw `upstream/main` still at `0aaea5a`. No head of
a read PR had moved. Of the eleven PRs updated since the review that were not
among the 211, four touch engine files and were read (#1125, #1126, #1127,
#1128); the other seven are classed under Excluded.

The working notes behind these verdicts, with the per-commit analyses, the
funnel's counts per candidate and the runtime size of each candidate commit,
are in the archived change `10-upstream-pr-intake`
(`openspec/changes/archive/*-10-upstream-pr-intake/`,
`review-notes-2026-09-25.md` and `triage-candidates-2026-09-25.md`). A
summary's `§n` names the section of those notes.

## PRs

| PR | Title | State | Head analyzed | Commits | Analyzed | Summary |
|---|---|---|---|---|---|---|
| #1128 | Metal: reject unsupported shapes in five kernels (BF16 partial blocks, head groups, visual mask, Qwen4 n_rot, tile maxima) | open | `fa7bc8a` | 5 | 2026-09-26 | `next sync` for the three guards that reach the child (see Commits); `d7b0b31` changes the vision patch-embedding rounding, so vision output is checked at that sync. The two Qwen4 indexer commits are not reachable. No speed effect |
| #1127 | Speed up callback-driven Metal prefill with layer overlap | open | `c71ca56` | 1 | 2026-09-26 | not reachable from V4.1: `metal_graph_prefill_layer_major` is called only from `ds4_session_eval_layer_slice`, and the overlap also requires `!ssd_streaming` |
| #1126 | Metal: resolve keep-alive pipeline before starting keep-alive threads | open | `242da6b` | 1 | 2026-09-26 | `next sync`: the default queue keep-alive thread, and the TP one, resolve their pipeline on their own thread against the non-thread-safe pipeline cache while the main thread compiles the first prefill's pipelines |
| #1125 | Metal: fix SSD-streaming expert cache slot leaks, in-flight recycling and prune hang | open | `6c41f9b` | 4 | 2026-09-26 | `next sync`: four fixes to the stream expert cache the child runs (see Commits). They touch the same functions as #952 `a2e2ea5` (`40-ssd-expert-reads` S1), which decides the port order when it starts |
| #1124 | Metal: parallelize fused FP8 KV max reduction | open | `e0b2093` | 2 | 2026-09-25 | not reachable from V4.1: the V4 Flash fused norm/RoPE/FP8 kernel, called only from the removed `metal_graph_encode_decode_layer_phase`; V4.1's `kernel_dsv41_quantize` already uses `simd_max` (§6) |
| #1123 | Metal: fix chunked-prefill SWA ring overflow and four latent kernel bugs | open | `4f9d0e8` | 5 | 2026-09-25 | `next sync`, keeping our deletions: none of the five fixes changes V4.1 output (§6) |
| #1120 | Specialize resident M5 Metal decode shapes | open | `b824ea6` | 5 | 2026-09-25 | `history: resident`: the V4.1 Q2 sum6 shape exists only in the resident kernels; streaming decode dispatches the slots6/addr/masked kernels. Porting the constants into the masked kernel would be exact and worth about 0.05% estimated (§8) |
| #1117 | Linux: read decode Engram rows in parallel, probing the page cache first | open | `144852e` | 1 | 2026-09-25 | not reachable from V4.1: Linux only; the Metal equivalent (16 dispatch readers) is in the child (§7) |
| #1090 | metal: speed up GLM Flash over 28% and DeepSeek V4.1 Flash over 50% on M3 Ultra | open | `849e039` | 6 | 2026-09-25 | `history: resident + chip`: every V4.1 path requires "Apple M3 Ultra", `!g_ssd_streaming_mode`, TP world 1 and mostly Q4_K experts, so it is inert here. Its router is the exact fix a #1042 port would need (`zone`); its server KV tool-map rewrite is `open` (§5) |
| #1089 | v4.1: rewind live sessions instead of rebuilding them | open | `f6639cf` | 1 | 2026-09-25 | `drop: output`: a rewound state equals "prefix then tail", not a fresh sweep (logits differ by 0.57-0.92). Given up: server multi-turn TTFT, a 21K turn measured 54.6 s -> 7.3 s on this machine; +640 MiB per session (§6) |
| #1083 | CUDA SSD streaming: hits-first expert launch, the Metal split's counterpart (+5 to +8 % decode) | open | `4c82792` | 2 | 2026-09-25 | not reachable from V4.1 (CUDA). Metal already has the counterpart: `ds4_gpu_stream_expert_split_worthwhile`, `begin_selected_load`, the masked address-table kernels (§7) |
| #1082 | CUDA SSD streaming: run the cached experts while the miss reads are in flight (+6 to +12 % decode) | closed | `5e46ff5` | 28 | 2026-09-25 | superseded by #1083 (wrong branch) (§7) |
| #1073 | Speed up DeepSeek V4.1 Flash on Metal | open | `3d3c83b` | 55 | 2026-09-25 | the chosen line for the decode glue zone. `adopt`: 2 -> `30`, 3 -> `60`, 6 plus their tests and refactors -> `70`; `idea`: 3 -> `60`; `drop: output`: 5, and the short sweep over token-major tails; `history`: 6 `two-macs`, 3 `quant`; 9 DSpark commits never; the rest drop, not reachable or `next sync` (see Commits). Claims are resident M3 Ultra (Q2 decode 19.8 -> 36.2 t/s); here about +5-9% decode estimated for the glue, bitwise on M5 unproven (§4) |
| #1067 | Metal V4.1 decode: one command-buffer wait per token, Engram reads on threads | open | `dceba87` | 5 | 2026-09-25 | `history: resident`: the flush (also `chip`: pre-M5 only) and the batched decode require `!streaming` (see Commits); `d1738d2` is `open`. Claims 17.9 -> 26.1 t/s resident Q4 (§3) |
| #1061 | metal: decode-shaped V4.1 indexer kernels for long contexts | open | `6856a23` | 1 | 2026-09-25 | `drop: output`: MMA decode scorer with a different f32 summation order. Given up: about 1-3 ms per token at 32K, 5-12 ms at 128K, estimated. A bitwise rewrite is possible: keep `score_one_direct`'s reduction, stream many rows per simdgroup (§6) |
| #1060 | metal: radix-select top-k for the V4.1 indexer | open | `be6a8ce` | 1 | 2026-09-25 | `drop: output`: differs from the bitonic network on tied scores (set and order). Given up: under 1 ms per token at 32K, 2-4 ms at 128K, estimated; measured on this machine at 435K (§6) |
| #1056 | Metal: optimize Qwen3.8 kernels, MTP state and SSD MoE scheduling (Up tp 40%) | open | `b1af94b` | 30 | 2026-09-25 | not reachable from V4.1: its SSD commits are Qwen-gated; the eviction-plan idea would trim only prefill seeding, under 1% (§7) |
| #1049 | perf(v41): reuse gathered KV across scalar reuse layers | closed | `0c5fa64` | 3 | 2026-09-25 | `history: resident`: `0c5fa64` requires `!g->streaming`; closed by its author at +0.79% on top of #1041. The other two commits are #1041's (§3) |
| #1043 | metal: Q4_K group-6 expert table by default for DeepSeek V4.1 Flash (+2.3% decode on M3 Ultra, greedy-identical) | open | `0e48ed8` | 1 | 2026-09-25 | `history: quant`: the group-6 table needs Q4_K gate and down, and `!g_ssd_streaming_mode` (§6) |
| #1042 | v41: fuse the single-box decode glue (HC, MoE, attention): +20% on M3 Ultra on top of #1041, bit-exact | open | `6e92e92` | 7 | 2026-09-25 | `history: zone`: the glue zone goes to #1073's line, one PR per zone. As submitted it is not exact against `0aaea5a` (stale softplus, #832's tie order) and M5 is untested; a port would need #1090's router and hardening (see Commits). About +3-6% decode estimated here (§5) |
| #1041 | v41: queue single-box decode layers and commit each without waiting (+37% decode on M3 Ultra, bit-exact) | open | `fdbf7f2` | 2 | 2026-09-25 | `adopt` `bd6f912` -> `30-decode-layer-queue`, with two scope fixes; `fdbf7f2` is `history: resident`. Measured on M2 Ultra Q2 SSD 10.64 -> 12.08 t/s; about +4-8% decode estimated here (§3) |
| #1035 | engram: parallelize DeepSeek V4.1 Flash decode reads on macOS | open | `ce0c537` | 5 | 2026-09-25 | superseded by `6c00e2d` + `077a257`: main reads with 16 dispatch workers; its hook would only fire in `ds41_graph_step_batch`, which streaming never runs (§7) |
| #1034 | metal: reduce decode synchronization for DeepSeek V4.1 Flash SSD streaming | open | `0a21d1a` | 3 | 2026-09-25 | `adopt` `9b50495` -> `30-decode-layer-queue`, test and bench flag only: its queue is `bd6f912`'s without the flush, opt-in. `7a18d09` not needed, `0a21d1a` docs. Measured M2 Ultra Q2 SSD 10.17 -> 11.32 t/s (§3) |
| #1033 | metal: add opt-in slab residency for DeepSeek V4.1 Flash （M2 192GB 0.25tk/s -> 13tk/s) | open | `36aecab` | 5 | 2026-09-25 | `adopt` `66f757b` -> `40-ssd-expert-reads`, only if a per-submission delay is measured first (§7). The other four commits are merges, a bench and docs |
| #1027 | Make BPE merging O(n log n) for large CJK pieces | open | `ee2e3a8` | 1 | 2026-09-25 | `next sync`, but #873 is preferred: the same fix, smaller, no env switch; this one calls `getenv` per piece and advertises a `DS4_BPE_VERIFY` that does not exist (§6) |
| #1010 | kv-cache: lazy-grow compressed KV caches instead of full-ctx up front | open | `c39be7b` | 1 | 2026-09-25 | not reachable from V4.1: CPU cache and generic `metal_graph_*` only; `ds41_graph_alloc` is untouched. A lazy-growth port would be an idea for 1M contexts only (§6) |
| #959 | metal: prune top-k argsort merge rounds to top_k | open | `b4605a0` | 3 | 2026-09-25 | `history: long`: `4b9ff60` is exact and covers the non-causal merge V4.1 decode uses; about 0.1 ms per token at 32K, 1 ms at 128K, estimated (see Commits) (§6) |
| #957 | fix(metal): coalesce adjacent --layers model map spans | open | `f22be7b` | 1 | 2026-09-25 | `drop`: rewrites the map function the V4.1 SSD initial map, the streaming prefill map and the TP shard map share, on a base that predates `660e1d4`'s view-lifetime handling (§6) |
| #954 | metal: pre-M5 optimizations — +3.65% MXFP4 prefill on M3 Ultra | open | `1b57506` | 21 | 2026-09-25 | not reachable from V4.1: MXFP4, pre-M5 gates or the old graph; `0c2a0d5` is `history: chip` (see Commits) (§8) |
| #952 | AProjQ4: imatrix-guided Q4_K attention and GPU runtime optimizations | open | `e9cc3d7` | 94 | 2026-09-25 | based on `0aaea5a`, with V4.1-specific SSD commits. `adopt` `a2e2ea5` -> `40`; `idea` `a3043bb` -> `50` (early load only), `bac91c2` + `c12d639` -> `60`; six small fusions `history: zone`; `2c9d48f` `next sync` (see Commits). The Q4_K attention itself is `quant` (§8) |
| #947 | Withhold the automatic Metal 4 tensor enable on M5 until accumulate parity | closed | `a11bf74` | 1 | 2026-09-26 | `drop`: closed upstream. Main keeps the tensor route on M5, V4.1 prefill dispatches the `_mpp_packed` kernels on it (§8), and the parity oracle runs on it; its drift claims were on GLM-5.3-Q2 |
| #902 | M2 Ultra benchmark + whitelist it for two pre-M5 fusion paths | open | `3a84f40` | 3 | 2026-09-25 | `drop`: an M2-only whitelist (§8) |
| #874 | Tune the Metal backend for M3 Ultra | open | `d06eba3` | 11 | 2026-09-25 | `history: resident` for `595e06d`, the only device-agnostic commit (see Commits); the rest is V4 Flash, FP8 KV and M3 Ultra work (§8) |
| #873 | tokenizer: fix bpe_emit_piece's O(n^2) merge loop (#853) | open | `142d95b` | 1 | 2026-09-25 | `next sync`, preferred over #1027: the same heap BPE with ties broken as before, so tokens are identical; `bpe_emit_piece` is on the V4.1 tokenization path (§6) |
| #864 | metal: speed up IQ2_XXS MoE prefill with half LUT and split MPP | open | `482e246` | 1 | 2026-09-25 | `idea` -> `60-prefill-sweeps`, the IQ2_XXS half LUT only; the split MPP is `drop: output`. Claim: V4 Flash resident M5 Max +5-8% prefill (see Commits) (§8) |
| #852 | metal: keep TP gate waits out of compute command buffers | open | `e01e215` | 1 | 2026-09-25 | `next sync`: a TP multi-session watchdog fix that applies under server session batching; the patch is 296 commits behind main and predates the poll gates, so it is not hand-ported (§3) |
| #850 | metal: scale default prefill chunk with prompt length | open | `7e8fd8b` | 1 | 2026-09-25 | not reachable from V4.1: `ds4_effective_prefill_chunk` is gone; V4.1 overrides `prefill_cap` (§7) |
| #849 | ssd streaming: router-lookahead expert prefetch, +5.2% on top of #848 (output byte identical) | open | `9b4bb9e` | 2 | 2026-09-25 | `idea` `60051d4` -> `50-ssd-miss-overlap`: as written it is inert on V4.1 (F16 routers only, relies on hash layers); a port needs the F32 router and drops the GLM and hash-layer parts. Measured +5.2% only on top of #848, -5.5% without it (see Commits) (§7) |
| #848 | ssd streaming: packed expert file, +10.7% on DeepSeek V4 Flash (output byte identical) | open | `1bc2fac` | 1 | 2026-09-25 | `drop`: the packer frees the GGUF's expert space that V4.1 prefill still maps through mmap, so it would compute on zeros; its gain came with a higher average read time and likely a fragmented baseline (§7) |
| #846 | metal: M1-class decode tuning, n-gram speculation, and batch-verifier groundwork | open | `8b08c21` | 1 | 2026-09-25 | `drop`: M1-only gates; the n-gram speculation needs a verifier the child does not have (§8) |
| #832 | metal: canonical top-k order + exact streaming top-512 selector | open | `eb2e545` | 9 | 2026-09-25 | `drop`: the canonical comparator reaches V4.1's non-causal sorts and breaks the invariant that decode and batch ids match; stream512 is unreachable; four commits are patch-identical to #830/#831 (§6) |
| #831 | metal: register-blocked, K-register-resident indexer prefill scorer (tiled4+tiled5) | open | `f7ad40c` | 5 | 2026-09-25 | not reachable from V4.1: the V4 Flash pre-M5 tiled scorer (§6) |
| #830 | metal: wide-tile indexer prefill scorer over half-packed Q/K (bit-exact, +4.7% prefill at 64k) | open | `55b7103` | 1 | 2026-09-25 | superseded by #831: its only commit is #831's first (§6) |
| #828 | metal: non-blocking GPU stage timestamps behind DS4_METAL_GPU_STAGE_TIMESTAMPS | open | `3add8f9` | 3 | 2026-09-25 | `open`: a diagnostic, off by default (see Commits). In SSD mode the buffers committed inside the routed MoE are untagged, so every committed buffer must be tagged while the probe is on (§3) |
| #822 | perf: optimize resumed streaming prefill boundaries | open | `b26a33c` | 1 | 2026-09-25 | not reachable from V4.1: its `metal_graph_prefill_*` and `test_engine_mgpu_placement.c` are gone (§7) |
| #798 | fix DeepSeek SSD and DSpark integration | open | `fb285af` | 3 | 2026-09-26 | `drop`: a DSpark change. Its SSD admission ledger (`ds4_ssd.c`) exists to budget the DSpark support GGUF under streaming; the child has no speculative decoding, and the remaining hunks sit on an August base |
| #782 | metal: lightning-indexer-organized DS4 indexer scorer (llt) | open | `d5c8fd0` | 1 | 2026-09-25 | not reachable from V4.1: V4 Flash 64-head scorers, and its prefill was measured not exact. Its decode layout is an idea for a bitwise rewrite of #1061 (§6) |
| #778 | dspark: fold first-token forward into verify + bit-exact M5 Metal decode wins | open | `d81a28f` | 3 | 2026-09-25 | not reachable from V4.1: DSpark, and HC-spread fusions only in the removed `metal_graph_encode_decode_layer_phase`; `c813ff1` is #777 (see Commits) (§8) |
| #777 | metal: fix staged B-tile tensor extents in the mm_id mpp kernel | open | `9cb0271` | 1 | 2026-09-25 | `next sync`: bit-identical; the swapped extents compile identically while NR1 = NK = 32, so it is a no-op today (§6) |
| #770 | metal: gate the M3-class fusion whitelists on the pre-M5 predicate | open | `dfea3a7` | 1 | 2026-09-25 | `drop`: the predicate swap changes nothing on "Apple M5 Max" (§8) |
| #758 | metal: accelerate M5 Max indexed prefill | open | `e154aa8` | 1 | 2026-09-25 | `adopt` -> `60-prefill-sweeps`, the rb16 hunk only, ported by hand: V4.1 prefill dispatches `heads16_dual`, rb16 is bitwise, fused512 is unreachable. Claim: V4 Flash resident, attention stage -11%, prefill +2.9% (see Commits) (§6) |
| #743 | metal: add optional polled release fence for the TP gate (~23% decode gain with `--tensor-parallel`) | closed | `0dcbfbc` | 1 | 2026-09-25 | superseded by `1a976b7`, main's default bounded GPU poll release (§3) |
| #739 | cuda: retain routed experts in bounded cache | open | `05632d2` | 3 | 2026-09-25 | not reachable from V4.1 (CUDA): the Metal cache already has per-(layer, expert) entries with decayed hotness and an LRU tie-break (§7) |
| #738 | cuda: overlap streamed expert uploads with compute | open | `e747490` | 2 | 2026-09-25 | not reachable from V4.1 (CUDA): unified memory has no upload step (§7) |
| #725 | ssd: enforce streaming cache floor at one-prefill minimum | open | `d7716f5` | 1 | 2026-09-25 | `drop`: a 240-slot floor; the cache here holds about 8090 slots (§7) |
| #647 | cuda: implement real per-(layer,expert) LRU for --ssd-streaming-cache-experts | open | `ab98473` | 4 | 2026-09-25 | not reachable from V4.1 (CUDA) (§7) |
| #621 | Support AProjQ4 GGUFs: Q4_K dense attention projections; Metal, ROCm and CUDA performance improvements; SSD streaming support for speed-bench; quality-of-life improvements; bugfixes | closed | `6a20b13` | 189 | 2026-09-25 | superseded by #952, except its SSD-read commits: `adopt` `8f5a745`, `f7695ea` -> `40-ssd-expert-reads`; `61e35e2` `open` (see Commits) (§8) |
| #570 | metal: pread pool dispatch stats and IO-tier pinning for streaming experts | open | `66ca6ef` | 2 | 2026-09-25 | `adopt` `a1afb82` -> `40-ssd-expert-reads` (pool queue depth and GB/s in the timing summary); `66ca6ef` `drop` (see Commits) (§7) |
| #559 | Add opt-in fused Q2 down-sum kernel | closed | `3d185ea` | 1 | 2026-09-25 | `drop`: atomic float adds in a nondeterministic order; the simdgroup path it changes is unused on M5 (§8) |
| #555 | Optimize Metal prefill and decode on all Apple Silicon chips | closed | `97efe60` | 3 | 2026-09-25 | already in main (`427e281`): its M5 part already runs in V4.1 prefill (§8) |
| #533 | metal: stop expert-miss readahead racing the pread pool (+13% GLM streaming decode) | closed | `20df520` | 3 | 2026-09-25 | `drop`: withdrawn; turning off the miss read-ahead by default regressed main's prefill. The question it raises is answered without code by `DS4_METAL_DISABLE_STREAMING_EXPERT_READAHEAD` in `40`'s switch sweep (§7) |
| #514 | Add sidecar for speed up ssd streaming | closed | `40d8de2` | 17 | 2026-09-25 | `drop`: closed by its author as useful only on low-RAM machines; its Q4 knobs drift tokens (§7) |
| #499 | Opt-in mlock of non-routed weights for SSD streaming (DS4_MLOCK_NONROUTED) | open | `d6a800e` | 1 | 2026-09-25 | superseded by `22e4172`: the static weights are already locked (9.37 GiB) (§7) |
| #464 | Fix slow decodes "poisoning" sleep times when using power throttling | open | `5e86cc4` | 2 | 2026-09-25 | not reachable from V4.1: it refuses `--power` below 100 (§7) |
| #454 | Metal: keep selected-address SSD prefill opt-in by default | closed | `356b450` | 1 | 2026-09-25 | not reachable from V4.1: `ds41_moe_batch` passes `force_resident = true`, so prefill never takes the batch selected-address path (§7) |
| #420 | Metal: protect tensor alloc/free byte counters with a mutex | open | `0bf5938` | 1 | 2026-09-25 | already in main (`d75e23d`): the counters sit under `g_tensor_mu` (§6) |
| #418 | Metal: FP8-packed compressed-KV cache + long-context memory optimizations | open | `2c54713` | 1 | 2026-09-25 | not reachable from V4.1: old-graph KV code, and its FP8 store is lossy; V4.1's compressed KV is already FP4/FP8 (§8) |
| #399 | Add multi-column attn-out low projection kernel for small batches | open | `1327f3a` | 1 | 2026-09-25 | `drop`: only 2-8-token prefill chunks, not bitwise; multi-session batching is refused under streaming (§6) |
| #307 | bench: add routed expert locality profiler | open | `e5455bb` | 1 | 2026-09-25 | not reachable from V4.1: CPU-only hooks; the Metal `DS4_EXPERT_PROFILE` is wired only into the old `metal_graph` path (§7) |
| #306 | metal: simdgroup MMA mini-GEMM for decode MoE [experimental] | closed | `6bfe54f` | 1 | 2026-09-25 | `drop`: measured slower on M5 Max, 30.1 -> 14.6 t/s (§8) |
| #169 | Metal: speed up M5 Max decode indexer | closed | `41cf971` | 6 | 2026-09-25 | `drop` (in main, modified): M5 support landed differently; its decode top-k 512 -> 8 changes output (§6) |
| #149 | Metal: correctness-gate M5 Max 4096 prefill (+5%) | closed | `b111079` | 2 | 2026-09-25 | superseded: the scratch change is in main, chunk sizing is now `ds41_prefill_limit`, and its barrier removal touches legacy kernels only (§8) |
| #73 | fix(ds4): Implement MoE low-memory streaming to work around macOS's kernel bug. | open | `c5d6349` | 1 | 2026-09-25 | `drop`: CPU `--low-mem` on a May base (§7) |
| #24 | Add experimental mlx-flash streaming mode | closed | `c20e478` | 11 | 2026-09-25 | `drop`: predates SSD streaming; rejected upstream (§7) |
| #15 | Add Metal 4 M5 prefill optimizations | closed | `b109d85` | 35 | 2026-09-25 | in main, modified: squashed as `63ceed6`; the routed-MoE TensorOps were removed (`d4fba7b`) and rebuilt as the packed kernels (`2ea3839`, `bd66c40`) (§8) |

## Commits

### #1128 (head `fa7bc8a`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `d7b0b31` | Use the BF16 mat-vec kernel when in_dim is not a multiple of 16 | next sync | `ds4_gpu_glm53_matmul_bf16` serves the V4.1 vision encoder; the mat-vec bounds the row read. It changes the patch-embedding rounding, so vision output is compared at that sync; text output is untouched |
| `82ffb0c` | Reject partial head groups in indexed mixed-batch attention | next sync | a latent guard on `ds4_gpu_attention_indexed_mixed_batch_heads_tensor`; V4.1's head counts are multiples of 8 |
| `3cbbb19` | Reject visual masks with more raw keys than positions | next sync | a latent guard on `ds4_gpu_fill_visual_mixed_batch_mask`, which vision prefill reaches |

`ad14a5f` and `fa7bc8a` patch the Qwen4 indexer, which the child does not have.

### #1126 (head `242da6b`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `242da6b` | Resolve the keep-alive pipeline before starting keep-alive threads | next sync | `ds4_gpu_queue_keepalive_start` runs by default after the model view warm-up; the race is a crash, not a speed change |

### #1125 (head `6c41f9b`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `a0fe413` | Return streamed-expert slab slots on every load error path | next sync | a lost slot shrinks the cache for the rest of the process |
| `2cf7986` | Mark GPU-copy expert entries in flight until their blit runs | next sync | the default path: prefill seeds the cache through `seed_experts_gpu_copy`; an idle-looking entry could be recycled before its blit ran |
| `a6fc294` | Keep per-layer expert cache counts in sync with live entries | next sync | `clear_layer` forced the count to 0 with in-flight entries still live, and the victim scans drifted |
| `6c41f9b` | Skip in-flight entries when pruning the global expert cache | next sync | `prune_global` could pick an in-flight entry forever and hang decode |

### #1123 (head `4f9d0e8`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `a54b5b0` | Keep chunked prefill within the SWA ring capacity | next sync | patches `metal_graph_prefill_chunked_range`, which the child deleted: keep the deletion. V4.1's `raw_prefill` holds `prefill_cap + 128` rows and a chunk never exceeds `prefill_cap` |
| `04b6423` | Derive HC expand barrier target from the arrival index | next sync | kept layer-slice code; merges cleanly |
| `afab7d6` | Skip pair-swiglu MoE matmul for any split TP world | next sync | a no-op with a TP world of at most 2 |
| `b354216` | Fix IQ2_XXS pair-swiglu gate/up row indexing | next sync | resident dumps only |
| `4f9d0e8` | Zero unused scratch lanes in FP8 KV quantize amax reduction | next sync | kept layer-slice code; merges cleanly |

### #1090 (head `849e039`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `d975878` | metal: fuse resident DeepSeek V4.1 decode on M3 Ultra | history: zone + resident + chip | its select-only router replicates the bitonic network exactly, ties and padding included, with the current softplus: the fix a #1042 port needs. The HC norm and shared-expert parts are #1042's subset; the histogram top-k needs GLM kernels; the Q4 tail cull and the M3 Ultra queue are inert here |
| `d3d6f6c` | metal: pipeline V4.1 decode and enforce exact fallback behavior | history: resident + chip | the pipeline is M3 Ultra resident only. Its hardening (runtime clamp and width arguments, a zero-safe collapse, fallback instead of failure, edge-value tests) goes with any #1042 port; the Engram overlap is negligible |
| `34794be` | glm: refine exact routing and preserve literal tool checkpoints | open | GLM routing is not reachable; its server KV tool-map rewrite is reviewed separately |

`06ba1c5` and `3cba8f0` are GLM (not reachable); `849e039` is docs. Both #1090
and #1042 define `kernel_dsv41_mul_mv_q8_0_f32_bf16`, in different files.

### #1073 (head `3d3c83b`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `2a281b0` | Queue DeepSeek V4.1 decode layers on a single node | adopt -> `30-decode-layer-queue` | the variant measured against #1041's `bd6f912`: flushes after layer 0 and every second layer; `engram_rows_b` removes the layer-13 drain on one box. Low, +1-3% estimated |
| `29ce271` | Give DeepSeek V4.1 prefill rows their own second Engram table | adopt -> `30-decode-layer-queue` | taken with `2a281b0`: fixes the fallback when `DS4_METAL_DISABLE_V41_BATCH_HC` is set |
| `1011874` | Publish DeepSeek V4.1 ratio-1 keys in batches on Metal | adopt -> `60-prefill-sweeps` | layer-20 key publication batched through the exact-rows F16 projection; exact per its unit tests |
| `3b7f8f2` | Select every key for short DeepSeek V4.1 index rows | adopt -> `60-prefill-sweeps` | select-all for rows with at most 512 visible keys; exact per its unit tests |
| `ce5a812` | Select DeepSeek V4.1 candidate blocks in batches | adopt -> `60-prefill-sweeps` | applies only above 16K, so it is judged on the guard prompt |
| `ccbf2c0` | Run the DeepSeek V4.1 decoder suffix from 2541 tokens | idea -> `60-prefill-sweeps` | with `64240fb` and `798c64f`: one sweep instead of two for 3072-8191-token prompts, taken only where main would already batch the tail (bitwise). Its change over token-major tails is `drop: output` |
| `64240fb` | Prefill DeepSeek V4.1 prompts under 8192 tokens on the plain schedule | idea -> `60-prefill-sweeps` | see `ccbf2c0` |
| `798c64f` | Round a short DeepSeek V4.1 sweep down only for a token-major tail | idea -> `60-prefill-sweeps` | see `ccbf2c0` |
| `e768396` | Skip DeepSeek V4.1 candidate selection while every block is kept | adopt -> `70-decode-glue-fusions` | up to 2048 blocks the filter is the identity: exact |
| `4fbbc4a` | Encode the DeepSeek V4.1 vocabulary head before the last decode drain | adopt -> `70-decode-glue-fusions` | the head part only: one buffer round trip less per token. Its short-sweep half was reverted and redone in `64240fb`/`798c64f` |
| `edceb7a` | Select DeepSeek V4.1 experts in one dispatch | adopt -> `70-decode-glue-fusions` | `kernel_dsv41_router_one` with main's softplus; must match the bitonic order on ties, tested with forced ties |
| `d95f8b6` | Round DeepSeek V4.1 activations inside the producing kernels | adopt -> `70-decode-glue-fusions` | BF16 rounding folded into the Q8_0 matvec, RMS norm, HC sum/expand and rope; about 8 dispatches per layer |
| `1923131` | Match the rope contraction of the DeepSeek V4.1 fused rope-quantize store | adopt -> `70-decode-glue-fusions` | explicit `fma` matching `kernel_dsv41_rope`; compiler dependent, with a bitwise unit test |
| `d8d1523` | Speed up DeepSeek V4.1 Metal decode and run DSpark verify rows on its kernels | adopt -> `70-decode-glue-fusions` | the non-DSpark subset, ported by hand: about 59 -> 17 dispatches per layer, asynchronous Engram start/finish. Above 800 lines, so at least +1.5% decode; dropped if the fusions cannot be separated from the DSpark code |
| `a3f6f31` | Port the decode-control regression test and fix its router batch call | adopt -> `70-decode-glue-fusions` | the `--decode-switch` harness, run with `--ssd-streaming` |
| `c6f4086` | Fold the DeepSeek V4.1 RoPE quantize test into the Metal test | adopt -> `70-decode-glue-fusions` | test, taken with the port |
| `0ac42d6` | Tidy the DeepSeek V4.1 comments and switches | adopt -> `70-decode-glue-fusions` | only the hunks the port needs |
| `8be1005` | Fold the one-row DeepSeek V4.1 entry points into their rows form | adopt -> `70-decode-glue-fusions` | only the hunks the port needs |
| `a15028e` | Round DeepSeek V4.1 vectors with the shared bf16 helper | adopt -> `70-decode-glue-fusions` | only the hunks the port needs |
| `4b1b151` | Score DeepSeek V4.1 index keys with one thread per key on Metal | drop: output | a different reduction; top-2048 can flip at near-ties. Given up: medium at 8K keys and above, estimated |
| `af7c02b` | Select DeepSeek V4.1 index candidates with a radix select on Metal | drop: output | ties by ascending id, and many scores tie at 0 after ReLU. Given up: medium at 16K keys and above, estimated |
| `262b4a6` | Multiply DeepSeek V4.1 verify rows through simdgroup matrices | drop: output | "rounds a few outputs differently"; built for DSpark verify. Nothing given up single-session |
| `a6b50ff` | Multiply the DeepSeek V4.1 shared expert and attention output rows through simdgroup matrices | drop: output | as `262b4a6` |
| `7da9535` | Sync idle server slots in the engine's prefill chunk | drop: output | `--batched-sessions` only: 2048 -> 8192 quanta change the chunking numerics. Given up: 4x fewer sweeps in batched server mode |
| `9f3892d` | Write DeepSeek V4.1 tensor-parallel partials into the slab slot and bind once | history: two-macs | TP pair only |
| `a13b513` | Split the DeepSeek V4.1 shared expert across the tensor-parallel ranks | history: two-macs | TP pair only |
| `867465c` | Fold the DeepSeek V4.1 tensor-parallel gate sums into the hyper-connection expand | history: two-macs | TP pair only |
| `c9bfdcc` | Release DeepSeek V4.1 tensor-parallel decode gates inside the command buffer | history: two-macs | TP pair only |
| `8387625` | Drop the DeepSeek V4.1 tensor-parallel gate trace | history: two-macs | TP pair only |
| `4fe6a78` | Guard the DeepSeek V4.1 tensor-parallel flag folds for non-Apple builds | history: two-macs | TP pair only |
| `d744ebb` | Run Q4_K DeepSeek V4.1 experts on the compact resident tiles | history: quant | Q4_K, pre-M5, resident |
| `5432223` | Keep the resident Q4_K expert tiles to the DeepSeek V4.1 shape | history: quant | Q4_K, pre-M5, resident |
| `e49643f` | Run the DeepSeek V4.1 shared expert beside the routed experts on Metal | history: quant | MXFP4, resident |
| `5c2dac7` | End the tensor parallelism bind line | next sync | a log newline |

The other commits: the nine DSpark commits (`a60edc6`, `c674b19`, `1e3bcf8`,
`bd85ba6`, `b7bcccd`, `1c69206`, `fd70919`, `258ad33`, `66dff86`) are never
taken, `66dff86` matters only for reaching the head state of `d8d1523`;
`8d73a0e` is `drop` (turns off `tp_shard`, breaking the 2 x 128 GB layout);
`dc81436` is not reachable (Q4/MXFP4 fallback); `7d89c59` is `drop` (test
plumbing for `4b1b151`'s scorer); `c4b66b9` is `drop` (the function it
deletes is already gone from the child); the quantizer commits `c016ea7`,
`0b2d6e2`, `b3d4a26` and the docs `aea1a0b` are not applicable; `ed43e1a`,
`2a55193`, `9219757` are CUDA; `3d3c83b` is a merge.

### #1067 (head `dceba87`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `6f7319c` | Metal V4.1 decode: flush command buffers every few layers instead of waiting per layer | history: resident + chip | `ds41_decode_queue_enabled` requires `!streaming` and a pre-M5 chip. Its separate Engram buffer per table removes only the layer-13 drain, one wait in streaming |
| `fd6dca4` | Metal V4.1 decode: read both Engram tables on reader threads while the GPU runs layer 0 | history: resident | the reader concurrency is already in main; what is left, both tables overlapped with the layer-0 encode, is under 0.5 ms per token estimated. Its original join at the first flush was unsafe; `dceba87` fixes that |
| `d1738d2` | Metal V4.1 decode: allocation-free pipeline lookup for the plain getters | open | the fast-lookup cache exists in the child but only the mul_mv getters use it; measure the CPU encode time first with `DS4_METAL_CB_TIMES` |

`2f59c4e` is `drop` (pre-M5 only, measured neutral, and it pushes int and bf16
payloads through the f32 copy kernel); `dceba87` is not reachable (streaming
sessions are never batched).

### #1042 (head `6e92e92`)

Every line is `history: zone`; the per-commit notes say what a port would take
if #1073's line were dropped.

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `b43fcce` | v41: fuse the decode hyper-connection glue (19 -> 6 dispatches per layer) | history: zone | needs an M5 test with zero and -0 residual rows; about 13 dispatches and 1 blit per layer |
| `c1bd531` | v41: fuse the decode MoE glue (router + select, shared expert, FFN tail) | history: zone | the shared-expert part is fine; the router has a stale softplus and #832's tie order; the tail is superseded by `f61a83d` |
| `d6a34d6` | v41: single-dispatch router select on M5 only; matvec + one select group | history: zone | default on this target, never run on M5; last-arriving-threadgroup pattern |
| `5b8b6ac` | v41: separate rollback switches for the router and shared-expert fusions | history: zone | needed for any A/B |
| `bc62855` | v41: expand4 can fold the routed + shared sum; early-down diagnostic | history: zone | superseded by `f61a83d` |
| `f61a83d` | v41: fuse the decode attention glue; shared down before the routed experts | history: zone | BF16 on store for Q8_0/F16; q/kv norm + KV RoPE + FP8 + window store 6 -> 1; logits collapse 4 -> 1 |
| `6e92e92` | v41: MoE fuse test compares ties to the canonical order only | history: zone | would be `drop`: it hides the tie divergence |

### #1041 (head `fdbf7f2`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `bd6f912` | v41: queue single-box decode layers and commit each without waiting | adopt -> `30-decode-layer-queue` | extends main's TP-only `queue_layers` to one box and flushes after every non-drain layer; on by default, with `DS4_METAL_DISABLE_V41_DECODE_QUEUE` and `_FLUSH` rollbacks. Two fixes: the queue is off when `layer_resident` (`--quality --ssd-streaming` otherwise fails at layer 1), and the flush is limited to `tp_world == 1`. About 81 -> 43 waits per token |
| `fdbf7f2` | perf(v41): queue resident decode through the logits tail | history: resident | `whole_token` requires `!g->streaming`; +1.4% resident on M3 Ultra |

### #1034 (head `0a21d1a`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `9b50495` | DeepSeek V4.1 Flash: queue bounded single-host Metal SSD decode | adopt -> `30-decode-layer-queue` | test and bench flag only: `check_stream_decode_queue` (two sessions on a 512-expert cache force eviction; logits, Engram history and state compared bitwise) and the `--ssd-streaming` flag of `metal_decode_schedule_bench`, retargeted to #1041's switch names. The queue code itself is `bd6f912`'s without the flush, opt-in |

`7a18d09` (an `__APPLE__` guard merge) is not needed; `0a21d1a` is docs.

### #1033 (head `36aecab`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `66f757b` | Metal: opt-in owned slab residency for DeepSeek V4.1 Flash | adopt -> `40-ssd-expert-reads` | only if `DS4_METAL_CB_TIMES` shows a per-submission delay: `DS4_METAL_STREAMING_SLAB_RESIDENCY=1` adds each slab to a residency set attached to the queue. Measured M2 Ultra 192 GB with a 135 GiB pool: 0.24 -> 9.31 t/s; our pool is the same share of RAM as their 104 GiB case, but at 6 t/s there is no full cliff here. Stays opt-in until measured |

### #959 (head `b4605a0`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `4b9ff60` | metal: prune top-k argsort merge rounds to top_k | history: long | exact: the first k outputs of a stable merge depend only on the first k of each run. Non-causal path only; main's causal path already caps reads at 512 |
| `e8c84dd` | tests: Metal top-k argsort correctness test | history: long | its test |
| `b4605a0` | metal: factor merge-round dispatch helper | history: long | an optional refactor |

### #954 (head `1b57506`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `0c2a0d5` | metal: speed up pre-M5 decode and short prefill | history: chip | its `attn_out_low` static trip matches V4.1's shape but is pre-M5 gated |

### #952 (head `e9cc3d7`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `a2e2ea5` | Recover partial Metal SSD cache reservations on worker failure | adopt -> `40-ssd-expert-reads` | fixes loading into a full cache: the service thread waiting on GPU work, allocation past the budget, a non-atomic `done_seq`, lost slab slots. No arithmetic change. Overlaps #1125 in the same functions |
| `a3043bb` | Optimize V4.1 Metal attention and overlap SSD expert loading | idea -> `50-ssd-miss-overlap` | the early-load part only: miss reads start right after routing, overlapping the shared expert, through the GLM-named producer `ds4_gpu_glm_stream_expert_cache_begin_selected_load_tensor` that the child removed. Its BF16-with-RoPE fusion belongs to the `70` zone. Measured M1 Max 2.43 -> 2.44-2.50 t/s |
| `bac91c2` | Accelerate V4.1 Metal SSD prefill with explicit expert buffers | idea -> `60-prefill-sweeps` | each layer's experts preread into two locked Metal buffers, the next layer's read overlapping compute, for single-chunk sweeps up to 2048 tokens; pre-M5 gate widened to M5. Claim M1 Max 32 GB, 437 tokens: 4.05 -> 14.7 t/s, byte-identical |
| `c12d639` | Extend V4.1 SSD prefill sweeps and release temporary Metal storage | idea -> `60-prefill-sweeps` | with `bac91c2`; together 849 lines, so at least +1.5% TTFT |
| `2b9d1c2` | Fuse V4.1 Metal BF16 boundaries in normalization and Q8 decode | history: zone | bit-exact, under about 1%; the `70` zone |
| `9f7e4eb` | Fuse V4.1 shared Q8 projections and BF16 SwiGLU on Metal | history: zone | as `2b9d1c2` |
| `2da41a4` | Fuse V4.1 BF16 activation and hyper-connection epilogues | history: zone | as `2b9d1c2` |
| `5d83b55` | Fuse V4.1 scalar Metal decode HC and BF16 epilogues | history: zone | as `2b9d1c2`; needs `0edc553` |
| `0edc553` | Separate GPU execution phases and reuse HC normalization operands | history: zone | the base of `5d83b55` |
| `ecf0b13` | Reuse selected V4.1 KV rows during sequential Metal decode | history: zone | as `2b9d1c2`, with indexer and mask skips |
| `2c9d48f` | Account for fixed weights in Metal manual SSD cache budgets | next sync | not a fix: it changes what a manual cache size means. If it lands, re-check that the 75 GiB dynamic cache still means the same thing |

### #874 (head `d06eba3`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `595e06d` | metal: restrict the matvec reduction tree to simdgroup 0 | history: resident | bit-exact and device-agnostic, hits `kernel_mul_mv_q8_0_f32`; about zero here |

### #864 (head `482e246`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `482e246` | metal: speed up IQ2_XXS MoE prefill with half LUT and split MPP | idea -> `60-prefill-sweeps` | the half LUT only, into `dequantize_iq2_xxs`: all 2048 entries equal 0.25 x the grid exactly, but the library compiles with fast-math, so it needs an exhaustive dequant equality test and on-device bitwise output. The split MPP (one 32-row op -> two 16-row ops) is `drop: output`: it may change the accumulation. Given up: part of the claimed +5-8% prefill |

### #849 (head `9b4bb9e`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `60051d4` | ssd streaming: prefetch the next layer's experts during idle disk time | idea -> `50-ssd-miss-overlap` | a background thread runs layer L+1's router on layer L's input and pre-reads the predicted experts into staging buffers; a retain mark protects them. A port registers the F32 router and drops the hash-layer and GLM hunks. About 800 lines, so at least +1.5% decode; the retain mark changes hit counts by design |
| `9b4bb9e` | let DS4_PF_TOPK=0 keep the certain hash-layer prefetch without speculative top-k | drop | a knob for hash layers, which V4.1 has none of |

### #828 (head `3add8f9`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `3f20d5e` | metal: non-blocking GPU stage timestamps behind DS4_METAL_GPU_STAGE_TIMESTAMPS | open | Metal `ds4_gpu_stage_flush`/`report`; its `metal_graph_*` hooks reach only the layer-slice path and its CUDA stub targets removed code |
| `3add8f9` | metal: GPU stage timestamps cover the DeepSeek V4.1 decode graph | open | V4.1 decode stage tags; adds about 15 commits per layer when on, so it measures a different schedule |

`1950f62` is a merge.

### #778 (head `d81a28f`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `c813ff1` | metal: fix staged B-tile tensor extents in the mm_id mpp kernel | next sync | the same patch as #777 `9cb0271` |

### #758 (head `e154aa8`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `e154aa8` | metal: accelerate M5 Max indexed prefill | adopt -> `60-prefill-sweeps` | the rb16 hunk only: gate `prefill_dual_heads`, `n_tokens >= 32`, "M5 Max"; the dual kernel is identical in the child; its `break` -> `continue` is equivalent because prefill sorts ids first. Decided on GPU section time |

### #621 (head `6a20b13`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `8f5a745` | Metal streaming: split expert slab preads to raise NVMe queue depth | adopt -> `40-ssd-expert-reads` | opt-in; each expert pread split into up to N 16 KiB-aligned pieces on the same pool; the same bytes. Measured +16% decode on M1 Pro, bit-identical |
| `f7695ea` | Metal streaming: opt-in F_NOCACHE descriptor for expert preads | adopt -> `40-ssd-expert-reads` | an optional `F_NOCACHE` descriptor for expert reads |
| `61e35e2` | metal: index live IQ2 SSD cache entries | open | a live-entry index for eviction, sized for V4 Flash; the child scans all 30,720 entries |

### #570 (head `66ca6ef`)

| Commit | Subject | Verdict | Reason |
|---|---|---|---|
| `a1afb82` | metal: report pread pool dispatch stats in the timing summary | adopt -> `40-ssd-expert-reads` | dispatches, `qd_avg`, `pool_gbps` and `task_gbps` in the timing summary; measurement only |
| `66ca6ef` | metal: keep expert pread threads on the important IO tier | drop | user-initiated QoS and `IOPOL_IMPORTANT`; neutral in the foreground on M1 Ultra and M5 Pro |

## Excluded

The 141 of the 211 candidates without a row above, and the seven PRs updated
since the review that do not touch engine files or are dominated by another
model, classed by title and hit columns. A PR that could reach V4.1's Metal
or streaming code and fits no class cleanly is read and gets a row above
instead; that is how #947 and #798 got theirs.

- Server and KV store: #1055 #1022 #1020 #1017 #1005 #1003 #1000 #985 #983
  #977 #969 #961 #960 #927 #924 #883 #882 #843 #827 #767 #752 #720 #704 #686
  #489 #363 #353 #327 #292 #148 #111 #106 #66 #59 #19.
- Agent: #963 #492 #443 #241.
- CLI, startup, build and CI: #876 #575 #379 #274 #184 #181 #119 #92.
- Tokenizer and loader: #942 #548 #545 #347 #295 #281 #82 #60 #58.
- Sampling: #841 #302 #195.
- Steering: #970 #282 #203 #168.
- Speculative decoding (DSpark, MTP, prompt lookup, suffix trees): #965 #915
  #835 #749 #677 #645 #590 #482 #480 #411 #396 #385 #371 #276 #261 #206.
- CUDA, ROCm and multi-GPU: #1130 #1116 #1070 #1064 #1036 #1031 #1011 #861
  #820 #817 #795 #717 #701 #592 #589 #568 #535 #517 #488 #451 #441 #383 #349
  #343 #187 #83.
- Vulkan: #557.
- CPU and x86: #796 #529 #511 #508 #305 #239 #218 #72.
- Other models (GLM, Qwen, MiMo, Hy3, V4 PRO, Vision-Exp): #1129 #1122 #1121
  #1047 #937 #571 #553 #528 #527 #523 #520 #502 #212.
- Distributed (a second Mac): #1018 #919 #715 #631 #401 #351.
- Multi-session batching (streaming sessions are never batched): #799 #530
  #516 #515 #67.
- KV or weight quantization and model variants (excluded by the output
  rule): #416 #265 #124.
- Quantizer and offline tools: #664 #662.
- Refactors and Metal work on a May base: #628 #286 #32 #31 #30.
