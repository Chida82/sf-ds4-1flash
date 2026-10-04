# Proposal

## Why

The cache manager scans entries to select victims, while a historical routing trace also suggests room for fewer misses than the current decayed-hotness policy. After `100`, separate the cost of managing the cache from the choice of what to retain; neither the old trace nor a disk-only benchmark establishes a current decode gain.

## What Changes

- Profile scan/clear/bind time and replay fresh routes using the existing `expert_cache_sim.py` before changing policy.
- First evaluate a compact live-entry index that preserves exactly the current victim comparator and all in-flight/protection rules.
- Separately trial global LRU using the existing last-used information, only when new traces justify it. The runtime still protects entries in flight and entries selected for the current operation.
- Hold expert slots and bytes fixed. Preserve byte-identical model results; declare policy-change comparisons explicitly rather than treating different miss counts as unexplained noise.

## Capabilities

### New Capabilities
None. Internal cache management, not a new user-facing cache mode (`skip_specs: true`).

### Modified Capabilities
None. Use the harness's existing cache-policy-change facility.

## Impact

- Cache entry lifecycle, victim scans and hotness accounting in `ds4_metal.m`; `tests/test_metal_ssd_experts.c`; replay tests only where the current simulator lacks the required evidence.
- #621 `61e35e2` is the relevant upstream live-index candidate; verify its V4.1 dimensions before adoption. Keep all #1125 safety fixes already taken by `40`.
- No resurrection of `50`'s neutral early-load path or #849's speculative router lookahead. No online policy autotuner or permanent choice of equivalent policies.
