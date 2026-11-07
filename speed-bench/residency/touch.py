#!/usr/bin/env python3
"""Warm or evict the page cache of the GGUF tensors whose name matches a regex; prints residency before and after.

    python3 speed-bench/residency/touch.py <gguf> warm|evict [regex [max-GiB]]

warm reads the ranges with plain pread (they enter the cache), evict drops them with msync(MS_INVALIDATE).
The default regex is every static tensor (all but the routed experts and the Engram tables). max-GiB stops a warm
after that many bytes (`warm engram_embd 20` stands for 20 GiB of other cached file reads)."""
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gguf_ranges as g  # noqa: E402

path, mode = sys.argv[1], sys.argv[2]
pat = re.compile(sys.argv[3]) if len(sys.argv) > 3 else g.STATIC
ranges = [(a, b) for name, a, b in g.tensors(path) if pat.search(name)]
if len(sys.argv) > 4:
    left, cut = float(sys.argv[4]) * 2**30, []
    for a, b in ranges:
        if left <= 0:
            break
        cut.append((a, min(b, a + int(left))))
        left -= cut[-1][1] - a
    ranges = cut
m = g.Mapping(path)
total = sum(b - a for a, b in ranges) / 2**20
before, t0 = sum(m.resident(a, b) for a, b in ranges) / 2**20, time.time()
for a, b in ranges:
    if mode == 'warm':
        for off in range(a, b, 64 << 20):
            os.pread(m.fd, min(64 << 20, b - off), off)
    elif mode == 'evict':
        m.evict(a, b)
    else:
        sys.exit(f'{mode}: warm or evict')
after = sum(m.resident(a, b) for a, b in ranges) / 2**20
print(f'{mode} {len(ranges)} tensors ({total:.0f} MiB): resident {before:.0f} -> {after:.0f} MiB in '
      f'{time.time() - t0:.2f} s')
m.close()
