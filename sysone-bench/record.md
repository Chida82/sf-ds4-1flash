# System One bench record

One row per run, baseline first. Commit: uncommitted, branch sys1 working tree
(on `1aff8d2`). Runs 2026-11-11 23:50 to 2026-11-12 05:08, 1017 Q2 GGUF, `./sf-ds4-1flash-server
--ssd-streaming --ctx 32768 --ssd-streaming-cache-experts 82GB`, no `--boost`.
Template version 1 (state first, T-C). Latency is per decision: the question's
own milliseconds plus its share of the state prefill (`run.py` sends the
decisions of one state in one request). Intervals: 95% bootstrap over states.

## Baseline (820)

| Set | Mode | n | Accuracy (95% CI) | NLL | Brier | ECE | Legal mass | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|
| fixtures-it (60 states) | sysone | 60 | 0.967 (0.917-1.000) | 0.051 | 0.038 | 0.029 | 0.9999 | 3455 | 5159 |
| typed-decisions test, 100-state subset | sysone | 500 | 0.682 (0.638-0.730) | 1.439 | 0.546 | 0.230 | 0.9985 | 3709 | 5176 |
| fixtures-it, choice only | sysone rotate 1 | 20 | 0.950 (0.850-1.000) | 0.095 | 0.071 | 0.036 | 1.0000 | 4423 | 5352 |
| typed-decisions subset, choice only | sysone rotate 1 | 150 | 0.693 (0.619-0.773) | 1.512 | 0.555 | 0.265 | 0.9997 | 7626 | 12517 |
| typed-decisions, 20 long states (stability set) | sysone | 100 | 0.800 (0.710-0.880) | 0.961 | 0.359 | 0.165 | 0.9997 | 3980 | 5906 |
| same, token-major prefill | sysone | 100 | 0.810 (0.720-0.890) | 0.939 | 0.337 | 0.164 | 0.9998 | 5352 | 7171 |
| fixtures-it | gen | 60 | 0.983 (0.950-1.000) | 0.345 | 0.033 | 0.017 | - | 3401 | 5102 |
| typed-decisions subset | gen | 477 | 0.679 (0.631-0.728) | 6.647 | 0.642 | 0.321 | - | 6213 | 7563 |
| typed-decisions subset, first 50 items | think | 50 | 0.720 (0.580-0.860) | 6.217 | 0.540 | 0.260 | - | 14915 | 116776 |
| fixtures-it, calibrated server | sysone | 60 | 0.967 (0.917-1.000) | 0.157 | 0.058 | 0.132 | 0.9999 | 3388 | 5149 |
| typed-decisions, first 100 items, calibrated server | sysone | 100 | 0.640 (0.550-0.730) | 0.855 | 0.500 | 0.097 | 0.9988 | 3685 | 5121 |

`gen` and `think` give one answer, scored as probability 1, so their NLL,
Brier and ECE only say how often a certain answer is wrong. `gen` on the
subset stopped at its deadline after 477 of 500 decisions (96 states) so the
model was free by 05:15; 0 parse failures. `think` ran on the first 50 items,
not 100, for the same deadline (about 27 s per item, p95 117 s): 3 replies
came back empty, most likely the 4096-token cap reached inside the
reasoning, and count as wrong.

Per type, typed-decisions subset (sysone):

| type | n | states | accuracy | 95% CI | NLL | Brier | ECE | mass mean | mass min | p50 ms | p95 ms | tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| noul | 150 | 100 | 0.733 | 0.653-0.801 | 1.417 | 0.493 | 0.240 | 0.9996 | 0.9971 | 3233 | 3672 | 99 |
| choice | 150 | 100 | 0.680 | 0.604-0.755 | 1.707 | 0.565 | 0.238 | 0.9996 | 0.9922 | 4644 | 5924 | 138 |
| score | 200 | 100 | 0.645 | 0.580-0.705 | 1.255 | 0.571 | 0.231 | 0.9969 | 0.9063 | 3760 | 4657 | 122 |
| all | 500 | 100 | 0.682 | 0.638-0.730 | 1.439 | 0.546 | 0.230 | 0.9985 | 0.9063 | 3709 | 5176 | 120 |


The typed-decisions subset is every fourth state of each workflow (25 per
workflow, 100 states, 500 decisions), out of the 400-state test split, to keep
the run near 30 minutes. Published on the full test split (2000 decisions):
Rizzo Flow 0.648, Jev 0.727, Laya fine-tuned on the train split 0.766.

## The three stated numbers

- **System One gap** (think minus sysone, the same 50 typed-decisions items):
  0.720 - 0.600 = **+12.0 points** (noul +7.1, choice +25.0, score +5.0; 14,
  16 and 20 items). Above 5 points: the bounded think of `860` is justified.
  The interval is wide at n = 50. `gen` (thinking off, generated answer)
  matches System One on 477 items: 0.679 against 0.675.
- **Flip rate under rotation** (choice, `--rotate 1`): typed-decisions
  **21.3%** (32/150; accuracy 0.680 at rotate 0, 0.693 at rotate 1); Italian
  fixtures 5.0% (1/20). Above 5%: the prior correction of `845` is justified.
- **ECE before and after the temperature** (typed-decisions subset; fitted on
  even ids, reported on the 258 odd ids, applied offline by `fit.py`, which is
  exactly what the server computes since T divides the logits):

| Type | T | NLL raw | NLL fitted | ECE raw | ECE fitted |
|---|---|---|---|---|---|
| noul | 8.0 (grid edge) | 0.937 | 0.475 | 0.204 | 0.121 |
| choice | 3.78 | 1.661 | 0.865 | 0.210 | 0.067 |
| score | 2.52 | 1.400 | 0.882 | 0.281 | 0.126 |
| all | - | 1.347 | 0.759 | 0.229 | 0.042 |

The raw probabilities are strongly over-confident. `noul` hit the top of the
0.25-8 grid: its best temperature is 8 or more.

Live check of `--sysone-calibration` (server started with the fitted file, it
logged "system one temperatures noul 8 choice 3.776 score 2.52"): on the first
100 typed-decisions items the option logits are bitwise equal to the raw run's,
the probabilities match the offline tempering within 5e-7, every `sf` entry
echoes its type's temperature, and ECE drops from 0.280 to 0.097 (NLL 1.683 to
0.855) with the same tops. On the Italian fixtures, where the model is already
right and sure, the typed-decisions temperatures raise ECE from 0.029 to 0.132:
a temperature is a property of the item distribution, fit it on data like the
traffic it will serve.

## Abstention (400 states)

200 labelled sources (the 60 Italian fixtures and 140 synthetic English items
with a known evidence sentence) and their twins without that sentence:

| Detector of "answer missing" | AUROC |
|---|---|
| 1. 1 - confidence | 0.888 |
| 2. p(extra option "insufficient: the state does not say") | **0.974** |
| 3. 1 - p(companion noul "the state contains the information...") | 0.778 |
| 4. 1 - legal mass | 0.833 |

**Abstention needs no engine work**: the explicit option reaches 0.974.

## Schedule stability

20 typed-decisions states of 1100-1500 characters (100 decisions), each
prefilled with layer sweeps (normal) and token by token
(`DS4_METAL_DISABLE_V41_LAYER_PREFILL=1`). Change of the top-two option logit
gap between the two: median 0.436, **95th percentile 1.410**, maximum 2.908;
no item has bitwise equal logits; the top option changes on **4 of 100**.
`SF_SYSONE_DELTA95` is set to 1.41: on the 500-decision run 92 answers
(18.4%) fall under it, and they are right 54.3% of the time against 71.3% for
the rest.

## Commands

```sh
W=<scratch dir>
python3 sysone-bench/convert.py --work $W            # 400 states, 2000 decisions
python3 sysone-bench/run.py --items sysone-bench/fixtures-it.jsonl --mode sysone --out $W/r-fx-sysone.jsonl
python3 sysone-bench/run.py --items $W/td500.jsonl --mode sysone --out $W/r-td-sysone.jsonl
python3 sysone-bench/run.py --items $W/fixtures-choice.jsonl --mode sysone --rotate 1 --out $W/r-fx-rot1.jsonl
python3 sysone-bench/run.py --items $W/td500-choice.jsonl --mode sysone --rotate 1 --out $W/r-td-rot1.jsonl
python3 sysone-bench/run.py --items $W/td-long100.jsonl --mode sysone --out $W/r-long-normal.jsonl
python3 sysone-bench/abstain_items.py make --fixtures sysone-bench/fixtures-it.jsonl --synthetic 140 --out $W/abstain.jsonl
python3 sysone-bench/run.py --items $W/abstain.jsonl --mode sysone --out $W/r-abstain.jsonl
python3 sysone-bench/abstain_items.py score --items $W/abstain.jsonl --results $W/r-abstain.jsonl
python3 sysone-bench/fit.py --results $W/r-td-sysone.jsonl --model-path deepseek-v4.1-flash.gguf --out $W/calibration.json
DS4_METAL_DISABLE_V41_LAYER_PREFILL=1 ./sf-ds4-1flash-server ...    # then:
python3 sysone-bench/run.py --items $W/td-long100.jsonl --mode sysone --out $W/r-long-slow.jsonl
./sf-ds4-1flash-server ... --sysone-calibration $W/calibration.json   # then:
python3 sysone-bench/run.py --items sysone-bench/fixtures-it.jsonl --mode sysone --out $W/r-fx-cal.jsonl
python3 sysone-bench/run.py --items $W/td100.jsonl --mode sysone --out $W/r-td100-cal.jsonl
python3 sysone-bench/run.py --items $W/td100.jsonl --limit 50 --mode think --out $W/r-td50-think.jsonl
python3 sysone-bench/run.py --items sysone-bench/fixtures-it.jsonl --mode gen --out $W/r-fx-gen.jsonl
python3 sysone-bench/run.py --items $W/td500.jsonl --mode gen --out $W/r-td-gen.jsonl --deadline <unix time>
```

`td500.jsonl`, `td500-choice.jsonl`, `td100.jsonl` and `td-long100.jsonl` are
the subsets described above, written from `convert.py`'s output.

## State cache (830, 2026-11-12)

Server: `./sf-ds4-1flash-server --ssd-streaming --ctx 32768` (cache defaults:
4 entries, 2048 MiB), uncommitted, branch sys1 working tree. Items: the first
20 distinct non-score states of `td-long100.jsonl` (median 369 prefix tokens:
over 256, so a miss is one layer sweep), one question each.

`run.py --scenario repeat`: requests 1-3 send the same state and question;
then the state with a 59-token note appended (`run.py`'s `EXTENSION`).

| Request | n | Path | Wall p50 | Wall p95 | State prefill p50 |
|---|---|---|---|---|---|
| 1 | 20 | miss 20 | 12169 ms | 12333 ms | 7973 ms |
| 2 | 20 | hit 20 | 3194 ms | 3349 ms | 1.1 ms |
| 3 | 20 | hit 20 | 3184 ms | 3324 ms | 1.1 ms |
| extended | 20 | extend 20 | 5417 ms | 5560 ms | 2004 ms |
| extended, from scratch (`--sysone-state-cache 0`) | 20 | — | 12277 ms | — | 8461 ms |

- Hits are bitwise equal to the creating request (all 40 option-logit sets).
- Extended against from scratch: the top differs on **1 of 20**; no logits are
  bitwise equal (expected: different schedule, and the extension's prefix is
  one token longer at the boundary on all 20, since the appended text is
  tokenized alone).
- A first run keyed on prefix tokens (as the design had it) found **0 of 20**
  extensions: BPE merged the appended text into the old state's last token.
  The cache is now keyed on the state text (830 `design.md`, decisions).

Snapshot cost (`DS4_LOG_TIMING` lines of `sysone_job`; `promessi_sposi.txt`
prefixes, one `noul` question):

| State tokens | Snapshot | Save | Load (first, second) | Hit prefill_ms |
|---|---|---|---|---|
| 1972 | 22.5 MiB | 4.0 ms | 2.9, 0.8 ms | 6.4 |
| 7851 | 58.4 MiB | 9.4 ms | 4.9, 2.1 ms | 7.7 |
| 31067 | 200.2 MiB | 29.1 ms | 19.5 ms | 22.8 |

Load at 8K is 5 ms, under the 150 ms threshold: no journal restore is needed.
The 8K and 31K states were reached as extensions of the smaller ones (the
same text grown), at 14.6 s and 41.7 s.

```sh
python3 sysone-bench/run.py --items $W/td-long100.jsonl --scenario repeat --out $W/repeat2.jsonl
./sf-ds4-1flash-server ... --sysone-state-cache 0     # then:
python3 sysone-bench/run.py --items $W/td-long100.jsonl --scenario extended --out $W/scratch.jsonl
```

## Live state (835, 2026-11-12)

Server: `./sf-ds4-1flash-server --ssd-streaming --ctx 32768
--ssd-streaming-cache-experts 82GB --sysone-state-cache 0` (cache off, so the
text-state reference prefills every request). Command:
`run.py --items td500.jsonl --scenario live --out live.jsonl`. Per state (20
typed-decisions states, choice and noul only): one chat turn (the state as a
customer message, "Draft a short reply.", thinking off, 160 tokens), then up
to three decisions with the conversation as a live state
(`"sf":{"state":"messages"}`), then the same decisions with the conversation
as a text state (`role: content` paragraphs).

| Layout | Decisions | Median wall ms | Median state prefill ms | Median prefix tokens |
|---|---|---|---|---|
| live | 60 | 2279 | 32 | 403.5 |
| text (`state_first`) | 60 | 10246 | 7682 | 430.5 |

Every live decision reused at least 99.5% of its prefix from the slot's live
session. Live median / text median = 0.22: under one third, so the feature
is **kept**.

Not measured here: accuracy of the live layout against `state_first` (the
question wording differs, "Question about the conversation above"); a live
decision after a thinking turn (reuses nothing by plain prefix, measured once:
`reused_tokens` 1, state prefill 2.0 s on a 68-token conversation).
