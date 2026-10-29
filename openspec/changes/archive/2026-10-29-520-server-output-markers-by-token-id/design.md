# Design

## Context

- **The generation loop** (`ds4_server.c`, the decode loop of the chat job).
  - Each step samples a token. `ds4_token_is_stop_for_think_mode` tests it as a stop by id.
  - Otherwise the loop appends `ds4_token_text`'s bytes to `text` and writes them to `--trace` (bytes only, no id).
  - It then feeds two trackers:
    - `thinking_state_feed` is fed when not inside a tool call. It compares the last 8 bytes against `<think>` and `</think>`.
    - With tools, `dsml_decode_tracker_update` re-scans `text` from its position, using `dsml_find_tool_start_from` and `raw_full_lit`. When reasoning just closed, it starts after `find_last_substr(text, "</think>")`.
  - `greedy_tool_syntax` reads both trackers, so a text match changes sampling.
- **Stream encoders.** The Anthropic, OpenAI chat and Responses live updaters (`anthropic_sse_stream_update`, `openai_sse_stream_update`, `responses_sse_stream_update`) each find `<think>`/`</think>` with `strstr` on the raw text, holding back `strlen("</think>") - 1` bytes.
- **Final parse.** `split_reasoning_content` uses `strstr("</think>")`. `parse_deepseek_generated_message_ex` searches `DS41_TOOL_CALLS_START` and uses `find_tool_structural_text(..., "</think>")`. The tool-block parser uses `raw_full_lit(DS41_TOOL_CALLS_START)`.
- **Text with no token record.** The same parsers also read client-supplied assistant history. After `510`, that history's content is encoded as literal text in the prompt.
- **The prompt-side caller.** `thinking_state_from_prompt` also calls `thinking_state_feed`, on the rendered prompt text. Since `510` it feeds only the bytes outside content ranges. When the feed becomes a test on token ids, that caller can read `r->prompt`'s ids instead, which already carry the same decision.
- **Marker tokens.** The V4.1 vocabulary has control tokens for `<think>`, `</think>`, `｜DSML｜` and end of sentence. `special_token_at`'s list includes them, and `ds4_token_is_thinking_control` already tests the think pair by id.

## Goals / Non-Goals

**Goals:**
- Only emitted control tokens act as boundaries in generated output.
- Response bodies are byte-identical whenever the model emitted every marker as its control token.

**Non-Goals:**
- Client stop strings.
- Parsing client-supplied history.
- The prompt side (`510`).
- Changing sampling, except that a literal spelling no longer switches to greedy tool syntax.

## Decisions

### D1. Measure before switching
- **Recording.** `--trace` writes each piece's token id beside its bytes, which is a diagnostic-only format change. A scratch script then reads traces of real requests and counts every marker string in the output by origin: control token, or ordinary tokens. The requests:
  - the server unit-test tool fixtures replayed through a model;
  - the harness's tool-call prompts;
  - 20 reasoning requests;
  - 20 agent turns that read this repository's files.
- **The gate.** Every marker that delimits real reasoning or a real tool call must come from its control token.
  - If any does not, recognizing by id would break that response, so the change stops and the owner chooses.
  - The likely alternative then is to recognize the spelled DSML block only when it is a complete, well-formed tool block. That is a different design.

- **Measured (task 1.2, 2026-10-28).** 45 greedy requests on the 1017 checkpoint through this branch's server (`82GB`, `reasoning_effort` low): 20 reasoning questions, 20 agent turns whose tool result is a 6000-character slice of this repository's files (server, tokenizer, docs, the security fixture, these changes), 5 tool requests. The script counts marker strings in the traced output by origin and prints counts and offsets only.

  | Requests | `</think>` control / spelled | `<think>` | end of sentence | `｜DSML｜` |
  |---|---|---|---|---|
  | reasoning (20) | 19 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
  | agent turns (20) | 22 / 28 | 0 / 11 | 0 / 2 | 156 / 37 |
  | tool requests (5) | 5 / 0 | 0 / 0 | 0 / 0 | 32 / 0 |

  - **Gate: passed.** Every response that closed its reasoning did so with the control token, and every response with tool calls carried control `｜DSML｜` tokens. No genuine boundary arrived spelled.
  - **The defect is common in agent work.** 5 of the 20 agent turns spell `</think>` inside their reasoning before the real one (16 occurrences), which today's `strstr` takes as the end of reasoning. Two turns (the ones quoting DSML-heavy code) made today's tracker enter a tool-call block on spelled `｜DSML｜`; both ended as "invalid tool call returned as assistant text", one of them with no control `｜DSML｜` at all.

### D2. Offsets beside the text
- **What the loop records.** When a sampled token is one of the marker ids, the loop records `(text.len before the append, kind)`. The record lives on the job beside `text`, and the stream encoders and the final parse receive it with the text.
- **Why offsets.** The text stays the single buffer every parser reads, and its bytes do not change.
- **Rejected: rewriting the parsers on token arrays.** It would touch every parser's structure, while the defect is only in which matches they accept.

### D3. One helper for every marker search
- **The helper.** `find_marker(raw, len, from, marker, record)` returns the next occurrence of `marker` that starts at a recorded offset of the matching kind. With no record (history text), it behaves like the search it replaces.
- **The sites.** `thinking_state_feed` becomes a test on the token id itself, with no text tail. Every other site passes through the helper:
  - the `strstr` and `find_last_substr` calls on `</think>`/`<think>`;
  - the DSML start search;
  - `raw_full_lit` on the tool-calls tag.
- **What text matching still does.** A spelled marker stays in the text and is escaped as content. The DSML block parser still checks the block's inner text grammar as today, but only starting from a genuine start.

### D2-D3 as built: a masked view instead of an offset record (2026-10-28)
- **Why the change.** The trackers, the three encoders and the parsers read the generated text in about 160 places (`raw +`, `raw_full_lit`, `strstr`, `find_any_tool_start`, ...). Passing an offset record to each search would touch every one of them.
- **What is built.** The generation loop keeps, beside `text`, an `output_view`: the same bytes, except that a marker the model spelled with ordinary tokens has some bytes replaced by a Unicode noncharacter of the same length. `<th` of `<think>` becomes U+FDD0, `</t` of `</think>` U+FDD1, the two `｜` of `｜DSML｜` U+FDD2 and U+FDD3 (the trailing one also breaks the short form `DSML｜`). A spelling is masked when the piece that completes it arrives; marker tokens (`ds4_token_output_marker`) are kept and recorded, and a spelling that overlaps one is left alone. Offsets do not move, so every parser keeps its code and reads the view; only emitted markers can match.
- **Original bytes back.** `json_escape_bytes` writes each of the four noncharacters as the bytes it replaced, so every stream delta and response body carries the model's text. Strings parsed from the view (content, reasoning, tool names, arguments, `raw_tool_text`) are unmasked before they are stored or sent. Client stop strings, plain streaming and the trace keep reading `text`.
- **Reasoning state.** The decode loop sets it from the token id; `thinking_state_feed` keeps only its prompt-side caller.
- **Limits.** If the generated text itself contains one of the four noncharacters, the view turns off for that response and parsing is as before. A client string holding one of them would be echoed with the replaced bytes; Unicode reserves these code points for internal use.
- **The grep of D3** therefore reads differently: the marker searches stay, and each one reads either the view (generated output) or client history text (no record, as before).

### D4. Tests
- **Model-less.** The trackers and encoders driven by synthetic text plus a record, in which `</think>` and the DSML tag appear once recorded and once literal:
  - reasoning, content and tool calls are assigned by the recorded ones only;
  - streaming deltas concatenate to the non-streamed body (the invariant of `server-text-encoding`).
- **Model-backed.**
  - The `501`-style before/after check on greedy requests with reasoning and tool calls: identical tokens and bodies.
  - One request designed to make the model quote `</think>` inside reasoning, to check the literal path end to end.

## Risks / Trade-offs

- **[The model sometimes spells a genuine marker with ordinary tokens]** → D1's gate. Measured before anything switches.
- **[A site is missed]** → It keeps today's behavior. A grep for the marker literals in runtime code (outside templates and tests) is part of the final review, and every hit must be a template write or go through the helper.
- **[History parsing diverges from generated parsing]** → Intended. History has no ids, and `510` already makes its content literal in the prompt.
