# Design

## Context

- The inputs are this change's two notes files. `review-notes-2026-09-25.md`
  covers the 69 PRs commit by commit and gives the head SHA analyzed for each
  one. `triage-candidates-2026-09-25.md` lists the 211 candidates with their
  hit counts.
  - The review also used a scratch bare clone and TSV files. Those lived in
    the session scratchpad and are not kept.
- 68 of the 69 PRs read are among the 211. The 69th is #1083, which is
  CUDA-dominated and was read as the successor of #1082. So the other
  candidates number 143, not the 142 the proposal first said.
- The sibling registry (`sf-q3-8flash/docs/upstream-prs.md`) supplies the
  skeleton: purpose, finding what changed, verdicts, PRs, commits, excluded.
  - That registry covers two large PRs, one line per commit.
  - Here there are 69 PRs, and #1073 alone has 54 non-merge commits.
- `openspec/config.yaml` has no `context:` yet. The workflow skips a context
  larger than 51,200 bytes without any error.
- `openspec/` and `.claude/` (the OpenSpec commands and skills) are untracked.
  `sf-q3-8flash` added the same two trees and its registry in one commit
  (`841c2df`).

## Goals / Non-Goals

**Goals:**
- A later review can compare upstream against the registry in minutes, using
  the recorded heads, the verdicts, and the commit lines that someone acts on.
- Every later artifact of this child applies the context entry.

**Non-Goals:**
- Re-running the 2026-09-25 funnel. Its counts are a dated snapshot. A later
  review runs the funnel on new PRs only.
- Re-judging verdicts. The registry copies the verdicts already decided. New
  verdicts come only from the re-triage (D5).
- Editing the notes after this change. They are dated evidence. A later
  review writes its own notes in its own change.

## Decisions

### D1. The q3 skeleton, with three differences

**a. Commit lines only for verdicts that someone acts on.** These are
`adopt`, `idea`, `drop: output`, `history`, `next sync` and `open`. Commits
with any other verdict are summarized in their PR's row.

- Alternative: one line per commit, as q3 does. That is about 300 lines,
  mostly "not reachable", and no later step reads them. The recorded head
  already lets a review find new commits.

**b. No `Updated` column.** A later review finds changes through `Last
review:`, the `updated:>=` search and the recorded head. A per-PR update date
would be a third record of the same fact.

**c. `history` takes a tag from a closed list.** A future hardware change can
then find its lines with one grep.

| Tag | Condition that makes the work relevant |
|---|---|
| `disks` | more disks, or much faster I/O |
| `resident` | enough RAM to keep the main weights resident |
| `two-macs` | a second Mac (a TP pair or a pipeline split) |
| `chip` | a chip other than the M5 Max |
| `quant` | a Q4_K or MXFP4 GGUF |
| `long` | contexts of 128K tokens and above |
| `zone` | the code zone belongs to another PR; relevant if that PR is dropped |

Tags combine with `+`: #1090 is `history: resident + chip`.

### D2. The proposal decides verdicts; the notes supply reasons and detail

The notes were written with the subagents' analyses. The proposal's lists
came after the owner's rules. Where the two differ:

- **#1049.** The notes say `drop`; the proposal says `history`. It becomes
  `history: resident`: the owner asked that resident-only work stay findable.
  The reason records that the author closed the PR at +0.79%.
- **#1073's nine TP commits.** The notes' split holds:
  - six are `history: two-macs`: `9f3892d2`, `a13b513e`, `867465cc`,
    `c9bfdcc9`, `83876259`, `4fe6a780`;
  - `8d73a0ef` is `drop`;
  - `dc81436d` is not reachable;
  - `5c2dac7e` is `next sync`.

  The proposal's "except `8d73a0ef`" was shorthand for this.

The proposal left some commits without a verdict. They are placed here
(checked in the scratch clone on 2026-09-25):

- #1073, taken with the `d8d1523b` port, so `adopt -> 70-decode-glue-fusions`:
  - `a3f6f313`, the decode-control test that the `--decode-switch` runs use;
  - `c6f4086f`, the RoPE quantize test folded into the Metal test;
  - `0ac42d6f`, `8be10050` and `a15028ee`, only the hunks the port needs.
- #1073, dropped:
  - `7d89c59c` is `drop`: test plumbing for `4b1b1519`'s wide scorer, which
    is not taken;
  - `c4b66b90` is `drop`, with the reason "already in the child": the
    function it deletes is already gone.
- `open`:
  - #1067 `d1738d2`;
  - #828 `3f20d5e` and `3add8f9`;
  - #621 `61e35e22`;
  - #1090 `34794be8`, only its server KV tool-map rewrite.
- `history`:
  - `resident`: #874 `595e06da`;
  - `chip`: #954 `0c2a0d53`;
  - `zone`: #1042; #952 `2b9d1c20`, `9f7e4eb6`, `2da41a49`, `5d83b550`
    (which needs `0edc5534`) and `ecf0b138`; #1090 `d9758788`'s router, which
    is the fix a #1042 port would need.

Alternative: re-derive every verdict from the diffs during apply. That redoes
the review.

### D3. Heads and counts come from `gh`, not from the scratch clone

- **Head:** the SHA in the notes, shortened to 7 characters as in the family
  (`sync-<sha7>`).
- **Commit count:**
  `gh api repos/antirez/ds4/compare/0aaea5a...<head> -q .ahead_by`. It is one
  command for every PR, whether or not its head has moved since, and it
  counts the same commits GitHub lists: those not in `0aaea5a`.
- **Title, state and subjects:** `gh pr view <N> -R antirez/ds4 --json
  title,state,commits`. For a commit that a force push removed, use
  `gh api repos/antirez/ds4/commits/<sha>`.

### D4. The 143 other candidates are listed by class, numbers only

Each class gets one line of PR numbers:

- server and KV store;
- agent;
- CLI, startup and build;
- tokenizer and loader;
- sampling;
- steering;
- speculative decoding (DSpark, MTP, others);
- CUDA, ROCm and multi-GPU;
- Vulkan;
- CPU and x86;
- other models;
- distributed (a second Mac);
- multi-session batching (streaming sessions are never batched);
- KV or weight quantization and model variants (excluded by the output rule);
- quantizer and offline tools;
- refactors on a May base.

A PR's class comes from its title and its hit columns. A PR that could reach
V4.1's Metal or streaming code and fits no class cleanly is read and gets a
row instead. Two such PRs are known now:

- #947, the M5 tensor enable, which `sf-q3-8flash` found already in its
  baseline;
- #798, V4 Flash SSD and DSpark fixes, with 176 streaming hits.

Alternative: one row with a reason per PR. That makes 143 reasons no one
reads, and the triage file already keeps each PR's hit counts.

### D5. Re-triage at apply time

Before any row is written, the two "finding what changed" commands run with
`updated:>=2026-09-25`.

- **A PR already read whose head has moved:** its new commits are triaged.
  Those with a verdict someone acts on get lines, the PR's summary is
  updated, and its recorded head advances.
- **A PR not yet seen:** it goes through the funnel's file and dominance
  tests. It is then either read and given a row, or put into a class.

`Last review:` is the date of that run. `sf-q3-8flash` did the same in its
section 3.

### D6. The notes stay with the change

The notes move with the change when it is archived. The registry names them
by change, not by path: "the archived change `10-upstream-pr-intake`
(`openspec/changes/archive/*-10-upstream-pr-intake/`)".

Alternative: move them to `docs/`. But `docs/` follows the code, and these
notes are dated evidence.

### D7. The context entry holds only what `AGENTS.md` lacks

- It keeps q3's wording where a rule is the same.
- It is rewritten where this child differs:
  - streaming-only measurement at a fixed 75 GiB dynamic cache;
  - parity through `SF_PARITY_FLAGS=--ssd-streaming`;
  - the metric of the phase a change touches, and the typical mix;
  - the 800-line threshold;
  - `history`.
- Rules that `AGENTS.md` already states are left out:
  - no commit or push without a request;
  - no speculative decoding.

  `AGENTS.md` is loaded into every session, and a rule kept in two places
  drifts. The proposal's rule list is trimmed to match.
- Target size: about q3's, 4-6 KB. That is far below the 51,200-byte limit,
  and the entry is added to every `openspec instructions` call.

### D8. The funnel is recorded as criteria, not as scripts

The review's two scripts lived in the scratchpad. The registry's method
section records what they computed. That is enough to run the funnel again on
new PRs:

- **Patches not in main:** `git cherry <main> <head>` prints at least one `+`.
- **Engine files:** the diff touches `ds4.c`, `ds4_metal.m`, `metal/*`,
  `ds4_engram.[ch]`, `ds4_deepseek41_gpu.h` or `ds4_gpu.h`.
- **Hits:** count the changed lines that match each pattern below, ignoring
  case. The changed lines are those of `git diff -U0 <merge-base> <head>` that
  match `^[+-][^+-]`, with `*.csv *.json *.md *.txt *.svg *.png` left out.

  | Hit | Pattern |
  |---|---|
  | V4.1 | `ds41\|deepseek41\|dsv41\|flash41\|v4\.1\|v41` |
  | Engram | `engram` |
  | SSD | `stream\|ssd` |
  | GLM | `glm` |
  | Qwen | `qwen` |
  | CUDA | `cuda\|\.cu\b\|hip\|rocm` |
- **Dominance:** a PR is kept when
  `GLM + Qwen + CUDA <= 4 × (V4.1 + Engram + SSD + 2)`.
- **Reach:** take the function name from the header of each hunk in an engine
  file, and look it up among the child's identifiers. Those are the words of
  its `ds4*` and `metal/*` sources.

Alternative: commit the scripts. That turns two throwaway scripts into a tool
someone has to maintain, when the criteria fit in five lines.

### D9. Git

- Work happens on branch `sf/10-upstream-pr-intake`, created from `main`.
- When the owner asks, the change lands as one commit:
  `sf: add the upstream PR registry and the OpenSpec perf plan`. It holds
  `docs/upstream-prs.md`, `openspec/` and `.claude/`, as q3's `841c2df` did.

## Risks / Trade-offs

- **A head moved, or was force-pushed, between the review and the apply.**
  Mitigation: D5, and the force-push fallback in the registry.
- **A PR put into a class hides a V4.1 change.** Mitigation: D4's rule that
  an uncertain PR is read. The triage file keeps its hit counts for a later
  look.
- **One-line reasons lose the notes' nuance.** Mitigation: each row names
  its notes section, and the notes stay in the archive.
- **Effects in the registry are estimates.** Mitigation: a summary says
  "estimated" until a change measures it. The measuring change then updates
  the line with its numbers, as q3's `30`-`60` did.
- **The context entry is skipped without an error.** Mitigation: tasks check
  its size, and check that `openspec instructions` prints it.
- **The scratch data is gone.** Mitigation: by D3, nothing depends on it.

## Migration Plan

None: no source, build or test file changes. Rollback deletes
`docs/upstream-prs.md` and the context entry.
