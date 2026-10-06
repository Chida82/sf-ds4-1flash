# Proposal

## Why

`140` added an opt-in second-drive path and `160` documented the server setup, but two facts are still unmeasured:
- what the `140` code costs on a machine with only the internal SSD, where the option is never set;
- what a user gains or loses with and without the external drive, side by side, in the README.

The owner sets the acceptance for the first at a loss of at most 0.1%.

## What Changes

- **Overhead without the drive.** A/B today's `main`, with `DS4_METAL_PREFILL_REPLICA` unset, against the same tree with `140`'s runtime code removed (a measurement-only revert, never landed). Accept if the loss is at most 0.1%, read from the pooled 95% CI. If it is above, find and remove the cost in the same change.
- **README table with and without the drive.** Time to first token at 2500-10000 tokens, append +300/+1500 and decode, for:
  - the internal SSD only;
  - the `140` copy on the TB5 drive, with the KV cache there too.

  Each figure comes from the harness, on the tested hardware, with its conditions and a link to the record.
- No other runtime change.

## Capabilities

### New Capabilities
None. Measurement and documentation (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `README.md` ("A second drive" and "Speed"), `speed-bench/perf-record.md`. If the overhead check fails, the replica code paths in `ds4.c`.
- Needs the external SSD with the `140` copy for the "with drive" arm.
- The 0.1% threshold is below a single invocation's resolution (pooled CIs of about +/-0.3-0.5%), so expect 2-3 invocations per comparison, preferably at night.
