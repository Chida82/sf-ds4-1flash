# Design

## Context

- **Renderer.** `render_chat_prompt_text_for_syntax` sends `SERVER_MODEL_SYNTAX_DEEPSEEK41` to `render_deepseek41_chat` → `render_deepseek41_chat_ordered` (`ds4_server.c`). It builds one buffer.
  - **The template writes:**
    - BOS, or EOS at a live tail;
    - `<｜System｜>`, then the tools block of `append_tools_prompt_text`. That block contains the literal DSML `calls`/`invoke`/`parameter` tags and the sentence "Finish reasoning with </think>";
    - `\n\n` separators;
    - `<｜User｜>`, `<tool_result>…</tool_result>`, `<｜Assistant｜>`, `<think>`, `</think>`;
    - the DSML call tags of `append_dsml_tool_calls_text`;
    - EOS after each assistant turn.
  - **Content, written raw with `buf_puts`:**
    - system, user and tool content (`append_tool_result_text`);
    - the assistant's `reasoning` and `content`;
    - tool names and argument values.
  - **`calls->raw_tool_text`.** When it is set, the renderer writes it verbatim in place of the rebuilt DSML. It holds the model's own generated tool block (`parse_deepseek_generated_message_ex`), or a stored canonical form.
  - **Existing escaping** covers only wrapper closers: `ds4_tool_text_needs_escape` for `</tool_result>`, and `</｜DSML｜ parameter>` in parameters. JSON-literal and attribute escaping is DSML-local.
- **Tokenizer.** `ds4_tokenize_rendered_chat` → `tokenize_rendered_chat_vocab` (`ds4.c`) walks every byte. At each one it tries `special_token_at`, a fixed list of 25 marker strings, with `｜DSML｜` matched as a bare substring. The text between two matches becomes one span, and `tokenize_span` encodes it with `bpe_tokenize_text` as one block (the JoyAI pre-tokenizer splits it inside).
- **Callers of that tokenizer.**

  | Site | Input | This change |
  |---|---|---|
  | `request_tokenize_multimodal_prompt` (3 calls: whole prompt, or the pieces between image markers) | rendered request | ranges |
  | `parse_completion_request` (`/completions`, prompt wrapped as a user message) | rendered request | ranges |
  | `build_live_prompt_suffix` (2 calls) | slices of the rendered request | ranges |
  | `canonicalize_tool_checkpoint` | a fresh render | ranges |
  | `ds4_kvstore_build_prompt_from_exact_prefix_and_text_suffix` (`ds4_kvstore.c`) | the request text after the cached prefix | ranges |
  | `build_prompt` (`ds4_cli.c`, when `is_rendered_chat_prompt`) | a pre-rendered chat, on purpose | unchanged |
  | `ds4_distributed.c` (`dist_prompt_is_rendered_chat`) | the same | unchanged |
  | `ds4_dump_text_tokenization`, `tests/ds4_test.c` (`test_long_story_fact_recall`), `tests/test_deepseek41_graph.c`, `tests/test_session_state.c` | fixtures and tools | unchanged |

- **Eval and steering** run the CLI with a plain `-p` prompt (`eval/generate.py` → `common.build_cli`). That path is `ds4_encode_chat_prompt`, which pushes BOS, role and think ids directly and BPE-encodes system and prompt text with no marker scan. It is not touched. The only exception is a prompt that itself starts with a chat marker, which the CLI treats as pre-rendered. No eval set does that today; the identity task checks it.
- **Disk KV cache** (`ds4_kvstore.c`).
  - **Lookup.** `ds4_kvstore_find_text_prefix` keys an entry by the SHA-1 of its text prefix. `ds4_kvstore_try_load_text` re-hashes and byte-checks the match.
  - **Prompt rebuild.** The exact token history comes from the payload. The request text after it is tokenized with the rendered-chat tokenizer.
  - **Header.** It is 48 bytes; byte 20 is `KV_CACHE_PAYLOAD_ABI = 2`.
  - **ABI mismatch.** `ds4_kvstore_read_header` returns false. `kv_cache_refresh` then leaves the file out of the index without deleting it, and `kv_cache_existing_compatible` returns before its `unlink` branch.
- **Output side** (investigated, item 6 of the request). Generation stops are detected by token id (`vocab_token_is_generation_stop`, `ds4_token_is_stop_for_think_mode`). Everything else matches strings on decoded text:
  - `thinking_state_feed` (`<think>`, `</think>`);
  - `split_reasoning_content` (`strstr(body, "</think>")`);
  - the DSML trackers (`dsml_decode_tracker_update`, `parse_deepseek_generated_message_ex`), which also decide `greedy_tool_syntax`;
  - client stop strings.

  `thinking_state_from_prompt` runs the same tracker over the whole rendered prompt to find the starting state.
- **Upstream** has the same scan. No sync will bring a fix.

## Goals / Non-Goals

**Goals:**
- Content is never promoted to a control token in a server prompt.
- Byte-identical rendered text, and identical tokens for every prompt whose content holds no marker string, proven on a corpus before the server switches.
- One rule for the request path and the disk KV cache.

**Non-Goals:**
- The CLI's and the distributed worker's pre-rendered input.
- Recognizing control markers in generated output by token id. The evidence is recorded below; the fix is `520-server-output-markers-by-token-id`.
- Parallel segment encoding (DeepInfer's second idea). It is a speed idea, and this change makes no speed claim.
- Rewording the tools prompt, whose instruction text contains `</think>` and DSML tags that are encoded as control tokens today. Changing it would change every tool request's tokens. It is left as it is.

## Decisions

### D1. Content ranges beside the rendered string
- **The mechanism.** The renderer appends to a small list of `[begin, end)` byte ranges each time it writes content: every `buf_puts` of message text, tool-result text, reasoning, tool names and argument values. The new tokenizer entry takes the text, the ranges and the text's offset within the rendered prompt. A marker is recognized only when its whole byte range lies outside every content range. Everything else is unchanged:
  - the walk;
  - the spans between recognized markers;
  - `tokenize_span` and its BPE block per span.
- **Why the tokens of benign prompts cannot change.** With no marker string inside content, the set of recognized markers is the set the old scan found. The spans are therefore the same byte strings, and BPE on the same strings gives the same tokens. Template and content keep sharing a BPE block exactly as today, for example `\n\n` followed by the first word of a user message.
- **Offsets.** Ranges are kept in the coordinates of `r->prompt_text` and stored on the request. The multimodal pieces, the live suffix and the disk-cache suffix are slices of that text at a known offset, so they pass the offset rather than re-rendering.
- **`raw_tool_text`.** It is the model's own generated DSML, written back verbatim, and it stays template: its tags remain control tokens, as today. A client can put any text there by sending an assistant turn with tool calls, but a client that writes the assistant history can already put anything in it. The case this change closes is third-party text: tool results, files and user content.
- **Alternatives rejected.**
  - **The renderer emits a token vector directly.** Encoding template pieces and content separately splits BPE blocks at every boundary, so benign prompts change tokens: what DeepInfer can afford with its own recipe, but not this child's output rule. Concatenating text pieces until the next marker would avoid that, but it is the same ranges mechanism with a much larger renderer rewrite.
  - **Escaping markers in content**, by inserting a character or substituting look-alikes. The rendered text changes, which breaks the byte-identity of the server tests and the disk cache's text keys, and the model reads altered text.

### D2. Which renderer gets ranges
- The V4.1 renderer is the one the server reaches.
- The V4 renderer (`render_deepseek_chat_prompt_text`, `SERVER_MODEL_SYNTAX_DEEPSEEK`) is reached through `render_chat_prompt_text`, which is marked `DS4_SERVER_MAYBE_UNUSED`; `test_render_think_max_prompt_prefix` uses it. Task 2.1 proves whether any server path still selects it (rule 15: reachability, not names):
  - **reached:** it gets ranges too;
  - **unreached:** it is left alone, and the finding goes into `AGENTS.md`'s "Names that lie" if it is surprising.
- **Answer (task 2.1, 2026-10-28): unreached at run time.** `request_init` sets `SERVER_MODEL_SYNTAX_DEEPSEEK` as a default, but each of its four production callers (`parse_chat_request`, `parse_anthropic_request`, `parse_responses_request`, `parse_completion_request`) overwrites it on the next line with `server_model_syntax_for_engine`, which returns `SERVER_MODEL_SYNTAX_DEEPSEEK41` unconditionally. The fallbacks `r ? r->model_syntax : SERVER_MODEL_SYNTAX_DEEPSEEK` in `build_tool_checkpoint_suffix` and `build_responses_visible_assistant_suffix` never see a null request in production (`&j->req`). `render_chat_prompt_text`, the only direct caller with the V4 value, is `DS4_SERVER_MAYBE_UNUSED` and called only from `DS4_SERVER_TEST` code. `nm ds4_server.o` shows no `render_deepseek_chat_prompt_text` symbol; that is not proof on its own (it can be inlined into `render_chat_prompt_text_for_syntax`), so the constant return is the evidence. The V4 renderer is left alone; not surprising enough for "Names that lie".

### D3. The starting reasoning state
`thinking_state_from_prompt` feeds the whole rendered prompt to the reasoning tracker. A user message that contains `<think>` can therefore make the server start a response believing it is inside reasoning. The ranges are already at hand, so the function skips content ranges too.

Correction after task 4.2: a user message cannot do it, because every request render ends with the template's `<think>` or `</think>`, which decides the state. Content can only decide it when the prompt ends in an assistant turn, where no template tag follows; that is the case the change fixes and tests.

This is input-side and uses the same data, so it belongs here. Output-side string matching does not, because it needs generated token ids, not ranges.

### D4. Disk KV cache: invalidate by ABI
- **The problem.** An entry written before this change stores the token history computed by the old scan. When a later request extends the same conversation, the text-prefix hit restores those tokens. If the cached content spelled a marker, the injected control tokens would survive the fix for as long as the entry lives. That is likely in agent work, which extends conversations by appending.
- **The fix.** `KV_CACHE_PAYLOAD_ABI` goes from 2 to 3. Old entries are skipped by `ds4_kvstore_read_header` and the cache starts cold once.
- **Old files.** They are not deleted, because the store does not delete files with another ABI today, and deleting files under a user's directory without being asked is not this change's call. `docs/SERVER.md` says the old entries can be removed by hand.
- **Alternatives rejected.**
  - **Re-tokenizing the cached prefix on every hit and comparing.** BPE boundaries at the cut can differ legitimately, which is why the store keeps exact prefix tokens in the first place, so a mismatch does not prove injection.
  - **Keeping old entries.** Benign entries would be fine, but the injected ones are exactly the ones agents re-hit.

### D5. No runtime switch back
- **How the old behavior stays reachable.** The old function stays: the CLI, the distributed worker and the tests use it. The identity test calls both paths directly, so comparisons need no environment variable.
- **Why no switch.** A server switch to restore the scan would keep an injection path that is selectable at run time, plus a second code path to maintain. If the owner wants one for debugging, it is a `disable` line in `ds4_env.def` and one branch at the tokenizer call.

### D6. Tests, in this order
1. **Reproduction**, which must fail on today's tree.
   - A rendered chat whose tool result spells `<｜User｜>`, `</think>`, `<｜end▁of▁sentence｜>` and the DSML opening tag.
   - The test asserts that no control-token id comes from content bytes.
   - It uses the test vocabulary that `tests/test_session_state.c` already builds, if that covers the markers. Otherwise it uses the GGUF's vocabulary through `vocab_load`, which reads the header only: no weights, no Metal.
2. **Identity on the corpus.** The old path against the new on:
   - the parity prompts rendered as single-user chats;
   - every server unit-test chat fixture (tool calls, tool results, history with reasoning, live tail, `/completions` wrapping);
   - a multimodal request (pieces between image markers);
   - the canonical tool checkpoint render.

   Tokens must be identical on every item whose content holds no marker string. Items that do hold one are listed with their expected difference.
3. **Adversarial expectations.**
   - Each marker of the list in user, system, tool, reasoning, assistant content and argument values: no control token from content, and the literal's ordinary tokens.
   - The two long-context fixture files used as one tool result each. They are dense with markers (the security file has 27 `｜DSML｜`).
4. **The disk cache.** A conversation with a marker in a tool result is stored, then extended. The rebuilt prompt must equal a cold request's tokens. A file written with ABI 2 is not loaded.
5. **The existing suites.** `make test` (server unit tests included), and `ds4_test`'s model-backed `test_long_story_fact_recall`, which takes the CLI path and must be unchanged. Parity runs through the CLI, so it is unaffected by construction; it runs anyway as the final gate.

## Risks / Trade-offs

- **[A content write is missed in the renderer]** → That content keeps today's behavior. The adversarial test writes every marker into every content kind the renderer handles. A new content kind added later needs its own case, which the test file's header says.
- **[A marker straddles a range boundary]** → The rule is "wholly outside", so a marker that starts in content and ends in template text is not recognized. The template always writes whole markers, so this only affects content.
- **[BPE merges produce a marker id from ordinary text]** → Not checked by reading. The adversarial test asserts that no marker id appears inside a content span's tokens.
- **[The cold disk cache costs one prefill per cached conversation]** → It happens once. The owner chooses when to update.
- **[The invalid-DSML recovery suffix keeps the old scan]** (found in task 4.3) → `build_invalid_dsml_tool_error_suffix` writes a server-made tool result after a malformed tool call: the parser's detail, then a reminder that copies the rendered system region of `prompt_text`, tools prompt included. `append_rendered_suffix_to_live_session` tokenizes it with no ranges. Marking the whole result as content would turn the tools prompt's template markers into text and change tokens on benign requests, against the output rule. Marking only the copied system content and the detail needs the source ranges carried into the copy; it is left for a follow-up. Exposure: the client's own system text and parser detail on a recovery path, not third-party content.
- **[Output-side spoofing remains]** → A model that writes `</think>` with ordinary tokens still ends reasoning in the server's split, and a DSML spelling still starts the tool tracker. Recorded here; `520-server-output-markers-by-token-id` moves those checks to token ids, as DeepInfer does.
