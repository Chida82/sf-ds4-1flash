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

| Key | Source | What to run |
|---|---|---|
| `td-full` | `LocalLLaMA/typed-decisions`, already fetched by `convert.py` | **all 400 states, 2,000 decisions** (`820` ran 100 states). If the dataset has a named test split, also report that split alone, since published figures are on it. The `a000` run of `td500` on template 2 counts towards it: run only the other 1,500 |
| `jevbench-231` | `github.com/fstandhartinger/jevbench`, `datasets/public/{original,easy,hard}.jsonl` (protocol `jevbench::v1.2`) | all 231 items |
| `jevify` | `github.com/fidecastro/jevify`: suites `policy-29`, `policy-hard-52`, `long-state-24` | all items; skip `doom-frames-41` (images) |

An item whose question type is `box`, needs an image, or has more than 26
options is skipped and counted in the record ("skipped: n, reason").

`convert.py --source jevbench|jevify --path DIR --out FILE`: read the item
files (read the format first; write the field mapping as a comment), emit the
`820` item format. Unit test in `tests/test_sysone_bench.py` on a three-item
sample file written by hand in the test, one per type.

## References (owner's choice, 2026-11-13)

Four fixed references, the same on every set: **Jev 1.13.0** (TypeSafe, the
product the API copies), **CLM-8B** (Contrastive-LM, the best-known open
System One), **the best Qwen-derived system** (a quality base model, not
DeepSeek), and **Rizzo Flow** (the open design closest to this one). A
reference with no published figure on a set has an empty cell ("-"); do not
substitute another system in its column. The last column is the best
published figure on the set from any system that is neither DeepSeek nor
reasoning, so every set has at least one comparison.

| Set | Jev 1.13.0 | CLM-8B | Best Qwen-derived | Rizzo Flow | Best other, non-DeepSeek |
|---|---|---|---|---|---|
| `td-full` | 0.727-0.738 | - | stock Qwen3.6-27B by logits 0.737 | 0.648 | stock Gemma-4-31B 0.741 |
| `jevbench-231` | 200/231, **per item** | 94/231 | NInfer Qwen3.8-Flash-Next mixed 207/231; swanOne (Qwen3.8-Flash-Next) 205/231 | - | Plumb-4B, JevOne 207/231 (tied with NInfer) |
| `policy-29` | - | - | `qwen3-vl-reranker-8b` 26/29 (a reranker) | - | `ternary-bonsai-2-27b`, `gemma-4-e4b-it` 29/29 |
| `policy-hard-52` | - | - | `qwen3-vl-reranker-2b` 34/52 (a reranker) | - | `ternary-bonsai-2-27b` 46/52 |
| `long-state-24` | - | - | - | - | `ternary-bonsai-2-27b` 24/24 |

Where to read them (copy each figure with its source and version into the
record; all are self-reported by the benchmark or the project, none
reproduced here):
- jevbench: `results/v1.2/jevbench-v1.2-per-task.json` has, for 52 systems,
  the outcome of every public item (`public_tasks`: `c` correct, `w` wrong,
  `f` failed, `n` not attempted). Jev 1.13.0 is there. CLM-8B, NInfer and
  swanOne are only in `results/v1.4.2.2/jevbench-v1.4.2.2-results.json`, as
  `public_accuracy` (verify that it times 231 is an integer before using it: Autoloops' 0.928 is not, so it is over another item count and is left out).
  The "best Qwen-derived" row is the highest `public_accuracy` whose display
  name or `underlying` names Qwen; also report the best by `sealed_accuracy`
  if it is a different system.
- jevify: its `README.md` tables (recipes and counts).
- typed-decisions: the sources listed in `docs/system-one.md` section 11.

DeepSeek rows are never references. The DeepSeek API run on jevbench is used
only for the quantization check below.

The jevbench sealed set (308 items, chance 0.293) is where systems separate:
Jev 1.13.0 scores 0.866 public but 0.367 sealed. It can be measured only by
giving the evaluator a reachable endpoint, and the owner does not want a
public endpoint now. Record the published sealed figures of the references
beside the table, and "not run: no public endpoint" for ours.

## Runs (server: `--ssd-streaming --ssd-streaming-cache-experts 82GB --ctx 32768`)

For each set:

1. `run.py --mode sysone` on every item.
2. Calibration: `fit.py` on the items whose id hash is even, then score the odd
   half raw and calibrated (this is `fit.py`'s existing split). Never fit and
   score on the same items.
3. `run.py --mode think --effort medium`: `/v1/chat/completions` with
   `"reasoning_effort":"medium"`, `max_tokens` 8192. The reasoning comes back
   in `reasoning_content` and is never parsed; the answer is the first option
   symbol in `content`. Empty or unparsable content counts as wrong and is
   counted separately; a `finish_reason` of `length` is counted too. Items:
   all of `jevbench-231`, `policy-29` and `policy-hard-52`; every tenth
   decision of `td-full` (200); not `long-state-24`.

Measured on one item (`hard-sol-a-multi_hop-09`, 4 options, 2,147 prompt
tokens, 2026-11-13): plain readout answered `confirm_l3` at 0.460 against
`require_steward` at 0.445 (wrong, `unstable`); medium effort reasoned for
267 completion tokens, about 10 s at 26 tokens/s plus a 13 s cold prefill,
and answered `C` (`require_steward`, right). Budget about 25 s per item cold
and 12 s with the state cached: about 2 h for the 512 thinking items.

`run.py` changes for step 3: an `--effort` option (`none|low|medium|high|max`,
default `high`, so `820`'s runs stay reproducible), and per item the
`completion_tokens`, `finish_reason` and the length of `reasoning_content`
in the output row. The report gains p50 and p95 of completion tokens.

`long-state-24` has states of 2k-32k tokens: run it last, alone, and record
the state prefill time per item.

Use `--deadline` to bound each run; a run cut by the deadline is reported
with its real n.

## Quantization check (Q2 against the production model)

Our weights are Q2. A score level with the references could be a quantization
loss, not a property of the model. jevbench's per-task file holds
"DeepSeek V4.1 Flash (thinking default)", the same model through DeepSeek's
production API (full precision): 226/231, every public item.

`sysone-bench/jb_compare.py --per-task FILE --results r.jsonl --items
items.jsonl [--system NAME]` (new, stdlib): for every system of the file,
accuracy on the 231 items and, against our results, the two discordant counts
(ours right and theirs wrong, the reverse) with the exact two-sided sign-test
p-value on them. A unit test on a hand-written two-system file.

Run it on our `think --effort medium` results against the DeepSeek row, and
on our plain readout against Jev 1.13.0. Read the first as:
- gap within 2 points, or p ≥ 0.05: no measurable quantization loss on this
  set;
- otherwise: rerun only the items we got wrong and they got right, with
  `--effort high`. If high recovers most of them, the gap is effort, not
  weights; if not, write "Q2 costs about N points with thinking on jevbench",
  N being the remaining gap. The API's default effort is not documented in
  the file: say so.

The check cannot separate quantization from the prompt: the API run used
jevbench's own adapter. Write that limit beside the result.

## Table (`sysone-bench/record.md`, "Public benchmarks")

One row per set and mode: n, accuracy with the state-level bootstrap interval
from `metrics.py`, NLL, ECE, p50 and p95 ms, and for `think` the p50/p95
completion tokens. Beside it the five reference columns above, each with its
source URL and version, and the note "self-reported, not reproduced". Our p50
beside each reference's published p50 where one exists (jevbench `speed`
`p50_s_raw`, jevify's ms column).

## Verdict (write it, do not soften it)

Per set, per reference with a figure, with our accuracy `a` and its interval:
- **ahead**: the interval's lower bound is above the reference;
- **behind**: the upper bound is below the reference;
- **level**: otherwise.
Where the reference has per-item outcomes (Jev on jevbench), use the sign test
instead: ahead or behind only at p < 0.05.

Do it for the plain readout and for `think`. Overall line, one of:
- "quality justifies the model": plain readout ahead of the best Qwen-derived
  system on at least two sets and behind on none;
- "no quality advantage in plain readout": otherwise. Then add the `think`
  figure: if `think` is ahead of every reference with a figure by 5 points or
  more on a set, write that the advantage exists only with reasoning, which
  points to `a025` and `a035`. Add the quantization check's line.

## Risks

- typed-decisions labels are model-generated: agreement with them is not
  accuracy. Say so in the table's caption.
- Benchmark versions differ between publications; quote the version with
  every score and do not compare across versions without saying so.
- The jevbench public set is near saturation for the stronger systems (Jev
  0.866 public, 0.367 sealed): "level" on it says little. Say so.
- `think` is not a System One: it costs about 10 s and 270 tokens per
  decision at medium. Report it as the model's ceiling, not as the endpoint's
  score.
