# Tasks

## 1. Registry

- [ ] 1.1 Fetch the heads of #1073 (`cad7933`), #1135 (`e5b19e2`), #1167 (`7217598`), #1168 (`8f60f7d`), #1192 (`d851854`) and #1204 (`4203d5f`) as read-only refs in the upstream mirror. Verify that each head SHA matches `gh pr view`.
- [ ] 1.2 `docs/upstream-prs.md`:
  - the #1073 row and its commit table moved to `cad7933`, with lines for `4f80638`, `ff95f53` and `cad7933`;
  - the nine DSpark commits set to `open` ("assigned by `310`"), and the Commits prose updated;
  - new rows for #1135, #1167, #1168, #1192 and #1204, with #1167 and #1168 as `idea -> 350` and `idea -> 330`.

  Verify that every commit a later change acts on has a line, and that the PR count in Method is updated.

## 2. #1135

- [ ] 2.1 Reachability by D1: a scratch counter at the compressed-mask copy, run once with a text prompt and once with an image prompt. Verify the result on the PR line (reached by text, by vision, or not reached).
- [ ] 2.2 If reached: run the PR's analytic test against main's kernel. If it fails, port `kernel_dsv4_causal_comp_mask`, the encode change and the test. Verify all of these:
  - the test passes;
  - harness `--kinds decode,append --bitwise` A = main, B = step: text output bitwise;
  - the image reproducer's first differing position is recorded.

  Set the line to `adopt -> 300`.

## 3. #1192 and #1204

- [ ] 3.1 #1204 against `70` S4f, site by site. If it adds nothing for one row, the verdict is `in main, modified` with the reason. Otherwise it is a step for 3.2.
- [ ] 3.2 Each reachable remaining commit is ported as a step and judged by the keep rule (sections mode when its predicted effect is below the harness's resolution). Verify the rows in `perf-record.md` and the verdict on its line.

## 4. Integration

- [ ] 4.1 `make test` (read the names of the tests that ran) and `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` from the StarForge checkout when code changed. Then `openspec validate 300-upstream-pr-intake-october --strict`. No commit or push without a request.
