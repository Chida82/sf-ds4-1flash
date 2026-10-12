# Design

## Context

- The V4.1 support gate (`ds4.c:30133-30146`) refuses `--dir-steering-file` with the
  upstream line "V4.1 requires Metal ... DSpark, steering and legacy diagnostics are
  not supported ...". SPEC §4 keeps that text verbatim; a past "tidy" of it broke the
  docs that quote it and added a sync conflict for nothing.
- The GPU graph already carries the steering hooks
  (`metal_graph_apply_directional_steering_ffn/_attn`, wired in the V4.1
  decode/prefill phases), and the CPU path too. Only the gate blocks startup.
- Upstream always refuses steering on V4.1. Lifting it is a child divergence by
  owner decision, for `401`-`405`.

## Goals / Non-Goals

**Goals:**
- Start V4.1 with a steering file behind an explicit opt-in.
- Keep the refusal text byte-identical for the default path.
- Disabled path bitwise identical.

**Non-Goals:**
- The correct application site (that is `401`).
- Any default-on behavior.

## Decisions

### D1. An explicit opt-in, not a silent lift
- A flag + env the user must set. The refusal is the default. This keeps upstream's
  contract for anyone who does not ask for steering, and makes the divergence
  visible at the call site.

### D2. Drop one term, keep the rest
- The opt-in removes only the `directional_steering_file` clause from `supported`.
  Distributed, load_slice, the tests, power and context limits still refuse, because
  the steering hooks are only validated for single-box Metal.

### D3. Marked divergence, rerere replays
- The gate edit is `sf:`-marked. At each upstream sync it conflicts; rerere replays
  the resolution (SPEC rule #3). Accepted as a permanent conflict site, the price of
  steering on V4.1.

## Risks / Trade-offs

- **[A sync rewords the refusal]** → the string is quoted in
  `tests/parity_prompts.txt` and the docs; env-check and parity catch a drift.
  Resolve by keeping upstream's new wording verbatim and re-applying the one-term
  drop.
- **[Opt-in given but wrong site applied]** → `401` lands the correct hook; until
  then the flag is for plumbing only, documented as such.
