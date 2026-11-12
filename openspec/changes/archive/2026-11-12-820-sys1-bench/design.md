# Design

Depends on `810`. Python is the system `python3`; **numpy is not installed
and must not be installed** (owner's machine rule): everything here is
standard library.

## Item format (JSONL, one decision per line)

```json
{"id":"td-0001","lang":"en","state":"...","question":{"type":"choice","instructions":"...","criteria":{"a":"...","b":null}},"label":"a"}
```

`label`: the option name for `choice`, the level index for `score`, `true` or
`false` for `noul`. `label` may be absent (then only `teacher` agreement is
reported). One question per item: isolation makes multi-question items
equivalent, and one per item keeps latency per decision readable.

## Data sets

| Set | Where it comes from | Use |
|---|---|---|
| `fixtures-it.jsonl` | written in this change: 60 Italian items (20 per type), states of 20-80 words, plain customer-service, scheduling and operations content, labels by construction | smoke and the Italian figure |
| `typed-decisions` | the public set Rizzo Flow and Laya both report (400 cases, 2000 decisions, four workflows). Find its Hugging Face id in Rizzo Flow's `benchmarks/` directory or Laya's model card; fetch with `hf download --repo-type dataset` into the shared cache, never into the repository | the cross-system figure: Rizzo 0.648, Laya fine-tuned 0.766, Jev 0.727 on its test split |
| JevBench public items | 231 items, cited by JevK5 and the LLM-as-Jev paper; locate from the paper's references | optional; skip if the items are not openly downloadable |

`sysone-bench/convert.py` turns a downloaded set into the item format; the
converted files stay in the scratch directory given by `--work`, outside the
repository. Only `fixtures-it.jsonl` is committed. If a set's licence or id
cannot be established, record that in `record.md` and go on with the others.

## `run.py`

```
run.py --base-url http://127.0.0.1:8002 --items FILE --mode sysone|gen|think|teacher
       [--limit N] [--rotate K] [--sf '{"layout":"schema_first"}'] [--out results.jsonl] [--label TEXT]
```

- `sysone`: `POST /v1/systemone` with `"sf":{"debug":true}` merged with `--sf`.
  Records probabilities, legal mass, `sf` timings and wall time.
- `gen`: `POST /v1/chat/completions`, `temperature` 0, `reasoning_effort`
  `none`, `max_tokens` 8. The user message is the state, the question and the
  options written exactly as the `800` template writes them, ending with
  "Answer only with its bracketed identifier." The answer is the first symbol
  found in the reply; none found counts as wrong and as a parse failure.
- `think`: the same with `reasoning_effort` `high` and `max_tokens` 4096.
- `teacher`: `think` twice (the second with `seed` set and `temperature` 0.7);
  the item's teacher label is the answer when both agree, else none.
- `--rotate K` rotates the option order by K before sending and maps the
  answer back (not for `score`).

Requests are sequential (the server serializes them anyway).

Metrics (`sysone-bench/metrics.py`, pure functions):
- accuracy: top equals label;
- NLL: `−ln p(label)`, clipped at `p ≥ 1e-9`;
- Brier: `Σ_k (p_k − y_k)²`, mean over items;
- ECE: 10 equal-width bins on the top probability, `Σ (n_b/N)·|acc_b − conf_b|`;
- `noul` is scored as a two-option question (yes, no);
- latency p50, p95, mean; tokens per item;
- legal mass mean and minimum;
- a 95% bootstrap interval (2000 resamples, fixed seed) on accuracy,
  resampling **states, not items**: sets such as `typed-decisions` carry about
  five decisions per state, and decisions on one state are correlated, so an
  item-level bootstrap understates the interval. Each item file therefore
  carries a `state_id` (the hash of the state text when the set gives none).

The summary prints one table row per question type and one overall, then one
line for `record.md`.

## Calibration

`fit.py --results results.jsonl --model-path GGUF --out calibration.json`:
split items by a hash of the id (even/odd), for each type search T on a
geometric grid 0.25..8 (61 points) minimizing NLL on the even half (it needs
`sf.debug` logits), report NLL and ECE on the odd half before and after.

```json
{"binding":{"model_bytes":365749832704,"model_mtime":1760000000,"template_version":1,"layout":"state_first"},
 "temperature":{"noul":1.31,"choice":1.18,"score":1.44},
 "fitted_on":"typed-decisions even ids, 1000 items","date":"2026-11-..."}
```

Server: `--sysone-calibration FILE` (help text in `ds4_help.c`). At startup the
server compares `binding` with the opened model's size and mtime and
`SF_SYSONE_TEMPLATE_VERSION`; a mismatch is a startup error that names the
field. `sysone_job` passes the type's temperature to `sf_sysone_decide`. With
`sf` in the request, the response's `sf` object carries `"temperature"` per
question. A request may send `"sf":{"temperature":1.0}` to override the file for one
request (A/B convenience).

## Baseline run (the acceptance of this change)

On `fixtures-it.jsonl` and on the `typed-decisions` test split:

1. `sysone` raw; 2. `gen`; 3. `think` on the first 100 items (it costs about a
minute per item); 4. `sysone --rotate 1`; 5. `fit.py`, then `sysone` again with
the calibration file.

`record.md` gets the table (rows: set × mode; columns: accuracy with interval,
NLL, Brier, ECE, legal mass, p50 and p95 ms) and three stated numbers:

- the **System One gap**: `think` accuracy minus `sysone` accuracy on the
  same 100 items;
- the **flip rate** under rotation: share of items whose top changes;
- ECE before and after the temperature.

These numbers decide later changes: a flip rate above 5% justifies the prior
correction of `a015`; a gap above 5 points justifies the bounded think of
`a025`.


## Two baselines later changes are judged against

Both use only this bench and `/v1/systemone`; neither touches the engine.

**Abstention.** Does the model know when the state lacks the answer? Build
`sysone-bench/abstain_items.py`: from at least 200 items that have a label,
make a twin of each by deleting from the state the sentence that carries the
answer (for the Italian fixtures the generator knows the sentence; for other
sets keep only items where a single sentence contains the label's key term)
and padding with a neutral sentence of the same length. For the 400 states
report the AUROC, as detectors of "answer missing", of:

1. `1 − confidence` (Jev's formula);
2. the probability of an explicit extra option
   `insufficient: the state does not say`, added to `criteria`;
3. a companion `noul`: "The state contains the information needed to answer:
   <instructions>";
4. `1 − legal_mass`.

If detector 2 or 3 reaches AUROC 0.9, record "abstention needs no engine
work". This number decides whether an attention-based abstention signal
(considered in `docs/system-one.md`) is ever worth a kernel.

**Schedule stability.** The prefill schedule changes logits (documented up
to 1.37). Run 100 decision items twice: once normally, once on a server
started with `DS4_METAL_DISABLE_V41_LAYER_PREFILL=1` (every row token by
token; slow, so use states under 300 tokens). Record the distribution of the
absolute change of the gap between the two best option logits, its 95th
percentile `delta95`, and the share of items whose top option changes.
Then `sf_sysone_finish` marks an answer whose top-two logit gap is under
`delta95` as unstable: the `sf` response object carries `"unstable":true`
(a constant `SF_SYSONE_DELTA95` in `sf_sysone.h`, with the record's date in
its comment). This replaces any engine-side "fragility" probe.

## Tests

`tests/test_sysone_bench.py` (run in `make test`, like `tests/test_ab_bench.py`):
metrics on hand-computed cases (a perfect predictor, a uniform one, a known
ECE), rotation mapping round-trip, the symbol extractor of `gen` on six
replies, `fit.py` recovering T = 2 from logits generated at T = 2.

## Decisions taken during apply (2026-11-11)

- **typed-decisions is read through the datasets-server JSON API**, not `hf
  download`: the set ships as parquet and no parquet reader is installed (and
  none may be). Rows go to `--work` only. Id, licence and splits are in
  `sysone-bench/README.md`. JevBench was not located as an open download:
  skipped.
- **Bounded runs.** typed-decisions ran on a 100-state subset (every fourth
  state of each workflow, 500 decisions), not the 400-state split, to keep a
  run near 30 minutes. The rotation run covers `choice` items only (rotation
  does not apply to `noul` and `score`).
- **One request per state.** `run.py` sends consecutive items of one state as
  one multi-question request (isolation makes the answers equal) and splits the
  state prefill time among them for per-decision latency.
- **`gen`/`think` prompt** uses the frozen template's wording (T-C: `A. text`,
  "Answer with the identifier only."), not "bracketed identifier", which was
  the pre-probe default.
- **Calibration check offline.** `fit.py --apply` tempers recorded logits; it
  equals the server's computation (T divides the logits). A short live run
  with `--sysone-calibration` confirmed it (below).
- **Abstention sources**: the 60 fixtures carry an `evidence` field; 140
  synthetic English items from templates with a known evidence sentence make
  up the 200 labelled sources (400 states). For `noul`, detector 2 asks the
  question as a choice {yes, no, insufficient}; for `score`, the extra level is
  appended last.
- **Schedule stability set**: 20 typed-decisions states of 1100-1500
  characters (about 300-400 tokens, so the normal schedule runs a layer sweep;
  under 256 tokens both schedules are token-major and identical).
- **Model-time budget (resumed 2026-11-12 03:31, model free by 05:15).**
  `think` ran on the first 50 typed-decisions items, not 100: at about 27 s
  per item (p95 117 s) 100 items would not fit next to the other runs. The
  gap is stated on those 50. `gen` on the subset stopped at a deadline after
  477 of 500 decisions. The calibrated server ran on the fixtures and the
  first 100 typed-decisions items, as an end-to-end check, not on the whole
  held-out half (the offline fit covers that, and the live run matched it
  within 5e-7). `teacher` mode is implemented but was never in the baseline.
- `SF_SYSONE_DELTA95` = 1.41, the measured 95th percentile; `unstable` is
  emitted only when true.
