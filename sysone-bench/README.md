# System One bench

Measures `POST /v1/systemone` (`docs/SERVER.md`, "System one") for accuracy,
calibration and latency, against the model's own generated answers. Change
`820`; results are in `record.md`. Standard-library Python only: nothing is
installed, and downloaded sets stay outside the repository (`--work`).

| File | What it does |
|---|---|
| `run.py` | sends a JSONL item set in one of four modes (`sysone`, `gen`, `think`, `teacher`) and prints one table row per question type, one overall, and a line for `record.md` |
| `metrics.py` | accuracy, NLL, Brier, ECE (10 bins), latency percentiles, legal mass, a state-level bootstrap interval, AUROC |
| `fit.py` | fits one temperature per question type on the even half of a `sysone` run and writes the file `--sysone-calibration` loads; `--apply` tempers a run offline |
| `convert.py` | fetches `typed-decisions` and writes it in the item format |
| `abstain_items.py` | builds the abstention twins and scores the four detectors |
| `fixtures-it.jsonl` | 60 Italian items, 20 per type, labels by construction, each with the `evidence` sentence that carries its answer |

## Item format

One decision per line:

```json
{"id":"td-0001","lang":"en","state_id":"…","state":"…","question":{"type":"choice","instructions":"…","criteria":{"a":"…","b":null}},"label":"a"}
```

`label` is the option name (`choice`), the level index (`score`) or
`true`/`false` (`noul`), and may be absent. `state_id` groups the decisions of
one state: the bootstrap resamples states, and `run.py` sends consecutive items
of one state in one request (questions are isolated, so the answers are those
of one request per item; the state is paid once and its prefill time is split
among the questions).

## typed-decisions

- Id: `LocalLLaMA/typed-decisions` on Hugging Face (cited by Laya's model card
  as "the typed-decisions benchmark"; Laya's fine-tuning notebook loads
  `load_dataset("LocalLLaMA/typed-decisions", "all", split=...)`).
- Licence: Apache-2.0 (dataset card metadata, read 2026-11-11).
- Splits (config `all`): test 400 states, 2000 decisions (600 choice, 600
  noul, 800 score); four workflows of 100 states each (agent-trace
  observability, customer service, invoice processing, security incidents).
  Labels are the argmax of a teacher's distribution (`gold.<q>.label`).
- The set is parquet and no parquet reader may be installed, so `convert.py`
  reads the rows as JSON from the datasets-server API
  (`datasets-server.huggingface.co/rows`) into `--work`.

JevBench's 231 public items were not located as an open download; skipped.

## Running

```sh
./sf-ds4-1flash-server --ssd-streaming --ctx 32768 --ssd-streaming-cache-experts 82GB &
W=$(mktemp -d)
python3 sysone-bench/convert.py --work $W
python3 sysone-bench/run.py --items sysone-bench/fixtures-it.jsonl --mode sysone --out $W/fx.jsonl
python3 sysone-bench/fit.py --results $W/td.jsonl --model-path deepseek-v4.1-flash.gguf --out $W/calibration.json
```

`make test` runs `tests/test_sysone_bench.py` (metrics on hand-computed cases,
rotation, the `gen` symbol extractor, `fit.py` recovering T = 2).
