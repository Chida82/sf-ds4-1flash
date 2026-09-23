# sf-ds4-1flash — agent notes

`sf-ds4-1flash` is a specialized fork of [ds4 / DwarfStar](https://github.com/antirez/ds4)
reduced to **one model on Apple Metal**. It is one *child* of the
[StarForge](https://github.com/Chida82/StarForge) family. This file explains
what this repo is and how to work in it. For code-quality rules read
`AGENT.md` (upstream's notes, trimmed): they apply unchanged.

## Identity

| | |
|---|---|
| Model | see `README.md` first line |
| Shape (`ds4.c`) | `DS4_SHAPE_FLASH41`, the only profile in the binary. `g_ds4_shape` stays **writable** (see below); `config_validate_model` refuses any GGUF whose `general.architecture` is not `deepseek41` |
| Backend | Metal only. No CUDA, no ROCm. CPU path kept as reference/debug and for model-less tests |
| Binaries | `sf-ds4-1flash`, `sf-ds4-1flash-server`, `sf-ds4-1flash-bench`, `sf-ds4-1flash-eval`. No agent binary |
| Server default port | `8002` |
| Home dir | `~/.sf/ds4-1flash` (CLI history; suggested `--kv-disk-dir ~/.sf/ds4-1flash/kv`) |
| Instance lock | `/tmp/sf-ds4-1flash.lock` (override: `DS4_LOCK_FILE`) |
| Vision | yes, `--vision gguf/DeepSeek-V4.1-Flash-Vision.gguf` |
| Memory | **SSD streaming is the normal mode**: Q2 is 341 GiB against a 128 GB machine. See "SSD streaming is not optional" below |
| Speculative decoding | none |
| Steering | tooling kept (SPEC.md §B), but the model **refuses to start** with `--dir-steering-file`, exactly as upstream |
| TP / RDMA / pipeline | yes |
| Upstream base | never written down: `git describe --tags --match 'sync-*' --abbrev=0` names the last sync, `git merge-base HEAD upstream/main` the base. A SHA typed into a file is a second source of truth that goes stale (SPEC.md §A) |

Other children of the family may be installed on the same machine: paths and
ports above are chosen so nothing collides with them or with upstream ds4.

`make cpu` must write its own binaries (`sf-ds4-1flash-cpu`, `-cpu-server`,
`-cpu-bench`, `-cpu-eval`). Upstream links the CPU-reference build over the four
default names; make cannot distinguish the flavours, so a later `make` relinks
nothing and the next model-backed run fails with "requires Metal". Fix the
Makefile at bootstrap rather than warning about it — the warning has already
failed twice.

## SSD streaming is not optional

This is the operational fact that shapes every model-backed command here, and
the one most likely to waste a day if it is missed.

The Q2 release is **340.6 GiB on disk**: about 152 GiB of main weights plus
**189 GiB of Engram tables**. Engram rows are read straight from the file in
*every* mode, resident included — the loader prints `Engram disk-only` — so the
GGUF must sit on a fast local SSD whatever else you do.

On a 128 GB Mac nothing loads without `--ssd-streaming`. With it, a run looks
like this (measured on this tree):

```text
Metal SSD streaming mode enabled; full model residency and warmup are skipped
expert budget before prefill reserve: 8913 (82.62 GiB)
cache target 82.62 GiB = 7.12 GiB prefill headroom + 75.50 GiB dynamic cache
Metal SSD static weights locked 9.37 GiB; pageable 0.00 GiB
V4.1 static context buffers 8073.52 MiB (ctx=32768), Engram disk-only
```

and generation lands around 6 t/s. That is the expected shape, not a
regression: the throughput is bounded by SSD reads, so compare a change against
a run in the *same* mode, never a resident number against a streaming one.

Pass it everywhere:

```sh
./sf-ds4-1flash --ssd-streaming --ctx 32768 -p "..."
./sf-ds4-1flash-server --ssd-streaming --ctx 32768
./sf-ds4-1flash-eval --ssd-streaming -m deepseek-v4.1-flash.gguf --suite core
./sf-ds4-1flash-bench --ssd-streaming --prompt-file speed-bench/promessi_sposi.txt

DS4_TEST_MODEL=deepseek-v4.1-flash.gguf DS4_TEST_SSD_STREAMING=1 ./ds4_test
```

and for the StarForge parity oracle, which runs upstream and this fork with the
same GGUF, through the machine-level hook rather than per prompt:

```sh
SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash
```

Without it both binaries fail to load and every prompt is reported as "a binary
produced no output", which reads like an ablation bug rather than a missing
flag. The knobs worth knowing: `--ssd-streaming-cache-experts N|NGB` sets the
expert cache target (auto by default), `--ssd-streaming-cold` skips the
popularity preload, and `--ssd-streaming-full-layers N` keeps the first N routed
layers fully resident.

The alternative to streaming is not more RAM in one box but **two 128 GB Macs
with TP/RDMA** (`docs/DISTRIBUTED.md`), which holds about 81 GiB of main weights
per rank and drops `--ssd-streaming`. A 256 GB or larger machine can hold the
main weights resident; the Engram tables still stay on disk.

## What is NOT here (do not re-add)

- `ds4-agent` and agent-only code (`ds4_agent.c`, `ds4_web.c`, its tests/docs).
  Use `sf-ds4-1flash-server` with an external agent (see `docs/CLIENTS.md`).
- CUDA / ROCm / multi-GPU placement, Linux memory helpers, DGX/Strix docs.
- Every other model: shapes, kernels, tokenizer tables, tests, docs, download
  targets. In files that remain, every non-obvious cut or conflict resolution
  that discards upstream code has a marker at the exact site:
  `/* sf-ablate(<area>): <what was removed; why this child does not need it> */`.
  Whole-file deletions have no marker-only replacement file. Where we were
  unsure and kept code: `/* sf-keep: ... */`.
- Features the registry marks as absent for this model (see Identity).

## Rules that keep upstream merges alive

1. **Never rename `ds4_*` files or `ds4_`/`DS4_` identifiers.** Only the
   outside is renamed: binaries (`BIN` in the Makefile), default paths, help.
2. **`git config rerere.enabled true`** must be on (it is; check with
   `git config rerere.enabled`). Ablated regions conflict at every upstream
   sync and rerere replays the resolution.
3. **Delete, don't `#ifdef`.** This repo is smaller code, not the same code
   behind flags.
4. **Docs follow code**: a paragraph about something not in this repo is
   deleted, not adapted. Docs are in English.
5. **Never `git merge -X ours/theirs`.**
6. **Never commit or push without an explicit user request.** Editing, testing,
   staging, or reading a checklist is not permission.
7. Commit subjects: `ablate(<area>):`, `simplify(<area>):`, `sync: upstream <sha7>`,
   `fix(<area>):`, `perf(<area>):`, `sf:`. Tags `sync-<sha7>` on `main` after
   every landed sync.

## Child-specific values

All in one block of the `Makefile`, each read at exactly one place:

| Define | Value |
|---|---|
| `SF_DEFAULT_MODEL` | default for `-m` |
| `SF_DEFAULT_PORT` | `8002` |
| `SF_HOME` | `~/.sf/ds4-1flash` |
| `SF_LOCK_FILE` | `/tmp/sf-ds4-1flash.lock` |

`DS4_*` environment variables are upstream's and are **not renamed**. Set them
inline (`DS4_METAL_CB_TIMES=1 ./sf-ds4-1flash ...`), never `export`.

## Speculative decoding: none

This child has no speculative decoding at all, and it is the only one of the
four where that is true. `--mtp`, `--mtp-model`, `--mtp-draft`, `--mtp-margin`,
`--mtp-timing`, `--mtp-exact-sampling`, `--dspark`, `--dspark-confidence` and
`--dspark-strict` do not exist in any frontend; `ds4_engine_has_mtp()` returns
false and `ds4_engine_mtp_draft_tokens()` returns 0.

Do not reintroduce them, and do not infer a mechanism from an identifier's
name: `glm_mtp` was the built-in-MTP switch every MTP model shared, not a GLM
thing, and it is pinned false here.

The DSpark draft/verify engine is still compiled in, marked `sf-keep` in
`ds4.c`. It hangs off `ds4_gpu_graph`, the DeepSeek V4 Flash/PRO Metal graph
that this model never allocates: `ds4_session_create` early-returns for
`DS4_MODEL_FAMILY_DEEPSEEK41` into `ds41_graph_alloc`. So it is unreachable at
runtime but still structurally reachable from live session helpers that clear
its state unconditionally. Removing it means removing the whole `ds4_gpu_graph`
session path, which also hosts twelve `metal_graph_*` helpers the `ds41_*`
graph does call. That is a separately measured ablation.

## Names that lie: do not remove by name, verify by reachability

Upstream grew several models in one tree, so many identifiers carry the name of
the model they were written for, not of the code they now serve. What this
child has established:

| Name family | What it really is here | Evidence |
|---|---|---|
| `glm_graph_*` | **dead in this tree**, unlike in `sf-q3-8flash` where it is the shared Metal graph host. The GLM-DSA session opens only under `DS4_MODEL_FAMILY_GLM_DSA`; V4.1 uses `ds41_graph_alloc` | `ds4.c` `ds4_session_create`: the DEEPSEEK41 early-return precedes any glm_graph code |
| `glm_graph_env_value`, `glm_graph_host_memory_bytes`, `qwen4_prefill_chunk_tokens` | shared helpers wearing a foreign name, called from live V4.1 paths | a prefix sweep over `glm_graph_*`/`qwen4_*` breaks memory admission |
| `ds4_gpu_mgpu.h` | not a CUDA header: the only reachable definer of `DS4_MAX_GPUS`, `struct ds4_gpu_tensor` and `ds4_gpu_config` for **both** the Metal and the CPU build | `ds4.c` includes it unconditionally; it sizes ~190 live graph arrays |
| `ds4_gpu_args.c/.h` | the opposite trap: the name says CUDA, `nm` says two pure-C string functions. Removed because the `--gpu*` flags went, not because it was CUDA code | `nm -u` resolved no CUDA symbol |
| `metal_graph_cuda_*`, `engine_cuda_tp_*` | the Metal graph host, named after the feature CUDA had first. Live, and not guarded by any CUDA macro | ~40 functions with live call sites |
| `glm53_quantize.py`, `glm53_validate_gguf.py`, `glm53_manifest.py`, `deepseek4_vision.py` | dependencies of **this model's** converters | `deepseek41_quantize.py`, `deepseek41_validate_gguf.py` and `deepseek41_vision.py` import them |
| `metal/deepseek4_vision.metal`, `metal/glm53_bf16.metal`, `metal/glm53_vision.metal` | required by the V4.1 vision encoder | deleting them breaks vision, not GLM |
| `tests/vision-fixtures/glm53/` | plain PNG/JPEG test data read by four kept tests | see that directory's README |
| `tests/test-vectors/flash-0731/` | a **prompt index** for `--metal-tensor-equivalence` and `--streaming-decode-prefill-correctness`, which compare two compute paths on *this* model. The expected logprobs inside `official.vec` are DeepSeek V4 Flash's and are never read by those tests | restored verbatim from upstream after deleting the tree broke both tests with `fp != NULL` |

Two oracles that the compiler cannot give you:

- `-Wunused-function` is a front-end diagnostic. A call inside a branch the
  optimiser folds away still counts as a reference, so a guard has to be
  removed as **text** before anything downstream falls out. And only `ds4.o`
  reports: `ds4_cpu.o` and `ds4_cpu_test_hooks.o` compile the same source with
  `-Wno-unused-function`, so they are verifiers, not oracles.
- `ds4_metal.m` separates models by function **name**, not by any family test,
  and its functions are exported. There the linker is the oracle: `nm -g` on
  `ds4_metal.o` against `nm -u` on every other object, with references internal
  to the same object closed over first.

The Metal library is assembled at **runtime** by concatenating `metal/*.metal`
from a hard-coded table in `ds4_metal.m`. A deleted kernel file must lose its
row there or startup fails with "Metal source not found", and no build step
catches it. `make test-mxfp4-metal` compiles the library and dispatches, so it
is the runtime oracle for that table.

## Models, build, test, verify

Models live once in the shared Hugging Face cache, not in this repo.
`download.sh <component>` calls `hf download` for this child's fixed Hub repo
and filename, then creates/updates a component symlink in `gguf/`. For the
main model it also updates the root default-model symlink to that component.
The cache location is `$HUGGINGFACE_HUB_CACHE`, else `$HF_HOME/hub`, else
`~/.cache/huggingface/hub`. Never use `curl`/`wget` or copy a GGUF into this
repo. `hf download` handles cache reuse, resume and verification.

```sh
make                 # the four binaries
make test            # model-less tests: seconds, run after every change
make help            # remaining targets (model-backed tests follow gguf/ symlinks)
./download.sh        # lists components; ./download.sh <component> fetches/symlinks one
```

Model-backed checks before a PR: the kernel tests of this model, `ds4_test`,
the exact speculative mechanism in Identity (DSpark, MTP, or none),
`./sf-ds4-1flash-eval`, and the **parity oracle** run from the StarForge orchestrator
(`tools/parity-check.sh sf-ds4-1flash`): upstream at our merge-base vs this repo,
same GGUF(s), same prompts (`tests/parity_prompts.txt`), greedy,
token-identical output, speed within ±2%.

## Removing code (ablation)

> Remove what is unreachable for this model on Metal, by reasoning. Small
> batches, `make test` after each. If a doubt is high and no test resolves it,
> leave the code with an `sf-keep` marker.

Order of tools: (1) the compiler — with the shape frozen, `-Wunused-function`
lists dead functions; (2) `make test`; (3) model-backed tests; (4) parity
oracle. Do not ablate in a first pass: the CPU forward code in `ds4.c`;
kernels shared with removed models (only clearly-tagged kernels go).

## Syncing with upstream

Done from the orchestrator (`SYNC.md` there), summarized:

```sh
git fetch upstream
git checkout -b sync/<sha7> main && git merge upstream/main
# modify/delete where we deleted → keep deleted (git rm)
# content conflicts → rerere first, then by hand; dropped code in a live file → sf-ablate marker
make test  →  model-backed tests  →  parity oracle
# commit/push/PR/main/tag only after the user explicitly asks
```

If upstream renamed or split a `ds4_*` file: stop and ask a human.

## When to stop and ask

- A conflict in `ds4.c` / `ds4_metal.m` on code not clearly tagged for a removed model.
- `make test` green but parity oracle red.
- You are about to remove steering, TP/RDMA, the CPU path, or anything in the Identity table.
