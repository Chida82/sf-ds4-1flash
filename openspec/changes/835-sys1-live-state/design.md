# Design

Depends on `830` (state snapshots, chat preservation, `sf_sysone_answer_from`).

## Step 0: establish when the live session is a prefix (before any feature code)

The whole gain depends on one fact that must be observed, not assumed: after
a chat turn, are the slot's live tokens a prefix of the tokens the chat
template gives for the same conversation plus one more user turn?

Likely trouble: the live session holds the assistant's turn *as generated*
(with its reasoning, and possibly without an end token), while a re-rendered
history holds it as the client sends it back (no reasoning). The chat path
already deals with this for normal continuation; find how.

Do this, and write the findings in the PR text before going on:

1. Read `generate_job_inner` (`ds4_server.c`) from its start to the first
   `ds4_session_sync` call and list, in order, the functions it uses to bring
   the slot to the request's prompt (live-prefix check, rewrite from the
   common prefix, disk KV load).
2. With a temporary log line (removed afterwards), run: a chat completion
   with thinking off; then the same conversation plus the assistant's answer
   plus a new user message. Log `ds4_session_common_prefix(session, &prompt)`
   and `prompt.len` for the second request. Repeat with reasoning effort
   `high`.
3. Outcomes:
   - both cases reuse all but the new turn → the plain design below works;
   - thinking-off reuses and thinking-on does not → implement the design, and
     document that a live-state decision after a *thinking* turn prefills the
     conversation again (still correct, only slow), unless step 1 found a
     single function that performs the reuse; if so call it instead of the
     bare sync and say which;
   - neither reuses → **stop and report**. The feature has no gain.

## Request

`"sf":{"state":"messages"}` and `state` an array of objects with string
`role` (`system`, `user`, `assistant`) and string `content`. Anything else
(tool roles, content arrays, images) → 422 naming the field. Without
`sf.state`, an array state keeps its `810` meaning (minified JSON text).

## Tokens

`M` = the conversation: `ds4_chat_begin`, then
`ds4_chat_append_message(e, &t, role, content)` for each message. (These are
the public functions the template is built from; if step 0 showed the chat
path renders through another function, use that one, so both produce the same
tokens.)

Question k's full prompt `R_k` = `M`, then:

1. `ds4_tokens_push(&t, ds4_token_user(e))`
2. `"Question about the conversation above: "`, instructions, `"\nOptions:\n"`,
   the option lines and the instruction line exactly as in `800`
3. `ds4_chat_append_assistant_prefix(e, &t, DS4_THINK_NONE)`
4. the frozen answer prefill of `800`

Every `R_k` starts with `M` by construction, so the shared prefix is `M`.
Add `sf_sysone_turn_suffix(so, q, out)` for steps 1-4, reusing the option-line
code of `sf_sysone_question_suffix`.

The decision does not use `SYS` from `800`: the conversation's own system
message stays. This is a different prompt from `state_first`, so it has its
own template version and its own calibration binding (`"layout":"live"`); a
`state_first` calibration is not applied to it (temperature 1, reported in
`sf`).

## Flow (`sysone_job`)

```
chat keep-snapshot as in 830
sync slot to M      (bare ds4_session_sync, or the function step 0 named)
answers = sf_sysone_answer_from(so, session, &M, NULL, questions, layout = live)
restore the chat snapshot as in 830
```

`830`'s state cache is not consulted in this layout: the live session is the
cache. The `sf` object reports `"layout":"live"` and `"reused_tokens"`: the
common prefix found before the sync.

## Tests

Unit: the request parsing rows; `sf_sysone_turn_suffix` begins with the user
marker and ends with the prefill tokens.

Live (`tests/test_sysone_http.py`): a chat completion (thinking off), then a
live-state decision with that conversation plus the answer as messages:
`reused_tokens` is at least the first request's prompt tokens, and the
decision's state prefill is under 0.5 s; then the conversation's next chat
turn prefills only its new tokens (`830`'s guarantee).

Bench (`run.py --scenario live`): 20 conversations of about 600 tokens; per
conversation one chat turn, then three live-state decisions. Record the
median decision latency against the same decisions sent with the
conversation as a `state_first` text state on a server without the state
cache.

Kept when the live median is at most one third of the `state_first` median.

## Step 0 findings (2026-11-12)

`generate_job_inner` (`ds4_server.c`) reaches the request's prompt in this
order: `ds4_session_common_prefix` against the live session; the live-prefix
probe and its special continuations (Responses tool-output ids, Anthropic
tool ids, and the **thinking live continuation**, which matches the visible
prefix of a turn whose live tokens carry hidden reasoning); a rewind
(`ds4_session_rewrite_from_common`) where allowed; the disk KV cache
(`kv_cache_*`); then `server_session_sync` for the rest.

Measured with the server's own prefill log (`chat ctx=A..B`; no temporary
log line was needed, the existing one prints the reused range):

| First turn | Second request (same conversation + answer + user turn) |
|---|---|
| thinking off, 17 prompt + 70 generated | `ctx=87..95`: 87 reused by plain token prefix |
| thinking high, 43 prompt + 153 generated | live 196 is **not** a token prefix (`live kv cache miss ... token-mismatch` on the plain check); reused only through `thinking live continuation match=visible-prefix` |

Outcome rule 2 applies: thinking-off reuses, thinking-on does not by plain
prefix. The thinking continuation is woven through `generate_job_inner`, not
one callable function, so the live layout uses a bare `ds4_session_sync` and
documents that a decision after a thinking turn prefills the conversation
again.

## Decisions taken during apply (2026-11-12)

- **Rendering through the chat endpoint's renderer, not the public
  `ds4_chat_append_message`.** `ds4_chat_append_message` writes an assistant
  message without the end-of-sentence token the generated turn ends with, so
  its tokens would diverge from the live session at that position and every
  decision would refill from scratch. The server renders the conversation with
  `render_chat_prompt_text_for_syntax` + `tokenize_rendered`, as the chat path
  does (the design allows it: "if step 0 showed the chat path renders through
  another function, use that one").
- **Question as an ordinary user message.** Because the rendering is text,
  the question turn is text too: `sf_sysone_turn_text(q)` ("Question about the
  conversation above: ..." + the `800` option lines + the instruction line),
  appended as one more `user` message and rendered with thinking off. The
  shared prefix `M` is the common token prefix of the conversation rendered
  alone and of every question's rendering; each question's suffix is the rest.
  `sf_sysone_turn_suffix` of the design is therefore `sf_sysone_turn_text`
  plus the server's renderer; `sf_sysone_answer_suffixes` takes the
  precomputed suffixes (`sf_sysone_answer_from` is now a wrapper of it with
  the template's suffixes, bitwise unchanged).
- `reused_tokens` is `ds4_session_common_prefix(session, M)` before the sync.
- The `layout` value `live` exists only in the response's `sf` object; no
  calibration file for it was fitted, so none can bind to it yet (a
  `state_first` file is not applied: temperature 1 unless `sf.temperature`).
