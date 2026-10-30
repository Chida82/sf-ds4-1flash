# Proposal

## Why

OpenAI-compatible agents choose how much the model reasons by sending a named effort. Pi, for example, cycles `minimal`, `low`, `medium`, `high`, `xhigh` and `max`, and sends the name as `reasoning_effort`. On V4.1 the server turns four of those six names into something other than what the client asked for:

| Name | Today (`parse_reasoning_effort_name`, `ds4_server.c:1078`) | V4.1 prompt today |
|---|---|---|
| `minimal` | `DS4_THINK_LOW` | thinking **on**, no effort line |
| `low` | `DS4_THINK_LOW` | thinking on, no effort line |
| `medium` | `DS4_THINK_MEDIUM` | thinking on, no effort line |
| `high` | `DS4_THINK_HIGH` | `Reasoning Effort: 75 (range 1-100, ...)` |
| `xhigh` | `DS4_THINK_HIGH` | the same as `high` |
| `max` | `DS4_THINK_MAX` | `Reasoning Effort: 100 ...` |

`ds4_deepseek41_reasoning_effort_text` (`ds4.c:26847`) renders a line only for `HIGH`, `MAX` and explicit numeric levels. `low` and `medium` therefore leave the model at its own default, `xhigh` equals `high`, and `minimal`, which clients use as their no-reasoning level, turns thinking on. V4.1's template takes a continuous level from 1 to 100, so each name can mean a distinct level.

A second defect sits on the steering side. The closure channel of the steering profile (`419`) places its onset from the prompt's effort level. Every frontend passes that level as `ds4_think_mode_level(mode)`, which returns -1 for the named `HIGH` and `MAX` modes. -1 is read as "unknown, count 75", so a `max` request tells the model 100 while the closure onset is placed for 75.

## What Changes

- **One table maps names to levels.** It lives in `parse_reasoning_effort_name`, the single entry point for chat-completions `reasoning_effort` and `chat_template_kwargs`, Anthropic `output_config.effort` and Responses `reasoning.effort`:

  | Name | New meaning | Prompt bytes vs today |
  |---|---|---|
  | `none` | no thinking | unchanged |
  | `minimal` | **no thinking** | **BREAKING**: thinking was on |
  | `low` | level 25 | **changed**: gains `Reasoning Effort: 25` |
  | `medium` | level 50 | **changed**: gains `Reasoning Effort: 50` |
  | `high` | `HIGH`, rendered 75 | unchanged |
  | `xhigh` | level 90 | **changed**: was 75 |
  | `max` | `MAX`, rendered 100 | unchanged |
  | `"0"`..`"100"` | that level (`"0"` = no thinking) | unchanged |

- **Precedence is pinned by tests, not changed:**
  1. An explicit disable always wins: `thinking:false`, `{"type":"disabled"}`, `think:false`, or the `chat_template_kwargs` equivalent.
  2. Then an effort of `none`, `minimal` or `"0"` means no thinking.
  3. Then the `deepseek-chat` alias disables thinking and `deepseek-reasoner` enables it, as today, only when no explicit thinking control was sent.
  4. Otherwise thinking runs at the effort level; the default stays `high`.
- **The steering level comes from the same table as the text.** A single helper returns the level the prompt carries: 75 for `HIGH`, 100 for `MAX`, N for numeric levels, and none when thinking is off. It feeds both `ds4_deepseek41_reasoning_effort_text` and the five `ds4_session_set_think_level` call sites (`ds4_cli.c` x4, `ds4_server.c:13816`). Only steered thinking runs at `max`, or at `/think-max` in the CLI, see a different closure onset.
- **Server unit tests.** The asserts at `ds4_server.c:17079-17081` (`minimal → LOW`, `medium → MEDIUM`) are updated. New tests cover the whole table, the four precedence rules, and the helper's level for every mode.
- **`docs/CLIENTS.md`.** Pi's `thinkingLevelMap` becomes the identity map, including `"max": "max"`. A short table gives each name's level. The value pi sends for `off` is checked in the server log and written down.

Non-goals:
- The V4.1 renderer's text format is not touched.
- The V4 Flash renderer (`render_deepseek_chat_prompt_text`, with its "Absolute maximum" Think Max prefix) is not touched. In this child only server tests reach it; it is an ablation candidate for another change.
- No token budget is enforced per level.
- The CLI's `/think N`, `/think-max` and `/nothink` keep their syntax.

## Capabilities

### New Capabilities
- `reasoning-effort`: how a request's thinking controls (effort names, numeric levels, thinking switches, model aliases) become V4.1's thinking mode, the effort line in the prompt, and the level reported to the session.

### Modified Capabilities
- `directional-steering`: "Closure onset schedule" reads the prompt's effort level. Named `high` and `max` become known levels (75 and 100) instead of "unknown, counts as 75".

## Impact

- **Code:**
  - `ds4_server.c`: `parse_reasoning_effort_name` and its tests. This function is upstream code, so it becomes one small conflict site, with an `sf:` marker, replayed by rerere.
  - `ds4.c`: the level helper, used by `ds4_deepseek41_reasoning_effort_text`.
  - `ds4.h`: the helper's declaration.
  - `ds4_cli.c`: the `set_think_level` call sites.
- **Docs:** `docs/CLIENTS.md`.
- **Behaviour:** this is a deliberate prompt change for `minimal`, `low`, `medium` and `xhigh` requests. `none`, `high`, `max` and numeric requests render byte-identical prompts. No speed claim. The parity oracle, which uses CLI defaults, is unaffected.
- **Order:** first of `610`-`650`. It has no dependency, and `640`'s acceptance test, which compares a server request with the CLI, relies on both sides deriving the steering level the same way.
- **Upstream registry:** no line of `docs/upstream-prs.md` covers effort mapping. Nothing to update.
