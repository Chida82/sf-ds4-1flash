# Tasks

Requires `800` merged into the working branch. Read `design.md` and
`docs/system-one.md` section 2 first.

## 1. Parse

- [x] 1.1 `sysone_request`, its free function, and `parse_sysone_request` following the parsing table; the three error writers (422 list, 400 code, 400 text).
- [x] 1.2 Unit tests for every table row in the `DS4_SERVER_TEST` block; register them where the other server tests are listed.
- [x] 1.3 `Makefile`: `sf_sysone.o` on the server, the CPU server and the `ds4_test` link lines. `make test` passes and prints the server suite.

## 2. Job

- [x] 2.1 `s->sysone` opened at startup after the engine, closed at shutdown.
- [x] 2.2 `struct job.sysone`; the route in `client_main`; `sysone_job`; the branch in `generate_job` reusing its unlock tail.
- [x] 2.3 Response writer with the golden-string unit test; the `sf` object rules.
- [x] 2.4 `send_models`: the `models` array; unit test on its JSON.

## 3. Live

- [x] 3.1 `tests/test_sysone_http.py` as in the design.
- [x] 3.2 Run it against `./sf-ds4-1flash-server --ssd-streaming --ctx 32768`. Paste its output (named checks) into the PR text.
- [x] 3.3 With the TypeSafe Python SDK only if it is already installed (`python3 -c "import typesafe"`); never install it on the machine. If absent, skip and say so. (Absent on 2026-11-11: skipped, see `live-run.md`.)

## 4. Docs

- [x] 4.1 `docs/SERVER.md`: section "System one" (endpoint, the three types, limits, the `sf` object, the cost note: a decision replaces the slot's live chat prefix until `830`).
- [x] 4.2 `docs/CLIENTS.md`: base-URL example for a Jev client and a `curl` example.
- [x] 4.3 `docs/MODEL_KNOWLEDGE.md`: endpoints list; "Logits over HTTP" row now points to `sf.debug`.
- [x] 4.4 `tests/test_sfctl.sh` still passes (no machine path or user name was added).
