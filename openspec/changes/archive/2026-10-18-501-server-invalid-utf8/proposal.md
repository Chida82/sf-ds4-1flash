# Proposal

## Why

On 2026-10-17 the server answered a non-streaming `/v1/chat/completions` request
with a body that is not valid UTF-8: byte `0xE2` at offset 563 followed by a byte
that is not a continuation byte. The configuration was `msuiche@5` +
`abliteration-attn@6`, with the 409 gate (`v41-floor-resist`, tau -0.03447,
layer 10). It was the first prompt of the 32-hard set, the generation ended with
`finish=stop` after 772 tokens, and Python's `json.loads` raised
`UnicodeDecodeError` (409 gate screen, `server_v41-msuiche@5~7d2765.log`).

The CLI showed the same symptom the same day, on idx 6 under the 4b
configuration (`msuiche L1-8 @5` + `abl L9-39 @6`): its stdout was not UTF-8.

JSON (RFC 8259) must be UTF-8, so a strict client fails on the whole response,
not on one character. The harness now decodes with `errors="replace"`
(`eval/common.py`, `eval/scale_sweep.py`) so the steering screens can go on, but
that hides the defect rather than fixing it.

The cause is visible in the source:
- `json_escape` and `json_escape_fragment_n` (`ds4_server.c`) copy every byte
  at or above 0x20 verbatim.
- `ds4_token_text` returns the raw byte-level BPE bytes of a token, and the
  vocabulary holds tokens that are partial UTF-8 sequences.
- Any token sequence the model emits that does not form valid UTF-8 therefore
  reaches the wire unchanged. Steering makes such sequences likelier, but
  nothing in the path is steering-specific.
- A non-streaming answer cut by `max_tokens` in the middle of a multi-byte
  character has the same effect: the stream-safe hold (`utf8_stream_safe_len`)
  passes everything through when `final` is true.

Upstream's `json_escape` is the same, so no sync will bring a fix.

## What Changes

- **Reproduce first.** These steps come before any code change:
  - a model-less unit test that feeds the JSON escaper invalid and incomplete
    sequences, and fails on today's tree;
  - the observed server case rerun from its exact configuration, with the
    invalid offsets recorded;
  - an unsteered case: a `max_tokens` cut inside a multi-byte character;
  - the CLI case rerun to stdout bytes.

  Prompts are named by dataset index only; no text is printed or stored.
- **Classify the cause.** The server's existing `--trace FILE` writes each
  generated token's raw bytes (`trace_piece`). Comparing those bytes with the
  response body separates two causes:
  - the model emitted an invalid byte sequence;
  - server text handling (stop strings, reasoning split, DSML/tool parsing)
    cut a valid sequence.
- **Fix at the one place every response passes.** The JSON escapers replace
  each maximal invalid subpart with U+FFFD:
  - valid UTF-8 is copied byte for byte, as today;
  - every response kind, streaming and not, is covered at once (chat, text
    completion, responses, reasoning, tool arguments);
  - if the trace shows the server cutting a valid sequence, that cut is fixed
    at its own site as well.
- **Make it visible.** When a response needed a replacement, the server logs
  one stderr line with the request, the number of replaced subparts and the
  first byte offset. The harness warns when it had to replace bytes, so screens
  record the event instead of hiding it.
- **CLI unchanged.** The CLI keeps writing the raw token bytes (it is a
  byte-faithful view). Its behaviour is documented.

## Capabilities

### New Capabilities
- `server-text-encoding`: the server's responses are always valid UTF-8 JSON.
  - How invalid or incomplete model byte sequences are replaced, streaming and
    not.
  - That valid text is passed through unchanged.
  - The diagnostics that report a replacement.

### Modified Capabilities
None.

## Impact

- `ds4_server.c`:
  - `json_escape` and `json_escape_fragment_n`, one shared validator;
  - the final-response and stream paths only for the log line;
  - server unit tests (`./ds4_test --server`).
- No new flag or environment variable: the investigation uses `--trace`.
- `eval/scale_sweep.py` and `eval/common.py`: a warning when a response needed
  replacement (decoding stays tolerant).
- `docs/`: a note on the CLI's raw bytes and the server's replacement.
- Output:
  - greedy tokens are unchanged;
  - JSON bytes are unchanged for every response that is valid UTF-8 today,
    which includes every existing test;
  - only responses that are invalid today change, from invalid bytes to
    U+FFFD.
- A client that sends a replaced answer back gets a KV prefix miss from that
  character on, the same miss a client that replaced it itself already gets
  today.
- No performance claim. The validator runs once per escaped byte, on text, not
  on the decode path, so no A/B is needed. Parity stays token-identical.
