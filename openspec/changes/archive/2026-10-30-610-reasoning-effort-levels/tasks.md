# Tasks

Work happens on a branch in a worktree, never on main. No commit or push without a request.

## 1. Level helper

- [x] 1.1 Add `ds4_think_mode_effort_level` to `ds4.c`/`ds4.h` (design D2) and make `ds4_deepseek41_reasoning_effort_text` use it. Verify `make test` and `make cpu` pass, and that the existing V4.1 render tests in `./ds4_test --server` are unchanged.
- [x] 1.2 Switch the five `ds4_session_set_think_level` call sites (`ds4_cli.c` x4, `ds4_server.c`) to the helper. Verify with a model-less unit test: one row per mode (`NONE`, `HIGH`, `MAX`, numeric 0/25/100, `LOW`, `MEDIUM`) gives -1/75/100/0/25/100/-1/-1, and `make test` names the test.

## 2. Name table

- [x] 2.1 Change `parse_reasoning_effort_name` to the table of design D1, with the `sf:` comment at the site. Verify by updating `test_reasoning_effort_mapping` and the `xhigh` assert in `test_api_thinking_controls_parse`; `make test` passes and names both.
- [x] 2.2 Add the render test of D4: for each name, the V4.1 render carries the expected effort line, or closes thinking for `none`/`minimal`. `high`, `max`, `"75"` and `"100"` match fixed strings captured from main before 2.1. Verify it fails on main for `low`/`medium`/`xhigh`/`minimal` and passes on the branch.
- [x] 2.3 Add the precedence tests of D3 through `parse_chat_request` and `parse_anthropic_request` (the spec's four scenarios), plus one Responses body with `reasoning.effort` `minimal`. Verify they pass on both main and the branch: the precedence is unchanged, only `minimal` differs, as the spec says.

## 3. Docs and client check

- [x] 3.1 Rewrite `docs/SERVER.md` lines 62-65: the name → level table, the precedence, and `minimal` as no thinking. Verify `git grep -n "Think Max\|xhigh" docs/` finds no statement left that contradicts the table.
- [x] 3.2 `docs/CLIENTS.md`: make pi's `thinkingLevelMap` the identity map, including `"max": "max"`. Verify the JSON block parses (`python3 -I -m json.tool` on the extracted block).
- [x] 3.3 Observe what pi sends for `off` (design D5): point pi at `nc -l 8002`, send one message at `off`, and read the raw request body. No model is needed. Write the finding in `docs/CLIENTS.md`. Verify the doc states the observed field, or that nothing was sent, plus the `deepseek-chat` fallback.

## 4. Verification

- [x] 4.1 `make test` (read the names of the tests that ran), and a greedy server request at `high` on main and on the branch: identical body apart from id and timestamps. Verify both.
- [x] 4.2 `openspec validate 610-reasoning-effort-levels --strict` passes.

Notes from the implementation:
- 2.2: the request parsers tokenize through the engine, which the unit tests do not have; `tokenize_rendered` now returns early without an engine (one `sf:` line), so the tests read `prompt_text`. The fixed `high` string matches the branch's render; the `HIGH` path of `ds4_deepseek41_reasoning_effort_text` gives 75 on both trees by construction. On main, `low`/`medium` parse to `LOW`/`MEDIUM` and render no line, and `minimal` to `LOW`, so the test fails there.
- 3.3: read from Pi 1.4.0's `openai-completions.js` instead of a socket capture, to leave `~/.pi` untouched: with `"thinkingFormat": "deepseek"`, `off` sends `"thinking":{"type":"disabled"}` unless the map sets `"off": null`, which sends nothing.
- 4.1: `make test` and `make cpu` pass. The model-backed comparison ran inside `640`'s acceptance 5.1: `deepseek-v4.1-flash` with no effort (= `high`), greedy, short and 2.2K prompts, on main's server and on the stacked branch: identical text and usage.
