# Tasks

Requires `810` and `820`.

- [x] 1.1 Trie build from tokenized `k]` paths with the two assertions; model-less tests.
- [x] 1.2 `sf_sysone_trie_probs` (the design's `sf_sysone_big_choice`, see "Answer struct (as built)"): root readout, frontier expansion with restore, renormalization, threshold shares, temperature; model-less tests on a fake readout function (pass the readout as a function pointer so the math is testable without a model).
- [x] 1.3 Model-backed checks in `make test-sysone` (40 Italian number names; the 26-option bitwise check).
- [x] 2.1 Server: limit 255, dispatch at 27, `evaluated_nodes` in `sf`; unit tests for 26, 27, 255, 256 options.
- [x] 3.1 Banking77 through the `s1b` converter (`--suite banking77`) and the 200-item run; record the row with the published figures beside.
- [x] 3.2 `docs/SERVER.md` (limit, cost per extra option), `docs/system-one.md` (approach F result), `sysone-bench/record.md`.
