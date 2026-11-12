#!/usr/bin/env python3
"""Split System One decision time into SSD read wait and the rest (change 915). Stdlib only.

    headroom.py --log server.log --results r1.jsonl [r2.jsonl ...]

The server runs with these probes set inline:
  DS4_METAL_GRAPH_PREFILL_PROFILE=1      one line per sweep layer; map= is the wait for its experts:
    ds4: V4.1 prefill layer=0 pos=0 rows=370 encoder_resident=0 map=12.345 engram=0.010 encode=1.200 drain=150.000 seed=0.500 ms
  DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY=1   process totals at exit (SIGTERM); missing_load is the CPU
    time reading a decode token's missing experts (the resident ones run meanwhile):
    ds4:   streaming expert timing total selected_calls=10 ... split_layers=4000 ... missing_load_avg=0.700 ms ...
  DS4_METAL_GPU_BUSY_PROFILE=1           cumulative GPU execution time, every 64 command buffers:
    ds4: gpu busy accum 1234.5 ms over 640 cbs
Requests are delimited by the server's per-request line "ds4-server: systemone slot ...".

Sweep read wait is split per request, so per results file. Decode read wait and GPU time are
process totals: they belong to the whole log.
"""
import argparse
import json
import re
import statistics

SWEEP = re.compile(r"V4\.1 prefill layer=\d+ .*\bmap=([\d.]+) .*\bdrain=([\d.]+) ")
DECODE = re.compile(r"streaming expert timing total .*\bsplit_layers=(\d+) .*\bmissing_load_avg=([\d.]+) ms")
GPU = re.compile(r"gpu busy accum ([\d.]+) ms over (\d+) cbs")
REQUEST = "systemone slot "


def parse_log(lines):
    """Per request [map_ms, drain_ms, sweep_layers]; process totals."""
    reqs, cur = [], [0.0, 0.0, 0]
    out = {"split_layers": 0, "decode_wait_ms": 0.0, "gpu_ms": 0.0, "gpu_cbs": 0}
    for ln in lines:
        m = SWEEP.search(ln)
        if m:
            cur[0] += float(m.group(1))
            cur[1] += float(m.group(2))
            cur[2] += 1
        elif REQUEST in ln:
            reqs.append(cur)
            cur = [0.0, 0.0, 0]
        elif (m := DECODE.search(ln)):
            out["split_layers"] = int(m.group(1))
            out["decode_wait_ms"] = int(m.group(1)) * float(m.group(2))
        elif (m := GPU.search(ln)):
            out["gpu_ms"], out["gpu_cbs"] = float(m.group(1)), int(m.group(2))
    out["requests"] = reqs
    return out


def request_walls(items):
    """run.py writes wall_ms = request wall / items of that request: regroup consecutive items of a state."""
    walls, last = [], None
    for it in items:
        if it["state_id"] != last:
            walls.append(0.0)
            last = it["state_id"]
        walls[-1] += it["wall_ms"]
    return walls


def summarize(log, results):
    """One row per results file, in the order its requests reached the server."""
    reqs, rows, i = log["requests"], [], 0
    for name, items in results:
        walls = request_walls(items)
        seg = reqs[i:i + len(walls)]
        i += len(walls)
        if len(seg) != len(walls):
            raise SystemExit(f"{name}: {len(walls)} requests in results, {len(seg)} in the log")
        rows.append({"results": name, "decisions": len(items), "requests": len(walls),
                     "wall_ms": sum(walls), "median_request_ms": statistics.median(walls),
                     "sweep_wait_ms": sum(s[0] for s in seg), "sweep_drain_ms": sum(s[1] for s in seg),
                     "swept_requests": sum(1 for s in seg if s[2])})
    if i != len(reqs):
        raise SystemExit(f"{len(reqs)} requests in the log, {i} in the results")
    return {"rows": rows, **{k: v for k, v in log.items() if k != "requests"}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", required=True)
    ap.add_argument("--results", required=True, nargs="+")
    a = ap.parse_args()
    with open(a.log, errors="replace") as f:
        log = parse_log(f)
    res = [(p, [json.loads(l) for l in open(p) if l.strip()]) for p in a.results]
    print(json.dumps(summarize(log, res), indent=1))


if __name__ == "__main__":
    main()
