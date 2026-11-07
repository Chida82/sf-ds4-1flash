#!/usr/bin/env python3
"""Totals of an `fs_usage -w -f diskio <pid>` capture: events, MiB and summed wait per event type, and page-ins
per second (PgIn = a mapped page read from disk on a fault).

    sudo fs_usage -w -f diskio -t 45 <pid> > fs.txt
    python3 speed-bench/residency/fs_summary.py fs.txt [...]"""
import collections
import re
import sys

for path in sys.argv[1:]:
    tot = collections.defaultdict(lambda: [0, 0, 0.0])
    per_s = collections.Counter()
    for line in open(path, errors='replace'):
        f = line.split()
        if len(f) < 9 or not re.match(r'\d+:\d+:', f[0]) or not f[3].startswith('B='):
            continue
        try:
            wait = float(f[-3])
        except ValueError:
            continue
        t = tot[f[1]]
        t[0] += 1
        t[1] += int(f[3][2:], 16)
        t[2] += wait
        if f[1].startswith('PgIn'):
            per_s[f[0][:8]] += 1
    print(f'== {path}')
    for ev, (n, b, w) in sorted(tot.items(), key=lambda x: -x[1][0]):
        print(f'  {ev:12s} {n:7d} events {b / 2**20:9.1f} MiB {w:8.2f} s waited')
    if per_s:
        print('  page-ins per second:', ' '.join(f'{k[6:]}:{v}' for k, v in sorted(per_s.items())))
