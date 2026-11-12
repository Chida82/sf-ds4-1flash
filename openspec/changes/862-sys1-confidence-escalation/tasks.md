# Tasks

Requires `820` and `860` (built and kept). If `860` was stopped by its gate, do not start.

## 1. Server

- [ ] 1.1 Parse `sf.escalate` (422 rules); `--sysone-escalate C:N` in `ds4_server.c` and `ds4_help.c`.
- [ ] 1.2 Second pass in `sysone_job` through `860`'s think path for the selected questions; response marks; `usage.output_tokens`.
- [ ] 1.3 Unit tests: parse rows, selection by threshold on fixed answers (calibrated and raw, `noul` uses max(p, 1−p)), the response's `sf` entries.
- [ ] 1.4 `make test`, `./ds4_test --server`.

## 2. Bench

- [ ] 2.1 `sysone-bench/escalate_sweep.py`; run it as in the design.
- [ ] 2.2 Table and chosen default in `sysone-bench/record.md`; `docs/SERVER.md` and `docs/system-one.md` describe the option and the cost.
