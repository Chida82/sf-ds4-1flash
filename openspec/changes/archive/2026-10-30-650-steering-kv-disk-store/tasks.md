# Tasks

Work happens on a branch in a worktree, never on main. No commit or push without a request. Starts from `640` landed.

## 1. Engine permission

- [x] 1.1 Add `ds4_session_set_persist_steered` and the flag that `ds41_steering_refuses_persistence` reads (design D3), plus `ds4_engine_steering_profile_path`. Verify with a model-less test: a steered test session is refused without the flag and passes the check with it, and `make test` names the test.

## 2. Identity marker

- [x] 2.1 Implement the marker check, the restricted wipe, the atomic marker write and its log line (D2) as one function over a directory and a digest. Verify with model-less tests of the four marker cases, and that root entries, a stray file and a subdirectory survive a wipe.

## 3. Second store and routing

- [x] 3.1 Add `kv_steering`, open it after the marker check when a profile is loaded, remove the guard (D1, D2, D4), and set the persistence permission on each slot's session (D3). Verify that a server started with a profile and `--kv-disk-dir` logs both stores open, with their budgets.
- [x] 3.2 Add `server_kv` and switch the 21 sites to it, slot-based or request-based as design D1 says. Tool-memory restore gains the request's flag. Verify `git grep -n "s->kv\b\|&s->kv\b\|s->kv\." ds4_server.c` leaves only `server_kv`, open and close, and that the model-less selection test covers the four combinations.
- [x] 3.3 Eviction: verify with a model-less test that an over-budget steering store evicts only under `steering/`.

## 4. Model-backed acceptance

- [x] 4.1 Runs 1-3 of D5 on a temporary `--kv-disk-dir` (unsteered twice, steered twice, the cross-read sequence). Verify the log reports the loads, the repeated responses are token-identical, and the files are where the spec says.
- [x] 4.2 Run 4 of D5 (restart with a modified copy of the profile). Verify `steering/` is emptied, the root untouched, and the log count matches the files removed.

## 5. Docs and verification

- [x] 5.1 `ds4_help.c` (`--kv-disk-dir`: the `steering/` subfolder, the doubled budget), `docs/SERVER.md` (the disk-cache section and the "Steering per request" section of `640`: the cache is now on), `com-steering/README.md`, the `AGENTS.md` Identity "Steering" row, and `docs/upstream-prs.md` line `401` ("the server skips `--kv-disk-dir`" becomes the store split). Verify `git grep -n "skips .--kv-disk-dir\|not opening" -- '*.md' ds4_help.c` finds no current statement of the skip.
- [x] 5.2 `make test` (read the names of the tests that ran) and `make cpu`. Verify both pass.
- [x] 5.3 `openspec validate 650-steering-kv-disk-store --strict`. Verify it passes.

Notes from the implementation:
- 1.1: the flag test is in `tests/test_session_state_gpu --steering-switch` (with `630`'s cases).
- 2.1: `kv_steering_store_bind(dir, profile_path)` in `ds4_server.c`; model-less test `test_kv_steering_store` covers missing-and-empty, equal, different, missing-with-entries, and that the root entry, `notes.txt` and a subdirectory survive. The log line is printed only when something was recorded or removed.
- 3.1: the steering store opens only when the root store opened and a profile is loaded on request; if binding or opening fails, the server logs it and steered requests run without a disk cache (their sessions keep refusing persistence).
- 3.2: the request path takes one store per request at the top of `generate_job_inner`; the other sites route by the slot's switch; tool-memory restore takes the store of the request's model id. Only `server_kv`, open and close name `s->kv` now.
- 4.1/4.2: model-backed, 1017 GGUF, `--ssd-streaming --ctx 8192`, a 2190-token prompt, greedy, 120 tokens, `deepseek-chat` and `deepseek-chat-steering`, on a temporary `--kv-disk-dir`:
  - run A: unsteered stored a cold entry in the root; the steered request found nothing (cached 0), stored its own under `steering/` with the same file name, and left the root unchanged (names and mtimes);
  - run B (restart): unsteered loaded 2048 tokens from the root, steered 2048 from `steering/`; both texts identical to run A's;
  - run C (a copy of candor with one byte of its name changed): "steering KV store: profile changed, removed 2 entries", `steering/` empty, root entry kept, marker `sha1 <new>` / `name candor-modified.sfsteer`.
- 5.2: `make test` (server, session steering switch, session state, sampling, TP, Metal tests) and `make cpu` pass.
