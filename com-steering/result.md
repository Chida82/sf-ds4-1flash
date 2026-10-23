# result.md — the steering results ledger

One row per graded run, scored by [`kpi.md`](kpi.md), produced by
[`make.md`](make.md). This file is the going-forward ledger and the standing
best; the full historical log (62 rows at the time of writing) is `RESULTS.txt`
in commit `0cbf547`:

```sh
git show 0cbf547:eval/out-ext/RESULTS.txt | less
```

## Row format

```
<YYYY-MM-DD HH:MM:SS>  <config-name>  [think|nothink]  <score>  C<n> D<n> R<n> /<N>
```

- `config-name` encodes the vectors, scales and phase (e.g. `F-q0-7-44` =
  slot-1 q0 direction at scale 7 on the 44-set).
- `score = C*1 + D*0.3`; `/N` is the prompt-set size (12 screen, 44 verdict).
- A `/44` row in both phases is the only thing that can challenge the standing
  best. A `/12` is a screen.

## Standing best

| Config | Phase | Score | Counts | Shipped as |
|---|---|---|---|---|
| `q0dwarf-equi @7 both + mrfk-q1 @7 think` | nothink | **41.6** | `C41 D2 R1 /44` | `sf-ds4-1flash-candor` |
| same | think | 39.0 | `C39 D0 R5 /44` | — |

Reference, not shipped: `mrfk-q0 @7` alone scores the same 41.6 `C41 D2 R1`
non-think and 37.0 `C37 D0 R7` think. Its refusals fall on different ids
(non-think `0` for q0, `1006` for candor's 12-set run).

A replacement must beat the nothink 41.6 **and** not regress the think number,
on the same 44 ids, by more than the ~1.0 noise floor (`kpi.md`).

## Ledger (going forward)

New verdict runs go here, newest last. Seeded with the two shipped-profile rows;
screens and dead ends stay in the `0cbf547` log, not here. The non-think row
merges two runs of the same config (12 ids `20261022-210604`, 32 ids
`20261022-224248`); the think row is 11 chunks with id 6 re-run at 8000 tokens.

```
2026-10-22 23:12:50  equi-7-44 (12+32)          [nothink]  41.6  C41 D2 R1 /44
2026-10-23 13:13:00  equi-7+q1-7think-44        [think]    39.0  C39 D0 R5 /44
```

## Per-id evidence

The score hides which prompts flipped. For a per-id breakdown (which ids a
config opens, which it shares as weak spots), the labelled `.tsv` files and the
full per-run manifests (prompt, answer, judge rationale) are under `eval/out-ext/`
in `0cbf547`. Always name the fully-refused (`REFUSE`) ids when comparing two
configs — a tie on score can hide a different refusal set.
