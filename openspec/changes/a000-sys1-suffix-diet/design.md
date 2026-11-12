# Design

Depends on `800`, `810`, `820`, `830` (all archived, in the tree). Read
`docs/system-one.md` section 7 and `sf_sysone.c` (276 lines) first.

## Must not do

- Do not edit `ds4.c`, `ds4_metal.m`, `ds4.h`.
- Do not change `sf_sysone_state_prefix`, `sf_sysone_turn_text` (the `835`
  live layout), `option_line`, the system text `SYS`, or `template_prompt` in
  `sysone-bench/run.py`.
- Do not change symbols, the answer prefill (`ANSWER_PREFILL` stays `""`) or
  the chat markers: every candidate ends with
  `ds4_chat_append_assistant_prefix(so->e, out, DS4_THINK_NONE)`, as today.
- Never run two model processes at once (one server, or one test, at a time).
  Stop the `sfctl` service first if it is loaded (`sfctl/README.md`).
- Do not commit. Do not start `a015` or `a005` work here.
- If a step fails in a way this file does not cover, stop and report.

## Candidates

`Q` is `q->instructions`. `LINES` is the concatenation of `option_line(q, i)`
for every option (each ends with `\n`). The instruction line is the literal
`Answer with the identifier only.` (no trailing newline).

| Template id | Name | Suffix text | Tokenized as |
|---|---|---|---|
| 1 | D0 | `\n\nQuestion: ` · `Q` · `\nOptions:\n` · each option line · instruction line | pieces, exactly as today |
| 91 | D1 | `\n\nQuestion: ` + `Q` + `\nOptions:\n` + `LINES` + instruction line | one string |
| 92 | D2 | `\n\nQuestion: ` + `Q` + `\n` + `LINES` + instruction line | one string |
| 93 | D3 | `\n\nQuestion: ` + `Q` + `\n` + `LINES` | one string |
| 94 | D4 | `\n\n` + `Q` + `\n` + `LINES` | one string |

"One string" means: build the whole text in one heap buffer and call
`ds4_tokenize_text(so->e, text, out)` once. The chat markers are appended
after it as token ids, never as text. Ids 91-94 exist only during this
change; the winner is renumbered 2 and the others are deleted (Freezing).

## Code, step A: the template id (before any model run)

Before editing, save the reference dump:
`./tests/test_sysone deepseek-v4.1-flash.gguf --tokens > W/tokens-before.txt`
(`W` is a scratch directory; `make tests/test_sysone` builds the binary).

`sf_sysone.h`:
- `int sf_sysone_open(sf_sysone **out, ds4_engine *e, int template_version, char *err, size_t errlen);`
- add `int sf_sysone_template(const sf_sysone *so);` (returns the id in use).
- leave `#define SF_SYSONE_TEMPLATE_VERSION 1` for now: it is the default id.

`sf_sysone.c`:
- `struct sf_sysone` gains `int template_version;`.
- `sf_sysone_open`: accept 1, 91, 92, 93, 94; for any other value write
  `unknown template version %d` into `err` and return 1. Store the id.
- `sf_sysone_question_suffix`: `if (so->template_version == 1)` keep the
  present body unchanged. Otherwise build the text of the table above with a
  small static helper `static void text_add(char **buf, size_t *len, size_t *cap, const char *s)`
  (grow with `realloc`, keep a terminating NUL), tokenize it once, free it,
  then append the assistant prefix as version 1 does.

Callers of `sf_sysone_open` (two, `grep -n sf_sysone_open`):
- `tests/test_sysone.c` `open_all`: pass `SF_SYSONE_TEMPLATE_VERSION`.
- `ds4_server.c` (in `main`, the block commented `sf: 810`): pass the
  config's `sysone_template`. The config variable is named `c` inside the
  option parser and `cfg` in `main`, where `cfg.sysone_calibration` is read:
  use the name in scope.

`ds4_server.c`:
- config field `int sysone_template;` beside `sysone_calibration`, default
  `SF_SYSONE_TEMPLATE_VERSION` where the other `sysone_*` defaults are set.
- option parse, beside `--sysone-calibration`:
  `--sysone-template N` with `parse_nonneg_int_arg`. No range check here:
  `sf_sysone_open` refuses unknown ids and the server already exits on its
  error.
- `sysone_response_json`: add a parameter `int template_version` after
  `model`; print it instead of `SF_SYSONE_TEMPLATE_VERSION`. Its one runtime
  caller passes `sf_sysone_template(s->sysone)`; the two unit-test callers
  pass `1`.
- `sysone_calibration_parse`: add a parameter `int template_version` after
  `model_mtime`; compare `c.version` with it instead of the macro (keep the
  message text). The runtime caller (next to `cfg.sysone_calibration`) passes
  `cfg.sysone_template`; the seven
  unit-test callers pass `1`.
- `ds4_help.c`: one `opt(...)` line after `--sysone-calibration`:
  `"--sysone-template N", "Question suffix template of POST /v1/systemone (default: the newest). A calibration file is bound to one template."`

`sysone-bench/fit.py`: `ap.add_argument("--template-version", type=int, default=1)`
and write `a.template_version` into the binding instead of the literal `1`.

Checks after step A (all must pass before any bench run):
- `make` and `make test` (read the lines: `sysone-bench: all tests passed`
  and the server test lines must be present, not only exit 0).
- `./ds4_test --server`.
- `./tests/test_sysone deepseek-v4.1-flash.gguf --tokens > W/tokens-after.txt`
  and `diff W/tokens-before.txt W/tokens-after.txt` prints nothing: template 1
  is token-identical, hence bitwise the same decisions.
- `make test-sysone` passes.

## Code, step B: the probe mode

`tests/test_sysone.c`, new mode `--suffix-probe` (leave `--probe`, the `800`
probe, as it is). Add it to `main` and to the usage string.

```
static int mode_suffix_probe(void)
  ids = {1, 91, 92, 93, 94}; names = {"D0","D1","D2","D3","D4"}
  for each fixture f in 0..11:
    prefix = sf_sysone_state_prefix(so, FIX[f].state)       (so is template 1)
    ds4_session_sync(session, &prefix); ds4_session_save_snapshot(session, &snap)
    for each candidate c:
      if (c > 0) ds4_session_load_snapshot(session, &snap)
      open a second handle: sf_sysone_open(&cand, engine, ids[c], ...)
      full = copy of prefix; sf_sysone_question_suffix(cand, &FIX[f].q, &full)
      ds4_session_sync(session, &full)
      read the option logits and legal mass exactly as mode_probe does
      sf_sysone_finish; ok = fixture_ok(&FIX[f], &a)
      accumulate: correct[c], mass_sum[c], mass_min[c], tok_sum[c] += full.len - prefix.len
      print "suffix-probe D2 fixture  3 top 0 value 0.998 mass 0.9999 tokens 31 ok"
      sf_sysone_close(cand)
  per candidate print:
    "suffix-probe D2: 12/12 correct, mean legal mass 0.9999, min 0.9996, mean suffix tokens 27.3"
```

Copy the loop of `mode_probe` and change only the suffix builder and the
token count; do not refactor `mode_probe`.

## Run 1: probe (about 5 minutes)

`./tests/test_sysone deepseek-v4.1-flash.gguf --suffix-probe > W/probe.txt`

Drop every candidate whose **minimum** legal mass is under 0.9 or that has
fewer correct fixtures than D0. Paste the five summary lines into
`sysone-bench/record.md` as a table (section "Suffix diet (a000)") and say
which candidates survive. If none survives, go to "No winner".

## Run 2: bench (about 40 minutes per template)

Item sets, in `W`:

```sh
python3 sysone-bench/convert.py --work $W      # typed-decisions test split, 2000 decisions
python3 - $W <<'PY'
import json, re, sys
W = sys.argv[1]
rows = [json.loads(l) for l in open(f"{W}/typed-decisions-all-test.jsonl")]
order, seen = {}, []
for r in rows:
    if r["state_id"] not in seen:
        seen.append(r["state_id"])
wf = {}
for s in seen:
    wf.setdefault(re.sub(r"_\d+$", "", s), []).append(s)
keep = {s for states in wf.values() for s in states[::4]}      # 25 states per workflow, 100 states
sub = [r for r in rows if r["state_id"] in keep]
assert len(sub) == 500, len(sub)
open(f"{W}/td500.jsonl", "w").writelines(json.dumps(r) + "\n" for r in sub)
ch = [r for r in sub if r["question"]["type"] == "choice"]
assert len(ch) == 150, len(ch)
open(f"{W}/td500-choice.jsonl", "w").writelines(json.dumps(r) + "\n" for r in ch)
PY
```

For `N` in 1 and then each surviving id, one server at a time:

```sh
./sf-ds4-1flash-server --ssd-streaming --ctx 32768 --ssd-streaming-cache-experts 82GB \
    --host 127.0.0.1 --port 8002 --sysone-template $N > $W/server-$N.log 2>&1 &
# wait until: curl -s http://127.0.0.1:8002/v1/models answers
python3 sysone-bench/run.py --items sysone-bench/fixtures-it.jsonl --mode sysone --out $W/r-fx-$N.jsonl
python3 sysone-bench/run.py --items $W/td500.jsonl --mode sysone --out $W/r-td-$N.jsonl
kill -TERM %1; wait
```

Wrap the whole sequence in `caffeinate -i` (it runs for hours). Check in the
first result line that the response says the right template:
`grep -c '"error"' $W/r-td-$N.jsonl` must print 0.

## Gate script

`sysone-bench/template_gate.py` (standard library; import `metrics`):

```
template_gate.py --base-td r-td-1.jsonl --cand-td r-td-N.jsonl
                 --base-fx r-fx-1.jsonl --cand-fx r-fx-N.jsonl
                 [--base-rot r-rot-1.jsonl --cand-rot r-rot-N.jsonl]
```

It pairs items by `id` (every id of the base file must be in the candidate
file, else exit 2) and prints one JSON object:

- `d_acc` = `metrics.accuracy(cand_td) - metrics.accuracy(base_td)`
- `d_nll` = `metrics.nll(cand_td) - metrics.nll(base_td)`
- `fx_wrong_more` = wrong(cand_fx) − wrong(base_fx), wrong = items whose
  `metrics.top(probs) != label`
- `legal_mass` = mean of `legal_mass` over cand_td
- `tokens_saved` = mean over td ids of `base.tokens - cand.tokens` (the
  prefix share inside `tokens` is equal on both sides, so the difference is
  the suffix)
- with the rotation files: `flip_base`, `flip_cand` = share of ids whose top
  differs between the unrotated td file and the rotated file (ids present in
  the rotated file only)
- `pass`: true when **all** hold: `d_acc >= -0.010`, `d_nll <= 0.02`,
  `fx_wrong_more <= 1`, `legal_mass >= 0.99`, `tokens_saved >= 3.0`, and,
  when rotation files are given, `flip_cand <= flip_base + 0.05`
- `failed`: the list of the names of the thresholds that did not hold.

Unit test in `tests/test_sysone_bench.py`: a hand-made base of 4 items and a
candidate with one more wrong answer and 5 fewer tokens each gives
`d_acc == -0.25`, `tokens_saved == 5`, `pass == false`, `failed == ["d_acc"]`.

## Choosing the winner

1. Run the gate without rotation files for each surviving candidate.
2. Among those with `pass` true, take the largest `tokens_saved`; break a tie
   by the lower `d_nll`.
3. Rotation check, only for that one: with the server on template 1 and then
   on the candidate, run
   `run.py --items $W/td500-choice.jsonl --mode sysone --rotate 1 --out $W/r-rot-$N.jsonl`,
   then the gate again with the rotation files. If it fails on the flip rate,
   take the next candidate of step 2 and repeat this step.
4. No candidate left: "No winner".

Write the table in `sysone-bench/record.md`: one row per candidate with
`d_acc`, `d_nll`, `fx_wrong_more`, `legal_mass`, `tokens_saved`, flip rates
when run, `pass`, `failed`; then one sentence naming the winner or saying
there is none.

## Freezing (only with a winner)

- `sf_sysone.c`: renumber the winner's id to 2; delete the other three
  candidates' branches; `sf_sysone_open` accepts 1 and 2 only.
- `sf_sysone.h`: `#define SF_SYSONE_TEMPLATE_VERSION 2` (the default).
- `tests/test_sysone.c`: delete `mode_suffix_probe` and its `main` branch
  (the record keeps its output). `mode_checks` runs twice: after the first
  pass, `sf_sysone_close(so)`, `sf_sysone_open(&so, engine, 1, ...)`, run it
  again, printing `template 2` / `template 1` before each pass. Do not close
  or reopen the engine: a process must hold one engine.
- `ds4_server.c` unit tests: the calibration test that expects a
  version-2 file to be refused (`const char *ver`) must now pass `1` as the
  build's version and still be refused; add one line asserting the same file
  is accepted with `2`.
- `sysone-bench/fit.py`: default of `--template-version` becomes 2.
- Calibration: `python3 sysone-bench/fit.py --results $W/r-td-2.jsonl
  --model-path deepseek-v4.1-flash.gguf --template-version 2 --out
  $W/calibration-v2.json` (rename the winner's result file to `r-td-2.jsonl`
  first); paste its table into the record beside version 1's temperatures.
- `docs/system-one.md` section 7: add "Template version 2 (change `a000`)"
  with the frozen layout in the same block form as version 1, the probe
  table, the gate row of the winner and the tokens saved; say that version 1
  stays available with `--sysone-template 1`.
- Checks: `make`, `make test`, `./ds4_test --server`, `make test-sysone`
  (both passes), and one request against a server on the default template
  whose response shows `"template_version":2`.

## No winner

- `git checkout -- sf_sysone.c sf_sysone.h ds4_server.c ds4_help.c tests/test_sysone.c sysone-bench/fit.py`
- Keep `sysone-bench/template_gate.py`, its unit test and the record.
- `docs/system-one.md` section 7: one paragraph, "Suffix diet (`a000`): no
  variant passed", with the reason from the table.
- `make test` again.

## Risks

- Fewer instruction tokens can shift the prior over options. `d_nll` and the
  rotation flip rate are the detectors; that is why the flip rate is part of
  the gate.
- The 500-decision set has an accuracy interval of about ±4.6 points
  (`820`): a 1-point threshold on the point estimate is within the noise.
  It is accepted as a guard against a clear loss, with `d_nll` as the finer
  measure; the record must print the paired counts (right→wrong and
  wrong→right) beside `d_acc`.
- Every `--sysone-state-cache` entry is keyed by the state prefix, which no
  candidate changes; the cache stays at its default.
