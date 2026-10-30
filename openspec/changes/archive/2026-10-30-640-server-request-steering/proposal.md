# Proposal

## Why

Today `--steering-profile` on the server applies the profile to every request. The server is shared by agents that should mostly run the plain model, with steering reserved for the requests that ask for it. The owner wants the profile loaded at startup and **off**, and each request to choose. Clients have to be able to choose without custom JSON fields, which many OpenAI-compatible agents (pi among them) cannot add. Every such client can choose the model, though, and the server already uses model aliases as switches: `deepseek-chat` and `deepseek-reasoner` turn thinking off and on.

## What Changes

- **BREAKING: the server's flag is renamed.** `--steering-profile-on-request NAME|FILE` loads the profile with every session's switch off (`630`). Passing `--steering-profile` to the server exits with an error naming the new flag. Silently starting unsteered would hide the change from anyone who relied on the old meaning. The CLI and eval keep `--steering-profile`, still meaning "on".
- **Requests opt in through the model id.** These aliases turn steering on for the request:
  - `deepseek-v4.1-flash-steering`;
  - `deepseek-chat-steering`;
  - `deepseek-reasoner-steering`.

  The suffix is stripped first, then the base alias keeps its thinking semantics and `610`'s precedence: an explicit thinking control wins over the alias. The response reports the model id the request sent.
- **A server without a profile answers 400** to a `-steering` id. The message names `--steering-profile-on-request`. A client must never believe it is steered when it is not.
- **`/v1/models` lists the `-steering` ids** only when a profile is loaded.
- **Each request sets its slot's switch** with `ds4_session_set_steering` before prefill. The request log line states whether steering was on.
- **No live state crosses the switch.** The first task maps every path by which a request reuses state another request left behind, and decides each one. Known so far:
  - `slot_probe_reuse` / `slot_probe_reuse_locked` (`ds4_server.c:10834`, routing and reuse scores);
  - resident checkpoints and continued prefixes;
  - tool memory and exact DSML tool replay (`kv_cache_restore_tool_memory_for_messages`, `tool_memory_attach_to_messages`);
  - membership of the decode batch;
  - any snapshot or payload endpoint.

  A slot whose session steering differs from the request's scores as reusing nothing, so the router prefers another slot. The engine's own guarantee from `630` (switching drops live state) stays the backstop.
- **Batching:** unsteered requests batch with each other. Steered ones decode serialized, which is the `630` engine decision; no server logic is added.
- **TP/RDMA is not touched.** A server with tensor parallelism refuses to start with `--steering-profile-on-request`, because the per-request switch is not carried to worker ranks and the transport frames are not changed.
- **The disk cache is unchanged in this change:** with a profile loaded the server still skips `--kv-disk-dir`, as today. `650` opens it with a separate steering store. This intermediate state is safe: nothing is cached that could cross.
- **Tests:**
  - **Server unit tests:**
    - alias parsing for the three ids, with and without the suffix, combined with explicit thinking controls;
    - 400 without a profile;
    - `/v1/models` with and without a profile;
    - the old flag refused;
    - TP plus the flag refused;
    - slot probe scoring with mismatched steering.
  - **Model-backed acceptance**, greedy, same prompt, thinking on and off:
    - with the profile loaded, a request without `-steering` is bitwise identical to a server started without a profile;
    - a request with `-steering` is bitwise identical to the same request on the server before this change, started with `--steering-profile` (same renderer, so the comparison is exact; the CLI renders its prompt differently).
- **Docs:**
  - `ds4_help.c`: the server option. The help also states that the CLI/eval flag of the same root means "on".
  - `docs/CLIENTS.md`: pi gets a second model, `deepseek-v4.1-flash-steering`, with the same `thinkingLevelMap`.
  - `com-steering/README.md` "Using a profile".
  - The Steering row of `AGENTS.md` Identity.

Non-goals:
- One profile only, with no per-request choice among several.
- No JSON field for steering.
- No live `/steer` endpoint.
- No TP support.

## Capabilities

### New Capabilities
- `request-steering`: how the server loads a steering profile, how a request selects it through its model id, the errors when it cannot, and the isolation of live state between steered and unsteered requests.

### Modified Capabilities
- `directional-steering`: "Steering profile file" names the server's `--steering-profile-on-request` alongside the CLI/eval `--steering-profile`.

## Impact

- **Code:** `ds4_server.c`:
  - argument parsing;
  - alias handling (`server_model_alias_known`, `model_alias_disables_thinking`, `model_alias_enables_thinking`);
  - `/v1/models`;
  - per-request switch;
  - slot probe;
  - logging;
  - tests.

  Also `ds4_help.c` and the docs listed above.
- **Clients:** none breaks. A client that sends today's ids gets today's unsteered behaviour. Steered clients change their model id.
- **Speed:** none claimed. Unsteered requests run the unsteered kernels; steered requests run today's steered path.
- **Order:** fourth. It needs `630`'s switch and `610`'s level helper, the latter so that the server/CLI comparison holds at every effort. `650` builds its cache routing on the request's steering flag introduced here.
