#!/usr/bin/env python3
"""A/B harness: two build trees of sf-ds4-1flash on one GGUF, under SSD streaming.

    python3 speed-bench/ab_bench.py --a ../sf-ds4-1flash-base --b . --kinds decode

Each tree's bench runs from its own directory (kernels load from metal/ in the cwd), in
streaming mode with a fixed expert cache and a fixed allocated context. Runs are warm-up
(A, B per kind), A B B A quads while the budget lasts, then the guards once. The verdict
per metric is the median gain over valid pairs with a bootstrap 95% interval, gated on
identical tokens (and bit-identical logits with --bitwise). See speed-bench/README.md.
"""

import argparse
import csv
import fcntl
import hashlib
import importlib.util
import io
import json
import os
import random
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = 'sf-ds4-1flash-bench'
LOCK = '/tmp/sf-ds4-1flash.lock'
PROMPT = 'speed-bench/promessi_sposi.txt'
MAX_BUDGET = 3600
BIG_RSS_KIB = 8 << 20
ACTIVE_PERCENT = 50.0
# The fixed streaming configuration of every run (design D3): the cache flag is a total
# from which the loader takes the prefill headroom; the window is what must come out.
CACHE_FLAG = '82GB'
CACHE_WINDOW = (74.5, 75.5)
CTX_ALLOC = 32768
STREAMING = ['--ssd-streaming', '--ssd-streaming-cache-experts', CACHE_FLAG, '--ctx-alloc', str(CTX_ALLOC)]

KINDS = {
    'decode': {'frontiers': (2048, 8192), 'gen': 256},
    'cold-2500': {'frontiers': (2500,), 'gen': 16},
    'cold-3500': {'frontiers': (3500,), 'gen': 16},
    'cold-5000': {'frontiers': (5000,), 'gen': 16},
    'cold-7500': {'frontiers': (7500,), 'gen': 16},
    'cold-10000': {'frontiers': (10000,), 'gen': 16},
    'append': {'frontiers': (5000, 5300, 6800), 'gen': 16},
    'guard-16896': {'frontiers': (16896,), 'gen': 16},
    'guard-decode': {'frontiers': (8192,), 'gen': 2500},
}
GROUPS = {
    'cold': [k for k in KINDS if k.startswith('cold-')],
    'guards': [k for k in KINDS if k.startswith('guard-')],
    'all': [k for k in KINDS if not k.startswith('guard-')],
}
# Seconds reserved for each guard's single A, B pair (design D6); measured in task 6.2.
GUARD_SECONDS = {'guard-16896': 80.0, 'guard-decode': 180.0}
# Headline metrics: the record row's cells, in order.
RECORD = ['decode 2048', 'decode 8192', 'ttft 2500', 'ttft 3500', 'ttft 5000', 'ttft 7500', 'ttft 10000',
          'append +300', 'append +1500', 'guard ttft 16896', 'guard decode 2500', 'e2e']
RECORD_LEAD = ['step', 'date', 'B commit', 'model', 'valid pairs', 'correctness']
# The typical mix of the end-to-end estimate (design D9).
E2E_PROMPTS = (2500, 3500, 5000, 7500, 10000)
E2E_ANSWERS = (200, 1000, 2000)
# Values used for both sides of the estimate when a kind was not run (design D9): the medians
# of the all-kinds A/A of 2026-09-27 (speed-bench/perf-record.md, Situation 0).
REFERENCE = {'decode 2048': 16.5, 'decode 8192': 16.9, 'ttft 2500': 45.5, 'ttft 3500': 36.8,
             'ttft 5000': 78.2, 'ttft 7500': 47.1, 'ttft 10000': 44.0}
MACTOP = {'time': ('timestamp',), 'freq': ('soc_metrics', 'gpu_freq_mhz'),
          'active': ('soc_metrics', 'gpu_active'), 'power': ('soc_metrics', 'gpu_power'),
          'temp': ('soc_metrics', 'gpu_temp'), 'thermal': ('thermal_state',)}
IDS = re.compile(r'^ds4-bench: gen\[ctx=(\d+)\] token ids:(.*)$', re.M)
CTX = re.compile(r'^ds4-bench: context buffers .*\(ctx=(\d+),', re.M)
LOADER = re.compile(r'^ds4: \w+ SSD streaming cache target .*\+ ([0-9.]+) GiB dynamic cache '
                    r'\((\d+) experts, ([0-9.]+) MiB each\)', re.M)
REPORT = re.compile(r'^ds4: Metal memory after frontier (\d+):', re.M)
CACHE = re.compile(r'^ds4:\s+streaming expert cache (.*)$', re.M)


class Stop(Exception):
    """Ends the harness with an exit status: 1 correctness or run failure, 2 refused or aborted."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


# --- inputs -----------------------------------------------------------------

def child_env(pairs, environ=None):
    env = {k: v for k, v in (os.environ if environ is None else environ).items()
           if not k.startswith('DS4_')}
    for pair in pairs:
        key, sep, value = pair.partition('=')
        if not sep or not key:
            raise Stop(2, f'--env {pair}: expected KEY=VALUE')
        env[key] = value
    return env


def build_envs(args):
    """A gets --env, B gets --env then --b-env."""
    return {'A': child_env(args.env), 'B': child_env(args.env + args.b_env)}


def model_label(path):
    """The file name, or the Hub file name for the default link (deepseek-v4.1-flash.gguf -> gguf/<component>)."""
    if path.is_symlink() and os.readlink(path).endswith('.gguf'):
        return Path(os.readlink(path)).name
    return path.name


def git(tree, *args):
    r = subprocess.run(['git', '-C', str(tree), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ''


def prepare_tree(path):
    tree = Path(path).resolve()
    if not (tree / 'Makefile').is_file() or not (tree / 'metal').is_dir():
        raise Stop(2, f'{path}: not a build tree (needs a Makefile and metal/)')
    r = subprocess.run(['make', '-C', str(tree), '-j8', BENCH], capture_output=True, text=True)
    if r.returncode != 0:
        raise Stop(2, f'{path}: make {BENCH} failed:\n{r.stdout[-2000:]}{r.stderr[-2000:]}')
    return {'path': tree, 'commit': git(tree, 'rev-parse', '--short', 'HEAD') or '?',
            'branch': git(tree, 'rev-parse', '--abbrev-ref', 'HEAD') or '?',
            'dirty': bool(git(tree, 'status', '--porcelain'))}


def select_kinds(text, what):
    out = []
    for name in (text or '').split(','):
        if not name:
            continue
        for kind in GROUPS.get(name, [name]):
            if kind not in KINDS:
                raise Stop(2, f'{what} {name}: choose kinds from {", ".join(KINDS)} or groups {", ".join(GROUPS)}')
            if kind not in out:
                out.append(kind)
    return out


# --- mactop -----------------------------------------------------------------

def parse_mactop(text):
    """mactop --headless streams one JSON object per line, prefixed by '[' or ','."""
    lines = [line.strip().lstrip('[,').rstrip(']').strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    samples = []
    for i, line in enumerate(lines):
        try:
            samples.append(json.loads(line))
        except ValueError:
            if i != len(lines) - 1:  # only the line being written at termination may be partial
                raise Stop(2, f'mactop log line {i + 1} is not JSON')
    return samples


def reading(sample, version='?'):
    r = {}
    for name, keys in MACTOP.items():
        value = sample
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                raise Stop(2, f'mactop {version} output has no {".".join(keys)}')
            value = value[key]
        r[name] = value
    r['time'] = datetime.fromisoformat(r['time']).timestamp()
    return r


def mactop_version():
    try:
        return subprocess.run(['mactop', '--version'], capture_output=True, text=True).stdout.split()[-1]
    except (FileNotFoundError, IndexError):
        return '?'


def preflight(max_temp):
    try:
        out = subprocess.run(['mactop', '--headless', '--count', '1', '--interval', '1000'],
                             capture_output=True, text=True, timeout=30).stdout
    except FileNotFoundError:
        raise Stop(2, 'preflight refused: mactop is required (brew install mactop); '
                      'the harness does not run without the GPU log')
    samples = parse_mactop(out)
    if not samples:
        raise Stop(2, 'preflight refused: mactop returned no reading')
    sample = samples[0]
    r = reading(sample, mactop_version())
    problems = []
    battery = sample.get('battery', {})
    if battery.get('present', False) and not battery.get('on_ac_power', False):
        problems.append('not on AC power: connect the charger')
    if r['thermal'] != 'Nominal':
        problems.append(f'thermal state is {r["thermal"]}, not Nominal')
    if r['temp'] >= max_temp:
        problems.append(f'GPU temperature {r["temp"]:.1f} C is not below {max_temp:g} C')
    try:
        with open(LOCK, 'a') as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
    except BlockingIOError:
        problems.append(f'{LOCK} is held: another sf-ds4-1flash process is running')
    ps = subprocess.run(['ps', '-axo', 'pid=,rss=,comm='], capture_output=True, text=True).stdout
    for line in ps.splitlines():
        pid, rss, comm = line.split(None, 2)
        if int(pid) != os.getpid() and int(rss) >= BIG_RSS_KIB:
            problems.append(f'pid {pid} ({comm}) has {int(rss) / 1048576:.1f} GiB resident')
    if problems:
        raise Stop(2, 'preflight refused:\n  ' + '\n  '.join(problems))
    return sample


class Monitor:
    def __init__(self, path):
        self.path = path
        self.file = open(path, 'w')
        self.proc = subprocess.Popen(['mactop', '--headless', '--count', '0', '--interval', '1000'],
                                     stdout=self.file, stderr=subprocess.DEVNULL)

    def check(self):
        if self.proc.poll() is not None:
            raise Stop(2, f'mactop exited during the run (status {self.proc.returncode}); the GPU log is incomplete')

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        self.file.close()

    def readings(self, version):
        return [reading(s, version) for s in parse_mactop(Path(self.path).read_text())]


# --- one run ----------------------------------------------------------------

def bench_cmd(tree, kind, model, csv_path, logits_dir=None, extra=()):
    k = KINDS[kind]
    cmd = [str(tree / BENCH), '-m', str(model), '--prompt-file', str(ROOT / PROMPT), *STREAMING,
           '--frontiers', ','.join(map(str, k['frontiers'])), '-n', str(k['gen']),
           '--show-output', '--cache-stats', '--csv', str(csv_path)]
    if logits_dir:
        cmd += ['--dump-frontier-logits-dir', str(logits_dir)]
    return cmd + list(extra)


def unit(metric):
    """Every ratio is printed as a gain: A/B for times, B/A for rates (design D9)."""
    if metric.startswith('first token'):
        return 'ms'
    if metric.split()[0] in ('decode', 'guard') and 'decode' in metric:
        return 't/s'
    return 's'


def seconds(row):
    return int(row['prefill_tokens']) / float(row['prefill_tps'])


def metrics(kind, rows):
    """Metric name -> value of one run, from its per-frontier CSV rows (design D9)."""
    fs = KINDS[kind]['frontiers']
    m = {}
    if kind in ('decode', 'guard-decode'):
        for f in fs:
            m['guard decode 2500' if kind == 'guard-decode' else f'decode {f}'] = float(rows[f]['gen_steady_tps'])
            m[f'first token {f} ms'] = float(rows[f]['gen_first_ms'])
    elif kind == 'append':
        m['prefill 5000'] = seconds(rows[5000])
        m['append +300'] = seconds(rows[5300])
        m['append +1500'] = seconds(rows[6800])
    else:
        f = fs[0]
        m[f'guard ttft {f}' if kind.startswith('guard-') else f'ttft {f}'] = seconds(rows[f])
        m[f'first token {f} ms'] = float(rows[f]['gen_first_ms'])
    return m


def parse_cache_reports(err_text, kind):
    """Per-frontier deltas of the expert-cache counters from the bench's --cache-stats reports."""
    heads = list(REPORT.finditer(err_text))
    totals = {}
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(err_text)
        m = CACHE.search(err_text, h.end(), end)
        if not m:
            raise Stop(1, f'{kind}: the cache report after frontier {h[1]} has no "streaming expert cache" line')
        fields = dict(re.findall(r'(\w+)=([0-9.]+)', m[1]))
        missing = [f for f in ('hits', 'misses') if f not in fields]
        if missing:
            raise Stop(1, f'{kind}: cache report line lacks {", ".join(missing)}: {m[0].strip()}')
        totals[int(h[1])] = {'hits': int(fields['hits']), 'misses': int(fields['misses']),
                             'pread_gib': float(fields.get('miss_pread', 0.0)),
                             'pread_ms': float(fields.get('pread_ms', 0.0))}
    deltas, previous = {}, {'hits': 0, 'misses': 0, 'pread_gib': 0.0, 'pread_ms': 0.0}
    for f in sorted(totals):
        deltas[f] = {k: totals[f][k] - previous[k] for k in previous}
        deltas[f]['lookups'] = deltas[f]['hits'] + deltas[f]['misses']
        previous = totals[f]
    return deltas


def parse_loader(err_text, kind):
    """(dynamic cache GiB, expert slots) of the loader's cache line, checked against the window."""
    m = LOADER.search(err_text)
    if not m:
        raise Stop(2, f'{kind}: the loader printed no SSD streaming cache line (is --ssd-streaming on?)')
    gib, slots = float(m[1]), int(m[2])
    if not CACHE_WINDOW[0] <= gib <= CACHE_WINDOW[1]:
        raise Stop(2, f'{kind}: dynamic expert cache {gib} GiB is outside {CACHE_WINDOW[0]}-{CACHE_WINDOW[1]} GiB: '
                      f'{m[0].strip()}')
    c = CTX.search(err_text)
    if not c or int(c[1]) != CTX_ALLOC:
        raise Stop(2, f'{kind}: allocated context is not {CTX_ALLOC}: {c[0].strip() if c else "no context line"}')
    return gib, slots


def parse_run(csv_text, err_text, kind):
    frontiers = list(KINDS[kind]['frontiers'])
    rows = {int(r['ctx_tokens']): r for r in csv.DictReader(io.StringIO(csv_text))}
    tokens = {int(m[1]): [int(t) for t in m[2].split()] for m in IDS.finditer(err_text)}
    cache = parse_cache_reports(err_text, kind)
    missing = [what for what, got in (('CSV rows', rows), ('token ids', tokens), ('cache reports', cache))
               if sorted(got) != frontiers]
    if missing:
        raise Stop(1, f'{kind}: bench output lacks {", ".join(missing)} for frontiers {frontiers}')
    gib, slots = parse_loader(err_text, kind)
    return {'rows': rows, 'tokens': tokens, 'cache': cache, 'metrics': metrics(kind, rows),
            'cache_gib': gib, 'cache_slots': slots}


def bench_args(args, build):
    """Extra bench arguments of one build: the shared ones, then B's own."""
    return list(args.bench_arg) + (list(args.b_bench_arg) if build == 'B' else [])


def run_bench(n, build, tree, kind, model, env, out, phase, bitwise, extra=()):
    stem = out / 'logs' / f'{n:02d}-{build}-{kind}'
    logits_dir = out / 'logits' / f'{build}-{kind}' if phase == 'warm-up' and bitwise else None
    if logits_dir:
        logits_dir.mkdir(parents=True)
    cmd = bench_cmd(tree, kind, model, f'{stem}.csv', logits_dir, extra)
    start = time.time()
    with open(f'{stem}.err', 'wb') as err:
        rc = subprocess.run(cmd, cwd=tree, env=env, stdout=subprocess.DEVNULL, stderr=err).returncode
    end = time.time()
    if rc != 0:
        raise Stop(1, f'{build} {kind} run failed (exit {rc}); see {stem}.err')
    run = parse_run(Path(f'{stem}.csv').read_text(), Path(f'{stem}.err').read_text(errors='replace'), kind)
    run.update(n=n, build=build, kind=kind, phase=phase, warmup=phase in ('warm-up', 'preheat'),
               start=start, end=end, duration=end - start, logits=logits_dir, note='')
    return run


# --- correctness -------------------------------------------------------------

def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def check_tokens(run, ref):
    for f, ids in ref['tokens'].items():
        pos = first_diff(ids, run['tokens'].get(f, []))
        if pos is not None:
            what = ('FAIL: baseline is nondeterministic, A runs differ' if run['build'] == 'A'
                    else 'FAIL: B differs from A')
            return f'{what}: {run["kind"]}, frontier {f}, token index {pos}'
    return None


def check_cache_config(run, ref):
    if run['cache_slots'] != ref['cache_slots']:
        raise Stop(2, f'{run["build"]} {run["kind"]}: expert cache has {run["cache_slots"]} slots, '
                      f'the first run had {ref["cache_slots"]}')


def load_logits_validator():
    path = ROOT / 'gguf-tools/quality-testing/compare_frontier_logits.py'
    spec = importlib.util.spec_from_file_location('compare_frontier_logits', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_logits(dir_a, dir_b, frontiers):
    """Bit-exact comparison of every prefill and decode dump, strictly validated."""
    cfl = load_logits_validator()
    # frontier order, prefill before decode, so the first difference says where drift starts
    names = sorted((p.name for p in dir_a.iterdir()), key=lambda n: (n.split('.')[0], '.decode.' in n))
    if not names or sorted(names) != sorted(p.name for p in dir_b.iterdir()):
        return f'FAIL bitwise: A and B dumped different files ({dir_a.name})'
    meta = json.loads((dir_a / names[0]).read_text())
    try:
        expected = cfl.validate_expectations(list(frontiers), meta['ctx'], meta['model'], meta['backend'],
                                             meta['quality'], meta['quant_bits'], meta['vocab'])
        previous = dict(zip(frontiers, (0,) + tuple(frontiers[:-1])))
        for name in names:
            f = int(re.match(r'frontier_(\d+)', name)[1])
            _, a, _ = cfl.validate_dump(dir_a / name, expected, f, previous[f])
            _, b, _ = cfl.validate_dump(dir_b / name, expected, f, previous[f])
            if a != b:
                index = next(i for i in range(0, len(a), 4) if a[i:i + 4] != b[i:i + 4]) // 4
                return f'FAIL bitwise: {name}: frontier {f}, vocabulary index {index}'
    except (cfl.InvalidDump, KeyError, OSError) as exc:
        return f'FAIL bitwise: {dir_a.name}: {exc}'
    return None


# --- schedule ----------------------------------------------------------------

def schedule(kinds, guards, deadline, runner, check, runs, preheat_until=0.0, clock=time.time):
    """Warm-up (A, B per kind), preheat, A B B A quads while they fit, then each guard once.

    runner(build, kind, phase) returns a run, appended to runs; check(runs) raises Stop on a
    correctness failure. A quad is predicted from the latest duration per build and kind, plus
    10%, and must end before the deadline minus the guards' reserve (design D6).
    """
    for kind in kinds:
        for build in 'AB':
            runs.append(runner(build, kind, 'warm-up'))
            check(runs)
    while kinds and clock() < preheat_until:
        runs.append(runner('AB'[len(runs) % 2], kinds[0], 'preheat'))
        check(runs)
    latest = {(r['build'], r['kind']): r['duration'] for r in runs}
    reserve = sum(2 * GUARD_SECONDS.get(g, 120.0) for g in guards)
    fits = True
    while fits and kinds:
        for kind in kinds:
            if clock() + 1.1 * 2 * (latest['A', kind] + latest['B', kind]) > deadline - reserve:
                fits = False
                break
            for build in 'ABBA':
                run = runner(build, kind, 'timed')
                runs.append(run)
                latest[build, kind] = run['duration']
                check(runs)
    for kind in guards:
        for build in 'AB':
            runs.append(runner(build, kind, 'guard'))
            check(runs)


# --- analysis ----------------------------------------------------------------

def judge(timed, readings):
    for run in timed:
        window = [x for x in readings if run['start'] - 1 <= x['time'] <= run['end']]
        active = [x['freq'] for x in window if x['active'] >= ACTIVE_PERCENT]
        run['freq'] = statistics.median(active) if len(active) >= 2 else None
        run['temp'] = max((x['temp'] for x in window), default=None)
        run['power'] = statistics.median([x['power'] for x in window]) if window else None
        run['thermal'] = sorted({x['thermal'] for x in window})
        if run['freq'] is None:
            run['note'] = 'unjudged: fewer than two active GPU samples'


def pairs(timed, kind):
    """(A, B) pairs of a kind: both halves of every A B B A quad, or a guard's single A, B."""
    runs = [r for r in timed if r['kind'] == kind and r['phase'] == 'timed']
    out = []
    for q in range(0, len(runs) - 3, 4):
        a1, b1, b2, a2 = runs[q:q + 4]
        out += [(a1, b1), (a2, b2)]
    guard = [r for r in timed if r['kind'] == kind and r['phase'] == 'guard']
    if len(guard) == 2 and [r['build'] for r in guard] == ['A', 'B']:
        out.append(tuple(guard))
    return out


def drop_disturbed(timed, kinds, fraction):
    """Drop the pair of any run whose GPU ran below fraction of its kind's median frequency: an
    external disturbance (another GPU user, a deeper throttle). The median is per kind because a
    sweep-heavy kind idles the GPU between layers and runs at a lower frequency by nature."""
    for kind in kinds:
        freqs = [r['freq'] for r in timed if r['kind'] == kind and r.get('freq')]
        if not freqs:
            continue
        median = statistics.median(freqs)
        floor = fraction * median
        for a, b in pairs(timed, kind):
            low = [r for r in (a, b) if r.get('freq') and r['freq'] < floor]
            if low:
                a['flag'] = b['flag'] = (f'pair dropped: run {low[0]["n"]} at {low[0]["freq"]:.0f} MHz, '
                                         f'below {fraction:.0%} of the kind\'s {median:.0f} MHz median')


def cache_drift(a, b, tolerance):
    """The first frontier whose expert-cache counters differ beyond the tolerance, or None (design D7)."""
    for f in sorted(a['cache']):
        x, y = a['cache'][f], b['cache'][f]
        lookups = max(x['lookups'], y['lookups'])
        for what in ('hits', 'misses'):
            if abs(x[what] - y[what]) > tolerance * lookups:
                return f'frontier {f}: {what} A {x[what]} B {y[what]} over {lookups} lookups'
        top = max(x['pread_gib'], y['pread_gib'])
        if top and abs(x['pread_gib'] - y['pread_gib']) > 0.05 * top:
            return f'frontier {f}: bytes read A {x["pread_gib"]:.2f} GiB B {y["pread_gib"]:.2f} GiB'
    return None


def drop_cache_drift(timed, kinds, tolerance, policy_change):
    for kind in kinds:
        for a, b in pairs(timed, kind):
            drift = cache_drift(a, b, tolerance)
            if drift and policy_change:
                a['note'] = b['note'] = f'cache state differs (declared policy change): {drift}'
            elif drift and not a.get('flag'):
                a['flag'] = b['flag'] = f'pair dropped: cache state differs, {drift}'


def gain(a, b, metric):
    return a / b if unit(metric) in ('s', 'ms') else b / a


def bootstrap_ci(values, resamples=10000, seed=1):
    """95% CI of the median by bootstrap (fixed seed); (None, None) below two values."""
    if len(values) < 2:
        return None, None
    rng = random.Random(seed)
    bs = sorted(statistics.median(rng.choices(values, k=len(values))) for _ in range(resamples))
    return bs[resamples // 40], bs[resamples - resamples // 40]


def verdict(runs, kinds, guards):
    """Per kind and metric: A and B medians over valid pairs, the median gain, its interval, n."""
    timed = [r for r in runs if not r['warmup']]
    table = []
    for kind in kinds + [g for g in guards if g not in kinds]:
        valid = [(a, b) for a, b in pairs(timed, kind) if not a.get('flag')]
        names = next((r['metrics'] for r in runs if r['kind'] == kind), {})
        for name in names:
            both = [(a['metrics'][name], b['metrics'][name]) for a, b in valid]
            gains = [gain(x, y, name) for x, y in both]
            lo, hi = bootstrap_ci(gains)
            table.append({'kind': kind, 'metric': name, 'headline': name in RECORD, 'guard': kind not in kinds,
                          'a': statistics.median([x for x, _ in both]) if both else None,
                          'b': statistics.median([y for _, y in both]) if both else None,
                          'gain': statistics.median(gains) if gains else None, 'lo': lo, 'hi': hi, 'n': len(gains)})
    return table


def e2e_estimate(table):
    """Typical-mix request time for A and B from the medians; unmeasured metrics take REFERENCE
    on both sides (design D9). Returns (a seconds, b seconds, gain, unmeasured names)."""
    cells = {t['metric']: t for t in table if t['a'] is not None}
    needed = ['decode 2048', 'decode 8192'] + [f'ttft {p}' for p in E2E_PROMPTS]
    unmeasured = [name for name in needed if name not in cells]
    sides = {}
    for side in 'ab':
        v = {name: cells[name][side] if name in cells else REFERENCE[name] for name in needed}
        total = 0.0
        for p in E2E_PROMPTS:
            rate = v['decode 2048'] if p <= 5000 else v['decode 8192']
            total += sum(v[f'ttft {p}'] + n / rate for n in E2E_ANSWERS)
        sides[side] = total / (len(E2E_PROMPTS) * len(E2E_ANSWERS))
    return sides['a'], sides['b'], sides['a'] / sides['b'], unmeasured


def pct(ratio):
    return f'{(ratio - 1) * 100:+.1f}%'


def num(value):
    return '-' if value is None else f'{value:.2f}' if value < 10 else f'{value:.1f}'


def record_header():
    names = RECORD_LEAD + RECORD
    return '| ' + ' | '.join(names) + ' |\n|' + '---|' * len(names)


def record_row(step, date, commit, model, valid_pairs, correctness, table, e2e):
    cells = {t['metric']: t for t in table}
    if e2e is not None:
        cells['e2e'] = {'b': e2e[1], 'gain': e2e[2]}
    row = [step, date, commit, model, str(valid_pairs), correctness]
    for key in RECORD:
        t = cells.get(key)
        row.append(f'{num(t["b"])} ({pct(t["gain"])})' if t and t.get('gain') is not None else '')
    return '| ' + ' | '.join(row) + ' |'


def summary(ctx, runs, table, status, correctness, e2e):
    timed = [r for r in runs if not r['warmup']]
    kinds, guards = ctx['kinds'], ctx['guards']
    all_pairs = [p for kind in kinds for p in pairs(timed, kind)]
    valid = sum(1 for a, _ in all_pairs if not a.get('flag'))
    lines = [f'sf-ds4-1flash A/B  {ctx["date"]}  {ctx["device"]}  mactop {ctx["mactop"]}']
    for label in 'AB':
        t = ctx[label]
        lines.append(f'{label}  {t["path"]}  {t["commit"]}{" (uncommitted changes)" if t["dirty"] else ""}')
    lines.append(f'model  {ctx["model_name"]} ({ctx["model"]})   env  {" ".join(ctx["env"]) or "-"}'
                 + (f'   B only  {" ".join(ctx["b_env"])}' if ctx.get('b_env') else ''))
    extra = ctx.get('bench_args', {})
    if any(extra.values()):
        lines.append(f'bench args  A {" ".join(extra["A"]) or "-"}   B {" ".join(extra["B"]) or "-"}')
    cache = ctx.get('cache')
    lines.append(f'streaming  cache {CACHE_FLAG} -> dynamic {cache[0] if cache else "?"} GiB, '
                 f'{cache[1] if cache else "?"} expert slots; ctx {CTX_ALLOC}')
    lines.append(f'time  {ctx["elapsed"]:.0f} s of {ctx["budget"]} s   runs {len(runs)} '
                 f'({len(runs) - len(timed)} untimed; first timed run at {ctx["preheat"]:.0f} s)   '
                 f'pairs {valid} valid, {len(all_pairs) - valid} dropped')
    freqs = [r['freq'] for r in timed if r.get('freq')]
    thermal = sorted(set().union(*(r.get('thermal', []) for r in timed)))
    if freqs:
        lines.append(f'GPU  timed runs at {min(freqs):.0f}-{max(freqs):.0f} MHz (median {statistics.median(freqs):.0f}), '
                     f'thermal {"/".join(thermal) or "?"}')
    lines.append(f'correctness  {correctness}')
    lines.append('')
    lines.append(f'{"kind":<13} {"metric":<20} {"A":>8} {"B":>8} {"gain":>7}  {"95% CI":<17} n')
    for t in table:
        ci = f'{pct(t["lo"])} .. {pct(t["hi"])}' if t['lo'] is not None else ''
        mark = '  (guard)' if t['guard'] else '' if t['headline'] else '  (detail)'
        lines.append(f'{t["kind"]:<13} {t["metric"]:<20} {num(t["a"]):>8} {num(t["b"]):>8} '
                     f'{pct(t["gain"]) if t["gain"] is not None else "-":>7}  {ci:<17} {t["n"]}{mark}')
    if e2e is not None:
        a, b, g, unmeasured = e2e
        lines.append(f'{"mix":<13} {"e2e":<20} {num(a):>8} {num(b):>8} {pct(g):>7}  {"":<17} -  (estimate'
                     + (f'; unmeasured, held at reference: {", ".join(unmeasured)})' if unmeasured else ')'))
    hit_rates = cache_hit_rates(timed, kinds + guards)
    if hit_rates:
        lines += [''] + [f'cache {kind}: hit rate A {a:.3f} B {b:.3f}' for kind, (a, b) in hit_rates.items()]
    notes = [f'run {r["n"]} {r["build"]} {r["kind"]}: {r.get("flag") or r["note"]}'
             for r in timed if r.get('flag') or r['note']]
    if notes:
        lines += [''] + notes
    thin = [f'{t["kind"]} {t["metric"]}' for t in table if t['headline'] and not t['guard'] and t['n'] < 2]
    if thin and status == 'PASS':
        lines += ['', f'INCONCLUSIVE: fewer than two valid pairs for {", ".join(thin)}']
    if any(ctx.get('bench_args', {}).values()) or ctx.get('b_env'):
        lines += ['', 'record row: none (bench arguments or a B-only environment make the figures '
                      'incomparable with the record)']
    else:
        lines += ['', 'record row:', record_row(ctx['B']['branch'], ctx['date'][:10], ctx['B']['commit'],
                                                 ctx['model_name'], valid, status, table, e2e)]
    return '\n'.join(lines), bool(thin)


def cache_hit_rates(timed, kinds):
    out = {}
    for kind in kinds:
        rates = {}
        for build in 'AB':
            c = [x for r in timed if r['kind'] == kind and r['build'] == build for x in r['cache'].values()]
            lookups = sum(x['lookups'] for x in c)
            rates[build] = sum(x['hits'] for x in c) / lookups if lookups else None
        if rates['A'] is not None and rates['B'] is not None:
            out[kind] = (rates['A'], rates['B'])
    return out


def write_samples(path, runs):
    fields = ['run', 'build', 'kind', 'phase', 'frontier', 'prefill_tokens', 'prefill_tps', 'gen_tokens', 'gen_tps',
              'gen_first_ms', 'gen_steady_tokens', 'gen_steady_tps', 'cache_hits', 'cache_misses',
              'cache_pread_gib', 'cache_pread_ms', 'gpu_freq_mhz', 'gpu_temp_max', 'gpu_power_median',
              'note', 'tokens_sha256']
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        for r in runs:
            if r['warmup']:
                continue
            for frontier, row in sorted(r['rows'].items()):
                c = r['cache'][frontier]
                ids = ' '.join(map(str, r['tokens'][frontier])).encode()
                w.writerow({'run': r['n'], 'build': r['build'], 'kind': r['kind'], 'phase': r['phase'],
                            'frontier': frontier, 'prefill_tokens': row['prefill_tokens'],
                            'prefill_tps': row['prefill_tps'], 'gen_tokens': row['gen_tokens'],
                            'gen_tps': row['gen_tps'], 'gen_first_ms': row['gen_first_ms'],
                            'gen_steady_tokens': row['gen_steady_tokens'], 'gen_steady_tps': row['gen_steady_tps'],
                            'cache_hits': c['hits'], 'cache_misses': c['misses'],
                            'cache_pread_gib': f'{c["pread_gib"]:.2f}', 'cache_pread_ms': f'{c["pread_ms"]:.3f}',
                            'gpu_freq_mhz': r.get('freq') or '', 'gpu_temp_max': r.get('temp') or '',
                            'gpu_power_median': r.get('power') or '', 'note': r.get('flag') or r['note'],
                            'tokens_sha256': hashlib.sha256(ids).hexdigest()})


# --- main --------------------------------------------------------------------

def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--a', required=True, help='baseline build tree')
    p.add_argument('--b', required=True, help='candidate build tree (may equal --a for an A/A run)')
    p.add_argument('-m', '--model', default=str(ROOT / 'deepseek-v4.1-flash.gguf'))
    p.add_argument('--kinds', help=f'comma list of kinds ({", ".join(KINDS)}) or groups ({", ".join(GROUPS)}), '
                                   'measured in A B B A quads')
    p.add_argument('--guards', help='comma list of kinds run once as one A, B pair after the quads')
    p.add_argument('--budget', type=int, default=1800, help=f'wall-clock seconds, at most {MAX_BUDGET}')
    p.add_argument('--bitwise', action='store_true', help='also require bit-identical logits')
    p.add_argument('--env', action='append', default=[], metavar='KEY=VALUE', help='set for both builds')
    p.add_argument('--b-env', action='append', default=[], metavar='KEY=VALUE',
                   help='set for B only, on top of --env (repeatable): measures a switch on one tree')
    p.add_argument('--bench-arg', action='append', default=[], metavar='ARG',
                   help='extra bench argument for both builds (repeatable; write --bench-arg=--flag)')
    p.add_argument('--b-bench-arg', action='append', default=[], metavar='ARG',
                   help='extra bench argument for B only (repeatable)')
    p.add_argument('--max-gpu-temp', type=float, default=60.0)
    p.add_argument('--min-freq-of-median', type=float, default=0.90,
                   help="drop a pair when one of its runs ran below this fraction of the timed runs' "
                        'median GPU frequency (an external disturbance)')
    p.add_argument('--preheat', type=float, default=0.0,
                   help='seconds of load before the timed rounds (at most half the budget)')
    p.add_argument('--cache-tolerance', type=float, default=0.01,
                   help="drop a pair whose hit or miss counts differ by more than this fraction of the "
                        "frontier's lookups")
    p.add_argument('--cache-policy-change', action='store_true',
                   help='the candidate changes the expert-cache policy: keep pairs whose cache state differs')
    p.add_argument('--out', help='output directory (default $TMPDIR/sf-ds4-1flash-ab/<UTC time>)')
    args = p.parse_args(argv)
    args.kinds = select_kinds(args.kinds, '--kinds')
    args.guards = select_kinds(args.guards, '--guards')
    if not args.kinds and not args.guards:
        raise Stop(2, f'select kinds with --kinds or --guards: {", ".join(KINDS)}; groups {", ".join(GROUPS)}')
    if not 0 < args.budget <= MAX_BUDGET:
        raise Stop(2, f'--budget {args.budget}: must be between 1 and {MAX_BUDGET} seconds')
    return args


def main(argv=None):
    begin = time.time()
    try:
        args = parse_args(argv)
        envs = build_envs(args)
        model = Path(os.path.abspath(args.model))
        if not model.is_file():
            raise Stop(2, f'{args.model}: model not found')
        trees = {'A': prepare_tree(args.a), 'B': prepare_tree(args.b)}
        now = datetime.now(timezone.utc)
        out = Path(args.out) if args.out else (Path(os.environ.get('TMPDIR', '/tmp')) / 'sf-ds4-1flash-ab'
                                               / now.strftime('%Y%m%dT%H%M%SZ'))
        (out / 'logs').mkdir(parents=True)
        sample = preflight(args.max_gpu_temp)
    except Stop as stop:
        print(f'ab_bench: {stop}', file=sys.stderr)
        return stop.code

    version = mactop_version()
    ctx = {'date': now.strftime('%Y-%m-%d %H:%M UTC'), 'device': sample.get('system_info', {}).get('name', '?'),
           'mactop': version, 'A': trees['A'], 'B': trees['B'], 'model': str(model),
           'model_name': model_label(Path(args.model)), 'env': args.env, 'b_env': args.b_env,
           'budget': args.budget,
           'kinds': args.kinds, 'guards': args.guards, 'bench_args': {b: bench_args(args, b) for b in ('A', 'B')}}
    counter = iter(range(1, 10_000))
    refs = {}
    runs = []

    def runner(build, kind, phase):
        run = run_bench(next(counter), build, trees[build]['path'], kind, model, envs[build], out, phase, args.bitwise,
                        bench_args(args, build))
        monitor.check()
        if runs:
            check_cache_config(run, runs[0])
        refs.setdefault(kind, run)  # the first run of a kind is A's warm-up (or a guard's A run)
        print(f'  run {run["n"]:2d} {build} {kind:<12} {phase:<7} {run["duration"]:.1f} s',
              file=sys.stderr, flush=True)
        return run

    def check(done):
        last = done[-1]
        problem = check_tokens(last, refs[last['kind']])
        if not problem and args.bitwise and last['phase'] == 'warm-up' and last['build'] == 'B':
            problem = check_logits(out / 'logits' / f'A-{last["kind"]}', out / 'logits' / f'B-{last["kind"]}',
                                   KINDS[last['kind']]['frontiers'])
        if problem:
            raise Stop(1, problem)

    status, correctness = 'PASS', 'PASS (tokens' + ('; bitwise)' if args.bitwise else ')')
    monitor = Monitor(out / 'gpu.json')
    try:
        load = time.time()
        schedule(args.kinds, args.guards, begin + args.budget, runner, check, runs,
                 min(load + args.preheat, begin + args.budget / 2))
    except Stop as stop:
        if stop.code != 1 or not runs:
            print(f'ab_bench: {stop}', file=sys.stderr)
            return stop.code
        status, correctness = 'FAIL', str(stop)
    finally:
        monitor.stop()
    ctx['elapsed'] = time.time() - begin
    ctx['cache'] = (runs[0]['cache_gib'], runs[0]['cache_slots']) if runs else None
    timed = [r for r in runs if not r['warmup']]
    ctx['preheat'] = (timed[0]['start'] - load) if timed else ctx['elapsed']
    judge(timed, monitor.readings(version))
    drop_disturbed(timed, args.kinds + args.guards, args.min_freq_of_median)
    drop_cache_drift(timed, args.kinds + args.guards, args.cache_tolerance, args.cache_policy_change)
    table = verdict(runs, args.kinds, args.guards)
    e2e = e2e_estimate(table) if table else None
    text, thin = summary(ctx, runs, table, status, correctness, e2e)
    write_samples(out / 'samples.csv', runs)
    (out / 'summary.txt').write_text(text + '\n')
    print(text)
    print(f'\noutput: {out}', file=sys.stderr)
    if status != 'PASS':
        return 1
    return 3 if thin else 0


if __name__ == '__main__':
    raise SystemExit(main())
