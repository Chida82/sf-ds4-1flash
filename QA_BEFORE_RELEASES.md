# QA Before Releases

This is the release gate for DwarfStar.  Run it before tagging or pushing a
release build.  The goal is not to prove every code path exhaustively; it is to
exercise the paths that have historically regressed: Metal graph inference,
SSD streaming, distributed execution, disk KV cache, and server APIs.

Keep this file procedural: commands, pass/fail criteria, safety constraints and
reproducible reference measurements. Put per-run results, failed experiments,
retries and investigation notes in a separate QA report, not here.

Do not run multiple huge model processes at the same time. Record the commit,
hardware, GGUF checksum, prompt, context size and non-default flags for every
manual run. Report skipped checks and unresolved failures explicitly.

Preferred release test hosts:

- Metal / distributed Mac testing: `mac-m5max-it` and `mac-m5max-us`.

The Mac hosts have DNS entries and are reached through an internet VPN.  They
are connected to each other over WiFi and also through a Thunderbolt 5
point-to-point link.  The TB5 route is the preferred distributed-inference
network when it is available, but it can be fragile and sometimes only works
when `ds4` is executed in the foreground.  Prefer these machines for release
testing, especially distributed inference.  Local fallback testing on this
machine is acceptable when needed; it is an M3 Max with 128 GB RAM.

## 1. Repository And Build Sanity

- Start from a clean tree except intentional release notes:
  `git status --short`.
- After fetching a bundle, rewriting commits, or resetting a remote test tree,
  force a clean build. Do not trust incremental `make`: restored source mtimes
  can be older than a stale executable. Record the tested binary's commit or
  verify it was rebuilt from the selected tree before running remote QA.
- Build the normal local target:
  `make clean && make`.
- Build CPU-only binaries as a compile check only:
  `make clean && make cpu`.
- Treat compiler warnings as build failures. Save each release and test build's
  complete output and require no `warning:` lines. Fix the source when
  possible; use a narrow target-specific suppression only when a test
  deliberately compiles a partial translation unit.
- Repeat the warning-free build gate on the release hardware:
  `make clean && make` on Metal.
- Run whitespace checks before committing:
  `git diff --check`.
- Confirm `./sf-ds4-1flash --help` and `./sf-ds4-1flash-server --help` render
  cleanly, with readable section colors and no broken wrapping.

## 2. Core Regression Tests

### Critical Input And Server Regression Pass

1. Send malformed OpenAI, Responses, and Anthropic requests with repeated
   owned string or array fields under ASan. Each request must fail cleanly and
   a following valid request must still work. Run `./ds4_test --server` too.
2. Replay at least 4,096 assistant/tool-result pairs through the Responses and
   Anthropic validators. Validation must remain linear-time and preserve the
   same accepted and rejected histories as a short replay.
3. Feed a distributed worker a snapshot header whose declared lengths exceed
   the configured and protocol limits. It must reject the header before a
   large allocation or payload read, without growing RSS materially.
6. Exercise unterminated and twice-closed reasoning in streaming and
   non-streaming OpenAI, Responses, and Anthropic requests, with and without
   tools. Reasoning must never leak into answer content.
7. Force a conversation past the in-memory KV threshold, restore the same disk
   checkpoint twice, and confirm the checkpoint file remains present after
   both successful loads. Corrupt checkpoints must still be rejected.
10. Run `./ds4_test --think-tool-recovery`, then repeat through all three HTTP
    APIs. A complete tool block inside unclosed reasoning must be recovered
    once, preceding prose must remain reasoning, and no synthetic continuation
    may be generated.
11. Run the server parser tests under UBSan with `NaN`, positive infinity, and
    negative infinity where integer JSON fields are expected. Conversion must
    be defined and clamped, with no sanitizer report.

## 3. Official Continuation Quality Gates

These tests are release-blocking after tokenizer, template, KV-cache, attention,
MoE routing, quantization, logit, or model-graph changes.  They are
teacher-forced continuation checks against hosted-model output and API
top-logprob slices, so do not replace them with one sampled chat answer.

## 4. SSD Streaming

SSD streaming is a capacity path, so test both correctness and user experience.

- Cold streaming measurement:
  run once with `--ssd-streaming-cold` and verify no deadlock, missing expert,
  or impossible slowdown.
- Confirm startup reports cache budget and that generation does not stall on
  repeated expert misses for a small interactive prompt.
- After changing model-map or memory accounting, test automatic sizing, an
  impossible large target such as `--ssd-streaming-cache-experts 500GB`, and
  `--ssd-streaming-cache-experts 1`. The large target must be reduced below
  the final memory-guard budget instead of failing or pressuring the machine
  into swap. The one-slot run must select direct per-layer reads and complete
  correctly without pretending that the selected-expert cache can hold one
  token's routed set. Preserve the startup lines showing the effective cache,
  global or per-layer decode map, and total planned memory.
- If streaming cache internals changed, test the same prompt twice and compare
  first-token/logprob sanity between runs.
- Cache and I/O optimizations must not change routed expert counts, weight
  precision or activation precision. With the same model and prefill chunks,
  require identical complete logits and deterministic output across cache
  policies. Test numerical-kernel changes separately against a reference.
- On Metal, compare the complete prefill logits with the previous executable
  at 2K/3K and 8K/12K frontiers, with generation and continued prefill between
  them. Exercise initial whole-layer reads, later selected-expert reads, cold
  caches and a mixed-size expert layer. Record initial and continued speed
  separately, including the first decode step rather than only steady speed.
  Save the exact commands and prompt files with each comparison. Equal context
  lengths do not imply equal input tokens. For short tool-result appends, test
  16, 43 and 114 tokens as well, followed by generation: a faster append must
  not merely move its I/O cost into the next decode steps.
- Deny the first static-weight `mlock` in a test build or interposer. Startup
  must leave those weights pageable and continue with correct output. Do not
  confuse this with denying every lock: the existing expert cache also needs
  locked buffers. Keep external memory monitoring enabled; do not deliberately
  trigger system OOM or a GPU watchdog reset.

  Also test an 8K prompt followed by a 4K append at a 16K context with the
  automatic cache and an explicit cache target. This crosses compact-indexer
  warmup, which reads weights from earlier layers after prefill releases their
  mappings. Compare full logits and monitor memory throughout, not just startup.
  For `sf-ds4-1flash-bench`, use `DS4_BENCH_FORCE_SNAPSHOT=1` when the extra snapshot fits;
  otherwise its large-payload fallback replays the prefix and changes the cache
  state before the append. Record which restoration method was used.

### SSD Performance References

| Workload | Prefill | Generation |
| --- | ---: | ---: |
| Initial 8K, 16 output tokens | about 91 t/s | about 3.7 t/s |
| 4K append, 16 output tokens | about 84 t/s | about 4.0 t/s |

For short appends, use the code-audit prompt, 1024 initial tokens, an 8K
allocation, a 66 GB cache hint (61.35 GiB effective), forced snapshot restore
and 64 greedy output tokens at each frontier:

| Added tokens | Append latency | Generation afterward |
| ---: | ---: | ---: |
| 16 | 2.9 s, three-run median | 5.11 t/s |
| 43 | 5.4 s, single run | 5.34 t/s |
| 114 | 8.7 s, single run | 5.39 t/s |

Compare with `DS4_METAL_DISABLE_STREAMING_PREFILL_BATCH_SELECTED_ADDR=1` as
an ablation, requiring identical full logits and generated text. Keep cache
misses/application read bytes separate from measured physical SSD traffic.

A stuck `pread`, unopenable GGUF or filesystem wait surviving cancellation is
not a passing timeout test. Stop inference, check the filesystem independently
and repeat the task only after the host is healthy. Do not increase timeouts
or count a pass on another host as resolving that failure.

## 5. Distributed Inference

Distributed code has regressed around route setup, KV snapshots, request IDs,
and split model loading.  Test it whenever distributed, KV, session, or model
loading code changes.

- Prefer `mac-m5max-it` and `mac-m5max-us` for Metal distributed tests.  Use the
  TB5 point-to-point link when it is working; otherwise note that the run used
  WiFi/VPN routing.
- Start workers first, then the coordinator.
- Test a small prompt and a longer prompt.
- Verify the coordinator waits for a complete route and exits cleanly.
- Verify `Ctrl+C` returns control after the current distributed token or chunk
  drains.
- Save and restore a distributed KV snapshot if that code changed.

## 6. Disk KV Cache

Disk KV cache bugs are high impact for server users.

- Start the server with:
  `./sf-ds4-1flash-server --ctx 100000 --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192`.
- Run the same request twice and verify the second request hits cache.
- Fill the cache enough to trigger eviction; verify the newly-written entry is
  not evicted and useful anchors are retained.
- Test rejection of incompatible checkpoints when model, quantization, context,
  or raw/compressed KV layout changes.

## 7. Server APIs

The server must keep compatibility across OpenAI, Responses, and Anthropic
clients.

- `GET /v1/models/deepseek-v4.1-flash` serves the loaded GGUF.
- Test OpenAI chat completion, OpenAI Responses, and Anthropic messages.
- After tool-parser changes, run `./ds4_test --server` and
  `make test-session-state`. These targets do not load model weights. Repeat
  the frontend suites with ASan/UBSan for parser and buffer changes.
- Truncate a tool argument using a small output budget and an explicit client
  stop, with and without streaming. Preserve `length` versus `stop`, never
  invent a complete action from an unfinished argument, and do not retry after
  a client stop. Model-error recovery must share the original output budget;
  usage includes the failed attempt. Partial SSE arguments may remain partial.
- Exercise actual `sf-ds4-1flash-server` coding sessions, not only isolated
  HTTP requests. Use Pi, OpenCode or another supported coding client
  for several read/edit/build/test rounds, including a harmless tool failure
  and recovery. Grow the conversation past 4K tokens and continue it.
  Capture `--trace` and check tool IDs, raw tool replay, rendered prompts,
  cache source, matched-prefix length and continued-prefill size after each
  tool result. An unchanged history should retain its reusable prefix;
  investigate repeated full prefills or unexplained canonicalization rebuilds.
  Conversely, editing an earlier message must invalidate the changed suffix.
  Compare a continued request with a fresh replay of the same full history,
  checking tool arguments, coherent output and context isolation. Record any
  necessary rebuild and its latency rather than counting a working tool alone
  as proof that prefix matching works.
- Run `python3 tests/test_server_vision_agent.py --url http://127.0.0.1:8002
  --pi /path/to/pi --output /tmp/vision-agent-qa` for both vision models. Pi must
  actually read the two images, edit the program and pass the independent
  output checks through Chat Completions, Responses and Anthropic. Image tool
  results must arrive as images, not disappear or become literal placeholders.
  Check cached-token accounting after every image-bearing tool continuation.
- Test SSE streaming with thinking enabled and disabled.
- Test keepalive during long prefill and confirm clients do not time out.
- In batched mode, close clients while their requests are queued, prefilling,
  and streaming decode. Repeat across OpenAI chat, Responses, Anthropic, and
  completions. Abandoned work must stop at the next backend-safe boundary, and
  a valid request after each cancellation must complete normally.
- For the repeatable chat-completions cancellation and slot-reuse gate, run
  `python3 tests/test_server_batching.py --url http://127.0.0.1:8002 --pairs 2
  --workers 4 --case short-sampled --max-tokens 12 --cancel-first 4`. Then run
  at least twelve short four-request waves against the same four-slot server.
  Every pair must remain deterministic and the server must answer `/v1/models`
  after malformed JSON and an over-context request.
- Test `--trace` and confirm rendered prompts, cache decisions, generated text,
  and tool-parser events are useful without leaking unrelated state.

For an unterminated tool call, capture raw model output, source revision,
output budget and stop reason before blaming inference, parsing or memory.
Literal-marker copying needs both deterministic parser tests and real-model
checks: the model can change the text before the parser sees it.

## 8. Download Script And Model Files

- Run `python3 tests/test_model_download.py`: it stubs the Hugging Face CLI and
  checks the property that matters, that `download.sh` only ever creates
  symlinks into the shared cache and never materialises a GGUF here.
- Run `./download.sh q2` and `./download.sh vision` for real once, and confirm
  `gguf/` plus `./deepseek-v4.1-flash.gguf` are symlinks into the cache.
- Verify an unknown component name fails clearly with exit 2.
- Verify README component names match the script and the Hugging Face repository.

## 9. Performance And Power

- Run `sf-ds4-1flash-bench` on the release machine and compare with tracked CSV baselines.
- Test `--power 100` is not throttled.
- Test `--power 50` visibly reduces duty cycle in CLI, server, eval, and
  bench where practical.
- Confirm context buffer size, raw KV rows, compressed KV rows, and mmap behavior
  match expectations for 32k, 100k, and any release-advertised context size.

## 10. Speed Regression

Performance is a release gate. A correct result that is unexpectedly much
slower still needs an explanation before release.

Use the same commit, GGUF checksum, prompt, context frontier, generated-token
count, power setting, and backend flags as the reference run. Let the machine
become idle, discard the first warm-up run, then record the median of three
runs. Do not compare different model checkpoints or quantizations. For batched
tests, record aggregate and per-session decode speed.

- A slowdown over 5% requires a clean rerun and investigation.
- A repeatable slowdown over 10% in prefill, decode, or aggregate batched
  decode is a release blocker unless the change and tradeoff are documented.
- Keep the complete `sf-ds4-1flash-bench` CSV. A single short-prompt average is not enough
  to detect a context-dependent regression.
- For speculative decoding, retain the generated text and draft-acceptance
  statistics. Repetition loops can inflate throughput; a faster bad answer is
  not a win. Separate changed continuation/acceptance from kernel cost using
  matched teacher-forced ordinary-decode measurements. Test code and prose.
- Compare startup time and peak memory as well as tokens per second when model
  loading, caches, streaming, or temporary arenas changed.
- Run the backend-specific batch tests in section 4. Fast single-session
  decode does not substitute for aggregate multi-session throughput.

### Metal Kernel And Speculation Gates

For M5 dense-kernel changes, run `MTL_DEBUG_LAYER=1 make test-metal-dense-mpp`.
It checks Q8 decode and Q4_0/Q4_K prefill against exactly representable CPU
dots, including repeated calls, partial token tiles and untouched output tails.
Keep host threadgroup allocations in sync with kernel staging: the dense
double-buffered TensorOps kernel needs 8 KiB, not 4 KiB.

For M5 routed-prefill changes, run `make test-metal-moe-prefill`. It compares
gate/up, FP16 intermediate, expert partials and final outputs against the
unpacked path, including empty experts, tile tails and scratch reuse.
Then build `make metal-prefill-variant-bench metal-decode-schedule-bench` and
use a resident Flash Q2 or mixed Q2/Q4 model for interleaved full-logit checks:

```sh
speed-bench/metal_prefill_variant_bench -m "$MODEL" \
  --prompt-file speed-bench/promessi_sposi.txt --prefix-tokens 2048 \
  --warmup-tokens 2048 --candidate-env DS4_METAL_DISABLE_ROUTED_MPP_PACKED
speed-bench/metal_prefill_variant_bench -m "$MODEL" \
  --prompt-file speed-bench/promessi_sposi.txt --prefix-tokens 16384 \
  --initial-tokens 12288 --warmup-tokens 2048 \
  --candidate-env DS4_METAL_DISABLE_ROUTED_MPP_PACKED
speed-bench/metal_decode_schedule_bench -m "$MODEL" \
  --prompt-file speed-bench/promessi_sposi.txt --prefix-tokens 8192 \
  --ctx 9216 --tokens 256 --candidate-env DS4_METAL_DISABLE_ROUTED_MPP_PACKED
```

Here `control` is the default fast path; `candidate` disables packing.
Require exact logits and no decode regression. Packing is an M5
resident-prefill optimization; test streaming and conventional kernels
separately when their dispatch or shared buffers change.

Use the matching drafter and `--nothink --top-p 0.95 --min-p 0.05 --seed 12345`.
The C prompt is: "Write a complete C hash table implementation with string keys,
insert, find, delete, and a test main. Output only C code."

For two-M5 TP, test the MXFP4 and mixed Q2/Q4 Vision Exp models with their
matching drafter. Use the same sampling settings and 256-token C prompt above,
plus the prompt "Write an unpredictable surreal scene with constantly changing
imagery and no repeated phrases." Reference means of two reversed-order runs,
explicit RDMA and 50/50 residency:

Ordinary MXFP4 TP reference on the C prompt is 53.19/50.93 t/s at temperature
0/1. Speculation need not beat ordinary decode on every prompt.

Also compare ordinary MXFP4 TP with and without
`DS4_METAL_DISABLE_ROUTED_MPP_PACKED=1`, using Promessi Sposi at 2K/4K/8K/16K
live frontiers. Repeat in reversed order and compare full frontier logits.
Investigate fresh-process variability with GPU/CPU clocks, temperature and
concurrent activity recorded. Require repeatable controls before attributing
small differences to a kernel. Include the matching official-continuation
fixture, not just a timing prompt.

Require `MTL_DEBUG_LAYER=1 make test-metal-moe-prefill` on both M5s. This covers
packed MXFP4 prefill, both expert-ownership halves, tiny batches and the actual
4096/2048/4096 static shapes. Static two-to-six-row outputs must be exact against
per-row decode. The synthetic static-shape model uses about 3.2 GiB of memory.
`DS4_METAL_DISABLE_TP_BATCH_MOE=1` restores per-row verifier experts for diagnosis;
`DS4_METAL_DISABLE_M5_TP_MXFP4_STATIC=1` disables the static specialization.
Neither is needed to enable the fast path.

Repeat the physical TP session oracle with two, four and six sessions. Do not
set `DS4_TEST_SKIP_MIXED`: ordinary decode and the mixed continued-prefill step
must both match full serial logits exactly. Check that the final TP residual
update is flushed before the output head; argmax agreement alone cannot catch
a stale residual. Test mixed Q2/Q4 on both one host and physical TP.

### Other Hardware References

These are comparison points for the stated model and workload, not portable
throughput promises. Establish a fresh matched baseline where the checkpoint,
prompt or settings are unavailable. Model-specific sections give additional
context sweeps and memory limits.

## 11. DeepSeek V4.1 Flash

V4.1 is a different architecture and checkpoint, not a replacement filename for
V4 Flash. Use the matching vectors in
`gguf-tools/quality-testing/deepseek-v4.1-flash-20260910/manifest.tsv`.
The dataset README explains the temperature-one API logprobs: compare
teacher-forced probabilities and API top-token agreement, not sampled-prefix
length alone. Never refresh old Flash vectors through an API alias that now
serves V4.1.

Also score the 100 short general prompts in
`gguf-tools/quality-testing/deepseek-v4.1-flash-20260910-general/manifest.tsv`
when comparing quantizations. Keep this broader probability check separate from
the long sparse-boundary tests; neither substitutes for the other.

### Metal

- Run `make test-engram test-deepseek41-gguf test-quality-api` and
  `./ds4_test --server`.
  Run `make test-download-model` to check that `download.sh` only creates
  symlinks into the Hugging Face cache and the default model link. Check the
  published artifacts with `./download.sh q2` and `./download.sh vision` on a
  runtime host.
- With real weights, run `tests/test_deepseek41_graph MODEL --session-fixture`
  and `tests/test_deepseek41_graph MODEL --partitions` under Metal API validation.
  Check restored continuation logits, compression carry, sliding-window wrap,
  cancellation and malformed snapshots. Zero-weight fixtures are not quality QA.
  On a sufficiently large resident Metal host, run
  `tests/test_deepseek41_prefill --resident MODEL speed-bench/promessi_sposi.txt`.
  This grows two sessions beyond 130K tokens while mixing scalar, layer-major
  and deferred prefills; it checks progress, complete state and restored decode.
  Omit `--resident` for the bounded SSD variant through 113K. Never run the
  resident variant on a 128 GiB Mac.
  Run `tests/test_deepseek41_graph MODEL --long-sessions PROMPT_FILE` with the
  dataset's `prompts/case_016.txt` for incremental prefill and exact restored
  continuation checks through 16385 tokens. This uses two sessions and a shared
  64 GiB expert-cache budget; monitor memory and do not overlap another inference job.
- After prefill scheduling changes, run
  `tests/test_deepseek41_graph MODEL --prefill-parity speed-bench/promessi_sposi.txt`
  under Metal API validation. This compares complete logits and all saved cache
  spans with token-major execution, including large continued chunks, snapshot
  restoration and cancellation. An in-flight partial layer stack must never
  be accepted as a valid snapshot.
  Run `make test-metal-ssd-experts test-metal-moe-prefill` too: seeded cache
  replacement must release physical buffers, not just reset entry counters.
  The SSD test covers IQ2 eight-expert and Q4/MXFP4 six-expert routes, cold/hot
  eviction, batched outputs and repeated physical-cache release. Its
  `--table-admission` mode must reject persistent full-expert tables during
  streaming, even with diagnostic table overrides. A resident one-row batch
  must not silently populate the SSD cache. For new large Q4 artifacts, start
  with a small cache and one continuation before the full scorer. Monitor host
  wired memory and swap independently of the engine's planned allocation;
  retained Metal residency sets can otherwise escape its accounting.
  `tests/test_metal_moe_prefill --ssd-address` checks the IQ2/Q2 address kernel
  across small and large row counts, checking index widths and output bounds.
  Compare short/long, initial/continued prefill with the same cache budget on
  the same host. Include first-token latency and steady decoding after prefill;
  a faster prefill that leaves a cold expert cache can lose overall.
- For the long-prompt resident-encoder schedule, run
  `tests/test_deepseek41_graph MODEL --encoder-parity speed-bench/promessi_sposi.txt`
  and `--encoder-long-parity` with the same prompt file. These need an automatic
  expert cache large enough to hold the encoder; use one inference process per
  128 GiB host. Compare complete logits and every cache span at 16,385 tokens,
  then append and decode, including snapshot restoration. `--encoder-cancel`
  separately checks interruption after pinning the full encoder and rebuilding
  the session; the short test also cancels a partially loaded encoder.
  Confirm the cache budget is restored and no encoder pages remain pinned.
  Memory must replace the expert cache, not sit beside it. A smaller budget or
  failed residency request must retain the two-layer path, with Engram on disk.
  Measure both schedules at 8k and 16k, including loading, first decode latency
  and at least 512 generated tokens. Use
  `DS4_METAL_DISABLE_V41_ENCODER_RESIDENCY=1` for the two-layer control.
- Score both single-host SSD streaming and two-host TP over real RDMA. Cover
  127/128/129, 511/512/513, 1023/1024/1025 and 16383/16384/16385 prompt tokens,
  then continued prefills and a real CLI/server coding task with tool calls.
  Compare bootstrap and calibrated weights on the same held-out cases.
  Also use the `20260911-long` and `20260911-extended` V4.1 manifests for
  8/16/32K and 64/96K prefixes. Compare whole-prompt paired probability scores;
  sampled API output is not a full-logit oracle. Investigate persistent TP
  differences instead of assuming that a different reduction order explains them.
- Exercise native resident and TP batching with unrelated sessions. Run
  `tests/test_metal_session_batch` with `DS4_TEST_BATCH_ISOLATION=1`,
  `DS4_TEST_SESSION_COUNT=2`, `4` and `8`, and `DS4_TEST_DECODE_STEPS=32`.
  Supply `DS4_TEST_MODEL` and an admitted `DS4_TEST_CONTEXT_SIZE`; repeat two
  sessions at 64K using `DS4_TEST_PROMPT_FILE`. This oracle changes companion
  prompts and row order, checks complete target logits exactly, tests invalid
  batches without advancing state, and resumes after a mixed prefill/decode call.
  Isolation does not establish equivalence to serial inference: separately run
  `score_official --session-batch N` on the short and long manifests. Test
  physical Metal TP native batches with at least three rows: two rows use
  ordered execution by design. Confirm dispatch in the log instead of assuming
  that `--session-batch` selects the native path.
  Measure aggregate throughput without Metal validation, including two-session
  cases.
  Require the `native_ds41=1` trace for admitted native shapes, including mixed
  batches with nonzero `prefill_rows`; a passing ordered fallback is not evidence
  for the native path. Image-bearing sessions currently use that fallback.
  Real concurrent server requests must also cover cancellation and prefix reuse;
  a serial prefill followed by batched decode is not a native mixed-layer path.
  Run `tests/test_metal_moe_prefill --v41-decode` for rows 1-9, including both
  TP ownership partitions. Its `--v41-q4-decode` mode checks the Q4 shape at
  rows 1-8 against independent one-row calls, both ownership partitions and
  untouched output tails. Run both: IQ2 success does not cover Q4 dispatch.
  Run `tests/test_deepseek41_graph --batch-admission`
  and `tests/test_deepseek41_graph MODEL --batch-head`; the latter compares
  every output logit with the scalar head and selected rows with double math.
  Use `DS4_TEST_MIXED_SHAPES=1` with `tests/test_metal_session_batch` for 1-7
  appended tokens sharing a batch with independent decoders. Repeat at 73,728
  context on a large resident host, not the 128 GiB RDMA pair: this fixture
  allocates ten sessions. Check causal state and subsequent decode at 64K.
  Keep HTTP identical-output comparisons at a fixed prefill chunk geometry;
  the default idle and concurrent schedules can round differently. Also run
  the default schedule for independent coding correctness and prefix reuse.
- Run `tests/test_tp_tcp` on macOS as well as Linux after transport changes.
  Exercise both real loopback TCP and socket pairs with tiny buffers, including
  stalled peers and half-closes. Darwin `sendmsg(MSG_DONTWAIT)` alone can still
  block; the exchange must restore descriptor flags on success and failure.
- Verify that Engram tables remain unmapped and unpinned in every mode, including
  weight warming and TP. On 128 GiB Macs, never try full main-model residency;
  use SSD streaming or one half of a two-Mac TP setup. Increase context gradually
  and monitor memory/swap. Larger-Mac residency requires separate physical QA.
  With both released Q2 and Q4 GGUFs, run `tests/test_deepseek41_graph MODEL --memory-plan`.
  It rejects Q4 residency on 128/256 GiB hosts and a Q4 shard on a 128 GiB rank,
  while admitting larger hosts and fitting the SSD cache to its remaining budget.
  The Q2 variant checks simulated 128/256/512 GiB admission and TP shard sizing.
  Neither variant allocates weights or context buffers; this is not physical-host QA.
  Repeat startup with `--warm-weights`: TP must warm only its owned shard,
  SSD streaming must skip the full-file pass, and inspection must not warm weights.
- Exercise `--think-level 0`, `1`, `25`, `100`, `/think 25`, `/think`, `--think`
  and `--think-max`; reject malformed/out-of-range values. Check changing effort
  in a live conversation invalidates the old prefix without losing its messages.
- For a served V4.1 model, run `tests/test_server_vision_agent.py` with
  `--model deepseek-v4.1-flash` against Chat, Responses and Anthropic. Require
  independently checked image-driven code edits and cached-prefix reuse,
  not just successful HTTP responses.
- Unsupported backends, pipeline and speculative modes must fail explicitly until
  their V4.1 implementation is validated; an older graph/drafter is not a fallback.

#### Metal Reference Checks

The calibrated Q2 main weights occupy about 151.8 GiB, Q4 about 294.15 GiB;
188.8 GiB of Engram remains disk-only. Validate the release artifacts with
the converter/payload and download checks above, not old bootstrap filenames.

Compare against the corresponding stored fixture and execution schedule:

| Model / execution | Fixture | Mean NLL | API top-token agreement |
| --- | --- | ---: | ---: |
| Q2, M5 SSD | General 100 | 0.364576009 | 2697/2994 |
| Q2, M3 Ultra resident batched prefill | General 100 | 0.365680596 | 2705/2994 |
| Q2, Metal TP | General 100 | 0.361471738 | 2699/2994 |
| Q4, M5 SSD | General 100 | 0.246523256 | 2896/2994 |
| Q4, M3 Ultra resident | General 100 | 0.252409161 | 2896/2994 |
| Q4, M5 SSD | Long 9, 8K/16K/32K | 0.335651410 | 542/576 |
| Q4, M3 Ultra resident | Long 9, 8K/16K/32K | 0.328760094 | 538/576 |
| Q2, M3 Ultra resident | Extended 6, 64K/96K | 0.558586149 | 327/384 |
| Q2, Metal TP | Extended 6, 64K/96K | 0.560655370 | 328/384 |
| Q4, M3 Ultra resident | Extended 6, 64K/96K | 0.366465846 | 360/384 |

These are reference scores, not claims of bit-identical cross-backend quality.
Different prefill schedules and hardware can change rounding and expert routes.
Compare paired case scores on the same schedule, including the long fixtures;
unchanged top-token totals alone do not rule out a loss increase. A release
calibration must record coverage and retain the fallback for unobserved experts.

- For Q4 native batches through eight rows, retain the 0.0002 full-logit
  bound against scalar controls. Test the consumed fused outputs rather than
  optional gate/up scratch that a fused kernel need not write. Keep exact
  companion-isolation and cache-state checks separate from scalar parity.
- Keep the warm-SSD matrix-prefill threshold at 1024 tokens when at least
  half the experts fit unless a new threshold passes the nine long and six
  extended official fixtures. A speed win at 512 tokens is not sufficient.
- During Q4 SSD tests, verify that persistent full-expert tables cannot retain
  whole layers outside the cache budget. Start with a guarded 32 GiB cache,
  then increase only after wired memory and swap remain bounded. Planned
  allocation alone is insufficient evidence of safe physical residency.
- Repeat the explicit non-Metal-4 control when investigating M5 versus M3
  scores. Test residency, prefill geometry and kernel arithmetic separately;
  do not infer a transport or SSD error from cross-hardware logits alone.

Q4 resident reference on a 512 GiB M3 Ultra: default paths, disk-only Engram,
36,864-token allocation, no Metal validation or speculation. These are medians
of three complete sweeps after a warmup, with 128 output tokens per frontier.
Exclude loading. Only the first row is initial prefill; later rows are appends.

| Context frontier | Added tokens | Prefill t/s | Generation t/s |
| ---: | ---: | ---: | ---: |
| 4,096 | 4,096 | 341.75 | 18.69 |
| 8,192 | 4,096 | 339.10 | 18.67 |
| 16,384 | 8,192 | 641.49 | 18.32 |
| 32,768 | 16,384 | 715.96 | 18.11 |

```sh
./sf-ds4-1flash-bench -m gguf/DeepSeek-V4.1-Flash-Q4.gguf \
  --prompt-file speed-bench/promessi_sposi.txt --ctx-start 4096 --ctx-max 32768 \
  --step-mul 2 --ctx-alloc 36864 --gen-tokens 128 --show-output --csv RESULT.csv
```

## 12. Release Sign-off

Do not sign off until:

- macOS Metal Flash passed.
- Official continuation quality gates passed for every released model family.
- Metal, CPU-only, and test builds completed without compiler warnings on
  every release target that was validated.
- Disk KV cache was exercised.
- Server API streaming was exercised.
- The speed-regression gate passed on every validated backend, with any skipped
  baseline or intentional slowdown documented.
- Metal 2/4/8/16-session exactness and forced fallback gates passed.
- Physical Metal TP batching passed when that backend is part of the release.
- Any skipped item is written down with the reason.
