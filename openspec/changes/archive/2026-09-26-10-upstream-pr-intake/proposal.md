# Proposal

## Why

Performance work on this child will borrow from unmerged
[antirez/ds4](https://github.com/antirez/ds4) pull requests. There are about
700 of them, and most are unrelated to V4.1, or cannot be measured on the
owner's machine. Nothing in git or OpenSpec records which PRs were read, up to
which head, or what was decided for each commit. Without that record, the
next review has to redo the 2026-09-25 triage from scratch.

The owner's acceptance rules for these changes were settled on 2026-09-25 (see
the context entry below). Every later change must carry them, so they belong in
`openspec/config.yaml`.

## What Changes

- Add `docs/upstream-prs.md`, a living registry modelled on `sf-q3-8flash`'s:
  - A purpose paragraph. The recorded head SHAs say what was reviewed; they are
    not a sync base, which stays in git (`sync-*` tags,
    `git merge-base HEAD upstream/main`).
  - The commands that find what changed since the last review:
    `gh api .../compare/<recorded>...<head>` for new commits, and
    `gh pr list --state all --search "updated:>=<date>"` for new PRs. Also the
    fallback for a force-pushed PR, and the `git cherry` test for "already in
    main".
  - A verdict legend:

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

    The `history` tags form a closed list (`design.md` D1): `disks`,
    `resident`, `two-macs`, `chip`, `quant`, `long`, `zone`.
- Populate the registry with the 2026-09-25 review.
  - **The funnel**, with the commands and criteria, so that a later review can
    reproduce it:

    | Stage | PRs |
    |---|---|
    | PR refs | 708 |
    | unmerged (440 open, 229 closed) | 669 |
    | with patches not in main (`0aaea5a`) | 664 |
    | touching `ds4.c`, `ds4_metal.m`, `metal/`, Engram or the GPU headers | 307 |
    | not dominated by GLM, Qwen or CUDA code | 211 |
    | read commit by commit | 69 |

    The 69 are 68 of the 211, plus #1083: it is CUDA-dominated and was read as
    the successor of #1082.

    Two reachability oracles were used: the pruned child itself (whether a
    hunk's function still exists in it) and call-site reading.
  - One row per PR read commit by commit: number, title, state, head
    analyzed, commit count, verdict summary.
    - Commit lines are added for every commit a later change, sync or review
      acts on: `adopt`, `idea`, `drop: output`, `history`, `next sync` and
      `open`.
    - All other commits are summarized in their PR's row.
  - The other 143 candidates are listed by class (`design.md` D4). A PR that
    fits no class cleanly is read and given a row instead.
  - Verdicts that point at a change:

    | Change | Commits |
    |---|---|
    | `30-decode-layer-queue` | #1041 `bd6f912` (adopt); #1073 `2a281b08`, `29ce2717` (adopt, a variant measured against it); #1034 `9b50495` (test and bench flag only) |
    | `40-ssd-expert-reads` | #570 `a1afb82`; #952 `a2e2ea53`; #621 `8f5a7458`, `f7695ea0`; #1033 `66f757b` (only if a submission delay is measured) |
    | `50-ssd-miss-overlap` | #952 `a3043bb2` (early load only); #849 `60051d4` (idea: port) |
    | `60-prefill-sweeps` | #1073 `ccbf2c08`, `64240fb9`, `798c64f4` (idea: bitwise subset only); #1073 `10118742`, `3b7f8f22`, `ce5a812f`; #952 `bac91c21`, `c12d639a`; #758 `e154aa8` (rb16 hunk only); #864 `482e246` (LUT only) |
    | `70-decode-glue-fusions` | #1073 `e7683961`, `4fbbc4a4`, `edceb7ab`, `d95f8b61`, `1923131d`, and `d8d1523b` without DSpark; with that port, the tests `a3f6f313` and `c6f4086f`, and the hunks it needs from `0ac42d6f`, `8be10050`, `a15028ee` |
  - `drop: output`, each with the benefit given up:
    - #1060: top-k ties;
    - #1061: f32 summation order; a bitwise rewrite is possible;
    - #1089: rewind state differs from a fresh sweep; agent turns at 21K take 54.6 s instead of 7.3 s;
    - #1073 short sweep over token-major tails;
    - #1073 `4b1b1519`, `af7c02b5`, `262b4a66`, `a6b50ff6`, `7da9535f`;
    - #864 split MPP.
  - `history`, by tag:
    - `resident`: #1067, #1041 `fdbf7f2`, #1049, #1120, #874 `595e06da`;
      #1090 is `resident + chip`;
    - `quant`: #1043, #1073 `d744ebb9`, `5432223d`, `e49643ff`;
    - `two-macs`: six #1073 TP commits, `9f3892d2` `a13b513e` `867465cc`
      `c9bfdcc9` `83876259` `4fe6a780`. Of the other three, `8d73a0ef` is
      `drop`, `dc81436d` is not reachable and `5c2dac7e` is `next sync`;
    - `long`: #959;
    - `chip`: #954 `0c2a0d53`;
    - `zone`:
      - #1042;
      - #952's small fusions, `2b9d1c20` `9f7e4eb6` `2da41a49` `5d83b550`
        `ecf0b138`;
      - #1090 `d9758788`'s router;
    - `disks`: none directly. Striped reads over several disks would be new
      work.
  - `open`: #1067 `d1738d2`; #828 `3f20d5e`, `3add8f9`; #621 `61e35e22`;
    #1090 `34794be8` (only its server KV tool-map rewrite).
  - `drop` for correctness or cost:
    - #848: its packer zeroes the expert space the prefill still maps;
    - #559: nondeterministic atomic sums;
    - #306: slower;
    - #832: breaks the tie invariant;
    - #957, #725, #514, #533;
    - DSpark commits: never; this child has no speculative decoding.
  - `next sync`: #1123 (keeping our deletions), #777 / `c813ff15`, #873 (in
    preference to #1027), #852.
- Add a `context:` entry to `openspec/config.yaml` carrying the rules below, so
  that every proposal, design and task list applies them:
  - **Registry and provenance.** The registry is consulted, and adopting or
    rejecting a commit updates its line in the same branch. Provenance goes in
    the registry and in commit messages, never in source comments.
  - **Names.** Change names are `<NN>-<kebab-name>`, numbered in execution
    order.
  - **Output.** No output change: greedy tokens stay identical, and bits too
    where a change claims it. No KV-cache or activation quantization. No
    prefill schedule or kernel that alters bits.
  - **Where to measure.** Only on the owner's M5 Max 128 GB, with
    `--ssd-streaming` and a fixed 75 GiB dynamic expert cache. A change with
    no measurable effect there is recorded as `history`, not ported. Quality
    runs (parity, eval) use `--ssd-streaming` with the largest admitted cache.
  - **Metric.** The metric is that of the phase the change touches: decode t/s,
    or TTFT for prefill.
    - The end-to-end time on the typical mix (prompts of 1-10K tokens, answers
      of 200-2000), computed from the measured phases, must not get worse.
    - Guard scenarios (prompt above 10K, answer above 2000 tokens) that get
      much worse are reviewed case by case.
  - **Keep rule.** Under 800 runtime lines, a step is kept when the pooled
    bootstrap 95% CI of its target metric lies above zero and no other
    metric's CI lies wholly below zero.
    - A neutral step is kept only if it deletes more lines than it adds.
    - Above 800 runtime lines, at least +1.5% on the target metric is needed.
    - Tests and benches do not count as runtime lines.
    - A tool step needs bitwise output and no metric below zero.
    - A prefill kernel step below the harness's resolution is decided on GPU
      section time (`DS4_METAL_V41_STAGE_PROFILE`), as in `sf-q3-8flash`.
  - **End of every performance change.**
    `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`
    passes, and an A/B against the start commit of the current segment of
    `speed-bench/perf-record.md` adds its row.
  - **Porting.** One upstream PR per code zone. Open PRs are ported as soon as
    they pass the threshold.
  - **Reviews.** Two reviews of ported code: a short one per step, and a final
    pass over the whole region, as in `sf-q3-8flash`.
  - **Git.** Work never happens on `main`.

  Rules that `AGENTS.md` already states are not repeated: no commit without a
  request, and no speculative decoding (`design.md` D7).

## Capabilities

### New Capabilities
None. This is a development record, not product behavior (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- New `docs/upstream-prs.md`; one `context:` entry in `openspec/config.yaml`.
- Source material, in this change's folder: `review-notes-2026-09-25.md` (the
  per-commit analyses of the 69 PRs, the facts re-checked in the main session,
  the funnel method, and the runtime size of each candidate commit) and
  `triage-candidates-2026-09-25.md` (the 211 candidates with their hit
  counts).
- No source, build or test change.
- Every later change (`15`-`70`) takes its commit list from the registry.
