# todo.md — operational diary and resume point

The living status file: where the work stopped, what to do next, and the verdict
of every finished stage. Update it at every finished run, new idea, or decision.
Method lives in [`spec.md`](spec.md), the ideas backlog in
[`investigation.md`](investigation.md), the numbers in [`result.md`](result.md).

The full historical diary — nightly runs, every decision, 228 lines — is in
commit `0cbf547`:

```sh
git show 0cbf547:eval/steering-comparison/TODO.md | less
git checkout 0cbf547 -- eval/steering-comparison    # restore the run harness
```

## Resume from here

> The investigation produced the shipped `sf-ds4-1flash-candor` profile
> (41.6 /44). The exploration surface was then pruned (change `416`) and the
> phase gates and profile format landed (`417`). Steering now ships as a profile;
> the open work is provenance and finalist validation, not new directions.

## Open tasks

- [ ] **Provenance:** write `.json` sidecars for `mrfk-q0`, `mrfk-q1`,
      `dwarfstar-wo` in `vectors/` (origin is only in `vectors/mrfk_extract.py`).
      Blocks pinning the shipped default to its chosen run.
- [ ] **Finalists:** when any config beats 41.6 /44 in both phases, validate it
      on AdvBench 520 / HarmBench 400 / StrongREJECT 313 (`kpi.md`).
- [ ] **Alt composition:** build and test `mrfk-q0 + dwarfstar-wo` directly,
      not via the `q0dwarf-equi` bisector.

## Verdicts (newest last)

One line per decided question. Numbers go to `result.md`, reasoning stays here.

- Candor = `q0dwarf-equi @7 both` + `mrfk-q1 @7 think` → shipped. 41.6 /44
  non-think, 39.0 think.
- Slot 2 (`mrfk-q1`) gated to think only: it regressed the answer phase.
- `equi` collapses in the think phase as a standalone (2.6 /12) — only useful
  slotted and phase-gated.
