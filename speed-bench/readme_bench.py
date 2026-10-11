#!/usr/bin/env python3
"""The README speed tables, every column measured in one session, every run from the same temperature.

    python3 speed-bench/readme_bench.py sweep --ds4 <ds4 tree at the merge-base> --replica <copy>
    python3 speed-bench/readme_bench.py shapes --replica <copy>

`sweep` is the "Against ds4" table: upstream's bench sweep (2048 to 32768 doubling, 128 tokens) for
ds4, sf, sf --boost, sf with the second-drive copy, and the copy with --boost. `shapes` is the
second-drive table: the A/B harness's prompt, append and decode shapes for the internal drive
only, the copy, and the copy with --boost.

The protocol (speed-bench/README.md, "README tables"):
- fanboost's own thermal protection must be paused, so a plain run gets the stock Apple fan curve;
- one block per build (ds4, then sf), each after a discarded warm-up run of that build, so every
  measured run follows a run of the same build: the first frontier of a run depends on the page
  cache the previous process left, and ds4 leaves more of the GGUF there than sf;
- the cool-down target is the chip's lowest reading in 60 s of full fans right after the warm-up,
  plus 2 C: a temperature the machine reaches after a hot run, not an idle floor it cannot;
- before every measured run, `fanboost max` until the chip is at or below the target and macOS
  reports thermal pressure Nominal (it stays Moderate or Heavy for up to two minutes after the
  chip has cooled), then `fanboost release` and a wait for the Apple curve;
- inside a block the columns are rotated (A B C, C B A, ...), --runs runs each, and every value is a
  median;
- chip and fans come from `fanboost status` every 2 s, thermal state and GPU clock from mactop.
"""

import argparse
import csv
import json
import os
import re
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_bench as ab  # noqa: E402

SWEEP = ['--ctx-start', '2048', '--ctx-max', '32768', '--step-mul', '2', '--gen-tokens', '128']
FRONTIERS = (2048, 4096, 8192, 16384, 32768)
SHAPES = ['cold-2500', 'cold-3500', 'cold-5000', 'cold-7500', 'cold-10000', 'append', 'decode']
SETTLE_SECONDS = 60
MARGIN_C = 2.0
COOL_TIMEOUT = 420
# Each column: name, tree ('ds4' or 'sf'), extra bench arguments, second-drive copy.
COLUMNS = {
    'sweep': [('ds4', 'ds4', [], False), ('sf', 'sf', [], False), ('sf --boost', 'sf', ['--boost'], False),
              ('sf + copy', 'sf', [], True), ('sf + copy --boost', 'sf', ['--boost'], True)],
    'shapes': [('internal', 'sf', [], False), ('copy', 'sf', [], True), ('copy --boost', 'sf', ['--boost'], True)],
}


# --- fanboost ---------------------------------------------------------------

def fan_status():
    """chip C, fan mode word, fan rpms, thermal-protection line from `fanboost status`."""
    out = subprocess.run(['fanboost', 'status'], capture_output=True, text=True).stdout
    chip = re.search(r'^chip\s+([0-9.]+)', out, re.M)
    mode = re.search(r'^ventole\s+(\S+)', out, re.M)
    thermal = re.search(r'^termica\s+(.*)$', out, re.M)
    if not chip or not mode:
        raise ab.Stop(2, f'fanboost status gave no chip or fan line:\n{out}')
    return {'chip': float(chip[1]), 'mode': mode[1], 'rpm': [int(x) for x in re.findall(r'^\s+F\d+\s+(\d+)', out, re.M)],
            'thermal': thermal[1] if thermal else ''}


def fanboost(cmd):
    subprocess.run(['fanboost', cmd], capture_output=True)


def settle_temperature():
    low, end = 1e9, time.time() + SETTLE_SECONDS
    while time.time() < end:
        fanboost('max')
        low = min(low, fan_status()['chip'])
        time.sleep(2)
    return low


def thermal_now(path):
    """macOS thermal pressure from the last complete line of the running mactop log."""
    with open(path, 'rb') as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - 32768))
        lines = f.read().decode(errors='replace').splitlines()
    for line in reversed(lines):
        try:
            return json.loads(line.strip().lstrip('[,').rstrip(']'))['thermal_state']
        except (ValueError, KeyError):
            continue
    return '?'


def cool_down(target, mactop_log):
    start = time.time()
    ready = lambda: fan_status()['chip'] <= target and thermal_now(mactop_log) == 'Nominal'
    # The idle chip reading jumps by several degrees from one sample to the next: decide once.
    while not (reached := ready()) and time.time() - start < COOL_TIMEOUT:
        fanboost('max')
        time.sleep(2)
    fanboost('release')
    end = time.time() + 30
    while fan_status()['mode'] != 'AUTO' and time.time() < end:
        time.sleep(1)
    return {'cool_s': round(time.time() - start), 'cool_reached': reached, 'start_chip': fan_status()['chip'],
            'start_thermal': thermal_now(mactop_log)}


class Sampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.samples, self.stop = [], threading.Event()

    def run(self):
        while not self.stop.is_set():
            s = fan_status()
            s['time'] = time.time()
            self.samples.append(s)
            self.stop.wait(2)

    def window(self, a, b):
        return [s for s in self.samples if a <= s['time'] <= b]


# --- runs -------------------------------------------------------------------

def command(table, trees, column, kind, csv_path, model):
    _, tree, extra, _ = column
    if table == 'sweep':
        binary = trees[tree] / ('ds4-bench' if tree == 'ds4' else ab.BENCH)
        return [str(binary), '-m', str(model), '--prompt-file', str(ab.ROOT / ab.PROMPT), '--ssd-streaming',
                '--ssd-streaming-cache-experts', ab.CACHE_FLAG, *SWEEP, '--csv', str(csv_path), *extra]
    return ab.bench_cmd(trees[tree], kind, model, csv_path, extra=extra)


def measure(table, trees, column, kind, out, n, model, replica, target, sampler, monitor):
    name, tree, _, copy = column
    cond = cool_down(target, monitor.path) if target is not None else {
        'cool_s': 0, 'cool_reached': True, 'start_chip': fan_status()['chip'], 'start_thermal': thermal_now(monitor.path)}
    stem = out / 'logs' / f'{n:02d}-{name.replace(" ", "_")}-{kind}'
    env = ab.child_env([f'DS4_METAL_PREFILL_REPLICA={replica}'] if copy else [])
    start = time.time()
    with open(f'{stem}.err', 'wb') as err:
        rc = subprocess.run(command(table, trees, column, kind, f'{stem}.csv', model), cwd=trees[tree], env=env,
                            stdout=subprocess.DEVNULL, stderr=err).returncode
    end = time.time()
    if rc != 0:
        raise ab.Stop(1, f'{name} {kind} failed (exit {rc}); see {stem}.err')
    loader = ab.LOADER.search(Path(f'{stem}.err').read_text(errors='replace'))
    if not loader or not ab.CACHE_WINDOW[0] <= float(loader[1]) <= ab.CACHE_WINDOW[1]:
        raise ab.Stop(2, f'{name} {kind}: dynamic expert cache outside {ab.CACHE_WINDOW} GiB; see {stem}.err')
    rows = {int(r['ctx_tokens']): r for r in csv.DictReader(open(f'{stem}.csv'))}
    fans = sampler.window(start, end)
    gpu = [r for r in monitor.readings(ab.mactop_version()) if start <= r['time'] <= end]
    states = {}
    for r in gpu:
        states[r['thermal']] = states.get(r['thermal'], 0) + 1
    cond.update(chip_max=max(s['chip'] for s in fans), rpm_min=min(min(s['rpm']) for s in fans[2:] or fans),
                modes=sorted({s['mode'] for s in fans}), thermal=states,
                gpu_mhz=statistics.median(r['freq'] for r in gpu) if gpu else None, seconds=round(end - start))
    print(f'  {n:2d} {name:<18} {kind:<11} {end - start:5.0f} s  cooled {cond["cool_s"]:3d} s'
          f'{"" if cond["cool_reached"] else " (timeout)"}, from {cond["start_chip"]:.1f} C {cond["start_thermal"]}, '
          f'peak {cond["chip_max"]:.1f} C, {"/".join(cond["modes"])}, {states}', flush=True)
    return {'n': n, 'column': name, 'kind': kind, 'rows': rows, 'conditions': cond}


def values(table, run):
    rows = run['rows']
    if table == 'sweep':
        v = {}
        for f in FRONTIERS:
            v[f'prefill {f}'] = float(rows[f]['prefill_tps'])
            v[f'generation {f}'] = float(rows[f]['gen_tps'])
            v[f'steady decode {f}'] = float(rows[f]['gen_steady_tps'])
            v[f'first token {f} ms'] = float(rows[f]['gen_first_ms'])
        return v
    v = ab.metrics(run['kind'], rows)
    if run['kind'] == 'decode':
        v['256 tokens after 8192 s'] = int(rows[8192]['gen_tokens']) / float(rows[8192]['gen_tps'])
    return v


def higher_is_better(metric):
    return metric.startswith(('prefill ', 'generation', 'steady decode')) and 'ms' not in metric \
        or metric.startswith('decode ')


def summarize(table, columns, runs):
    per = {c[0]: {} for c in columns}
    for run in runs:
        for k, v in values(table, run).items():
            if not (table == 'shapes' and k == 'prefill 5000'):
                per[run['column']].setdefault(k, []).append(v)
    base = columns[0][0]
    lines = [f'| Metric | {base} | ' + ' | '.join(f'{c[0]} | vs {base}' for c in columns[1:]) + ' |',
             '|---|' + '---:|' * (2 * len(columns) - 1)]
    for metric in per[base]:
        b = statistics.median(per[base][metric])
        cells = [f'{b:.1f}']
        for c in columns[1:]:
            x = statistics.median(per[c[0]][metric])
            gain = x / b - 1 if higher_is_better(metric) else b / x - 1
            cells += [f'{x:.1f}', f'{gain * 100:+.1f}%']
        lines.append(f'| {metric} | ' + ' | '.join(cells) + ' |')
    spread = ['', 'Spread (max-min)/median per column, worst metric:']
    for c in columns:
        worst = max(((max(v) - min(v)) / statistics.median(v), m) for m, v in per[c[0]].items())
        spread.append(f'- {c[0]}: {worst[0] * 100:.1f}% ({worst[1]})')
    if table == 'shapes':
        spread.append('')
        for c in columns[1:]:
            cells = [{'metric': m, 'a': statistics.median(per[base][m]), 'b': statistics.median(per[c[0]][m])}
                     for m in per[base]]
            a, b, g, _ = ab.e2e_estimate(cells)
            spread.append(f'- typical mix, {c[0]} vs {base}: {a:.1f} s -> {b:.1f} s, {(g - 1) * 100:+.1f}%')
    return '\n'.join(lines + spread)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('table', choices=COLUMNS)
    p.add_argument('--ds4', help='ds4 build tree at the merge-base (sweep only)')
    p.add_argument('--replica', required=True, help='byte-identical copy of the GGUF on the second drive')
    p.add_argument('--runs', type=int, default=3)
    p.add_argument('--out', default=None, help='output directory (default $TMPDIR/sf-ds4-1flash-readme/<table>-<time>)')
    args = p.parse_args(argv)
    columns = COLUMNS[args.table]
    trees = {'sf': ab.ROOT}
    if args.table == 'sweep':
        if not args.ds4:
            p.error('sweep needs --ds4')
        trees['ds4'] = Path(args.ds4).resolve()
    if not Path(args.replica).is_file():
        raise ab.Stop(2, f'{args.replica}: no copy there (is the second drive mounted?)')
    if 'pausa' not in fan_status()['thermal']:
        raise ab.Stop(2, 'fanboost thermal protection is on: run `fanboost pause` so plain runs get the Apple curve')
    for name, tree in trees.items():
        bench = 'ds4-bench' if name == 'ds4' else ab.BENCH
        if subprocess.run(['make', '-C', str(tree), '-j8', bench], capture_output=True).returncode:
            raise ab.Stop(2, f'make {bench} failed in {tree}')
    ab.preflight(60.0)
    out = Path(args.out or Path(os.environ.get('TMPDIR', '/tmp')) / 'sf-ds4-1flash-readme' / f'{args.table}-{datetime.now():%Y%m%d-%H%M}')
    (out / 'logs').mkdir(parents=True)
    model = (ab.ROOT / 'deepseek-v4.1-flash.gguf').resolve()
    sampler, monitor = Sampler(), ab.Monitor(out / 'mactop.log')
    sampler.start()
    try:
        kinds = SHAPES if args.table == 'shapes' else ['sweep']
        # One block per build, so no sf run follows a ds4 run: ds4 leaves its own prefill reads in the
        # page cache and the next process, of either build, loses on the first frontier.
        blocks = [[c for c in columns if c[1] == t] for t in dict.fromkeys(c[1] for c in columns)]
        runs, n, target = [], 1, None
        for block in blocks:
            measure(args.table, trees, block[0], kinds[0], out, 0, model, args.replica, target, sampler,
                    monitor)  # warm-up, discarded
            if target is None:
                floor = settle_temperature()
                target = floor + MARGIN_C
                print(f'after the warm-up, {SETTLE_SECONDS} s of full fans reach {floor:.1f} C; every measured '
                      f'run starts at or below {target:.1f} C', flush=True)
            for r in range(args.runs):
                order = block if r % 2 == 0 else block[::-1]
                for kind in kinds:
                    for column in order:
                        runs.append(measure(args.table, trees, column, kind, out, n, model, args.replica, target,
                                            sampler, monitor))
                        n += 1
    finally:
        sampler.stop.set()
        monitor.stop()
    (out / 'runs.json').write_text(json.dumps([{k: v for k, v in r.items() if k != 'rows'} for r in runs], indent=1))
    text = summarize(args.table, columns, runs)
    (out / 'summary.md').write_text(f'floor {floor:.1f} C, target {target:.1f} C, runs {args.runs}\n\n{text}\n')
    print('\n' + text)
    print(f'\noutput: {out}', file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except ab.Stop as e:
        print(f'readme_bench: {e}', file=sys.stderr)
        sys.exit(e.code)
