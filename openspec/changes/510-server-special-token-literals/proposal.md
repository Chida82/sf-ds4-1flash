# Proposal

## Why

The server turns text inside messages into control tokens. `render_deepseek41_chat_ordered` (`ds4_server.c`) builds one string from the chat template and the raw content of every message:
- system and user content;
- tool results, through `append_tool_result_text`;
- the assistant's reasoning and content;
- tool-call arguments.

`ds4_tokenize_rendered_chat` (`ds4.c`) then scans that whole string with `special_token_at`, a fixed list of 25 marker strings, and maps every match to its control token. Content that spells `<｜User｜>`, `<｜Assistant｜>`, `<｜System｜>`, `<think>`, `</think>`, `｜DSML｜` or `<｜end▁of▁sentence｜>` therefore becomes a turn boundary, a reasoning boundary or a tool call. The only existing escaping protects wrapper closers (`</tool_result>`, `</｜DSML｜ parameter>`), not the chat markers.

In local use this happens without any attacker: an agent that reads this repository's own sources, docs or test prompts gets them back as tool results, and those files contain the markers. The model then sees forged turns and forged reasoning ends in its context.

The defect was found by reading the code and has not been run yet. The first task reproduces it.

DeepInfer (`doc/inference_deployment_qa.md`, "tokenization") avoids it this way:
- it records the special tokens the prompt builder inserts, and their positions;
- it encodes everything else with the base vocabulary, so a marker spelled in content stays ordinary text.

## What Changes

- **Reproduce first.** A tokenizer-level test renders a chat whose tool result contains `<｜User｜>` and `</think>`, and shows today's control tokens in the prompt. Model-less where the test vocabulary allows; otherwise it reads only the GGUF's vocabulary.
- **Content is literal text.** The renderer records, beside the string it builds, the byte ranges that came from message content. The rendered-chat tokenizer recognizes a marker only when its bytes lie wholly outside those ranges.
  - The rendered string stays byte for byte what it is today.
  - Text between two real markers is still encoded as one BPE block, exactly as today.

  As a result, a prompt whose content holds no marker string tokenizes to the same tokens as today.
- **Template markers stay markers.** The template itself emits some markers, and those stay control tokens:
  - BOS and EOS;
  - the role tags;
  - `<think>` and `</think>`;
  - the DSML tags of tool calls in the history;
  - the markers inside the tools prompt.

  Tool-call names and argument values are content.
- **Every server tokenization site** takes the ranges:
  - the chat and multimodal requests;
  - `/completions`, which wraps its prompt as a user message;
  - the live prompt suffix;
  - the tool checkpoint canonicalization;
  - the disk KV cache's text suffix (`ds4_kvstore_build_prompt_from_exact_prefix_and_text_suffix`).
- **Disk KV cache.** Lookup stays by text, and the rendered text does not change. Entries written before this change may hold control tokens taken from content. They are invalidated by raising `KV_CACHE_PAYLOAD_ABI` (header byte 20) from 2 to 3. Today a file with another ABI is skipped by the index, not deleted.
- **Pre-rendered input is unchanged.** The CLI (`build_prompt` when `is_rendered_chat_prompt` sees a rendered prompt) and the distributed worker keep the full scan, because they receive rendered chats on purpose. The tests built on that behavior (`tests/long_context_story_prompt.txt` through `test_long_story_fact_recall`) are not touched.
- **Identity proof before the switch.** A test tokenizes a corpus with the old and the new path and requires identical tokens whenever content holds no marker string. The corpus:
  - the parity prompts rendered as chats;
  - the server's tool-call, history and reasoning fixtures;
  - the `/completions` wrapper;
  - multimodal and live-tail prompts.

  Adversarial cases show the expected, documented difference.
- **Output side, investigated only.** The server finds `</think>`, DSML and tool calls in generated output by matching strings on decoded text. The design records the evidence; the fix is `520-server-output-markers-by-token-id`.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `server-text-encoding`: the spec covers the prompt direction as well:
  - message content is encoded as literal text;
  - template markers stay control tokens;
  - prompts without marker strings in content keep their tokens;
  - the disk KV cache follows the same rule.

## Impact

- **`ds4_server.c`:**
  - the DeepSeek V4.1 renderer and its helpers record content ranges;
  - the seven tokenization call sites pass them;
  - server unit tests.
- **`ds4.c` / `ds4.h`:** a ranges-aware entry point beside `ds4_tokenize_rendered_chat`. The old function stays for the CLI, the distributed worker and the tests.
- **`ds4_kvstore.c`:**
  - the text-suffix tokenization takes the ranges;
  - `KV_CACHE_PAYLOAD_ABI` goes from 2 to 3, so the disk cache starts cold once.
- **Not affected.** Eval and steering runs go through the CLI with a plain prompt, and so through `ds4_encode_chat_prompt`, which never scans content for markers. Their tokens and every recorded steering score stay valid.
- **Output.** Greedy tokens are unchanged for every prompt whose content holds no marker string:
  - parity (CLI) is unaffected by construction;
  - `ds4_test` and the server tests stay identical.

  Only prompts whose content spells a marker change, from a control token to the marker's ordinary tokens.
- **No performance claim and no A/B.** The range check is one comparison per scanned position, on the request path, not the decode path.
- **`docs/SERVER.md`:** one paragraph on literal content.
