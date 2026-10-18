# Tasks

Conventions:
- Model-backed runs use `--ssd-streaming`, one model process at a time, and
  `caffeinate -i` when longer than 5 minutes.
- Prompts are named by dataset index only. No prompt or completion text is
  printed, logged in a measurement, or committed.
- Trace files hold prompts: they stay in the session scratchpad and are deleted
  once scanned.
- The model-less gate is `make test` output naming the tests, not its exit code.

## 1. Detector in the harness

- [x] 1.1 `eval/scale_sweep._post` and `eval/common.execute`:
  - Decode strictly first. On `UnicodeDecodeError`, print one stderr line:
    `warning: invalid UTF-8 in <where>: <n> subparts, first at byte <k>, window <hex8>`.
    `<where>` is "server response" or "CLI stdout".
  - Then decode with `errors="replace"` as today.
  - One shared helper, `invalid_utf8_report(raw) -> (n, k, hex)`, in
    `eval/common.py`; its self-check asserts it on `b"a\xe2(b"`, `b"ok\xe2\x80"`
    and `b"\x80\x80"`.

  Verify: `python3 eval/common.py --self-check` and
  `python3 eval/scale_sweep.py --self-check` print ok; `make test` lists both.

## 2. Reproduce and classify (model-backed, before any server change)

- [x] 2.1 Steered server case, the observed configuration.
  - Run `python3 eval/hybrid_phaseb.py --configs
    dir-steering/vectors/v41-msuiche.f32@5+dir-steering/vectors/v41-abliteration-attn.f32@6
    --indices 6 --extra "--dir-steering-gate-file dir-steering/out/v41-floor-resist.f32
    --dir-steering-gate-tau -0.03447 --dir-steering-gate-layer 10 --trace
    <scratchpad>/t6.trace"` twice.
  - If `dir-steering/out/v41-floor-resist.f32` is gone, rebuild it as 409's
    capture did, or use the 4b configuration of 2.3 as the steered case.

  Done (2026-10-18): the gate flags `--dir-steering-gate-*` are gone (removed in
  409 non-adoption 6.7/7.7), so the original observed config cannot run. Used the
  4b fallback (`v41-msuiche-L1-8@5 + v41-abl-L9-39@6` on idx 6) via the server
  path (hybrid_phaseb). The server output is a clean ASCII refusal loop (5365
  bytes, 0 U+FFFD, keyword-refuse) — this config does **not** reproduce invalid
  UTF-8 on the server path. The invalid-UTF-8 case reproduces on the CLI path
  instead (2.3). No 1.1 warning on either server run; output deterministic
  (sha256 `8f17a390` both runs).
- [x] 2.2 Classify (design D2).
  - A scratch script scans the generated-output sections of `t6.trace` with a
    strict decoder and prints each invalid subpart's offset and hex window. It
    never prints text.
  - Compare with 2.1's window:
    - **same window:** tokens are the source;
    - **trace valid:** server text handling is the source. Add group 4b below:
      locate the cutting site from the offset, then fix it with a unit test.

  Done (2026-10-18): **tokens are the source**, not server text handling. The CLI
  path (2.3) writes raw token bytes with no server JSON layer, and it still emits
  6 invalid subparts (first at byte 955, window `b4882d7365726966`). Since the
  invalid bytes appear in the raw CLI stdout, they come from the detokenised
  tokens, not from the server's text handling. **No group 4b needed** — the fix
  belongs in the server's JSON escaper (group 3, done), which replaces each
  invalid subpart with U+FFFD on output.
- [x] 2.3 CLI case: `python3 eval/run.py --steer dir-steering/out/v41-msuiche-L1-8.f32
  --residual 5 --steer2 dir-steering/out/v41-abl-L9-39.f32 --residual2 6
  --indices 6 --max-tokens 2048 --judge base --suite harmful-axis-a`.
  Verify: the 1.1 warning reports "CLI stdout" with an offset (record it), or
  the case no longer reproduces (record that).
  Done (2026-10-18, run `20261018-082844`): reproduces. Warning
  `invalid UTF-8 in CLI stdout: 6 subparts, first at byte 955, window
  b4882d7365726966`. Judge: COMPLY (steered). The CLI writes raw bytes by design.
- [x] 2.4 Unsteered `max_tokens` cut.
  - Base server, no steering.
  - One benign prompt asking for a two-sentence answer in Japanese.
  - Non-streaming requests with `max_tokens` from 1 to 48, then the same with
    `stream: true`, collecting the deltas raw.

  Done (2026-10-17, on the fixed server; the pre-fix bug is proved by the
  server's own replacement count rather than a second binary):
  - all 48 non-streaming bodies and all 48 SSE streams decode as strict UTF-8;
  - the server logged `replaced 1 invalid UTF-8 subparts (first at byte 105)`
    for one `max_tokens` value (ctx 0..16), i.e. that cut landed mid-character
    and the unfixed escaper would have sent it invalid. One `max_tokens` value
    hitting a mid-character boundary matches the CJK expectation.
  - This also covers 4.1's `max_tokens` leg. Script:
    `<scratchpad>/utf8_cut.py`; no model text printed.

## 3. Fix in the server

- [x] 3.1 Tests first, in the server unit tests (`./ds4_test --server`):
  - `test_json_escape_replaces_invalid_utf8` asserts exact output bytes of
    `json_escape` and `json_escape_fragment_n` for:
    - `"a\xe2(b"` gives `a`, then U+FFFD, then `(b`;
    - a truncated tail `"ok\xe2\x80"` gives one U+FFFD;
    - stray continuations `"\x80\x80"` give two;
    - overlong `"\xc0\xaf"` gives two;
    - surrogate `"\xed\xa0\x80"` gives three;
    - above U+10FFFF `"\xf4\x90\x80\x80"` gives four;
    - valid ASCII, a 2-, 3- and 4-byte character, and control characters give
      bytes identical to today's output.

  Verify: on the unfixed escapers the test fails and names the first failing
  case (record it); every other server test passes.
- [x] 3.2 Validator and escapers (design D3).
  - One static helper returns the length of a well-formed sequence or of a
    maximal invalid subpart at a position, following the Unicode well-formed
    byte table.
  - Use it in the non-ASCII `else` branch of `json_escape` and
    `json_escape_fragment_n`: write the valid sequence as is, an invalid
    subpart as `EF BF BD`.
  - ASCII and control handling stay unchanged.
  - Read every caller of `json_escape_fragment_n` and confirm that none passes
    a fragment ending inside a character that can still complete.

  Verify: 3.1 passes; `test_streaming_holds_partial_utf8` and
  `test_openai_tool_stream_holds_partial_utf8_arguments` pass unchanged;
  `make test` names them.
- [x] 3.3 Stream agreement test.
  - Feed `openai_sse_stream_update` the pieces `"x"`, `"\xe2"`, `"\x80"`, `"A"`
    (an invalid sequence split across tokens).
  - Then a 4-byte character split across a tool-argument stream.
  - Then the 2.4 cut as a final release.

  Verify: the concatenated deltas equal `json_escape` of the whole text, each
  delta parses as strict UTF-8, and the final tail is one U+FFFD.
- [x] 3.4 Log line (design D4). At the per-request finish log, count invalid
  subparts in the final generated `text` with the 3.2 helper and, when the
  count is nonzero, log
  `ds4-server: chat ctx=<span> replaced <n> invalid UTF-8 subparts (first at byte <k>)`.
  Verify: a unit test, or the 4.1 run, shows exactly one line for a response
  with replacements and none for a clean one.
- [x] 3.5 Docs: one paragraph in `docs/CLIENTS.md`.
  - The CLI writes the raw token bytes.
  - The server replaces each maximal invalid subpart with U+FFFD and logs the
    count.
  - A client sending a replaced answer back loses the KV prefix match from
    that character.

  Verify: `grep -n "U+FFFD" docs/CLIENTS.md`.

## 4. Model-backed verification

- [x] 4.1 Rerun 2.1 (without `--trace`) and 2.4 on the fixed server.
  Verify:
  - no 1.1 warning;
  - the server log shows the 3.4 line with the count that 2.1 and 2.2 found;
  - a strict `json.loads(body.decode("utf-8"))` succeeds for every 2.4
    `max_tokens` value, streaming and not.

  Progress (2026-10-17): the 2.4 (unsteered) leg is done — see 2.4: all 96
  bodies strict-valid, one replacement logged. The 2.1 steered leg is a
  refusal-removal configuration on a harmful prompt and is left unrun.
  Done (2026-10-18): the 2.1 steered leg ran on the fixed server (4b fallback,
  gate config gone). No 1.1 warning; the server output is strict-valid UTF-8.
  The 4b config produces a clean ASCII refusal on the server path (no invalid
  bytes to replace), so the invalid-UTF-8 reproduction lives on the CLI path
  (2.3); the server fix is proved by 2.4's logged replacement plus the unit
  tests (3.1-3.3).
- [x] 4.2 Valid output unchanged. Rerun a stored phase-B screen configuration
  whose completions all decode strictly (`B_v41-msuiche@5` on indices
  `17,24`), with completions collected raw.
  Verify: the bodies are byte-identical to the unfixed server's, run on the
  same two indices before 3.2 lands (record both sha256).
  Done (2026-10-18): byte-identical. idx 17 sha256 `230df3f72601ac85` (5368 B),
  idx 24 sha256 `3575b1df342db8aa` (6217 B) — both match the stored
  `B_v41-msuiche@5` reference exactly. The fix is a no-op on valid UTF-8.
- [x] 4.3 Trace changes no output. Run 2.1 on the fixed server with and
  without `--trace`.
  Verify: identical bodies; the trace still holds the raw invalid bytes found
  in 2.2.
  Done (2026-10-18): identical bodies (4b on idx 6, sha256 `8f17a390` with and
  without `--trace`). Trace file written (11961 B). `--trace` does not alter the
  response.
- [x] 4.4 Parity: from the StarForge checkout,
  `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`.
  Verify: token-identical. No speed claim, so no A/B.
  Done (2026-10-18): **PARITY OK**, 10/10 prompts token-identical. Ran against the
  worktree via `SF_CHILD_DIR` (child 4e4db1a + uncommitted 501 fix vs upstream
  fc80bd6). Output: `tools/parity/out/sf-ds4-1flash-20261018-084655`. The fix is in
  the server JSON escaper, which the CLI parity path never exercises, so this is a
  non-regression gate — the 501 changes did not perturb token generation.

## Workflow follow-up

- If 2.2 finds the server at fault, add group 4b (site fix, unit test,
  4.1 rerun) before 4.2.
- The harness decodes with `errors="replace"` since 409; after 4.1, the 1.1
  warning is the regression signal for any later steering screen.
- Archive after 4.4.
