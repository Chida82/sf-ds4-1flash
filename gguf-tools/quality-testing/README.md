# Official-Continuation Quality Testing

This directory contains the prompts, tracked official fixtures, and scripts used
to compare local GGUF variants against hosted-model continuations.

The main metric is target-token negative log likelihood: collect an
official continuation, then ask each local GGUF how much probability it assigns
to that exact continuation token by token.  This avoids judging quality from one
sampled answer.

## 1. Tracked Fixture Sets

Curated fixtures are kept in the repository so release QA can run without
calling hosted APIs:

The hosted APIs expose output-token logprobs and top-logprob alternatives, not
full vocabulary logits.

The scorer verifies each API token's bytes against the local token boundaries,
not just the number of tokens. If they differ, it still scores the continuation
text but skips API logprob comparisons for that case. Alternatives containing
Unicode replacement characters are excluded because the original token bytes
may have been lost by the provider.

## 2. Collect Official Continuations

```sh
export DEEPSEEK_API_KEY=...
python3 gguf-tools/quality-testing/collect_official.py \
  --model deepseek-flash \
  --endpoint https://api.deepseek.com/chat/completions \
  --prompts gguf-tools/quality-testing/prompts.jsonl \
  --out /tmp/deepseek-v4.1-flash-new \
  --count 100 \
  --max-tokens 24 \
  --top-logprobs 20 \
  --thinking disabled \
  --reasoning-effort omit
```

Use one output directory per checkpoint. For PRO 0813 through the official
DeepSeek API:

The script writes:

- `data/<model>/prompts/case_*.txt`
- `data/<model>/continuations/case_*.txt`
- `data/<model>/responses/case_*.json`
- `data/<model>/manifest.tsv`

The prompt list is tracked in `prompts.jsonl`.  Curated fixture directories are
also tracked after review; ad-hoc API collection directories should stay
untracked until they are intentionally promoted into the release QA set.

Use `--system TEXT` when the reference needs an explicit system message.
`--system ''` sends an empty message, which is different from omitting it:
some providers insert a default system prompt when none is supplied. The
collector records this setting and rejects a changed system message on resume.
For a nonempty system message, render the matching local chat prompt and use
`--rendered-prompt`; the scorer's ordinary prompt mode adds no system message.

## 3. Build The Local Scorer

From the repository root:

```sh
make gguf-tools/quality-testing/score_official
```

The scorer links against the DS4 runtime, using Metal on macOS.

## 4. Score GGUF Variants

Add `--continued-prefill N` to process each prompt in two calls, leaving its
last `N` tokens for the second call. This checks continued-prefill quality
against the same official answers. Every prompt must contain more than `N`
tokens; otherwise the scorer fails instead of silently skipping the test.

Add `--session-batch N` (2 to 8) to score an official continuation alongside
unrelated, independently advancing sessions. The scorer rotates their row
order on every step. Compare against a run without this option using the same
manifest, model and context; budget memory for all `N` sessions.

Check session isolation separately on a dedicated Metal host:

```sh
DS4_TEST_MODEL=MODEL.gguf DS4_TEST_BATCH_ISOLATION=1 \
  DS4_TEST_SESSION_COUNT=4 DS4_TEST_DECODE_STEPS=32 \
  MTL_DEBUG_LAYER=1 ./tests/test_metal_session_batch
```

This requires exact logits when companion prompts and row order change, then
checks a continued prefill and resumed serial decoding. It also checks that
invalid batches leave the target unchanged. It does not replace serial/batch
quality comparisons: different arithmetic can round differently without
sessions contaminating one another. Use `DS4_TEST_PROMPT_FILE` and
`DS4_TEST_CONTEXT_SIZE` to repeat at longer prefixes. For physical TP, the test
also accepts `DS4_TEST_TP_RDMA_DEVICE` and `DS4_TEST_TP_GID_INDEX` alongside
its coordinator/worker settings. Throughput measurements must run separately
without Metal API validation.

For Metal V4.1 prefill scheduling changes, also run:

```sh
make tests/test_deepseek41_prefill
./tests/test_deepseek41_prefill --dispatch
MTL_DEBUG_LAYER=1 ./tests/test_deepseek41_prefill MODEL.gguf speed-bench/promessi_sposi.txt
```

The model test uses SSD streaming and two 128K sessions. Run it alone on a
dedicated host with at least 128 GiB RAM. It alternates small and large appends
through 113K context, checking dispatch, progress, unchanged-prefix reuse,
saved state and subsequent decoding against a control without decoder deferral.
Keep the official continuation checks too: this scheduling test does not judge
quality across different floating-point operation orders. Measure speed without
Metal API validation, separately for initial and continued prefills.

Run the same mixed-prefix test over physical RDMA on two dedicated Metal hosts.
Start the worker with the same model and a 131072-token context, then the test
on the coordinator (replace the host and RDMA device names):

```sh
# Worker
MTL_DEBUG_LAYER=1 ./sf-ds4-1flash -m MODEL.gguf --ctx 131072 \
  --tensor-parallel --role worker --coordinator COORDINATOR 19455 \
  --transport rdma --rdma-device WORKER_DEVICE --rdma-gid-index 1

# Coordinator
MTL_DEBUG_LAYER=1 ./tests/test_deepseek41_prefill --tensor-parallel \
  MODEL.gguf speed-bench/promessi_sposi.txt COORDINATOR 19455 COORDINATOR_DEVICE 1
```

This compares equal TP prefill partitions and queued versus synchronous decode,
including full logits and cache state. TP snapshots rebuild both ranks from
tokens, so restoration is compared with an equivalent fresh replay. Also run
the official scorer in TP mode for initial and continued prompts; scheduling
parity alone does not establish model quality.

Add `--quality` to disable DS4's speed-oriented numerical shortcuts. For an
independent llama.cpp comparison of a DeepSeek V4 GGUF, use the same manifest
and the token-identical DS4 prompt renderer:

For a full-residency vs SSD-streaming comparison, score the same model twice and
add the streaming flags to one run:

## 5. Compare

```sh
python3 gguf-tools/quality-testing/compare_scores.py /tmp/old.tsv /tmp/new.tsv
```

Output fields:

- `avg_nll`: average negative log likelihood; lower is better.
- `delta_new_minus_old`: negative means the new GGUF fits the official
  continuation better.
- `case_wins_new_old_ties`: per-prompt NLL wins.
- `first_token_matches`: how often the local greedy first token matches the
  official first token.
- `avg_greedy_lcp`: average greedy longest common prefix against the official
  continuation. This measures exact agreement, not general answer quality;
  one early mismatch discards all later agreement. Do not use it alone as a
  quality gate, especially for sampled references. Compare paired NLL and
  API probability agreement under matching execution settings as well.
- `api_target_mae`: when the manifest includes `response_file`, absolute
  local-vs-API logprob delta for aligned official output tokens.
- `api_top_coverage`: fraction of API top-logprob alternatives that map exactly
  to one local tokenizer token.
- `api_top1_rate`: how often the API top alternative equals the local greedy
  token.
- `api_topn_recall`: fraction of mapped API top-N alternatives found in the
  local top-N for the same position.
- `api_top_mae`: local-vs-API logprob MAE over mapped API top alternatives.
- `api_pair_rate`: pairwise ordering agreement among mapped API alternatives.

## 6. Validate regression artifacts

Two standard-library Python tools check saved artifacts without running inference. For matched `score_official` runs with API logprob coverage, require the complete intended manifest and finite, consistent counts and scores:

Exit 0 with `--strict-identical` requires every per-case value to match; omit it to report valid differences without deciding their acceptability. Unlike `compare_scores.py`, validation rejects missing/duplicate cases, malformed fields and changed coverage denominators. This stricter mode requires the current four-column manifest and scorer TSV format with nonzero API coverage; use the existing comparator for continuation-only references without API logprobs.

Compare complete vocabulary dumps from `ds4-bench --dump-frontier-logits-dir`:

```sh
python3 gguf-tools/quality-testing/compare_frontier_logits.py \
  /tmp/old-logits /tmp/new-logits --frontiers 2048 4096 --ctx 8192 \
  --model /models/model.gguf --quality false --quant-bits 2 --vocab 129280 \
  --output /tmp/frontiers.json
```

Supply the exact expected metadata: `ctx` is allocated capacity; each frontier is total context, and prefill is its increase from the previous frontier (initially zero). Each directory must contain exactly the requested dumps. Exit 0 requires complete finite float32 bit identity; exit 1 reports drift, invalid artifacts or an operational error. JSON distinguishes `identical`, `drift` and `invalid`, with full-vector hashes, differing counts and maximum absolute differences. The output path must be new. The parser follows the writer's nine-significant-digit float format and preserves signed zero.

Matching argmax is insufficient: a measured 8K–64K comparison retained all four argmax IDs while full vectors differed, with maximum absolute difference 7.45228. This is numerical drift, not by itself proof of worse generation quality. Record prompt/weight hashes, source/build identity, settings and successful run completion separately; these tools cannot recover that provenance from score tables or dumps, and do not replace model-quality checks.

Run the host-only positive and negative controls:

```sh
python3 -m unittest discover -s gguf-tools/quality-testing/tests -v
```
