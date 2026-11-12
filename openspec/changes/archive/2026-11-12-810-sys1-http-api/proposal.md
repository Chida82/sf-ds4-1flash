# Proposal

## Why

Laya, JevK5 and Rizzo Flow all serve TypeSafe's `POST /v1/systemone`
(`docs/system-one.md`, section 2). A server that speaks it is usable at once by
the TypeSafe Python and JavaScript SDKs, by the LangChain harness, and by the
public benchmarks, with only a base URL changed. `800` gave the engine-side
core; this change puts it behind that endpoint in `sf-ds4-1flash-server`.

## What Changes

- `POST /v1/systemone`: request and response in the Jev shape, for `noul`,
  `choice` (1-26 options) and `score` (1-10 levels).
- `GET /v1/models` also carries Jev's `models` array, beside the OpenAI `data`
  array it has today.
- Jev's error statuses: 422 with a `detail` list for validation, 400 with
  `max_tokens_exceeded` for a request over the context.
- An optional request object `"sf"` for this server's extensions, and an
  `"sf"` object in the response only when the request had one. Without it the
  response has exactly Jev's fields.
- A decision runs on the slot's session, unsteered, as one queued job like any
  other request.

## Non-goals

- `box`, `assets`, images: 422.
- More than 26 options: 422 until `a040`.
- Bearer authentication: the server has none on any endpoint; `sfctl` binds
  it to localhost. Not added here.
- Keeping the chat session's live KV across a decision: `830`.
- Calibration: `820`.

## Impact

- `ds4_server.c`: route, parser, job branch, response writer, unit tests under
  `DS4_SERVER_TEST`.
- `Makefile`: the server and `ds4_test` link `sf_sysone.o`.
- `tests/test_sysone_http.py`: live test.
- Docs: `docs/SERVER.md`, `docs/CLIENTS.md`, `docs/MODEL_KNOWLEDGE.md`.
