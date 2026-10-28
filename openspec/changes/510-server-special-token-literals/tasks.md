# Tasks

Work happens on a branch in a worktree, never on main. No commit or push without a request.

## 1. Reproduce

- [ ] 1.1 Add the reproduction test (design D6.1) to the server unit tests. It renders a V4.1 chat whose tool result spells `<｜User｜>`, `</think>`, `<｜end▁of▁sentence｜>` and the DSML opening tag, then asserts that no control-token id comes from content bytes. Verify it fails on today's tree with the ids it found, and that `make test` names it.

## 2. Ranges and the tokenizer entry

- [ ] 2.1 Reachability of the V4 renderer (D2): find every path that selects `SERVER_MODEL_SYNTAX_DEEPSEEK` at runtime. Verify by `nm` or a runtime probe, and record the answer in this change's design before 2.2.
- [ ] 2.2 The V4.1 renderer and its helpers record content ranges (D1): message text, tool results, reasoning, assistant content, tool names and argument values. `raw_tool_text` stays template. Verify the rendered string is byte-identical on every server unit-test fixture.
- [ ] 2.3 A ranges-aware tokenizer entry in `ds4.c`/`ds4.h` beside `ds4_tokenize_rendered_chat`, which stays. Verify `make test` and `make cpu`.

## 3. Identity proof (before switching the server)

- [ ] 3.1 The identity test (D6.2): old against new path on the parity prompts rendered as chats, every server chat fixture, `/completions`, a multimodal request, the live suffix and the canonical tool checkpoint. Verify identical tokens on every marker-free item, and print the count of items compared.
- [ ] 3.2 The adversarial cases (D6.3), including both long-context fixtures as tool results. Verify the expected differences, and that no marker id appears inside a content span's tokens.

## 4. Switch the server

- [ ] 4.1 Pass ranges at the seven server call sites (request, multimodal pieces, `/completions`, live suffix, tool checkpoint). Verify 1.1 now passes and 3.1 still passes through the real call sites.
- [ ] 4.2 `thinking_state_from_prompt` skips content ranges (D3). Verify that a user message containing `<think>` no longer starts the response inside reasoning.
- [ ] 4.3 Disk KV cache (D4): the text-suffix tokenization takes the ranges at its offset, and `KV_CACHE_PAYLOAD_ABI` goes to 3. Verify D6.4: the extended conversation's rebuilt prompt equals a cold request's tokens, and an ABI 2 file is not loaded.

## 5. Verification and docs

- [ ] 5.1 `make test` (read the names of the tests that ran), `DS4_TEST_MODEL=... DS4_TEST_SSD_STREAMING=1 ./ds4_test` for `test_long_story_fact_recall`, a greedy server request without markers before and after (identical tokens and body), and `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` from the StarForge checkout. Verify every one passes bitwise.
- [ ] 5.2 `docs/SERVER.md`: content is literal text; the disk cache starts cold once after this change, and old files can be deleted. Verify there is no doc line saying content markers act as control tokens.
- [ ] 5.3 Check that `520-server-output-markers-by-token-id` still matches this change's output-side findings (design, Context and Risks). `openspec validate 510-server-special-token-literals --strict`.
