# Design

Depends on `800`. The wire format is in `docs/system-one.md`, section 2; read
it first. Idiom to copy: how `ds4_server.c` parses with `json_ws`,
`json_string`, `json_raw_value`, `json_skip_value`, and writes with `buf_puts`
and `json_escape`.

## Request handling

In `client_main` (`ds4_server.c`), next to the other `POST` routes, before the
generic `request` path:

```
POST /v1/systemone  ->  sysone_request sr; parse; on failure 422/400; else job
```

`sysone_request` (new struct, in `ds4_server.c`):

```c
typedef struct {
    char *model;                 /* as sent; echoed only in logs */
    char *state;                 /* text; object/array states are minified JSON */
    int n;                       /* questions */
    char **names;                /* question keys, in request order */
    sf_sysone_question *q;       /* owns its strings */
    bool has_sf;                 /* request carried an "sf" object */
    bool sf_debug;               /* sf.debug */
} sysone_request;
```

Parsing rules:

| Field | Rule | On violation |
|---|---|---|
| body | valid JSON object | 400 |
| `model` | string, required; any value is accepted and answered by the local model | 422 `loc ["body","model"]` |
| `state` | string → as is. Object or array → `json_minify_raw_value` of the raw text. Required | 422 |
| `questions` | object, 1-64 entries; keys non-empty, unique | 422 |
| question `type` | `noul`, `choice`, `score` | 422; `box` → 422 with msg "box is not supported by this model server" |
| `instructions` | string → as is; object/array → minified JSON; null or missing → "" | — |
| `choice.criteria` | object, 1-26 entries; value string → text, object/array → minified JSON, null → NULL | 422; 27-255 entries → 422 "more than 26 options is not supported yet" |
| `score.criteria` | array, 1-10 entries; same value rule | 422 |
| `noul.criteria` | optional object with optional `true` / `false`; same value rule | 422 |
| `assets` | must be absent | 422 |
| `sf` | optional object; known key `debug` (bool); unknown keys ignored | — |
| any other top-level key | ignored | — |

Question order is the order of the keys in the request body; the response
keeps it.

422 body: `{"detail":[{"loc":["body","questions","<name>","criteria"],"msg":"...","type":"value_error"}]}`
(one entry; stop at the first error). 400 body for the context limit:
`{"detail":{"code":"max_tokens_exceeded","message":"..."}}`. Other 400s use
`{"detail":"<message>"}`. These three writers are new small functions; do not
route them through `http_error`, whose body is the OpenAI shape.

## Job

`struct job` gains `sysone_request *sysone` (NULL for every other request).
`client_main` enqueues the job exactly as the generic path does (`enqueue`,
`wait_for_job_or_disconnect`).

In `generate_job`, after `ds4_session_set_cancel` and before the steering
block, branch:

```
if (j->sysone) { sysone_job(s, slot, j); goto finish; }   /* finish = the existing unlock tail */
```

`sysone_job`:

1. `request_live_state_clear(s, slot)`: the slot's live chat state is about to
   be replaced (this is what the steering branch below it already does).
2. If `ds4_session_steering(slot->session)`: `ds4_session_set_steering(slot->session, false)`;
   on failure 500.
3. `ds4_session_set_think_level(slot->session, 0)`.
4. `sf_sysone_decide(s->sysone, slot->session, sr->state, sr->q, sr->n, NULL, answers, &prefix_tokens, err, sizeof err)`.
   An error containing `max_tokens_exceeded` → 400; any other → 500.
5. Write the response.

`s->sysone` is created with `sf_sysone_open` when the server starts, after the
engine opens; a failure there is a startup error (the message names the
symbol).

Boost: a decision is not a max-effort job; `request_boosts` is not consulted.

The slot's session is left at the last question's suffix. The next chat
request finds no matching prefix and prefills again, or recovers through the
disk KV cache. `830` removes this cost; until then `docs/SERVER.md` states it.

## Response

```json
{"model":"<server_model_id_from_engine>","answers":{
  "<name>":{"type":"noul","noul":0.9731},
  "<name>":{"type":"choice","choice":"refund_request","confidence":0.88,
            "probabilities":{"refund_request":0.92,"shipping_question":0.05,"praise":0.03}},
  "<name>":{"type":"score","score":1.43,"confidence":0.35,
            "legend":{"0":"...","1":"...","2":"..."},
            "probabilities":{"0":0.0,"1":0.57,"2":0.43}}},
 "usage":{"input_tokens":<prefix + all suffixes>,"output_tokens":0}}
```

Numbers are printed with `%.6g`. `legend` values are the level texts as sent
(minified JSON when the level was an object).

When the request had `sf`, the response adds:

```json
"sf":{"template_version":1,"prefix_tokens":612,"prefill_ms":6480.2,
      "questions":{"<name>":{"suffix_tokens":41,"ms":1290.5,"legal_mass":0.97,
                             "logits":{"refund_request":18.2, ...}}}}
```

`logits` only when `sf.debug` is true.

## `GET /v1/models`

`send_models` keeps its OpenAI object and adds a sibling key:
`"models":[{"name":"<id>","description":"DeepSeek V4.1 Flash, system one readout","release_date":"<build date>"}]`,
one entry per id it already lists. Use the `YYYY-MM-DD` of the GGUF file's
mtime; if that is awkward to reach, use the fixed string of the model release
already present in the tree and say so in the PR text.

## Logging

One `server_log` line per decision: state tokens, questions, total ms, the
minimum legal mass. A legal mass under 0.5 logs a `DS4_LOG_WARNING` naming the
question.

## Tests

Unit (`./ds4_test --server`, under `DS4_SERVER_TEST`, like the existing parse
tests): each row of the parsing table has one accepting and one rejecting
case; the response writer on fixed `sf_sysone_answer` values matches a golden
string; the `sf` object is absent without `sf` in the request.

Live (`tests/test_sysone_http.py`, pattern `tests/test_deepseek41_http.py`,
standard library only): starts nothing, takes `--base-url`; sends fixture 1 of
`800` with three questions; checks field names and types against section 2 of
`docs/system-one.md`, probabilities summing to 1 within 1e-6, `output_tokens`
0; sends one request per error row and checks the status; then sends a chat
completion, a decision, and the same chat completion again and checks the two
chat answers are equal at temperature 0. Run this check on a server started
without `--kv-disk-dir`: with a disk cache the second chat could resume from a
checkpoint, and a different prefill schedule gives different, equally valid
bits (`docs/MODEL_KNOWLEDGE.md`, Determinism).

## Risks

- A long decision blocks chat requests on the same slot, as any request does.
- `ds4_test` is built with test hooks: it must link `sf_sysone.o` too, or the
  `--server` suite stops linking. `make test` must still name the server suite
  in its output.
