#!/usr/bin/env python3
"""Replay a routed-expert selection trace through LRU and Belady caches of a given size.

usage: expert_cache_sim.py --trace FILE --moe-layers N --slots S [--stderr BENCH_STDERR]
       expert_cache_sim.py --self-test

The trace is what DS4_MOE_RECORD_SELECTED_IDS writes: six int32 expert ids per routed MoE
call, calls in layer order within each token, MoE layers cycling every N entries. Keys are
(layer, expert), the cache is global over layers with S slots, both replays start empty. With
--stderr the measured misses of the same run are read from its last "streaming expert cache"
report, so the three numbers print side by side (design D13 of 20-perf-bench-harness).
"""

import argparse
import heapq
import re
import struct
import sys
from collections import OrderedDict


def read_trace(path, moe_layers):
    data = open(path, 'rb').read()
    ids = struct.unpack(f'<{len(data) // 4}i', data[:len(data) - len(data) % 4])
    if len(ids) % 6:
        raise SystemExit(f'{path}: {len(ids)} ids is not a multiple of 6')
    calls = [ids[i:i + 6] for i in range(0, len(ids), 6)]
    if len(calls) % moe_layers:
        raise SystemExit(f'{path}: {len(calls)} calls is not a multiple of {moe_layers} MoE layers')
    return [(i % moe_layers, e) for i, call in enumerate(calls) for e in call]


def lru_misses(accesses, slots):
    cache, misses = OrderedDict(), 0
    for key in accesses:
        if key in cache:
            cache.move_to_end(key)
        else:
            misses += 1
            if len(cache) >= slots:
                cache.popitem(last=False)
            cache[key] = True
    return misses


def belady_misses(accesses, slots):
    """Evict the resident key used farthest in the future (lazy max-heap over next uses)."""
    nxt = {}
    next_use = [0] * len(accesses)
    for i in range(len(accesses) - 1, -1, -1):
        next_use[i] = nxt.get(accesses[i], len(accesses))
        nxt[accesses[i]] = i
    cache, heap, misses = {}, [], 0
    for i, key in enumerate(accesses):
        if key in cache:
            cache[key] = next_use[i]
        else:
            misses += 1
            if len(cache) >= slots:
                while True:
                    use, victim = heapq.heappop(heap)
                    if cache.get(victim) == -use:
                        del cache[victim]
                        break
            cache[key] = next_use[i]
        heapq.heappush(heap, (-next_use[i], key))
    return misses


def measured_misses(path):
    last = None
    for line in open(path, errors='replace'):
        m = re.search(r'streaming expert cache .*misses=(\d+)', line)
        if m:
            last = int(m[1])
    if last is None:
        raise SystemExit(f'{path}: no "streaming expert cache" report')
    return last


def self_test():
    a = [(0, e) for e in (1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5)]
    assert (lru_misses(a, 3), belady_misses(a, 3)) == (10, 7), (lru_misses(a, 3), belady_misses(a, 3))
    assert lru_misses(a, 5) == belady_misses(a, 5) == 5
    assert belady_misses(a, 2) <= lru_misses(a, 2)
    print('self-test ok')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--trace')
    p.add_argument('--moe-layers', type=int)
    p.add_argument('--slots', type=int)
    p.add_argument('--stderr', help="the run's bench stderr, for the measured misses")
    p.add_argument('--self-test', action='store_true')
    args = p.parse_args(argv)
    if args.self_test:
        return self_test()
    if not (args.trace and args.moe_layers and args.slots):
        p.error('--trace, --moe-layers and --slots are required')
    accesses = read_trace(args.trace, args.moe_layers)
    tokens = len(accesses) // (6 * args.moe_layers)
    print(f'{tokens} tokens, {len(accesses)} lookups over {args.moe_layers} MoE layers, '
          f'{len(set(accesses))} distinct (layer, expert) pairs, {args.slots} slots')
    print(f'LRU misses     {lru_misses(accesses, args.slots)}')
    print(f'Belady misses  {belady_misses(accesses, args.slots)}')
    if args.stderr:
        print(f'measured misses {measured_misses(args.stderr)}')


if __name__ == '__main__':
    raise SystemExit(main())
