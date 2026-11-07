#!/usr/bin/env python3
"""One page-cache snapshot of the GGUF, resident bytes per tensor kind and layer band, written as JSON.

    python3 speed-bench/residency/snap.py <gguf> <out.json>
    python3 speed-bench/residency/snap.py --diff <start.json> <end.json>

The Engram tables (193 GiB, read with F_NOCACHE) are skipped; the decoder layers' static tensors come first, so a
snapshot taken as a prefill starts sees them before the prefill reaches them (about 3 s for the whole file)."""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gguf_ranges as g  # noqa: E402


def snapshot(path):
    t0 = time.time()
    ts = [t for t in g.tensors(path) if 'engram_embd' not in t[0]]
    ts.sort(key=lambda t: ('_exps.' in t[0], not re.match(r'blk\.(2\d|3\d|4[0-2])\.', t[0])))
    m = g.Mapping(path)
    groups = {}
    for name, a, b in ts:
        r = groups.setdefault(g.group(name), [0, 0])
        r[0] += m.resident(a, b)
        r[1] += b - a
    m.close()
    return {'t0': t0, 't1': time.time(), 'groups': groups}


def diff(a, b):
    ga, gb = json.load(open(a))['groups'], json.load(open(b))['groups']
    rows = sorted(((gb[k][0] - ga.get(k, [0])[0]) / 2**20, k) for k in gb)
    for kind, f in (('statics', lambda k: '_exps' not in k), ('experts', lambda k: '_exps' in k)):
        print(f'{kind}: {sum(ga[k][0] for k in ga if f(k)) / 2**20:.0f} -> {sum(gb[k][0] for k in gb if f(k)) / 2**20:.0f} MiB')
    for d, k in reversed(rows[-10:]):
        if d > 0:
            print(f'  +{d:7.0f} MiB  {k}')


if __name__ == '__main__':
    if sys.argv[1] == '--diff':
        diff(sys.argv[2], sys.argv[3])
    else:
        json.dump(snapshot(sys.argv[1]), open(sys.argv[2], 'w'))
