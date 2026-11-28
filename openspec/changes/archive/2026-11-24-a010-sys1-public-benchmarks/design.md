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

## Sets (owner's choice, 2026-11-19)

| Key | Source | What to run |
|---|---|---|
| `jevbench-231` | `github.com/fstandhartinger/jevbench`, `datasets/public/{original,easy,hard}.jsonl` (protocol `jevbench::v1.2`) | all 231 items |
| `jevify` | `github.com/fidecastro/jevify`: suites `policy-29`, `policy-hard-52` | all items |
| `s1b` | `github.com/alilibx/system-one-bench` (Apache-2.0): suites `ag_news`, `boolq`, `sst2`, `sst5`, `xnli_en`, `xnli_fr`, `emotion` | the suite's exact published items: 200 each, XNLI 150 each, 1,300 in all |

Left out, and why (owner, 2026-11-19):
- `typed-decisions`: its labels are a consensus of teacher models, so it
  rewards imitating them; the system that tops it (a 9B fine-tune, 0.800) is
  unremarkable elsewhere. The `a000` runs stay an internal regression check.
- `jevify long-state-24`: 24 cases written by jevify's author, no system has
  a published figure, ours is already 24/24 (record, a010 in progress).
- `s1b` `banking77` (77 options) and CLINC-150 (151): more than the 26 option
  symbols of the readout. The Arabic `s1b` suites: not asked for.
- The suites of arXiv 2610.00346 (GoEmotions, politeness, power, derailment):
  their items are not published, so only an interval comparison on other
  draws would be possible. Not run.

An item whose question type is `box`, needs an image, or has more than 26
options is skipped and counted in the record ("skipped: n, reason").

`convert.py --source jevbench|jevify --path DIR --out FILE`: read the item
files, emit the `820` item format (field mapping in a comment). Unit test in
`tests/test_sysone_bench.py`.

`convert.py --source s1b --path REPO --work DIR --out FILE`: rebuild each
suite as `build_suites.py` does (read it, never run it): the split's row
indices shuffled by `random.Random(0)`, the first N kept, its option texts
copied verbatim. Rows come from the Hugging Face datasets-server API in pages
of 100, cached under `--work`. The API serves the dataset's current revision,
not the pinned one, so every rebuilt suite is hashed as `data_lock.py` does
(canonical JSON per case, sha256 per suite) and **refused when the hash
differs from `data.lock.json`**: a converted suite is exactly the items the
published figures were measured on.

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
| `jevbench-231` | 200/231, **per item** | 94/231 | NInfer Qwen3.8-Flash-Next mixed 207/231; swanOne (Qwen3.8-Flash-Next) 205/231 | - | Plumb-4B, JevOne 207/231 (tied with NInfer) |
| `policy-29` | - | - | `qwen3-vl-reranker-8b` 26/29 (a reranker) | - | `ternary-bonsai-2-27b`, `gemma-4-e4b-it` 29/29 |
| `policy-hard-52` | - | - | `qwen3-vl-reranker-2b` 34/52 (a reranker) | - | `ternary-bonsai-2-27b` 46/52 |
| `s1b` `ag_news` | 0.875 | - | Mammoth-1 (Qwen3.5-27B) 0.920 | - | Laya Router 0.925 |
| `s1b` `boolq` | 0.895 | - | Mammoth-1 0.920 | - | Drex Max 0.930 |
| `s1b` `sst2` | 0.945 | - | Mammoth-1 0.960 | - | d1_1 0.980 |
| `s1b` `sst5` | 0.635 | - | Mammoth-1 0.590 | - | Jev 0.635 |
| `s1b` `xnli_en` | 0.880 | - | Mammoth-1 0.913 | - | Drex Max 0.953 |
| `s1b` `xnli_fr` | 0.767 | - | Mammoth-1 0.860 | - | Drex Max 0.913 |
| `s1b` `emotion` | 0.565 | - | Mammoth-1 0.590 | - | Mercury 0.915 |

For `s1b` the Qwen-derived reference is Mammoth-1, the largest system there
whose base is a declared Qwen model; the best Qwen 9B per suite (Dexy,
Elephant, MSFT-D1) goes beside it in the record. Its "best other" column
includes small systems that may have trained on the source (Mercury's
emotion score); say so in the caption.

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
- `s1b`: `results.json` at commit `40d9b094b51f177b483136ff8441614661ab48a3`,
  `suite:<name>.acc` per system key (`jev` is Jev 1.13.0 on 7 Oct 2026 through
  its own API; `or_jev` the same through OpenRouter). Aggregate accuracy only:
  no per-item outcomes, so the comparison is by interval.

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
   all of `jevbench-231`, `policy-29` and `policy-hard-52`; the first 30
   items of each `s1b` suite (210; their order is already a random draw).

Measured on one item (`hard-sol-a-multi_hop-09`, 4 options, 2,147 prompt
tokens, 2026-11-13): plain readout answered `confirm_l3` at 0.460 against
`require_steward` at 0.445 (wrong, `unstable`); medium effort reasoned for
267 completion tokens, about 10 s at 26 tokens/s plus a 13 s cold prefill,
and answered `C` (`require_steward`, right). Budget about 25 s per item cold
and 12 s with the state cached: about 2 h for the 522 thinking items.

`run.py` changes for step 3: an `--effort` option (`none|low|medium|high|max`,
default `high`, so `820`'s runs stay reproducible), and per item the
`completion_tokens`, `finish_reason` and the length of `reasoning_content`
in the output row. The report gains p50 and p95 of completion tokens.

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

- `s1b` sources are classic public datasets, likely seen in pretraining by
  every model compared, ours included. A 200-item suite has an interval of
  about ±5 points: differences under that are level.
- Benchmark versions differ between publications; quote the version with
  every score and do not compare across versions without saying so.
- The jevbench public set is near saturation for the stronger systems (Jev
  0.866 public, 0.367 sealed): "level" on it says little. Say so.
- `think` is not a System One: it costs about 10 s and 270 tokens per
  decision at medium. Report it as the model's ceiling, not as the endpoint's
  score.
