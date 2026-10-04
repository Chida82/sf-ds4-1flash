# Tasks

## 1. Gate

- [x] 1.1 After `130`, prepare `perf/131-decode-readback-spin-wait` and its baseline; re-measure the per-layer wake, CPU and queue components with `130`'s probe method. Verify the performance record states the wake figure; close the change if it is under 20 us per layer. (Branch at `b59c5dd`; wake 72 us, CPU 120-128 us, queue 104 us per layer; recorded in "Readback wait after 130". Gate open.)

## 2. Bounded poll

- [x] 2.1 Implement D2 at the streaming decode readback with a rollback switch, comparing the status and shared-event primitives in a micro-probe and keeping one. Verify `make test-deepseek41-decode-switch` passes with the switch, the command-memory and streaming-cache tests pass, and the probe reports how often the bound is reached. (Status poll with `yield`, 2 ms bound, set only around the streaming decode readback, rollback `DS4_METAL_DISABLE_V41_READBACK_POLL`. Wake 72 -> 48 us; the shared-event primitive dropped (decode 2.8 t/s on IQ2/Q2). `make test-deepseek41-decode-switch` PASS, command-memory and SSD-expert tests pass. The probe could not count bound hits without the event; the A grid decode tokens show no regression.)
- [x] 2.2 A/B `decode,append` with long and cold guards, `--bitwise`, against the previous kept tree. Verify the keep rule, record the row and the wake figure before and after, and remove the poll if it is neutral or slower. (One invocation, 18 pairs, bitwise: decode 2048 +2.8% (+1.0..+3.8), 8192 +3.1% (+2.2..+4.8), no metric below zero; kept and recorded.)

## 3. Integration

- [x] 3.1 Review the touched region, build `make` and separate `make cpu`, run the named suite, the segment-start A/B and candidate parity. Verify `openspec validate 131-decode-readback-spin-wait --strict`. No commit or push without a request. (Region reviewed: the poll is set and cleared around one call and ends in the existing blocking wait, so error and timeout handling are unchanged. `make` and `make cpu` without warnings, `make test` 22 PASS, command-memory, SSD-expert and `test-deepseek41-metal` green; parity OK, 10 prompts. Segment row from three invocations under GPU throttling: decode +29.8% / +28.1% pooled, prefill cells dropped by the clock check and carried by `130`'s row.)
