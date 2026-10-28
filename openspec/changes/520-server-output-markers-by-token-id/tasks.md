# Tasks

Starts after `510`. Work happens on a branch in a worktree, never on main. No commit or push without a request.

## 1. Measure (D1)

- [ ] 1.1 `--trace` writes each piece's token id. Verify that a traced request's ids decode to the traced bytes.
- [ ] 1.2 Trace the D1 request sets and count marker strings in the output by origin. Do not read completion text: the script reports counts and offsets only. Verify that every boundary of real reasoning and real tool calls came from its control token, and record the counts in this change's design. If any did not, stop and ask the owner.

## 2. Offsets and helper

- [ ] 2.1 The marker-id query in `ds4.c`/`ds4.h`, and the offset record on the job (D2). Verify `make test`.
- [ ] 2.2 `find_marker` (D3), and every marker search site moved to it: the thinking tracker by id, `split_reasoning_content`, the generated-message parser, the DSML tracker and start search, and the three stream encoders. Verify with a grep for the marker literals in runtime code that every remaining hit is a template write.

## 3. Tests and verification

- [ ] 3.1 Model-less tests (D4) in the server unit tests. Verify `make test` names them.
- [ ] 3.2 Model-backed before/after on greedy requests with reasoning and tool calls (identical tokens and bodies), plus the quoting request. Then `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` from the StarForge checkout. Verify each passes.
- [ ] 3.3 `docs/SERVER.md`: markers in output are recognized by token id, and spelled markers are text. `openspec validate 520-server-output-markers-by-token-id --strict`.
