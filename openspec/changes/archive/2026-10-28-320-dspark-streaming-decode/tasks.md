# Tasks

Starts only after `310`'s decision is "go to 320". Work happens on a branch in a worktree, never on main.

## 1. Harness tool step (S0)

- [ ] 1.1 Add `speed-bench/` code text (a C file of this tree, with its SHA-256 in `speed-bench/README.md`) and the `decode-code` kind to `ab_bench.py` (outside `all`, the mix and the record row). Verify: an A/A on main with `--kinds decode-code` is bitwise with no metric below zero, and `--kinds all` does not run it.

## 2. The port (S1)

- [ ] 2.1 Loader and flags: the support-GGUF loader and metadata check (V4.1 branch only), `--dspark`, `--mtp-model` and `--dspark-confidence` in the CLI and the bench, the startup size line, and the refusals of the spec. Verify each refusal scenario of `dspark-drafting` by running it.
- [ ] 2.2 Drafter, cycle and back-off from #1073 by call site (D1), the streaming gate removed, sampling turning drafting off (D6), and the bench counters. Keep D7b's arguments and `DS4_DSPARK_SPEC_LOG` (classified in `ds4_env.def`). Verify that `make` builds without warnings (`make env-check` included), and that a 256-token greedy run under `--ssd-streaming --dspark` prints counters with accepted tokens.
- [ ] 2.3 Verify rows under streaming (D3): a widened mailbox, the union lookup, misses on the decode path, rows-form expert kernels (`310`'s configuration). Verify the expert-cache counters include the verified rows' reads.
- [ ] 2.4 Tests (D2): rows test (k = 1..5 at 2048 and 8192, logits and KV bitwise) and rollback test (forced rejection at each j), both in `make test`. Verify by reading the names of the tests that ran.
- [ ] 2.5 Measure S1 (D7): B without the flag against main, `--kinds decode,append --bitwise`; then B with `--dspark --mtp-model <file>` against main, `--kinds decode-code,decode`, with pooled CIs. Verify the keep rule and `310`'s prose rule; append the rows to `perf-record.md`.

## 3. Reviews and output check

- [ ] 3.1 Short review after S1, then the final pass over the touched region: check it against `AGENT.md`, delete what the port made dead, and measure each refinement like a step. Verify `make test` and the harness rows.
- [ ] 3.2 Greedy 1024 tokens with and without the flag on `tools/parity/sf-ds4-1flash.txt` and one image prompt. Verify identical tokens; on an image mismatch, apply the image fallback of the design's risks (no drafting with image tokens) and add it to the spec.
- [ ] 3.3 `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` from the StarForge checkout (without the flag). Verify a pass.

## 4. Files and documentation

- [ ] 4.1 `download.sh`: a DSpark component for `310`'s file (`hf download` into the shared cache, symlink in `gguf/`). Verify that a dry run prints the expected file and symlink.
- [ ] 4.2 Child docs (D8): `AGENTS.md` (the identity row, the section rewritten, "Names that lie"), a `README.md` section (flag, memory, measured gains per kind, why prose gains little), and `docs/upstream-prs.md` lines `adopt -> 320`. Verify there is no paragraph left that says this child has no speculative decoding.
- [ ] 4.3 Prepare the StarForge registry change (D8) in the orchestrator checkout, uncommitted. Verify `tools/lib.sh` and `AGENTS.md` agree.

## 5. Integration

- [ ] 5.1 `make test`, the harness rows, parity and `openspec validate 320-dspark-streaming-decode --strict`. No commit or push without a request; the change lands as one signed commit with its refinements.
