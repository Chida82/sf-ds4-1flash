# Design

## Context

Every server API funnels a named effort through `parse_reasoning_effort_name` (`ds4_server.c:1078`), reached from `parse_reasoning_effort_value`:
- chat `reasoning_effort` and `chat_template_kwargs`;
- Anthropic `output_config.effort`;
- Responses `reasoning.effort`.

Numeric strings go to `ds4_think_mode_parse_level` and become `DS4_THINK_LEVEL_BASE + N`.

Each of the four request parsers then applies the same three lines: `ds4_server.c:3725`, `3941`, `4970`, `5176`.

```
if (!got_thinking && model_alias_disables_thinking(model)) thinking_enabled = false;
if (!got_thinking && model_alias_enables_thinking(model))  thinking_enabled = true;
think_mode = think_mode_from_enabled(thinking_enabled, effort);   /* NONE wins */
```

`ds4_think_mode_for_context` is the identity in this child, because upstream's Think Max downgrade excludes V4.1.

V4.1 renders the effort with `ds4_deepseek41_reasoning_effort_text` (`ds4.c:26847`). That function maps `HIGH` to 75 and `MAX` to 100, and numeric modes to their level. Anything else, `LOW` and `MEDIUM` included, renders no line.

Frontends report the steering level with `ds4_session_set_think_level(s, ds4_think_mode_level(mode))`, at `ds4_cli.c:489`, `656`, `745`, `880` and `ds4_server.c:13816`. `ds4_think_mode_level` returns -1 for every named mode.

## Goals / Non-Goals

**Goals:**
- One table, in one function, from names to modes.
- One function that answers "which level does this mode put in the prompt", used both by the renderer and by the session level.
- Unchanged bytes for `none`, `high`, `max` and numeric requests.

**Non-Goals:**
- Changing `ds4_think_mode_level` or `ds4_think_mode_name`. Both are upstream and keep their meaning: numeric modes only.
- Removing `DS4_THINK_LOW` / `DS4_THINK_MEDIUM` from the enum. They are upstream and still used by the V4 renderer's tests.
- The CLI's commands.

## Decisions

### D1. Names become numeric modes, except `high` and `max`

`parse_reasoning_effort_name` returns:
- `DS4_THINK_NONE` for `none` and `minimal`;
- `DS4_THINK_LEVEL_BASE + 25` for `low`;
- `DS4_THINK_LEVEL_BASE + 50` for `medium`;
- `DS4_THINK_LEVEL_BASE + 90` for `xhigh`;
- the unchanged `DS4_THINK_HIGH` and `DS4_THINK_MAX` for `high` and `max`.

`high` and `max` keep their enums because they already render 75 and 100. Turning them into numeric 75 and 100 would give identical prompts, but it would change the log name (`high` becomes `75`) and break the tests that compare with `DS4_THINK_MAX`, for nothing.

Alternative considered: map in `ds4_deepseek41_reasoning_effort_text`, so that `LOW` renders 25 and `MEDIUM` 50. That would fix `low`/`medium` but not `xhigh` (which parses to `HIGH`) or `minimal`. It would also put the table in `ds4.c`, away from the names it interprets.

The function is upstream code, so the edit carries one `sf:` comment at the site, replacing the upstream comment that says `minimal` is "the smallest non-zero level".

### D2. `ds4_think_mode_effort_level`

A new function beside `ds4_think_mode_level` in `ds4.c`, declared in `ds4.h`:
- `HIGH` → 75;
- `MAX` → 100;
- numeric → N;
- everything else → -1.

`ds4_deepseek41_reasoning_effort_text` calls it instead of its two inline overrides; its output is unchanged by construction. The five `ds4_session_set_think_level` call sites pass it instead of `ds4_think_mode_level`.

-1 keeps today's meaning, "unknown, counts as 75", for `NONE`, where the level is never read because the closure runs only in thinking, and for `LOW`/`MEDIUM`, which no V4.1 frontend produces after D1.

Alternative considered: change `ds4_think_mode_level` itself. It is upstream, and `ds4_think_mode_name` and the numeric-parse tests rely on its -1 for named modes.

### D3. Precedence is tested, not rewritten

The four parsers already implement the precedence of the spec:
- `got_thinking` blocks the alias;
- an explicit disable sets `thinking_enabled = false`;
- `think_mode_from_enabled` returns `NONE` for a `NONE` effort, regardless of the flag.

No code changes. The tests go through `parse_chat_request` and `parse_anthropic_request`, with request bodies, so a future edit to any of the lines above fails a test.

### D4. Tests

All in the server unit tests (`make test`), with no model:
- `test_reasoning_effort_mapping`: the new table, replacing the `minimal`/`medium` asserts. The `ds4_glm_reasoning_effort_text` asserts stay, since that function is not touched.
- `test_api_thinking_controls_parse`: `xhigh` now yields level 90.
- A render test: for each name, `render_chat_prompt_text_for_syntax(SERVER_MODEL_SYNTAX_DEEPSEEK41, ...)` contains the expected `Reasoning Effort: N` line, or none plus `</think>` for `none` and `minimal`. `high`, `max` and the numeric `"75"`/`"100"` produce byte-identical renders to a fixed string taken from today's tree.
- Precedence: the four scenarios of the spec through the request parsers.
- The helper: one row per mode.

### D5. Docs

- `docs/SERVER.md` (lines 62-65) still describes the V4 behaviour: "Think Max only with sufficient context", "`xhigh` maps to normal thinking". It is replaced by the name → level table and the precedence.
- `docs/CLIENTS.md`: pi's `thinkingLevelMap` becomes the identity, including `max`.
- What pi sends for `off` is observed once, without a model: pi's base URL points at a listening socket (`nc -l 8002`) that prints the raw request. The result is written in `CLIENTS.md`. If pi sends no thinking control for `off`, the doc says so and points to the `deepseek-chat` model id as the reliable way.

## Risks / Trade-offs

- [A client relies on `minimal` meaning "a little thinking"] → It now gets none. This is intended and recorded as BREAKING in the proposal and in `docs/SERVER.md`. `low` (25) is the nearest replacement.
- [Prompt bytes change for `low`/`medium`/`xhigh`] → Their disk KV cache entries from before the change no longer match by text and are simply not hit. Nothing is invalidated by hand.
- [The steering level changes under `max`] → Only steered thinking runs at `max` are affected. The closure onset moves from the level-75 point to the level-100 point, which is what the spec always meant.
- [Upstream edits `parse_reasoning_effort_name`] → One small conflict site, resolved once and replayed by rerere. The `sf:` comment marks it.

## Migration Plan

None beyond the docs. There is no stored state to convert.
