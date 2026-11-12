# Tasks

Requires `800` and the `820` item files. No engine source is edited:
`git diff main -- ds4.c ds4_metal.m ds4.h ds4_server.c` must print nothing at
the end.

- [ ] 1.1 `sysone-bench/screen_fit.py`: the payload parser function and its two synthetic-payload unit tests (pos 5, pos 300) in `tests/test_sysone_bench.py`. `make test` names the test.
- [ ] 1.2 `sysone-bench/sf_capture.c` with jobs `D` and `T`, the header assertions, the 256-token refusal; `Makefile` target `sysone-capture`. Check `grep -c '^test:' Makefile` is still 1.
- [ ] 1.3 Smoke: three `D` jobs and three `T` jobs from `fixtures-it.jsonl`; the record sizes are exactly 1 + 4 + 104 + 2 × 81920 and 1 + 81920 bytes; the teacher logits equal those of `make test-sysone` for fixture 1.
- [ ] 2.1 `sysone-bench/screen_prep.py`; the Banking77 26-intent subset (reuse `a040`'s converter if it exists, else add it here).
- [ ] 2.2 The capture run. Note the wall time and the skipped jobs.
- [ ] 3.1 Analysis A and B in `screen_fit.py` with their unit tests.
- [ ] 3.2 Run the fit after the capture process exited. Two tables (40 rows each) and the two verdicts in `sysone-bench/record.md`.
- [ ] 3.3 `docs/system-one.md`: the verdicts, with the "what a pass would buy" sentence. Delete the capture file from the work directory.
