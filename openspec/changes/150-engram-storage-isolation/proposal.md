# Proposal

## Why

Moving sparse Engram reads to a separate device may reduce contention with internal expert streaming, but standalone small-read tests favor the internal SSD and `70` may already hide Engram latency. After `140` is resolved, evaluate isolation as an independent performance hypothesis, not as a promised speedup or disk-space saving.

## What Changes

- Add opt-in `DS4_ENGRAM_REPLICA=<existing-GGUF>` for a validated secondary Engram source in single-box Metal SSD streaming, leaving the canonical GGUF and expert source unchanged.
- Preserve exact row bytes, hash/layout metadata, validation, bounded reads and lifecycle semantics; replace the same-inode requirement only for this explicit, content-validated source.
- Compare internal-only, Engram-isolated and (only if `140` was kept) combined up-plus-Engram placement, with actual reader/conversion behavior and startup verification costs visible.
- Start with a complete replica. Compact Engram files and removal of internal Engram storage are separate format/capacity work and are not implemented here. A replica alone frees no internal space.
- Stop without runtime changes if isolation cannot improve an exposed target under the performance gate. Capacity-only motivation requires a separate user decision, not an exception invented by this change.

## Capabilities

### New Capabilities
- `engram-secondary-source`: opt-in content-validated external Engram reads with unchanged model output and safe failure behavior.

### Modified Capabilities
None. `dual-ssd-prefill`, if implemented, is composed through its existing option, not redefined.

## Impact

- `ds41_graph_alloc` and engine-scoped source lifetime in `ds4.c`; only necessary descriptor plumbing in `ds4_engram.c/.h`; existing loader, Engram and graph tests; storage docs and measured evidence.
- Numeric ordering follows `140`, but implementation does not require its speed hypothesis to succeed. Reuse a landed validation helper if present; otherwise implement only this source's bounded validation.
- No formatting, firmware changes, persistent environment changes, automatic GGUF duplication or Hugging Face cache moves. External file creation remains separately authorized work.
