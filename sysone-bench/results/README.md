# Bench results

Raw per-item rows of the runs recorded in `../record.md`, kept so later
changes can reuse them instead of running the model again (`a030` reuses the
`a010` plain rows as rotation 0, `a035` the thinking rows). No case text is
stored: rows hold item ids, labels, option logits and probabilities, replies
(an option symbol), timings and token counts. The item files are rebuilt with
`convert.py`, which checks each system-one-bench suite against its published
hash (`record.md`, "Public benchmarks").

| Directory | Change | Files |
|---|---|---|
| `a010/` | public benchmarks | `r-<set>-sys.jsonl` (plain readout, `run.py --mode sysone`), `r-<set>-think.jsonl` (`--mode think --effort medium`; the `s1b-*` ones are the 30-item subsets), `cal-<set>.json` (`fit.py` output); `r-jevbench-sys.jsonl` is the run after the `state_id` fix; `r-jb-window.jsonl` the items 41-90 re-run alone after the runner incident; `r-bk10.jsonl`, `r-jb40-a040.jsonl`, `r-s1b-banking77-sys.jsonl` belong to `a040` |
| `a015/` | schema-first layout (dropped) | `sf.tsv`: `tests/test_sysone --schema-first` rows (id, hit/miss, top, legal mass, schema ms, state ms, suffix ms, state tokens, suffix tokens, logits) |
| `a020/` | prior contrast | `blank-<set>.jsonl`: `run.py --blank-state` rows, id = the question key |
| `a025/` | think trajectory | `traj.tsv`: `tests/test_sysone --think-trajectory` rows (id, n, kind, top, legal mass, logits), probes every 32 tokens; `traj1-noprobe.tsv`: the probe-free control |
