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
| Shape (`ds4.c`) | `DS4_SHAPE_FLASH41` — `g_ds4_shape` is `static const`; a GGUF with another shape is refused |
| Backend | Metal only. No CUDA, no ROCm. CPU path kept as reference/debug and for model-less tests |
| Binaries | `sf-ds4-1flash`, `sf-ds4-1flash-server`, `sf-ds4-1flash-bench`, `sf-ds4-1flash-eval`. No agent binary |
| Server default port | `8002` |
| Home dir | `~/.sf/ds4-1flash` (CLI history; suggested `--kv-disk-dir ~/.sf/ds4-1flash/kv`) |
| Instance lock | `/tmp/sf-ds4-1flash.lock` (override: `DS4_LOCK_FILE`) |
| Vision | yes |
| Speculative decoding | none |
| Steering | yes (`--dir-steering-file`, `/steer`, `dir-steering/`) |
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

## Speculative decoding contract

Follow the Identity row exactly. A DSpark-only child keeps its separate support
GGUF loader, `--dspark*`, `--mtp-model`, `--mtp-exact-sampling`, DSpark tests,
and shared speculative helpers even when their names contain `mtp`; it removes
`DS4_SUPPORT_MTP_LEGACY`, `--mtp`, `--mtp-draft`, `--mtp-margin`,
`--mtp-timing`, `DS4_TEST_MTP`, and `mtp-verify-depth`. A built-in-MTP child
keeps only its model's MTP path. A `none` child removes both. Do not infer the
mechanism from an identifier's name.

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
