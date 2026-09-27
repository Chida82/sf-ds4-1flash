#!/usr/bin/env python3
"""Pooled gains of several ab_bench invocations, with a bootstrap 95% CI.

usage: ab_pool.py <kind> --metric <name> <out dir>...

The metric is one the harness reports for that kind ("decode 8192", "ttft 5000", "append +300",
...), recomputed from each invocation's samples.csv. Pairs the harness dropped are left out, as
in its own verdict. See "Pooling" in speed-bench/README.md.
"""

import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_bench as ab  # noqa: E402


def run_values(out, kind, metric):
    """(build, value, dropped) per timed run of the kind, in run order."""
    runs = {}
    with open(Path(out) / 'samples.csv', newline='') as f:
        for r in csv.DictReader(f):
            if r['kind'] == kind and r['phase'] == 'timed':
                runs.setdefault(int(r['run']), []).append(r)
    values = []
    for n in sorted(runs):
        rows = {int(r['frontier']): r for r in runs[n]}
        m = ab.metrics(kind, rows)
        if metric not in m:
            raise ab.Stop(2, f'{out}: {kind} has no metric {metric}; choose from {", ".join(m)}')
        values.append((runs[n][0]['build'], m[metric], runs[n][0]['note'].startswith('pair dropped')))
    return values


def pooled(kind, metric, dirs):
    """The valid pair gains of every invocation: (A1, B1) and (B2, A2) of each A B B A quad."""
    gains = []
    for out in dirs:
        q = run_values(out, kind, metric)
        if not q or [b for b, _, _ in q] != list('ABBA') * (len(q) // 4):
            raise ab.Stop(2, f'{out}: {kind} timed runs are not in A B B A order')
        for i in range(0, len(q), 4):
            a1, b1, b2, a2 = q[i:i + 4]
            gains += [ab.gain(a[1], b[1], metric) for a, b in ((a1, b1), (a2, b2)) if not (a[2] or b[2])]
    return gains


def main(argv):
    try:
        if len(argv) < 4 or argv[1] != '--metric':
            raise ab.Stop(2, __doc__.split('\n\n')[1])
        kind, metric, dirs = argv[0], argv[2], argv[3:]
        if kind not in ab.KINDS:
            raise ab.Stop(2, f'{kind}: choose a kind from {", ".join(ab.KINDS)}')
        gains = pooled(kind, metric, dirs)
    except (ab.Stop, OSError, ValueError, KeyError) as exc:
        print(f'ab_pool: {exc}', file=sys.stderr)
        return exc.code if isinstance(exc, ab.Stop) else 2
    if not gains:
        print(f'ab_pool: {kind} {metric}: no valid pairs', file=sys.stderr)
        return 1
    lo, hi = ab.bootstrap_ci(gains)
    ci = f'{(lo - 1) * 100:+.2f}..{(hi - 1) * 100:+.2f}' if lo is not None else '-'
    print(f'{kind} {metric} pooled n={len(gains)} median {(statistics.median(gains) - 1) * 100:+.2f}% 95% CI {ci}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
