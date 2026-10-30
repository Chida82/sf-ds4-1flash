# Tasks

Work happens on a branch in a worktree, never on main. No commit or push without a request. Starts from `610`, `620` and `630` landed.

## 1. Inventory

- [x] 1.1 List every server path that consumes or produces a slot's live state: routing, probe tiers, prefix sync and rewind, live tool state and DSML replay, checkpoints, batch membership, payload or snapshot calls, disk cache. Record each with its rule in design D5's table, adding rows for what the table misses. Verify `git grep -n "ds4_session_sync\|ds4_session_rewind\|ds4_session_invalidate\|ds4_session_tokens\|live_tool\|tool_replay" ds4_server.c` has no call site outside the recorded rows.

## 2. Configuration

- [x] 2.1 Add `--steering-profile-on-request`, turn `--steering-profile` into a startup error, add the TP/distributed check, and set every slot off after creation (design D1). Put the checks in a configuration-check function. Verify with model-less tests of that function: old flag, TP leader, distributed worker, and the accepted case.
- [x] 2.2 `ds4_help.c`: the server's help lists `--steering-profile-on-request` and says steering is selected per request with a `-steering` model id. Verify `./sf-ds4-1flash-server --help` shows it and no longer lists `--steering-profile`.

## 3. Model ids and the model list

- [x] 3.1 Add `model_id_split`, make the alias predicates compare the base id, and store `r->steering` in the four parsers (D2). Verify model-less tests on the six ids, including `deepseek-chat-steering` with and without `thinking: true`.
- [x] 3.2 Add `request_steering_check` at the queueing point (D2). Verify model-less tests: 400 without a profile, 400 for `foo-steering`, accepted with a profile.
- [x] 3.3 `append_models_list` and the `/v1/models/<id>` resolution (D3). Verify model-less tests with and without a profile.

## 4. Per-request switch and isolation

- [x] 4.1 `generate_job` sets the slot's switch from `j->req.steering` (D4). Verify `./ds4_test --server` passes.
- [x] 4.2 Add the probe gate in `slot_probe_reuse_locked` and any further rule the inventory (1.1) requires (D5). Verify the model-less probe test: a steered request scores `REUSE_NONE` on an unsteered checkpoint and the reverse, while a matching slot keeps its score.
- [x] 4.3 Logs: the `steer` flag and the trace line (D6). Verify with a model-less test of `log_flags`, or by reading one request's lines in 5.3.

## 5. Model-backed acceptance

- [x] 5.1 Acceptance 1 of D7: main without a profile against the branch with the profile, requests without the suffix, greedy, thinking on and off. Verify identical tokens and usage.
- [x] 5.2 Acceptance 2 of D7: main with `--steering-profile` and `deepseek-v4.1-flash` against the branch with `-steering`. Verify identical tokens and usage.
- [x] 5.3 Acceptance 3 of D7: one slot, unsteered, steered, unsteered on the same prompt. Verify each request evaluates its whole prompt (log), the third response equals the first, and the log lines carry `steer` only on the second.

## 6. Docs and verification

- [x] 6.1 `docs/CLIENTS.md`: pi gets a second model `deepseek-v4.1-flash-steering` with the same `thinkingLevelMap`. `docs/SERVER.md` gets a "Steering per request" section: flag, ids, 400, the one-slot re-prefill note, and that the disk cache is off while a profile is loaded (until `650`). Also `com-steering/README.md` "Using a profile" and the `AGENTS.md` Identity "Steering" row. Verify `git grep -n -e "--steering-profile" -- docs/ README.md AGENTS.md com-steering/README.md` shows the server only with `-on-request`.
- [x] 6.2 `make test` (read the names of the tests that ran) and `make cpu`. Verify both pass.
- [x] 6.3 `openspec validate 640-server-request-steering --strict`. Verify it passes.

Notes from the implementation:
- 1.1 inventory. Every reuse of a slot's live state is chosen by `slot_probe_reuse_locked` (routing scores, the live tiers, the Responses/Anthropic continuations) and runs inside `generate_job_inner`, after `generate_job` has set the switch. Rows added to D5: the Responses/Anthropic live continuation (a request that needs live tool state held under the other setting gets the existing 409 "continuation state is not available; retry by replaying"); the slot's live tool state is cleared with `request_live_state_clear` when the switch changes; the "evict" disk store before a load runs after the switch, on an empty session; `ds4_sessions_eval_batch` is the engine's per-item rule (`630`); tool-memory restore at parse time reads only text maps, and stays on the root store until `650`.
- 3.1/3.2: `r->steering` is set once, by `request_steering_check` at the queueing point, rather than in the four parsers; the parsers' alias rule compares the base id through `model_base_is`. An unknown plain id is still accepted as before; only an unknown base with the suffix (`foo-steering`) is a 400.
- 4.3: the request log flag is `STEER` (upper case, like the existing flags), added after `log_flags` on the prompt start/done lines; the trace prints `steering: on|off`.
- 5.x: model-backed, 1017 GGUF, `--ssd-streaming --ctx 8192`, greedy, `max_tokens` 200, a short prompt (22/48 tokens) and a 2.2K-token one, thinking on (`deepseek-v4.1-flash`) and off (`deepseek-chat`). Main's server was built from `git archive main`.
  - 5.1: branch with the profile, plain ids == main without a profile: 4/4 identical text, prompt and completion tokens.
  - 5.2: branch `-steering` ids == main with `--steering-profile`: 4/4 identical.
  - 5.3: one slot, chat / chat-steering / chat on the short prompt: each logged `ctx=0..22:22` (whole prompt), `STEER` only on the second, third == first.
  - Also: a server without a profile answers 400 to `deepseek-v4.1-flash-steering` and lists only `deepseek-v4.1-flash`.
- 6.2: `make test` and `make cpu` pass on the combined tree (run after `650`).
