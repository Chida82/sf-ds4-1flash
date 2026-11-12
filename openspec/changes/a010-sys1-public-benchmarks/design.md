# Design

Depends on `810`, `820`. Read `docs/system-one.md` section 11 and
`sysone-bench/README.md` first. Standard-library Python only; install nothing.

## Rules for downloaded material

- Everything goes under the `--work` scratch directory, never into the
  repository.
- Repositories are fetched with `git clone --depth 1` into a new empty
  directory. **Never run code from them**: only read their data files. Run
  `convert.py` from this repository with the data path as an argument, with
  `python3 -I`.
- Before using a set, open its licence file or dataset card and copy the
  licence name into the record. No licence found: do not run it; write "not
  run: licence not established".
- Record the commit hash (repositories) or revision (Hugging Face) of every
  source.

## Sets

| Key | Source | What to run | Published scores to quote |
|---|---|---|---|
| `td-full` | `LocalLLaMA/typed-decisions`, already fetched by `convert.py` | **all 400 states, 2,000 decisions** (`820` ran 100 states). If the dataset has a named test split, also report that split alone, since published figures are on it | Jev 0.727-0.738; stock Qwen3.6-27B logits 0.737; stock Gemma-4-31B 0.741; Rizzo Flow 0.648; fine-tuned Laya 0.766, DeBERTa 0.793 |
| `jevbench-231` | `github.com/fstandhartinger/jevbench`, the public item file (find it in the repository; record its path and the benchmark version string) | all 231 items | Qwen3.5-4B via LLM2Jev 76.2%; open-jev-fast 197/231; Tacit-9B 0.887 (say which version each used, if stated) |
| `jevify` | `github.com/fidecastro/jevify`: suites `policy-29`, `policy-hard-52`, `long-state-24` | all items; skip `doom-frames-41` (images) | DeepSeek-V4-Flash 28/29, 47/52, 24/24 |

An item whose question type is `box`, needs an image, or has more than 26
options is skipped and counted in the record ("skipped: n, reason").

`convert.py --source jevbench|jevify --path DIR --out FILE`: read the item
files (read the format first; write the field mapping as a comment), emit the
`820` item format. Unit test in `tests/test_sysone_bench.py` on a three-item
sample file written by hand in the test, one per type.

## Runs (server: `--ssd-streaming --ssd-streaming-cache-experts 82GB --ctx 32768`)

For each set:

1. `run.py --mode sysone` on every item.
2. Calibration: `fit.py` on the items whose id hash is even, then score the odd
   half raw and calibrated (this is `fit.py`'s existing split). Never fit and
   score on the same items.
3. `run.py --mode think` on the first 60 items (about 30 s each). Empty
   replies count as wrong and are counted separately.

`long-state-24` has states of 2k-32k tokens: run it last, alone, and record
the state prefill time per item.

Use `--deadline` to bound each run; a run cut by the deadline is reported
with its real n.

## Table (`sysone-bench/record.md`, "Public benchmarks")

One row per set and mode: n, accuracy with the state-level bootstrap interval
from `metrics.py`, NLL, ECE, p50 and p95 ms. Beside it the published scores,
each with its source URL, and the note "self-reported, not reproduced".

## Verdict (write it, do not soften it)

Reference for each set: the best published score of a **stock model read by
logits without training** (for `td-full`: 0.741; for `jevify`: the
DeepSeek-V4-Flash counts; for `jevbench-231`: 76.2%).

Per set, with our plain-readout accuracy `a` and its interval:
- **ahead**: the interval's lower bound is above the reference;
- **behind**: the upper bound is below the reference;
- **level**: otherwise.

Overall line, one of:
- "quality justifies the model": ahead on at least two sets and behind on none;
- "no quality advantage in plain readout": otherwise. Then add the `think`
  figure: if `think` is ahead of the reference by 5 points or more on a set,
  write that the advantage exists only with reasoning, which points to `a025`
  and `a035`.

Also write the latency beside the verdict: our p50 against the published
latency of the reference where one exists.

## Risks

- typed-decisions labels are model-generated: agreement with them is not
  accuracy. Say so in the table's caption.
- Benchmark versions differ between publications; quote the version with
  every score and do not compare across versions without saying so.
