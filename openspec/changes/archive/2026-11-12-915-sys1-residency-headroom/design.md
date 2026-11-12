# Design

Depends on `810`, `820`, `830`. Read `docs/system-one.md` section 10 and
`docs/DISTRIBUTED.md` first. No source file of the engine or server is
edited in this change.

## Stage 1: decomposition on one Mac

### Runs

As run (2026-11-12): `DS4_METAL_CB_TIMES` prints only the first 400 command
buffers of a process and the decode keep-alive counter counts no System One
token, so stage 1 used `DS4_METAL_GRAPH_PREFILL_PROFILE=1`,
`DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY=1` and
`DS4_METAL_GPU_BUSY_PROFILE=1`, one server per run (`headroom.py`'s
docstring). Stage 2 uses the same three. The original plan follows.

Start the server with the probes set **inline** (never `export`):

```sh
DS4_METAL_CB_TIMES=1 DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY=1 \
  ./sf-ds4-1flash-server --ssd-streaming --ssd-streaming-cache-experts 82GB \
  --ctx 32768 --sysone-state-cache 0 > WORK/server-probe.log 2>&1
```

`--sysone-state-cache 0` turns `830`'s cache off so that every request pays
its state. Then, with `sysone-bench/run.py --mode sysone`:

| Run | Items | Why |
|---|---|---|
| S | the 60 Italian fixtures (states under 256 tokens: token by token) | the decode-rate regime |
| L | the first 30 states of the typed-decisions subset used by `820` (about 370 tokens: one sweep) | the sweep regime |
| L2 | run L again, same order, same server process | the expert cache is now warm for these states: shows what misses cost |

A probe changes timing. Run S and L once more on a server started **without**
the two variables and record the wall-time difference per decision; if the
probes add more than 10%, say so beside every figure.

### Parser

`sysone-bench/headroom.py --log WORK/server-probe.log --results results.jsonl`
(standard library only). Before writing it, run one request with the probes
and read the log: the exact line formats are whatever `ds4_metal.m` prints for
`DS4_METAL_CB_TIMES` and for the streaming expert timing summary; copy two
sample lines of each into a comment at the top of the parser. It sums, per
request (requests are delimited by the server's `systemone slot` log line):

- `gpu_ms`: GPU execution time of the command buffers;
- `encode_ms`, `queue_wait_ms`: as printed;
- `read_wait_ms`: time decode tokens waited on the pread pool, and prefill
  read time, from the timing summary;
- `wall_ms`: from the results file.

`other_ms = wall − gpu − encode − read_wait`. If the log does not allow a
per-request split (the summary prints only at exit), split per **run**
instead: start one server per run and divide by the number of decisions. Say
which was done.

Unit test in `tests/test_sysone_bench.py`: the parser on a fixed 20-line
sample log gives fixed sums.

### Table (in `sysone-bench/record.md`, section "Residency headroom")

Per run: decisions, median wall ms, share of GPU, share of read wait, share of
the rest, and the **predicted resident time** `wall − read_wait`.

### Go/stop rule

Let `r = read_wait / wall`, median over run L (the sweep regime, where the
state cost lives):

- `r >= 0.5`: residency would at least halve a decision. Write "go for
  stage 2" and the predicted speed-up `1 / (1 − r)`.
- `0.25 <= r < 0.5`: write "modest"; stage 2 is optional and `a045` is not
  justified by residency alone.
- `r < 0.25`: write "compute-bound: more machines buy parallel requests, not
  faster decisions". Stage 2 is not run.

Also write the same ratio for run S (question suffixes): it bounds what
residency does for the per-question cost.

## Stage 2: two Macs (only with a second 128 GB Mac cabled; ask the owner)

**Dropped (2026-11-12): no second Mac exists.** Estimates from stage 1 stand
in for steps 3 and 4 in `sysone-bench/record.md`; step 5 (session batching)
stays an open question. The plan below is kept for whoever has resident
weights one day.

Do not start without the owner's word: it needs the second machine, the same
commit built on both, and the GGUF on both.

1. Bring up tensor parallelism as `docs/DISTRIBUTED.md` says (worker first,
   then the server as leader, RDMA; no `--ssd-streaming`).
2. `tests/test_sysone_http.py` against the TP server: all checks must pass.
   If isolation or determinism lines fail, stop and report.
3. Runs S and L of stage 1 against it. Record median wall ms and the ratio to
   stage 1. Compare with the prediction: a measured time more than 1.5 times
   the predicted resident time means the link costs more than the reads
   saved; record that.
4. Accuracy must not move: same items, tops equal to stage 1 on at least 95%
   (TP kernels round differently; `820`'s `delta95` is the reference for how
   much logit gaps may move).
5. Session batching: start the server with `--batched-session 4` (read its
   help text first) and send four different decisions at once; record whether
   the log shows batched decode and the wall time against four in sequence.
   This only observes existing behaviour; a batched branch path inside
   `sf_sysone_decide` is a later change if the figure warrants it.

## Risks

- The probes may not separate read wait from GPU wait cleanly (a GPU batch
  blocked on wiring pageable statics looks like GPU time). The static-weight
  lock of `760` is on by default; confirm the log line "lock" at engine open
  and say so in the record.
