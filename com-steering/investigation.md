# investigation.md — what is under test and where it stands

The living exploration: the directions in play, the open ideas, the roads
already closed. The method they rest on is [`spec.md`](spec.md); the next
concrete actions are [`todo.md`](todo.md); the numbers are
[`result.md`](result.md). Update the *Current state* block whenever a run lands.

## Goal

A direction (or a two-slot pair) whose axis-A score beats the best single vector
with **no quality regression** in either reasoning phase. "Better" is defined in
[`kpi.md`](kpi.md); a verdict is a `/44` run, both phases.

## Current state

- **Shipped:** `sf-ds4-1flash-candor` — slot 1 `q0dwarf-equi @7` both phases,
  slot 2 `mrfk-q1 @7` think only. Standing number **41.6 /44** non-think,
  39.0 think. Pair is near-orthogonal (`|cos|` median 0.105).
- Slot 2 helps only in the think phase; on the answer phase it made results
  worse, so it is gated off there.

## Directions in play

| Vector | Provenance recorded? | Note |
|---|---|---|
| `q0dwarf-equi` | yes (sidecar) | slot 1 of the shipped profile |
| `q0dwarf-interleave` | yes (sidecar) | alternative composition of the same two inputs |
| `msuiche-1017` | yes (sidecar) | 1017-native control vector |
| `mrfk-q0` | **no** | slot 1's parent — provenance only in `vectors/mrfk_extract.py` |
| `mrfk-q1` | **no** | slot 2 itself — same gap |
| `dwarfstar-wo` | **no** | `equi`'s other parent |

The three missing sidecars matter: the shipped profile currently rests on files
whose origin is recorded nowhere durable. Closing them is a prerequisite for
pinning a shipped default to the run that chose it (see `todo.md`).

## Open ideas

Live hypotheses worth a run. Promote to `todo.md` when picked up, retire to
*Closed roads* when ruled out.

- [ ] Close the three missing provenance sidecars, then re-confirm Candor.
- [ ] A composition that starts from `mrfk-q0` + `dwarfstar-wo` directly rather
      than from `q0dwarf-equi` (the "never one fusion" rule, `spec.md`).
- [ ] Finalist validation on the large external sets once a config beats 41.6.

## Closed roads

Ideas already measured and dropped stay recorded so they are not re-tried. The
full reasoning and numbers are in the historical diary
(`0cbf547:eval/steering-comparison/TODO.md`, 228 lines) and `STEERING.md` beside
it. When you drop an idea, add a one-line verdict to `todo.md` and, if it carries
a number, a row to `result.md`.
