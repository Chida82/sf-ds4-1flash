# Tasks

Requires `820`. Section 3 requires `a015` kept.

- [x] 1.1 `run.py --blank-state` (dedupe per distinct question and rotation; under `schema_first` blank inside the same grouped request).
- [x] 1.2 `contrast_fit.py` with both priors, the β grid, state-level split and paired bootstrap; unit tests in `tests/test_sysone_bench.py`: β = 0 equals the baseline; a synthetic set with a planted option bias recovers β near 1 and removes the flips.
- [x] 2.1 Blank-state runs for each layout in use, rotations 0 and 1 (state_first only; rotation 0 only, see Progress).
- [x] 2.2 The fit; one table per layout in `sysone-bench/record.md`; apply the gate and write the decision.
- [x] 3.1 (Not done: archived as measured, not applied.) On "keep" with `a015`: `prior_beta` in the calibration file, its loader, the factor in `sf_sysone.c`, the unit test.
- [x] 3.2 (The result is in section 8; no server change, so no `docs/SERVER.md`.) `docs/system-one.md`: the result, and the sentence that a015's β = 1 is one point of this family. `docs/SERVER.md` if 3.1 was done.

## Progress (2026-11-24, overnight)

Data are the `a010` sets, not typed-decisions (owner, 2026-11-19). The
system-one-bench suites ask one question of 150-200 states each, so the batch
prior needs no extra request; the content-free prior is one blank-state
request per distinct question (7 for system-one-bench, one per item for
jevbench and the policy suites). Rotation runs (`--rotate 1`) are not part of
tonight's queue: the flip-rate half of the gate waits; the NLL/accuracy half
is decided on what was run.

Result (record, "Prior contrast (a020)"): content-free prior kept for
`choice` on system-one-bench at β 0.25 (−0.019 nats, accuracy unchanged);
dropped for `noul`, for jevbench and the policy suites, and the batch prior
everywhere. Section 3 waits for `a015`'s verdict; the flip-rate half of the
gate needs `--rotate 1` runs, not made.

Open question for the owner (2026-11-24): section 3 depended on `a015`, which
was dropped. The only keep is β 0.25 on system-one-bench `choice` (−0.019
nats, no accuracy change). Either archive this change as "measured, not
applied", or write a `state_first` production step (a blank-state prior read
once per distinct question and cached), which costs one extra readout per new
question for 0.019 nats.

Archived as measured, not applied (owner, 2026-11-24): 0.019 nats on one
question type does not pay for an extra prior readout per new question.
Specs not applied (`--skip-specs`).
