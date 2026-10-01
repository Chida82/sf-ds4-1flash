#!/usr/bin/env python3
"""Unit tests of speed-bench/ab_bench.py, ab_pool.py and expert_cache_sim.py on synthetic data.

Run directly: python3 tests/test_ab_bench.py -v (not part of make test)."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f'speed-bench/{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # ab_pool imports ab_bench: the same module object, so Stop is one class
    spec.loader.exec_module(module)
    return module


ab = load('ab_bench')
ab_pool = load('ab_pool')
sim = load('expert_cache_sim')

HEADER = 'ctx_tokens,prefill_tokens,prefill_tps,gen_tokens,gen_tps,gen_first_ms,gen_steady_tokens,gen_steady_tps,kvcache_bytes\n'
LOADER = ('ds4: metal SSD streaming cache target 82.00 GiB; effective 82.00 GiB = 7.12 GiB prefill headroom + '
          '74.88 GiB dynamic cache (8081 experts, 9.49 MiB each)\n')
CTX = 'ds4-bench: context buffers 8073.52 MiB (ctx=32768, backend=metal, prefill_chunk=8192, raw_kv_rows=128, compressed_kv_rows=32769)\n'


def report(frontier, hits, misses, pread=None):
    line = (f'ds4: Metal memory after frontier {frontier}: runtime 1.00 GiB + streaming experts 74.00 GiB = 75.00 GiB tracked live\n'
            f'ds4:   streaming expert cache budget=8081 experts entries=8081 expert=9.49 MiB target=74.88 GiB live=74.88 GiB, '
            f'hits={hits} misses={misses} hit_rate=0.900 wraps=0 evictions=10 buffer_allocs=1 buffer_reuses=2')
    if pread is not None:
        line += f' evict_dontneed=0.00 GiB miss_willneed=0.00 GiB miss_pread={pread:.2f} GiB pread_ms={pread * 100:.3f}'
    return line + '\n'


DECODE_CSV = HEADER + ('2048,2048,130.00,256,15.00,2500.000,255,17.00,24118324\n'
                       '8192,6144,280.00,256,15.00,2600.000,255,17.20,0\n')
DECODE_ERR = (LOADER + CTX + 'ds4-bench: gen[ctx=2048] decoded text: "x"\n'
              'ds4-bench: gen[ctx=2048] token ids: 1 2 3 4\n' + report(2048, 1000, 100, 1.0) +
              'ds4-bench: gen[ctx=8192] token ids: 5 6 7 8\n' + report(8192, 2100, 180, 1.8))
COLD_CSV = HEADER + '2500,2500,60.00,16,10.00,2400.000,15,16.00,0\n'
COLD_ERR = LOADER + CTX + 'ds4-bench: gen[ctx=2500] token ids: 9 9 9\n' + report(2500, 500, 50)


def fake_run(build, kind, n, values, phase='timed', tokens=None, cache=None):
    """A run whose every metric equals `values` (or the given dict), with unit cache counters."""
    names = {'decode': ['decode 2048', 'decode 8192', 'first token 2048 ms', 'first token 8192 ms'],
             'cold-2500': ['ttft 2500', 'first token 2500 ms'], 'cold-5000': ['ttft 5000', 'first token 5000 ms'],
             'append': ['prefill 5000', 'append +300', 'append +1500'],
             'guard-decode': ['guard decode 2500', 'first token 8192 ms'],
             'guard-16896': ['guard ttft 16896', 'first token 16896 ms']}[kind]
    metrics = values if isinstance(values, dict) else {name: values for name in names}
    return {'build': build, 'kind': kind, 'n': n, 'phase': phase, 'warmup': phase in ('warm-up', 'preheat'),
            'note': '', 'metrics': metrics, 'duration': 10.0, 'tokens': tokens or {2048: [1, 2, 3]},
            'cache': cache or {2048: {'hits': 1000, 'misses': 100, 'pread_gib': 1.0, 'pread_ms': 100.0, 'lookups': 1100}},
            'cache_gib': 74.88, 'cache_slots': 8081, 'rows': {}}


def quads(kind, a_values, b_values, start=1):
    runs = [fake_run('A', kind, 0, 1.0, 'warm-up'), fake_run('B', kind, 0, 1.0, 'warm-up')]
    n = start
    for a1, b1, b2, a2 in zip(a_values[::2], b_values[::2], b_values[1::2], a_values[1::2]):
        for build, v in (('A', a1), ('B', b1), ('B', b2), ('A', a2)):
            runs.append(fake_run(build, kind, n, v))
            n += 1
    return runs


class Parsing(unittest.TestCase):
    def test_decode_run(self):
        run = ab.parse_run(DECODE_CSV, DECODE_ERR, 'decode')
        self.assertEqual(run['tokens'], {2048: [1, 2, 3, 4], 8192: [5, 6, 7, 8]})
        self.assertEqual(run['metrics']['decode 2048'], 17.0)
        self.assertEqual(run['metrics']['decode 8192'], 17.2)
        self.assertEqual(run['metrics']['first token 2048 ms'], 2500.0)
        self.assertEqual((run['cache_gib'], run['cache_slots']), (74.88, 8081))

    def test_cache_deltas(self):
        cache = ab.parse_cache_reports(DECODE_ERR, 'decode')
        self.assertEqual(cache[2048], {'hits': 1000, 'misses': 100, 'pread_gib': 1.0, 'pread_ms': 100.0, 'lookups': 1100})
        self.assertEqual(cache[8192]['hits'], 1100)
        self.assertEqual(cache[8192]['misses'], 80)
        self.assertAlmostEqual(cache[8192]['pread_gib'], 0.8)

    def test_cache_report_without_pread(self):
        cache = ab.parse_cache_reports(COLD_ERR, 'cold-2500')
        self.assertEqual(cache[2500]['pread_gib'], 0.0)
        self.assertEqual(cache[2500]['lookups'], 550)

    def test_cache_report_missing_field(self):
        err = COLD_ERR.replace('misses=50 ', '')
        with self.assertRaises(ab.Stop) as cm:
            ab.parse_cache_reports(err, 'cold-2500')
        self.assertEqual(cm.exception.code, 1)
        self.assertIn('misses', str(cm.exception))

    def test_cold_metrics(self):
        run = ab.parse_run(COLD_CSV, COLD_ERR, 'cold-2500')
        self.assertAlmostEqual(run['metrics']['ttft 2500'], 2500 / 60.0)
        self.assertEqual(run['metrics']['first token 2500 ms'], 2400.0)

    def test_loader_outside_window(self):
        err = COLD_ERR.replace('74.88 GiB dynamic', '60.00 GiB dynamic')
        with self.assertRaises(ab.Stop) as cm:
            ab.parse_run(COLD_CSV, err, 'cold-2500')
        self.assertEqual(cm.exception.code, 2)
        self.assertIn('60.0 GiB', str(cm.exception))

    def test_loader_line_missing(self):
        with self.assertRaises(ab.Stop) as cm:
            ab.parse_run(COLD_CSV, COLD_ERR.replace(LOADER, ''), 'cold-2500')
        self.assertEqual(cm.exception.code, 2)

    def test_wrong_context(self):
        with self.assertRaises(ab.Stop) as cm:
            ab.parse_run(COLD_CSV, COLD_ERR.replace('ctx=32768', 'ctx=2533'), 'cold-2500')
        self.assertEqual(cm.exception.code, 2)

    def test_missing_frontier(self):
        with self.assertRaises(ab.Stop) as cm:
            ab.parse_run(DECODE_CSV, DECODE_ERR.replace('token ids: 5 6 7 8', 'nothing'), 'decode')
        self.assertIn('token ids', str(cm.exception))

    def test_bench_command(self):
        cmd = ab.bench_cmd(Path('/t'), 'append', Path('/m.gguf'), '/o.csv', extra=['--x'])
        self.assertEqual(cmd[0], '/t/sf-ds4-1flash-bench')
        for flag in ('--ssd-streaming', '82GB', '32768', '--show-output', '--cache-stats'):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index('--frontiers') + 1], '5000,5300,6800')
        self.assertEqual(cmd[cmd.index('-n') + 1], '16')
        self.assertEqual(cmd[-1], '--x')

    def test_kind_selection(self):
        self.assertEqual(ab.select_kinds('cold', '--kinds'), ab.GROUPS['cold'])
        self.assertEqual(ab.select_kinds('decode,guards,decode', '--kinds'), ['decode', 'guard-16896', 'guard-decode'])
        with self.assertRaises(ab.Stop):
            ab.select_kinds('plain', '--kinds')
        with self.assertRaises(ab.Stop):
            ab.parse_args(['--a', '.', '--b', '.'])

    def test_units_and_gain(self):
        self.assertEqual(ab.unit('decode 2048'), 't/s')
        self.assertEqual(ab.unit('guard decode 2500'), 't/s')
        self.assertEqual(ab.unit('ttft 5000'), 's')
        self.assertEqual(ab.unit('append +300'), 's')
        self.assertEqual(ab.unit('first token 2048 ms'), 'ms')
        self.assertAlmostEqual(ab.gain(66.0, 60.0, 'ttft 5000'), 1.1)   # B faster: positive
        self.assertAlmostEqual(ab.gain(50.0, 55.0, 'decode 2048'), 1.1)

    def test_section_ratios(self):
        err = COLD_ERR + ''.join(
            f'ds4: V4.1 stage layer={il} pos=0 rows={rows} {label}={ms:.3f} ms\n'
            for il in (0, 1) for rows, core, other in ((2048, 2.0, 6.0), (452, 1.0, 1.0))
            for label, ms in (('attention core/index', core), ('shared/routed ffn', other / 2),
                              ('hc expand', other / 2)))
        run = ab.parse_run(COLD_CSV, err, 'cold-2500', ['attention core/index'])
        self.assertAlmostEqual(run['metrics']['sections 2048 rows'], 4.0 / 12.0)
        self.assertAlmostEqual(run['metrics']['sections 452 rows'], 1.0)
        self.assertNotIn('sections 2048 rows', ab.parse_run(COLD_CSV, err, 'cold-2500')['metrics'])
        self.assertEqual(ab.unit('sections 2048 rows'), 'ratio')
        self.assertAlmostEqual(ab.gain(0.5, 0.4, 'sections 2048 rows'), 1.25)   # B's share smaller: positive

    def test_sections_flag(self):
        args = ab.parse_args(['--a', '.', '--b', '.', '--kinds', 'cold', '--sections', 'attention core/index'])
        self.assertEqual(args.sections, ['attention core/index'])
        self.assertEqual(ab.build_envs(args)['A']['DS4_METAL_V41_STAGE_PROFILE'], '1')
        with self.assertRaises(ab.Stop):
            ab.parse_args(['--a', '.', '--b', '.', '--kinds', 'cold', '--sections', 'attention'])


class Environment(unittest.TestCase):
    def test_inherited_stripped(self):
        env = ab.child_env(['DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY=1'],
                           {'DS4_METAL_DISABLE_V41_WIDE_PREFILL': '1', 'PATH': '/bin'})
        self.assertEqual(env, {'PATH': '/bin', 'DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY': '1'})
        with self.assertRaises(ab.Stop):
            ab.child_env(['NOVALUE'])

    def test_b_env_reaches_only_b(self):
        args = ab.parse_args(['--a', '.', '--b', '.', '--kinds', 'decode', '--env', 'X=1',
                              '--b-env', 'DS4_METAL_DISABLE_STREAMING_EXPERT_READAHEAD=1'])
        envs = ab.build_envs(args)
        self.assertNotIn('DS4_METAL_DISABLE_STREAMING_EXPERT_READAHEAD', envs['A'])
        self.assertEqual(envs['B']['DS4_METAL_DISABLE_STREAMING_EXPERT_READAHEAD'], '1')
        self.assertEqual((envs['A']['X'], envs['B']['X']), ('1', '1'))


class Mactop(unittest.TestCase):
    SAMPLE = {'timestamp': '2026-09-27T10:00:00+00:00', 'thermal_state': 'Nominal',
              'soc_metrics': {'gpu_freq_mhz': 1300, 'gpu_active': 80.0, 'gpu_power': 20.0, 'gpu_temp': 50.0}}

    def test_stream_with_partial_last_line(self):
        text = '[' + json.dumps(self.SAMPLE) + '\n,' + json.dumps(self.SAMPLE) + '\n,{"timestamp": "2026'
        samples = ab.parse_mactop(text)
        self.assertEqual(len(samples), 2)
        self.assertEqual(ab.reading(samples[0])['freq'], 1300)

    def test_bad_middle_line(self):
        with self.assertRaises(ab.Stop):
            ab.parse_mactop('[{"a": 1}\n,not json\n,{"a": 2}\n')

    def test_missing_key(self):
        with self.assertRaises(ab.Stop) as cm:
            ab.reading({'timestamp': '2026-09-27T10:00:00+00:00', 'thermal_state': 'Nominal', 'soc_metrics': {}}, '9.9')
        self.assertIn('9.9', str(cm.exception))
        self.assertIn('gpu_freq_mhz', str(cm.exception))


class Schedule(unittest.TestCase):
    def run_schedule(self, kinds, guards, budget, durations, preheat=0.0):
        clock = [0.0]
        runs, log = [], []

        def runner(build, kind, phase):
            d = durations[kind]
            clock[0] += d
            log.append((build, kind, phase))
            return {'build': build, 'kind': kind, 'phase': phase, 'duration': d, 'warmup': phase != 'timed'}

        ab.schedule(kinds, guards, budget, runner, lambda r: None, runs, preheat, clock=lambda: clock[0])
        return log

    def test_quads_after_warmup_then_guards(self):
        log = self.run_schedule(['decode'], ['guard-decode'], 10_000, {'decode': 10.0, 'guard-decode': 20.0})
        self.assertEqual(log[:2], [('A', 'decode', 'warm-up'), ('B', 'decode', 'warm-up')])
        timed = [x for x in log if x[2] == 'timed']
        self.assertEqual([b for b, _, _ in timed[:4]], ['A', 'B', 'B', 'A'])
        self.assertEqual(log[-2:], [('A', 'guard-decode', 'guard'), ('B', 'guard-decode', 'guard')])

    def test_budget_leaves_room_for_guards(self):
        # warm-up 20 s, a quad is predicted at 44 s; the guard reserve is 2 * 180 s
        log = self.run_schedule(['decode'], ['guard-decode'], 20 + 44 + 360 + 1, {'decode': 10.0, 'guard-decode': 1.0})
        self.assertEqual(sum(1 for x in log if x[2] == 'timed'), 4)
        log = self.run_schedule(['decode'], ['guard-decode'], 20 + 44 + 360 - 1, {'decode': 10.0, 'guard-decode': 1.0})
        self.assertEqual(sum(1 for x in log if x[2] == 'timed'), 0)
        self.assertEqual(log[-1], ('B', 'guard-decode', 'guard'))

    def test_preheat_until_deadline(self):
        log = self.run_schedule(['decode'], [], 1000, {'decode': 10.0}, preheat=55.0)
        preheat = [x for x in log if x[2] == 'preheat']
        self.assertEqual(len(preheat), 4)  # warm-up ends at 20 s; runs at 30, 40, 50, 60
        self.assertEqual([b for b, _, _ in preheat], ['A', 'B', 'A', 'B'])


class Analysis(unittest.TestCase):
    def test_pairs_and_median_gain(self):
        runs = quads('decode', [50.0, 50.0, 50.0, 50.0], [55.0, 55.0, 60.0, 60.0])
        table = ab.verdict(runs, ['decode'], [])
        row = next(t for t in table if t['metric'] == 'decode 2048')
        self.assertEqual(row['n'], 4)
        self.assertAlmostEqual(row['gain'], 1.15)
        self.assertAlmostEqual(row['lo'], 1.1)
        self.assertAlmostEqual(row['hi'], 1.2)
        self.assertTrue(row['headline'])
        self.assertFalse(next(t for t in table if t['metric'] == 'first token 2048 ms')['headline'])

    def test_seconds_gain_positive_when_faster(self):
        runs = quads('cold-5000', [66.0, 66.0], [60.0, 60.0])
        row = next(t for t in ab.verdict(runs, ['cold-5000'], []) if t['metric'] == 'ttft 5000')
        self.assertAlmostEqual(row['gain'], 1.1)
        self.assertEqual(ab.pct(row['gain']), '+10.0%')

    def test_dropped_pair_leaves_the_other(self):
        runs = quads('decode', [50.0, 50.0], [55.0, 90.0])
        timed = [r for r in runs if not r['warmup']]
        timed[1]['flag'] = timed[0]['flag'] = 'pair dropped: test'
        row = next(t for t in ab.verdict(runs, ['decode'], []) if t['metric'] == 'decode 2048')
        self.assertEqual(row['n'], 1)
        self.assertAlmostEqual(row['gain'], 1.8)

    def test_disturbed_run_drops_its_pair(self):
        runs = quads('decode', [50.0] * 4, [50.0] * 4)
        timed = [r for r in runs if not r['warmup']]
        for r, f in zip(timed, [1300, 1310, 1290, 1305, 1300, 900, 1310, 1300]):
            r['freq'] = f
        ab.drop_disturbed(timed, ['decode'], 0.90)
        self.assertTrue(timed[4].get('flag') and timed[5].get('flag'))
        self.assertIn('run 6', timed[4]['flag'])
        self.assertFalse(any(r.get('flag') for r in timed[:4] + timed[6:]))

    def test_frequency_floor_is_per_kind(self):
        # a sweep-heavy kind runs the GPU at 900 MHz by nature: judged against its own median
        runs = quads('decode', [50.0] * 2, [50.0] * 2) + quads('cold-5000', [70.0] * 2, [70.0] * 2, start=5)
        timed = [r for r in runs if not r['warmup']]
        for r, f in zip(timed, [1500, 1510, 1490, 1505, 910, 900, 920, 905]):
            r['freq'] = f
        ab.drop_disturbed(timed, ['decode', 'cold-5000'], 0.90)
        self.assertFalse(any(r.get('flag') for r in timed))

    def test_cache_drift_drops_pair_or_notes_it(self):
        a = fake_run('A', 'decode', 1, 50.0)
        b = fake_run('B', 'decode', 2, 50.0,
                     cache={2048: {'hits': 960, 'misses': 140, 'pread_gib': 1.4, 'pread_ms': 140.0, 'lookups': 1100}})
        self.assertIn('hits A 1000 B 960', ab.cache_drift(a, b, 0.01))
        self.assertIsNone(ab.cache_drift(a, fake_run('B', 'decode', 3, 50.0), 0.01))
        timed = [a, b, fake_run('B', 'decode', 3, 50.0), fake_run('A', 'decode', 4, 50.0)]
        ab.drop_cache_drift(timed, ['decode'], 0.01, False)
        self.assertIn('cache state differs', a['flag'])
        self.assertFalse(timed[2].get('flag'))
        timed = [fake_run('A', 'decode', 1, 50.0), b, fake_run('B', 'decode', 3, 50.0), fake_run('A', 'decode', 4, 50.0)]
        ab.drop_cache_drift(timed, ['decode'], 0.01, True)
        self.assertFalse(timed[0].get('flag'))
        self.assertIn('declared policy change', timed[0]['note'])
        self.assertEqual(timed[2]['note'], '')

    def test_bytes_read_rule(self):
        a = fake_run('A', 'decode', 1, 50.0)
        b = fake_run('B', 'decode', 2, 50.0,
                     cache={2048: {'hits': 1000, 'misses': 100, 'pread_gib': 1.2, 'pread_ms': 100.0, 'lookups': 1100}})
        self.assertIn('bytes read', ab.cache_drift(a, b, 0.01))

    def test_guard_single_pair(self):
        runs = [fake_run('A', 'guard-decode', 1, 50.0, 'guard'), fake_run('B', 'guard-decode', 2, 55.0, 'guard')]
        table = ab.verdict(runs, [], ['guard-decode'])
        row = next(t for t in table if t['metric'] == 'guard decode 2500')
        self.assertEqual((row['n'], row['lo'], row['guard']), (1, None, True))
        self.assertAlmostEqual(row['gain'], 1.1)

    def test_inconclusive_below_two_pairs(self):
        runs = quads('decode', [50.0, 50.0], [50.0, 50.0])
        timed = [r for r in runs if not r['warmup']]
        timed[0]['flag'] = timed[1]['flag'] = 'pair dropped: test'
        table = ab.verdict(runs, ['decode'], [])
        text, thin = ab.summary(self.ctx(['decode']), runs, table, 'PASS', 'PASS (tokens)', None)
        self.assertTrue(thin)
        self.assertIn('INCONCLUSIVE', text)

    @staticmethod
    def ctx(kinds, guards=()):
        return {'date': '2026-09-27 10:00 UTC', 'device': 'M5 Max', 'mactop': '2.1.5',
                'A': {'path': '/a', 'commit': 'aaaaaaa', 'branch': 'main', 'dirty': False},
                'B': {'path': '/b', 'commit': 'bbbbbbb', 'branch': 'perf/x', 'dirty': False},
                'model': '/m.gguf', 'model_name': 'm.gguf', 'env': [], 'budget': 1800, 'kinds': list(kinds),
                'guards': list(guards), 'elapsed': 100.0, 'preheat': 0.0, 'cache': (74.88, 8081)}

    def test_e2e_full_and_partial(self):
        table = [{'metric': 'decode 2048', 'a': 17.0, 'b': 18.7}, {'metric': 'decode 8192', 'a': 17.0, 'b': 18.7}]
        table += [{'metric': f'ttft {p}', 'a': 40.0, 'b': 40.0} for p in ab.E2E_PROMPTS]
        a, b, g, unmeasured = ab.e2e_estimate(table)
        self.assertEqual(unmeasured, [])
        self.assertAlmostEqual(a, 40.0 + (200 + 1000 + 2000) / 3 / 17.0)
        self.assertAlmostEqual(b, 40.0 + (200 + 1000 + 2000) / 3 / 18.7)
        self.assertGreater(g, 1.0)
        a2, b2, g2, unmeasured = ab.e2e_estimate(table[:2])
        self.assertEqual(len(unmeasured), 5)
        self.assertAlmostEqual(a2 - b2, (200 + 1000 + 2000) / 3 * (1 / 17.0 - 1 / 18.7))

    def test_record_row_cells(self):
        runs = quads('decode', [50.0, 50.0], [55.0, 55.0])
        table = ab.verdict(runs, ['decode'], [])
        e2e = ab.e2e_estimate(table)
        row = ab.record_row('perf/x', '2026-09-27', 'bbbbbbb', 'm.gguf', 2, 'PASS', table, e2e)
        header_cells = ab.record_header().split('\n')[0].count('|') - 1
        self.assertEqual(row.count('|') - 1, header_cells)
        self.assertEqual(header_cells, len(ab.RECORD_LEAD) + len(ab.RECORD))
        cells = [c.strip() for c in row.strip('|').split('|')]
        self.assertEqual(cells[6], '55.0 (+10.0%)')
        self.assertEqual(cells[8], '')          # ttft 2500 not run
        self.assertNotEqual(cells[-1], '')      # e2e always estimated
        text, thin = ab.summary(self.ctx(['decode']), runs, table, 'PASS', 'PASS (tokens)', e2e)
        self.assertFalse(thin)
        self.assertIn('record row:', text)
        self.assertIn('unmeasured, held at reference', text)
        self.assertIn('8081 expert slots', text)


class Correctness(unittest.TestCase):
    def test_token_mismatch_position(self):
        ref = fake_run('A', 'decode', 1, 1.0, tokens={2048: [1, 2, 3], 8192: [4, 5, 6]})
        run = fake_run('B', 'decode', 2, 1.0, tokens={2048: [1, 2, 3], 8192: [4, 9, 6]})
        self.assertEqual(ab.check_tokens(run, ref), 'FAIL: B differs from A: decode, frontier 8192, token index 1')
        self.assertIsNone(ab.check_tokens(fake_run('B', 'decode', 3, 1.0, tokens=ref['tokens']), ref))

    def test_nondeterministic_baseline(self):
        ref = fake_run('A', 'decode', 1, 1.0, tokens={2048: [1, 2, 3]})
        run = fake_run('A', 'decode', 2, 1.0, tokens={2048: [1, 2]})
        self.assertIn('nondeterministic', ab.check_tokens(run, ref))
        self.assertIn('token index 2', ab.check_tokens(run, ref))

    def test_cache_slots_must_match(self):
        ref = fake_run('A', 'decode', 1, 1.0)
        run = fake_run('B', 'decode', 2, 1.0)
        run['cache_slots'] = 7498
        with self.assertRaises(ab.Stop) as cm:
            ab.check_cache_config(run, ref)
        self.assertEqual(cm.exception.code, 2)

    def dump(self, directory, name, values, argmax=0):
        directory.mkdir(parents=True, exist_ok=True)
        text = ('{\n  "source":"ds4-bench",\n  "model":"m",\n  "backend":"metal",\n  "quality":false,\n'
                '  "quant_bits":2,\n  "prompt_tokens":2500,\n  "frontier_tokens":2500,\n  "prefill_tokens":2500,\n'
                '  "ctx":32768,\n  "vocab":%d,\n  "argmax_id":%d,\n  "argmax_logit":%s,\n  "logits":[%s]\n}\n'
                % (len(values), argmax, values[argmax], ','.join(values)))
        (directory / name).write_text(text)

    def test_bitwise_one_bit_and_signed_zero(self):
        cfl = ab.load_logits_validator()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.dump(tmp / 'A', 'frontier_002500.logits.json', ['1.00000012', '-0', '0.5'])
            self.dump(tmp / 'B', 'frontier_002500.logits.json', ['1.00000024', '-0', '0.5'])
            problem = ab.check_logits(tmp / 'A', tmp / 'B', (2500,))
            self.assertIsNotNone(problem)
            self.assertIn('frontier 2500, vocabulary index 0', problem)
            self.dump(tmp / 'C', 'frontier_002500.logits.json', ['1.00000012', '0', '0.5'])
            self.assertIn('vocabulary index 1', ab.check_logits(tmp / 'A', tmp / 'C', (2500,)))
            self.dump(tmp / 'D', 'frontier_002500.logits.json', ['1.00000012', '-0', '0.5'])
            self.assertIsNone(ab.check_logits(tmp / 'A', tmp / 'D', (2500,)))
        self.assertTrue(hasattr(cfl, 'validate_dump'))


class Pooling(unittest.TestCase):
    def write_samples(self, directory, kind, a_values, b_values, dropped=()):
        runs = quads(kind, a_values, b_values)
        for r in runs:
            r['rows'] = {2048: {'prefill_tokens': '2048', 'prefill_tps': '130.00', 'gen_tokens': '256', 'gen_tps': '15.0',
                                'gen_first_ms': '2500.0', 'gen_steady_tokens': '255', 'gen_steady_tps': str(r['metrics']['decode 2048'])},
                         8192: {'prefill_tokens': '6144', 'prefill_tps': '280.00', 'gen_tokens': '256', 'gen_tps': '15.0',
                                'gen_first_ms': '2600.0', 'gen_steady_tokens': '255', 'gen_steady_tps': str(r['metrics']['decode 8192'])}}
            r['cache'] = {f: r['cache'][2048] for f in (2048, 8192)}
            r['tokens'] = {f: [1, 2] for f in (2048, 8192)}
            if r['n'] in dropped:
                r['flag'] = 'pair dropped: test'
        directory.mkdir(parents=True)
        ab.write_samples(directory / 'samples.csv', runs)

    def test_pool_two_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.write_samples(tmp / 'one', 'decode', [50.0, 50.0], [55.0, 55.0])
            self.write_samples(tmp / 'two', 'decode', [50.0, 50.0, 50.0, 50.0], [60.0, 60.0, 60.0, 60.0], dropped=(1, 2))
            gains = ab_pool.pooled('decode', 'decode 2048', [tmp / 'one', tmp / 'two'])
            self.assertEqual(len(gains), 5)
            self.assertAlmostEqual(sorted(gains)[0], 1.1)
            with self.assertRaises(ab.Stop) as cm:
                ab_pool.pooled('decode', 'no such metric', [tmp / 'one'])
            self.assertIn('choose from decode 2048', str(cm.exception))

    def test_non_abba_order_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.write_samples(tmp / 'one', 'decode', [50.0, 50.0], [55.0, 55.0])
            self.assertEqual(len(ab_pool.pooled('decode', 'decode 2048', [tmp / 'one'])), 2)
            text = (tmp / 'one/samples.csv').read_text().replace(',B,decode,timed', ',A,decode,timed')
            (tmp / 'one/samples.csv').write_text(text)
            with self.assertRaises(ab.Stop) as cm:
                ab_pool.pooled('decode', 'decode 2048', [tmp / 'one'])
            self.assertEqual(cm.exception.code, 2)


class CacheSim(unittest.TestCase):
    def test_lru_and_belady(self):
        a = [(0, e) for e in (1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5)]
        self.assertEqual((sim.lru_misses(a, 3), sim.belady_misses(a, 3)), (10, 7))
        self.assertEqual(sim.lru_misses(a, 5), 5)

    def test_trace_layers(self):
        import struct
        with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
            f.write(struct.pack('<12i', *range(12)))
        accesses = sim.read_trace(f.name, 2)
        self.assertEqual(accesses[:6], [(0, e) for e in range(6)])
        self.assertEqual(accesses[6:], [(1, e) for e in range(6, 12)])


if __name__ == '__main__':
    unittest.main()
