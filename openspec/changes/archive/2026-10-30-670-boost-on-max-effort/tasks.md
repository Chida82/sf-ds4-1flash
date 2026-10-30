# Tasks

Work happens on a branch in a worktree, never on main. No commit or push without a request. Starts from main with `610`-`650` landed.

## 1. GPU layer and engine

- [x] 1.1 In `ds4_metal.m`, split `ds4_gpu_set_boost` into `ds4_gpu_boost_check(const char *flag)` (today's check and three messages, with the flag name substituted) and `ds4_gpu_boost_active(bool)`. `g_boost` accesses become relaxed `__atomic` loads and stores. `ds4_gpu_set_boost` stays as check + active + fan hint (design D1). Declare both in `ds4_gpu.h`. Verify `make` and `make cpu` build, and `./sf-ds4-1flash-server --help` still starts.
- [x] 1.2 `ds4.h`/`ds4.c`: add `ds4_engine_options.boost_on_request`. Engine open calls `ds4_gpu_boost_check("--boost-on-max-effort")` for it and leaves boost off. Add `ds4_engine_set_boost(ds4_engine *, bool)`, which is a no-op unless the engine was opened with `boost_on_request` and is a no-op in the `DS4_NO_GPU` build (D2). Verify `make test` passes and `make cpu` builds.

## 2. Server

- [x] 2.1 Parse `--boost-on-max-effort` into `c.engine.boost_on_request`. Generalise `server_config_check_steering` into `server_config_check` and add the refusal of `--boost` together with `--boost-on-max-effort` (D4). Verify a model-less test of the check function: both flags refused, each flag alone accepted, and the existing steering cases unchanged.
- [x] 2.2 Add the predicate (`ds4_think_mode_effort_level(mode) == 100`) and the counter transition helper, then use them in `generate_job` under `model_mu`, with one log line per transition (D3). Verify model-less tests:
  - the predicate on parsed requests: chat `max`, `"100"`, `xhigh`, `high`, no effort, `max` with `thinking: false`, Anthropic `output_config.effort` `max`, Responses `reasoning.effort` `max`;
  - the helper: 0→1 and 1→0 report a transition, 1→2 and 2→1 do not.
- [x] 2.3 `ds4_help.c`: the server lists `--boost-on-max-effort`, says it needs fanboost like `--boost`, that it boosts only while a max-effort request generates, and that it excludes `--boost`. Verify `./sf-ds4-1flash-server --help runtime` (or wherever `--boost` is listed) shows it, and that the CLI's help does not.
- [x] 2.4 Docs: in `README.md`, add the per-request variant to the `--boost` section. In `AGENTS.md`, add one sentence on the server flag to the `--boost` paragraph. Update `fanboost/README.md` only if it lists the engine's flags. Verify `git grep -n -e "--boost-on-max-effort"` shows help, README and AGENTS.

## 3. Model-backed acceptance

Run with `--ssd-streaming`, the 1017 GGUF, greedy and short `max_tokens` (for example 256), with the fanboost daemon running and nothing else on the machine.

- [x] 3.1 Server with `--boost-on-max-effort`. Send one `high` request, then one `max` request. Verify:
  - the log has no boost line for `high`, and exactly one on line and one off line for `max`;
  - `fanboost status` during the `max` request shows the fans at maximum;
  - the close stats print `decode keep-alive tokens=` greater than 0.
- [x] 3.2 The same `max` and `high` requests on a server without the flag (main built from `git archive main`). Verify text, prompt tokens and completion tokens are identical to 3.1's.
- [x] 3.3 Startup refusal: start with `--boost --boost-on-max-effort`. Verify exit with the error naming both flags, before the model loads. The fanboost-down refusal shares `--boost`'s verified path. Check its message by reading the diff that substitutes the flag name.

## 4. Integration

- [x] 4.1 `make test` (read the names of the tests that ran) and `make cpu`. Verify both pass.
- [x] 4.2 `openspec validate 670-boost-on-max-effort --strict`. Verify it passes.

No A/B run and no parity oracle in this change: it is opt-in and leaves the default path unchanged. The parity oracle runs once at the end of the project.

## Workflow follow-up

- Final review pass over the touched region against `AGENT.md`, then archive and land as one signed commit when the owner asks.
