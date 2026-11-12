# Design

Depends on `810` (and on `820` for its measurements).

## Core change (`sf_sysone`)

Split `sf_sysone_decide` so the server can own the state step:

```c
/* Answer the questions from a session already synced to `prefix`
 * (ds4_session_tokens(s) equals prefix). `snap`, when not NULL, is a snapshot
 * of exactly that state and is used for the restores; when NULL and
 * n_questions > 1 the function takes its own. */
int sf_sysone_answer_from(sf_sysone *so, ds4_session *s, const ds4_tokens *prefix,
                          const ds4_session_snapshot *snap,
                          const sf_sysone_question *q, int n_questions,
                          const double *temperature, sf_sysone_answer *answers,
                          char *err, size_t errlen);
```

`sf_sysone_decide` becomes: build the prefix, `ds4_session_sync`, call
`sf_sysone_answer_from`. Its tests from `800` must pass unchanged.

## The cache (`ds4_server.c`)

```c
typedef struct {
    ds4_tokens tokens;            /* the state prefix, the key */
    ds4_session_snapshot snap;    /* session state at tokens.len */
    uint64_t last_used;           /* monotonic counter */
} sysone_state_entry;
```

An array of `N` entries in `server`, guarded by the mutex that already
serializes model work on the slot (the cache is only touched inside
`sysone_job`). Lookup for a request with prefix P:

1. **Exact**: an entry with `tokens.len == P.len` and equal tokens
   (`memcmp`) → `ds4_session_load_snapshot`, no prefill.
2. **Extension**: among entries whose tokens are a proper prefix of P
   (`ds4_tokens_starts_with(&P, &entry.tokens)`), the longest →
   `ds4_session_load_snapshot`, then `ds4_session_sync(s, P)` prefills
   only `P.len − entry.tokens.len` tokens. Store the new state as its own
   entry.
3. **Miss**: `ds4_session_sync(s, P)` from scratch, store.

The comparison is on tokens, not on a hash: a collision would silently answer
about the wrong state.

Storing: `ds4_session_save_snapshot` right after the state is reached, before
any question. Evict the least recently used entry while the count exceeds `N`
or the summed `snap.len` exceeds the byte budget; an entry larger than the
whole budget is not stored (log once).

The extension path depends on the `800` layout rule that the state prefix
ends right after the state text. Note that a caller's state must grow by
*appending* for this to hit: a JSON object state re-serialized with a new key
in the middle is a miss.

**Output note for the record.** The prefill schedule decides the bits
(`docs/MODEL_KNOWLEDGE.md`, Determinism): a state reached as 1500 tokens in
one sweep and the same state reached as 1200 cached + 300 appended can give
different, equally valid logits. Exact hits are bitwise equal to the request
that created the entry. The spec states both; the bench measures how many tops
change on the extension path.

## Preserving the chat session

In `sysone_job`, before touching the session:

```
keep = ds4_session_checkpoint_valid(sess) && !ds4_session_steering(sess)
       && ds4_session_pos(sess) > 0 && ds4_session_payload_bytes(sess) <= budget
if keep: ds4_session_save_snapshot(sess, &chat)      /* reuse one buffer kept in the slot */
... decision ...
if keep: ds4_session_load_snapshot(sess, &chat)
else:    request_live_state_clear(s, slot)           /* as 810 does today */
```

When `keep` is true `request_live_state_clear` is **not** called: the live
tool memory describes the chat state that is coming back. A steered chat
session cannot be snapshotted (`ds41_steering_refuses_persistence`); it takes
the `else` path, and the decision turns steering off as in `810`. After the
job, the worker's existing `slot_refresh_live_text` call runs as for any job.

If the restore fails, call `ds4_session_invalidate(sess)` and
`request_live_state_clear`, log a warning, and still return the decision: the
chat pays a prefill, nothing is wrong.

## Measurements (with `820`'s bench)

`run.py --scenario repeat`: for each of 20 states of about 600 tokens, three
requests with one question each, then one request with the state extended by
100 tokens. Report the latency of request 1, of requests 2-3, and of the
extension, and the share of tops on the extension that differ from a
from-scratch run of the same extended state.

Snapshot cost: states of 2K, 8K and 32K tokens; print `snap.len` and the
milliseconds of save and of load (server log, `DS4_LOG_TIMING`). Record all in
`sysone-bench/record.md`.

**Fallback, only if load at 8K exceeds 150 ms**: stop and write the numbers
into `record.md` with a proposal for a journal restore (save only what a
suffix of under 128 tokens can overwrite: per layer the raw-window rows it
writes, the compressor frontier, the Engram history, the logits). That needs
`ds4.c` and is a separate change; do not start it here.

## Tests

Unit (`DS4_SERVER_TEST`): lookup picks exact over extension and the longest
extension; eviction by count and by bytes; an oversize entry is not stored.
These use `ds4_session_new_test_checkpoint`-style shells and fake snapshots:
no model.

Live (`tests/test_sysone_http.py`, extended): the same request twice, the
second with `sf` set, reports `prefill_ms` under 100 and equal probabilities;
chat, decision, chat continuation: the server log shows the chat continuation
prefilled only its new tokens.

## Decisions taken during apply (2026-11-12)

- **The cache is keyed on the state text, not on the prefix tokens.** The
  first bench run (20 typed-decisions states, a note appended to each) found
  0 of 20 extensions: the state is tokenized as one piece, so BPE merges the
  appended text into the old state's last tokens (`}` + `\n...`) and the old
  prefix is no longer a token prefix of the new one. Lookup now takes the
  entry with equal text (hit) or the longest entry whose text is a byte prefix
  of the request's state (extend); an extension's prefix is the entry's
  tokens plus the tokens of the appended text alone. The key is still
  compared in full (no hash). Equal text gives equal tokens, so a hit is the
  same as in the design. An extended state's tokens can differ from a
  from-scratch tokenization at the boundary, which the spec already allows
  ("MAY differ in bits"); the bench reports the changed-top share.
- The chat snapshot is a local buffer per decision, not one kept in the slot
  (shortcut: one allocation of the payload per decision; keep it in the slot
  if `805` shows the allocation matters).
- The chat-keep rule uses `--sysone-state-cache-mb` as the payload budget.
- Snapshot save/load times are logged at `DS4_LOG_TIMING` by `sysone_job`.
