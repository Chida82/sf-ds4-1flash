# Tasks

## 1. Evidence already taken (2026-11-06)

- [x] 1.1 Fresh-process gap localized: README sweep at `fa51b38`, `fc51998` and `main` (prefill 2048 -17% on `main` only), screens over the sync switches (router copy alone), CB_TIMES and the encoder timeline (equal kernel time, GPU stalls in layers 20-39)
- [x] 1.2 Mechanism: `fs_usage` page-ins (up to 1.4 GiB / 13 s in slow runs), page-cache snapshots per tensor (router F32 300 -> 125 MiB before the prefill), and the fixed-start-state series (`purge` plus a static read: main 161.8 = copies off 161.0 t/s; cold 117.2 = 116.5)
- [x] 1.3 Copy the evidence tools (snapshot, warm/evict, `fs_usage` summary, memory sampler) from the scratchpad into `speed-bench/residency/` with a README, so the scenarios below can be rerun

## 2. Server regime (decides section 4)

- [x] 2.1 One `sf-ds4-1flash-server` process, `--ssd-streaming`, `82GB`: request A (2048-token prompt, 2000 generated tokens), then request B (an unrelated 2048-token prompt). Record `fs_usage -w -f diskio` and the static-tensor snapshots around request B, and B's prefill time
- [x] 2.2 The same with the narrow copies off (the three switches), and once more with the copies on and 20 GiB of unrelated file reads between A and B
- [x] 2.3 Record the page-ins and times in `speed-bench/perf-record.md`. If B pages in under 64 MiB of static weights with the copies on and no other reads, section 4 is not built, and the requirement stays as a guard

## 3. Prefault at engine open

- [x] 3.1 After the expert-cache lock-ahead, when the static weights stay pageable: touch the decode-static spans (`POSIX_MADV_WILLNEED`, then one read per page, bounded per call), with `DS4_METAL_DISABLE_STREAMING_STATIC_PREFAULT` classified in `ds4_env.def`; print how many GiB were already resident and how long it took
- [x] 3.2 `make test`; bench logits at 2048 and 8192 byte-identical with and without the switch
- [x] 3.3 Fixed start states without root (`touch.py evict .` then `warm`; `sudo purge` cross-checked twice): statics warm, and a full file cache (statics, then 60 GiB of other reads), the switch off against on, three each; residency of the statics at the prefill start by `snap.py` (back-to-back order measured first and dropped: 11.5-12.8 s noise whatever the switch)
- [x] 3.4 Cold start (`purge` before each run): engine open to end of the first prefill, the switch off against on

## 4. Lock the skipped wide weights (not built: 2.3 measured no static page-in)

- [x] 4.1 NOT NEEDED (2.3: request B paged in no static weight). The wide-weight lock was not built; `760` locks every static weight at `82GB` instead
- [x] 4.2 NOT NEEDED (see 4.1)

## 5. Docs

- [x] 5.1 `AGENTS.md` (SSD streaming: start-state dependence and the switches), `speed-bench/README.md` (what a fresh-process run measures; the README tables' start state), `speed-bench/perf-record.md` (evidence and results)
