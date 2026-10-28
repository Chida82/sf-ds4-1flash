# Design

## Context

The V4.1 residual steering runtime already carries everything this schedule needs except
the time axis. `ds41_steering_apply_gates(s)` (`ds4.c` ~28519) runs once per forward and
writes the two per-slot scales into `s->ds41_graph.residual_scale` /
`residual_scale2` from the engine's constant `directional_steering_residual_scale[2]`,
after applying each slot's think/answer gate (`directional_steering_phase[i]`). It is
called from `ds41_steering_on_prompt` (opening phase, last prompt token) and
`ds41_steering_on_decode` (each fed token; flips `steering_in_think` at the
end-of-thinking id). The profile loader `cpu_load_directional_steering` (~26319-26344)
already parses per-slot `vector`, `scale`, `phase` from the `.sfsteer` JSON header.

The archived `403` wrote the requirement text for a decay schedule but did **not** retain
or implement it (verified: no decay field in `ds4.c`/`ds4.h`/`ds4_cli.c`); it tested
decay-to-0.2 via removed CLI flags and lost 30.9 vs 39.0. This change implements the
decay-to-**0** variant, carried by the profile, and measures it on the composite candor
profile — the configuration `403` never ran.

## Goals / Non-Goals

**Goals:** add the smallest time-varying scale that realizes `S − (S−F)·(3t²−2t³)` per
slot, per phase, driven only by profile fields; keep `N = 0` bitwise-constant; measure it
on the 44-set in both phases against the standing candor numbers.

**Non-Goals:** CLI decay flags, cyclic schedules, FFN/attention schedules, speculative
decoding, a shape selector. No change to the shipped constant profile until the
experiment wins.

## Decisions

### D1. Inject the curve at the single per-token scale site
`ds41_steering_apply_gates` is the one place a per-token scale is produced for both slots.
After the existing phase gate zeroes an out-of-phase slot, multiply the surviving scale by
the smoothstep factor for that slot's current phase position:

```
for i in {0,1}:
    S = gated sc[i]                      # already 0 if out of phase
    N = e->directional_steering_decay_tokens[i]
    F = e->directional_steering_decay_final[i]
    if N > 0 and S != 0:
        t = clamp(s->steering_phase_tok / (float)N, 0, 1)
        f = t*t*(3 - 2*t)                # 3t² − 2t³
        sc[i] = S - (S - F) * f          # F ≤ S, so this only decreases
```

A slot gated off keeps `S = 0`, so the decay never resurrects it. `N = 0` skips the block
and leaves the constant scale — bitwise identical to today.

### D2. One per-session phase-position counter
Add `int steering_phase_tok` to the session. `ds41_steering_on_prompt` sets it to 0 (the
final prompt forward predicting the first answer token is position 0, so it gets S).
`ds41_steering_on_decode(token)` advances the schedule for the *next* forward: if `token`
is the end-of-thinking id it resets the counter to 0 (answer phase restarts the dose, D-
spec "Answer dose restarts"); otherwise it increments. Both helpers then call
`apply_gates`. A single counter is enough because both slots share the same phase
boundary; a slot with its own window reads the same `p` and divides by its own `N`.

Counting is gated the same way phase tracking already is (`ds41_steering_gated`): a
profile with no decay fields and no phase gate does no per-token work and matches the
ungated run. Decay implies the counter must run even when both slots are phase `both`, so
the gate predicate widens to "any slot gated **or** any slot has `N > 0`".

### D3. Carry the schedule in the profile, not in new flags
Add optional `decay_tokens` (int ≥ 0) and `decay_final` (number, `0 ≤ F ≤ scale`) to each
slot object in the `.sfsteer` JSON header. The loader stores them in two new engine
arrays `directional_steering_decay_tokens[2]` / `directional_steering_decay_final[2]`,
defaulting to 0 (window) when absent, which is the constant path. Absent `decay_final`
with a nonzero `decay_tokens` defaults to 0 (the release-to-zero intent). The raw
`--dir-steering-*` path gains nothing: no CLI decay option, consistent with the non-goal.
Validation (finite, range, non-negative) runs where the profile's scale/phase are already
validated, refusing with the slot index and field name.

### D4. The experiment profile is a separate file
Build `com-steering/profiles/sf-ds4-1flash-candor-decay.sfsteer` from the same two vectors
and scales as the shipped profile, adding `decay_tokens: 30, decay_final: 0` to both
slots. The shipped `sf-ds4-1flash-candor.sfsteer` is not touched. If the experiment wins
the gate (`403` D1), a follow-up promotes the fields into the shipped profile; if it
loses, the experiment profile and findings stay as the record and nothing ships.

### D5. Output is expected to change; bitwise applies only to N=0
Unlike a perf change, the decay alters tokens by design, so the acceptance test is the
axis-A verdict, not bitwise parity. The one bitwise claim is `N = 0`: a decode-switch
style run (a decay profile with `decay_tokens: 0` vs the constant profile) must match
logits, KV and Engram bitwise over 65 tokens. A second unit check asserts the applied
scale at positions `p = 0, N/2, N, N+5` equals the closed-form smoothstep, and that the
counter resets at the think boundary.

## Risks / Trade-offs

- **[The schedule loses again, like 403]** → the gate is explicit and cheap: one 44-id run
  per phase decides it, and a loss leaves the shipped profile untouched. The distinct bet
  is decay-to-0 on the composite, not decay-to-0.2 on a single vector.
- **[Batching]** → gated/scheduled sessions already decline the native batched decode
  (one scale per batched forward). The decay rides that same path; no new batch support.
- **[Persistent KV / snapshots]** → already refused under a nonzero steering scale
  (`401`); a scheduled scale is still nonzero at the start, so the existing refusal covers
  it. No new cache interaction.
- **[8000-token budget cost]** → the think run at MT=8000 is the budget that produced the
  standing 39.0; reusing it keeps the comparison honest. Model time is the main cost, run
  one process at a time under SSD streaming.

## Migration

None. No shipped configuration loads a decay profile; every existing run is bitwise
unchanged. The engine gains two zero-default arrays and one session counter.
