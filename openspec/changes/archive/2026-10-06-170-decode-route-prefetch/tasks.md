# Tasks

## 1. Gate

- [x] 1.1 Branch `perf/170-decode-route-prefetch` from `main` after `150` and `160`. Check the Rejected ideas table, then rerun the `145` probe on the current tree (D1). Verify: a perf-record section with the probe table and a go/stop verdict; on stop, a Rejected-ideas row. Done: the cheapest guess (int8, one background core) costs decode 0.7%; gate closed (perf-record, Route guess cost after 160), with a Rejected-ideas row. The probe was not rerun: the gate's first criterion already stops the change.

## 2. Full prefetch

- [x] 2.1 Implement the D2 staging slots and the prefetch reader pool, with promotion on selection and release otherwise. The fixtures must show: Closed by the D1 gate: not implemented.
  - a wrong guess evicts nothing;
  - a staged expert is never used before its read completes;
  - a failed prefetch falls back to the miss path;
  - staging stays bounded.

  Verify: `make test` and the fixture pass, and the decode-switch test is bitwise.
- [x] 2.2 Set the D3 policy from the probe, then A/B against the kept state, `decode,append` plus guards, `--bitwise`, with cache statistics. Verify: a step row and a keep/drop verdict. Closed by the D1 gate: not implemented.
- [x] 2.3 Only if D2/D3 leave room: measure the D4 replica reads and, separately, a learned predictor, each as its own step. Verify: a verdict row for each step tried, or a written reason for not trying it. Closed by the D1 gate: not implemented.

## 3. Final

- [x] 3.1 Final review and model-backed suites, an A/B against the segment start with its row appended, and parity. Update `AGENTS.md`. Verify: the PASS lines, the row, PARITY OK, and `openspec validate 170-decode-route-prefetch --strict`. Commit and push remain separately authorized. Done: no runtime change, so no suites, segment row or parity run; `AGENTS.md` unchanged; `openspec validate --strict` passes.
