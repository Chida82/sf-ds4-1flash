# Residency tools

Under SSD streaming the static weights (9.4 GiB: everything but the routed
experts and the Engram tables) are reached through the model mapping and stay
pageable at the `82GB` cache. Whether they are in the file cache when a prefill
starts changes its speed by up to 27% (`speed-bench/perf-record.md`, change
`750`). These tools look at that state and set it.

| Tool | What it does |
|---|---|
| `snap.py <gguf> <out.json>` | One page-cache snapshot, resident MiB per tensor kind and layer band (Engram tables skipped, about 3 s). `--diff a.json b.json` prints what was paged in between two snapshots |
| `touch.py <gguf> warm\|evict [regex]` | Reads tensors into the cache (`pread`) or drops them (`msync(MS_INVALIDATE)`); the default regex is every static tensor |
| `fs_summary.py <capture>...` | Totals of `sudo fs_usage -w -f diskio <pid>`: events, MiB and wait per type. `PgIn` is a mapped page read from disk on a fault; `RdData[AN]` are the engine's uncached `pread`s |
| `memsample.py <out.tsv> <pid>` | Free, wired, file-backed memory and the pressure level every 0.25 s until the process exits |

`snap.py` and `touch.py` open their own read-only mapping of the GGUF and close
it before they exit; `mincore` on it reports the unified buffer cache the
engine's mapping uses. A mapping held for a whole run may change what the
kernel evicts, so take snapshots at chosen moments rather than sampling
continuously.

## Fixed start state

A fresh process's first prefill depends on what earlier processes left in the
file cache, by up to 17% at 2048 tokens (perf-record, change `750`). For a
reproducible start, before each run, without root:

```sh
python3 speed-bench/residency/touch.py <gguf> evict .  # drop every page of the GGUF from the file cache
python3 speed-bench/residency/touch.py <gguf> warm     # read every static tensor back
```

The first 2048-token prefill then repeats within 0.6% (12.58-12.66 s, five
runs), the same as with `sudo purge` in place of the evict (12.58-12.60 s).
`evict .` alone gives the cold start: every static weight is faulted in
during the prefill. Measure residency with `snap.py`, not with `fs_usage`:
page-ins include Engram rows and routed experts, so they do not say which
static weights were missing. Both `sudo purge` and `fs_usage` need root. Use
them only to cross-check a new method.
