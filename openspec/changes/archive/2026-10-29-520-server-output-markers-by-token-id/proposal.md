# Proposal

## Why

`510` stops prompt content from becoming control tokens. The output side has the mirror defect. The server decides where reasoning ends and where a tool call starts by searching the decoded text for marker strings, not by looking at the token ids the model emitted. When the model writes the characters of `</think>` or `<｜DSML｜ calls>` with ordinary tokens, the server acts as if it had emitted the control token: it quotes them, explains them, or copies them from a file it was given. The marker can then:
- end reasoning early, so reasoning text leaks into the answer;
- open a tool call the model never made;
- switch sampling to greedy tool syntax (`greedy_tool_syntax`).

The pieces involved:
- **Reasoning state.** `thinking_state_feed` matches `<think>`/`</think>` on the tail of the decoded text.
- **The final split.** `split_reasoning_content` and the generated-message parser (`parse_deepseek_generated_message_ex`) use `strstr`.
- **The DSML tracker.** `dsml_decode_tracker_update` and `dsml_find_tool_start_from` work on text.
- **The three live stream encoders** (Anthropic, OpenAI chat, Responses) search the raw text for `</think>` again.
- **What is already by token id:** generation stops, through `ds4_token_is_stop_for_think_mode`.

This is most likely in the same agent work `510` describes, where the model discusses or edits files that contain these markers. DeepInfer recognizes `</think>` and `｜DSML｜` "by token ID", so that "the same text spelled out by the model using ordinary tokens is correctly preserved as literal content" (`doc/inference_deployment_qa.md`).

## What Changes

- **Measure first.** Before any switch, the generation loop records which byte ranges of the generated text came from marker token ids. A measurement on real reasoning and tool-call requests answers whether every genuine marker arrives as its control token. If some genuine tool call or reasoning end arrives spelled with ordinary tokens, recognizing by id would break it, and the change stops and asks the owner.
- **Marker offsets.** The generation loop keeps, beside the generated text, the byte offsets where a marker token id was emitted: think open and close, the DSML marker, end of sentence.
- **One helper for every output parser.** The trackers, the final split, the tool parser and the stream encoders accept a marker occurrence only at a recorded offset. Any other spelling is literal text, and it reaches the client as text in whatever field it falls in: reasoning, content or a tool argument.
- **Unchanged.**
  - Client stop strings, which are text by definition.
  - Parsing text that has no token record: client-supplied assistant history, which `510` already encodes as literal content.
  - The bytes of the generated text.
- **Tests.**
  - A model-less test drives the trackers with a token-id record in which `</think>` and the DSML tag appear once as ids and once as plain text. Only the ids may act.
  - A model-backed check confirms that ordinary greedy requests with reasoning and tool calls give identical response bodies before and after.

## Capabilities

### New Capabilities
- `server-output-markers`: how the server recognizes reasoning and tool-call boundaries in generated output, by the token ids the model emitted, with literal spellings kept as text.

### Modified Capabilities
None.

## Impact

- **`ds4_server.c`:**
  - the generation loop records marker offsets;
  - the thinking tracker, `split_reasoning_content`, the generated-message parser, `dsml_decode_tracker_update`/`dsml_find_tool_start_from`, and the three stream encoders search through the helper;
  - server unit tests.
- **`ds4.c`/`ds4.h`:** a small query for the marker token ids, beside `ds4_token_is_thinking_control`.
- **`--trace`** also writes the token id next to each piece. The measurement needs it.
- **Output.**
  - Greedy tokens never change: this is response parsing, not sampling, except that `greedy_tool_syntax` no longer fires on a literal spelling.
  - Response bodies are identical whenever every marker in the output came from its token id, which the measurement must show is the normal case.
- **No performance claim.** The work is one offset check per marker candidate, on text, outside the decode path.
