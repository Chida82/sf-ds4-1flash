# Design

## Context

See proposal.md. The server writes checkpoints inline in the request (cold store during prefill, continued stores every 10000 tokens, evict and shutdown stores) and loads at most one file per hit. Both block the request, so a slower directory can show up in TTFT and end-to-end time. `ds4_kvstore_open` evicts at open with the configured budget (default 4096 MiB), and the index is the directory itself, rescanned at each lookup. `ab_bench.py` drives the bench binary, not the server; `serve_concurrency_bench.py` drives the server.

## Goals / Non-Goals

**Goals:** a measured per-shape cost of moving the KV cache to the external SSD in the setup the owner will actually run, and documentation of the command when that cost is accepted.

**Non-Goals:** a read-only fallback directory, an import or copy option, changes to `ds4_kvstore.c` or the server, larger KV budgets, physically unplugging the drive to test failure.

## Decisions

### D1. Gate on 140/150

Run only after `140` and `150` are decided. If neither kept an external placement, record that the external drive is not part of the normal setup and close without measuring or documenting.

### D2. Arms and shapes

Both arms run `sf-ds4-1flash-server --ssd-streaming --ssd-streaming-cache-experts 82GB` with the kept `140`/`150` environment and the same `--kv-disk-space-mb`. Only `--kv-disk-dir` differs: the internal per-child directory versus `/Volumes/<external>/sf-ds4-1flash/kv` (per-child name, rule 8). Two shapes from `serve_concurrency_bench.py` at concurrency 1, inside the typical workload (prompts 1-10K tokens, answers 200-2000):
- cold: fresh-nonce prompts, which write cold and continued checkpoints;
- hit: prompts whose prefix must be served from disk, proven by the server's `kv cache hit` log lines (a memory-slot hit does not count).

Pass `--model` explicitly: the bench's default model name is a sibling's. ABBA order with a server restart per arm, so page-cache order does not favor one directory. No `purge` (needs `sudo`).

### D3. Acceptance

Per shape: median E2EL and TTFT change, with the pooled bootstrap 95% CI. The owner accepts a cost down to -0.2% for the wear benefit. Accepted when the median E2EL change is at least -0.2% on both shapes. Otherwise documentation is not changed and the per-shape percentages, with their CIs, go to the owner for a decision. Also record bytes written per request (from the checkpoint sizes in the server log) to state the wear moved off the internal SSD, and the load ms per MiB, to show whether hits came from disk or from the page cache.

### D4. Documentation

`README.md`: the server command with `--kv-disk-dir` on the external SSD and the one-time move of an existing cache with the server stopped (`mv <old>/*.kv <new>/`), noting that eviction state moves with the files. `docs/SERVER.md` and the suggested path in `AGENTS.md` follow. If the drive is not mounted, the server logs that it cannot create the directory and runs without a disk cache; the docs say so.

Alternative rejected in exploration: a read-only second KV directory or an import flag. The move does the same with no upstream code to carry through syncs.

## Risks / Trade-offs

- [Hits served from the page cache hide the disk difference] -> record load ms per MiB and say which arm read from disk.
- [ExFAT has no journaling; an unplug can tear a file] -> already handled by the store: a short file is never indexed and a corrupt payload is discarded at load (`ds4_kvstore.c`). Read, not tested by unplugging.
- [A large budget meets the external pSLC write cliff, about 45 GiB] -> the measured budget is stated in the docs; larger budgets are not claimed.
- [KV writes compete with `140`/`150` external reads] -> both arms carry the kept placement, so the contention is inside the measurement.

## Migration Plan

Docs only. Rollback is pointing `--kv-disk-dir` back to the internal directory and moving the files back. No commit or push without an explicit request.
