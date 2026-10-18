# Design

## Context

See proposal.md, Why. The relevant code paths:

- **Token bytes.** `ds4_token_text` (`ds4.c`) maps a token's GPT-2 byte-level
  code points back to raw bytes. A token can carry part of a multi-byte
  character, so the bytes of a token sequence are valid UTF-8 only if the model
  completes every character it starts.
- **Generation loop.** The server's loop (`ds4_server.c`, about line 12849)
  appends each piece to `text`, feeds the thinking/DSML trackers, and writes
  the piece raw to the `--trace` file (`trace_piece`). Stop strings, KV prefix
  matching and tool parsing all work on these raw bytes.
- **Escapers.** Every client-visible string is serialized by `json_escape`
  (96 call sites, plus 16 through `json_escape_n`) or `json_escape_fragment_n`
  (3, stream fragments). Both copy every byte at or above 0x20 unchanged.
- **Stream hold.** `utf8_stream_safe_len` holds an incomplete trailing
  character between stream deltas. It releases everything when `final` is true.
- **CLI.** It writes the raw pieces to stdout (`print_generated_token`).
- **Harness.** `eval/common.execute` and `eval/scale_sweep._post` decode with
  `errors="replace"` since 409; before that they raised.
- **Upstream.** `upstream/ds4` has the same escapers, unchanged.

The observed server case is the 32-hard set's first prompt, idx 6 in the
`B_v41-msuiche@5` order. Its 13-token prompt generated 772 tokens and stopped
on a stop token, so the invalid byte sits inside the answer, not at a
`max_tokens` cut. The CLI case is idx 6 under the 4b configuration. The CLI
writes token bytes verbatim, so an invalid sequence on its stdout can only come
from the tokens, which already points to the model as the source.

## Goals / Non-Goals

**Goals:**
- Reproduce three cases on demand, with the configuration recorded and without
  printing prompt text:
  - the observed steered server case;
  - an unsteered `max_tokens` cut;
  - the CLI case.
- Find out whether the invalid bytes come from the tokens or from the server's
  text handling, before the fix hides the evidence.
- Make every server response valid UTF-8, keeping valid text and greedy tokens
  byte-identical.

**Non-Goals:**
- Changing what the model generates, or steering's tendency to produce broken
  byte sequences. That belongs to the steering quality work (`420`).
- Constraining decoding to valid UTF-8 (masking tokens). It changes the
  generated tokens.
- Changing the CLI's raw output.
- Preserving byte-exact round trips of invalid text through clients. JSON cannot
  carry invalid bytes.

## Decisions

### D1. Reproduce with existing tools before writing the fix

- **Locating the bytes.** The harness decodes strictly first. If that fails, it
  prints one stderr warning with the first invalid byte offset, the number of
  invalid subparts and an 8-byte hex window, then falls back to `replace`. The
  warning lives in `scale_sweep._post` and `common.execute`; it has no text, so
  it is safe on harmful prompts. This turns every screen into a detector at no
  cost.
- **Steered server case.**
  `eval/hybrid_phaseb.py --configs v41-msuiche.f32@5+v41-abliteration-attn.f32@6
  --indices 6 --extra "<the 409 gate flags> --trace <scratchpad>/t6.trace"`.
  It is the same server path, flags and prompt order as the failing screen.
  Greedy runs are deterministic, so two runs must report the same offset.
- **Unsteered case.** The base server, a benign prompt that asks for an answer
  in a CJK script, and non-streaming `max_tokens` from 1 to 48. Every cut that
  ends inside a character gives an invalid tail today. The same prompt with
  `stream: true` shows that the last delta carries it too.
- **CLI case.** `eval/run.py` with the 4b configuration on idx 6
  (`--indices 6`). The warning in `common.execute` gives the offset.
- **Alternatives.** Each one was rejected:
  - A new server probe for token ids: `--trace` already writes every generated
    token's raw bytes, which is what the classification needs.
  - Saving raw response bodies to disk: the offset and hex window are enough,
    and a stored body would hold harmful text.

### D2. Classification rule

Scan the generated-output sections of the trace file for invalid subparts with
a strict decoder, and compare their hex windows with the response warning:
- **Same window in the trace:** the tokens produced it. The fix is D3 alone.
- **Trace valid but response invalid:** the server's text handling cut a valid
  sequence. That site gets its own fix and test in this change, on top of D3,
  and the task list grows by one group.

The trace holds the prompts, so it stays in the session scratchpad, is read
only by the scanning script (offsets and hex), and is deleted after.

### D3. Replace maximal invalid subparts in the escapers

- **Where.** One static validator walks the bytes and returns, at each
  position, either the length of a valid sequence or the length of a maximal
  invalid subpart. It follows the Unicode well-formed byte table: `C2..DF`,
  `E0 A0..BF`, `ED 80..9F`, `F0 90..BF`, `F4 80..8F` and so on. It is used in
  the `else` branch of `json_escape` and `json_escape_fragment_n`. A valid
  sequence is copied as is; an invalid subpart is written as `EF BF BD`.
  - ASCII stays on the existing fast branch.
  - The diff is one helper plus two branch edits, in code shared with
    upstream: a small, stable conflict site at syncs.
- **Why the escapers.**
  - They are the one place every client-visible string passes: chat,
    completion, responses, reasoning and tool arguments, streaming or not.
  - Fixing them once covers every caller.
  - The raw `text` buffer stays raw, so stop strings, KV prefix matching,
    DSML parsing and the trace keep seeing the model's bytes.
- **Alternatives rejected:**
  - Sanitizing `text` at token append: it changes what stop strings and the KV
    prefix see, and hides the evidence from the trace.
  - Dropping the bytes: it loses the signal that something was there.
  - Escaping each byte as `\u00XX`: that creates mojibake characters that were
    never generated.
  - Per-endpoint fixes: about 110 sites.
  - Masking tokens at sampling: it changes tokens (non-goal).
- **Streaming agreement.** The stream hold never ends a delta inside a
  sequence that could still complete. A stray continuation byte is its own
  maximal subpart. So replacing per delta gives the same characters as
  replacing the whole text. A unit test pins this with a sequence split across
  two pieces.
- **The `final` release.** The stream path with `final` true and the
  non-stream path then emit an incomplete tail as one U+FFFD instead of raw
  bytes.

### D4. One log line per affected response

At the existing per-request finish log, the server counts invalid subparts in
the generated text (the same validator, on the final `text`) and, when the
count is nonzero, logs:

    ds4-server: chat ctx=<span> replaced <n> invalid UTF-8 subparts (first at byte <k>)

The escapers stay context-free; counting once per request is cheap and does not
double count across deltas.

### D5. The CLI keeps raw bytes

The CLI is a byte-faithful view of the tokens; a terminal renders or replaces
as it likes. `docs/CLIENTS.md` gets one paragraph covering both behaviours:
- the CLI writes the raw token bytes;
- the server replaces invalid subparts with U+FFFD and logs it.

## Risks / Trade-offs

- **[Risk] A caller of `json_escape_fragment_n` passes a fragment that ends
  inside a valid character, which would now become U+FFFD.** → Mitigation:
  read every caller during the fix. The existing tests
  `test_streaming_holds_partial_utf8` and
  `test_openai_tool_stream_holds_partial_utf8_arguments` must keep passing
  unchanged. Add a case where a 4-byte character arrives split in a tool
  argument stream.
- **[Risk] Output bytes change for a case thought valid.** → Mitigation: the
  validator copies only well-formed sequences, so every existing server unit
  test and every stored phase-B completion that decodes strictly must
  serialize identically. Rerun one stored screen configuration on two indices
  and compare the bodies byte for byte. Parity stays token-identical.
- **[Trade-off] Prefix miss on the next turn.** A client that sends a replaced
  answer back re-tokenizes U+FFFD differently from the original tokens, so the
  KV prefix match ends there. Today such a client either fails to parse the
  response or replaces the bytes itself, with the same miss.
- **[Risk] The classification finds the server at fault.** → Mitigation: D2
  adds a site fix and test inside this change; D3 still lands, because tokens
  alone can produce invalid bytes (the CLI case and the `max_tokens` cut).
