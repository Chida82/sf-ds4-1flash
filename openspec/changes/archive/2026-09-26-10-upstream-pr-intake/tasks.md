# Tasks

## 1. Branch

- [x] 1.1 Create the branch.
  - Run `git switch -c sf/10-upstream-pr-intake main` (design D9).
  - Verify:
    - `git branch --show-current` prints `sf/10-upstream-pr-intake`;
    - `git status --short` lists only `.claude/` and `openspec/`.

## 2. Registry skeleton

- [x] 2.1 Create `docs/upstream-prs.md`.
  - Open with a purpose paragraph: which unmerged
    [antirez/ds4](https://github.com/antirez/ds4) PRs were reviewed for this
    child, up to which head, and the verdict on each commit.
  - Add the sentence that the head SHAs record what was reviewed and are not
    a sync base. The base stays in git: the `sync-*` tags and
    `git merge-base HEAD upstream/main`.
  - Add a `Last review:` line; 3.1 fills it in.
  - Verify: the file exists, and `grep -c '^Last review:' docs/upstream-prs.md`
    prints 1.
- [x] 2.2 Add "Finding what changed".
  - The two commands from `sf-q3-8flash`'s registry: `gh api
    repos/antirez/ds4/compare/<recorded>...<head>` for new commits on a PR
    already read, and `gh pr list --state all --search
    "updated:>=<YYYY-MM-DD>"` for PRs updated since.
  - The force-push fallback, `gh pr view <N> --json commits`, diffed against
    the recorded lines by subject.
  - The "already in main" test: `git fetch upstream pull/<N>/head`, then
    `git cherry -v upstream/main FETCH_HEAD`. A `+` line whose subject is in
    `git log upstream/main --format=%s` means `in main, modified`.
  - Verify: the compare command runs on #1041 from its recorded head
    `fdbf7f2` without an error. It prints any commits newer than that head,
    and nothing if the head has not moved.
- [x] 2.3 Add the verdicts.
  - The legend with the 13 verdicts from proposal.md.
  - The `history` tag table from design D1 (7 tags, combined with `+`).
  - The rule: a change that adopts or rejects a commit updates that commit's
    line in the same branch.
  - The output rule: a commit that changes greedy output, or quantizes the KV
    cache or activations, is `drop: output`, and its line records the
    benefit given up.
  - Verify: the legend has 13 verdict rows and the tag table has 7 rows.
- [x] 2.4 Add "Method".
  - The funnel table from proposal.md, with the note that the 69 are 68 of
    the 211 plus #1083.
  - The criteria from design D8, and the sources from design D3.
  - Where the notes are, by change name and archive glob (design D6).
  - Verify:
    - the stage counts read 708, 669, 664, 307, 211 and 69;
    - `grep -c 'archive/\*-10-upstream-pr-intake' docs/upstream-prs.md`
      prints 1.

## 3. Re-triage what arrived after the review

- [x] 3.1 Run the re-triage (design D5).
  - **Upstream main.** Run `git fetch upstream` and
    `git log --oneline 0aaea5a..upstream/main`.
    - If `main` moved, check every commit the registry plans to `adopt` or
      mark `idea`, `next sync` or `open`, with `git cherry` and by subject.
      Any that landed become `already in main` or `in main, modified`.
    - Record the `main` SHA of the run in "Method".
  - **Updated PRs.** Run `gh pr list -R antirez/ds4 --state all --search
    "updated:>=2026-09-25" --json number,title,state,headRefOid,updatedAt`.
    - A read PR whose `headRefOid` does not start with its recorded head:
      list its new commits with the compare command, and triage them per
      design D1a. Its head in the registry becomes the triaged one.
    - A PR neither read nor among the 211: run the engine-file and dominance
      tests of design D8, using `gh pr diff <N>`. It then gets a row (4.3) or
      a class (4.4).
  - Set `Last review:` to the run date.
  - Verify: "Method" names the `main` SHA the run saw, and `Last review:`
    shows the run date. Coverage is checked in 5.2.

## 4. Populate the registry

- [x] 4.1 Add the "PRs" table.
  - One row per PR read: the 69, plus any the re-triage read.
  - Columns: PR, Title, State, Head analyzed, Commits, Analyzed, Summary
    (design D1b, D3).
    - Head analyzed: from the notes, shortened to 7 characters.
    - Title and State: from `gh pr view`.
    - Commits: `gh api repos/antirez/ds4/compare/0aaea5a...<head> -q
      .ahead_by`.
    - Summary: the verdicts in one or two clauses. Name the notes section,
      and write "estimated" for any effect nobody measured.
  - Verify:
    - every PR number the notes cite has a row. Take the numbers with
      `grep -o '#[0-9]\{2,4\}' review-notes-2026-09-25.md | sort -u`; a loop
      over them prints nothing missing;
    - every head cell matches `^[0-9a-f]{7}$`;
    - #1073's Commits cell is at least 55: 54 non-merge commits plus the
      merge `3d3c83bb`.
- [x] 4.2 Add the "Commits" section.
  - Every read PR with a commit that someone acts on (design D1a) gets a
    `### #<N> (head <sha>)` table. Columns: Commit, Subject, Verdict, Reason.
  - Subjects: from `gh pr view <N> --json commits`. For a commit a force push
    removed, use `gh api repos/antirez/ds4/commits/<sha>`.
  - Verdicts: from proposal.md's lists and design D2.
  - Verify:
    - for each of `30`, `40`, `50`, `60` and `70`, the `-> <change>` lines
      hold exactly the SHAs of proposal.md's mapping row, compared on their
      first 7 characters;
    - a loop prints nothing missing: every PR or SHA in proposal.md's
      `drop: output`, `history`, `next sync` and `open` lists has a line;
    - `grep -o 'history: [a-z+ -]*' docs/upstream-prs.md | sort -u` prints
      only design D1's tags.
- [x] 4.3 Read #947 and #798 (design D4) against the child, plus any PR the
  re-triage flagged.
  - Run `git fetch upstream pull/<N>/head`, then `git cherry -v upstream/main
    FETCH_HEAD`.
  - For each hunk, check whether its function still exists in the child.
  - Give each PR a row, and commit lines where design D1a calls for them.
  - Verify: #947 and #798 have rows, and each of their commits has a verdict
    in the row or on a commit line.
- [x] 4.4 Add the "Excluded" section.
  - List the other candidates from `triage-candidates-2026-09-25.md`, plus
    the PRs the re-triage put in a class.
  - Group them by design D4's classes, one line of numbers per class.
  - Add one line on how a PR was classed, and on the read-if-unsure rule.
  - Verify:
    - every one of the 211 triage numbers appears exactly once, either as a
      row or on a class line. Take them with `awk` from the file's `text`
      block; a loop prints nothing missing and nothing doubled;
    - no class line holds a PR that also has a row.

## 5. OpenSpec context and close

- [x] 5.1 Add a `context: |` block to `openspec/config.yaml`.
  - It holds the rules in proposal.md's list: registry and provenance,
    names, output, where to measure, metric, keep rule, the end of every
    performance change, porting, reviews, git.
  - Use `sf-q3-8flash`'s wording where a rule is the same. Leave out what
    `AGENTS.md` already states (design D7).
  - Verify: `openspec instructions design --change 20-perf-bench-harness
    --json | python3 -c 'import json,sys; c=json.load(sys.stdin)["context"];
    print(c); print(len(c.encode()))'` prints the block and a byte count of
    at most 6,144.
- [x] 5.2 Re-run the search from 3.1. A PR that arrived since then goes
  through 3.1 first.
  - Verify: every number the search prints appears in the registry; a loop
    prints nothing missing.
- [x] 5.3 Read the registry once, top to bottom, against proposal.md and the
  notes.
  - Check that:
    - every summary agrees with its PR's commit lines;
    - no reason contradicts the notes;
    - no line calls an estimated effect measured.
  - Fix what you find.
  - Verify: the checks of 4.1-4.4 still pass.
- [x] 5.4 Check that no source, build or test file changed.
  - `git status --short` lists only `docs/upstream-prs.md`, `openspec/` and
    `.claude/`. Nothing is under `*.c`, `*.m`, `*.metal`, `Makefile` or
    `tests/`.
  - Verify: `openspec validate 10-upstream-pr-intake` passes.
- [x] 5.5 Only once the owner asks for the commit: make one commit on
  `sf/10-upstream-pr-intake` (design D9).
  - It holds `docs/upstream-prs.md`, `openspec/` and `.claude/`.
  - Subject: `sf: add the upstream PR registry and the OpenSpec perf plan`.
  - Verify: `git show --stat HEAD` lists exactly those paths.
