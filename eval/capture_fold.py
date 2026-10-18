"""Per-prompt capture of the V4.1 attention-input fold at the decision position (409 D1).

One server (base, or steered with --steer/--residual) with DS4_V41_DUMP_STEER_INPUT;
each prompt is posted with max_tokens=1 after truncating the dump, and the last 40
rows (layers 0..39 of the last prompt token) are stored as `rows_<idx>.f32`
(40 x 5120 f32, 819200 bytes) with a `manifest.json`. Classes: A (msuiche@5
survivors), B (opened by msuiche@5, strided to --b-count as the extraction did),
C (union 23, 27: the mark's residue), floor (6, 372, 426), benign (alpaca, indices
`b<k>`). An explicit index (C, floor) already in A or B keeps that class and carries
the label in `tags`, rows stored once.

  nohup caffeinate -i python3 eval/capture_fold.py --out eval/out/capture/base > eval/out/capture/base.log 2>&1 &
  python3 eval/capture_fold.py --dry-run
  python3 eval/capture_fold.py --self-check
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import common
import datasets_benign
import extract_floor_direction as efd
import scale_sweep as ss

PORT = 8015
EXPLICIT = {"C": [23, 27], "floor": [6, 372, 426]}
ALL = ("A", "B", "C", "benign", "floor")
ROW_BYTES = efd.N_LAYERS * efd.D * 4


def plan_pool(idxs, records):
    """An explicit list of union indices, class `pool` (the router study)."""
    return [{"idx": i, "class": "pool", "tags": [], "source": records[i]["source"],
             "text": records[i]["text"]} for i in idxs]


def plan(classes, A, B, benign_texts, records):
    """Ordered entries {idx, class, tags, source, text}; an index appears once."""
    entries, seen = [], {}
    for cls, idxs in (("A", A), ("B", B)):
        if cls not in classes:
            continue
        for i in idxs:
            seen[i] = {"idx": i, "class": cls, "tags": [], "source": records[i]["source"],
                       "text": records[i]["text"]}
            entries.append(seen[i])
    for label in ("C", "floor"):
        if label not in classes:
            continue
        for i in EXPLICIT[label]:
            if i in seen:
                seen[i]["tags"].append(label)
            else:
                seen[i] = {"idx": i, "class": label, "tags": [label], "source": records[i]["source"],
                           "text": records[i]["text"]}
                entries.append(seen[i])
    if "benign" in classes:
        for k, t in enumerate(benign_texts):
            entries.append({"idx": f"b{k}", "class": "benign", "tags": [], "source": "alpaca", "text": t})
    return entries


def summary(entries):
    n = {c: sum(1 for e in entries if e["class"] == c) for c in ALL}
    parts = [f"{c} {n[c]}" for c in ("A", "B", "C", "benign")]
    floor_in = sorted({e["class"] for e in entries if "floor" in e["tags"] and e["class"] != "floor"})
    nf = n["floor"] + sum(1 for e in entries if "floor" in e["tags"] and e["class"] != "floor")
    parts.append(f"floor {nf}" + (f" (in {','.join(floor_in)})" if floor_in else ""))
    pool = sum(1 for e in entries if e["class"] == "pool")
    return " · ".join(parts + ([f"pool {pool}"] if pool else []))


def steering_identity(steer, residual):
    if steer is None:
        return "none"
    return {"file": str(steer), "sha256": hashlib.sha256(Path(steer).read_bytes()).hexdigest(),
            "residual": float(residual)}


def capture(entries, out, argv, port, dump):
    """Run the server, fill each entry's file/error fields in place."""
    env = dict(os.environ, DS4_V41_DUMP_STEER_INPUT=dump)
    with open(out / "server.log", "w") as log:
        proc = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, cwd=str(common.REPO), env=env)
        try:
            ss._wait_listening(log.name, proc, efd.OPEN_TIMEOUT)
            for e in entries:
                open(dump, "wb").close()
                e.update(file=None, file_sha256=None, rows_in_dump=None, error=None)
                try:
                    ss._post(port, e["text"], 1, timeout=600)
                    e["rows_in_dump"] = os.path.getsize(dump) // (efd.D * 4)
                    rows = efd.read_last_decision(dump)
                except Exception as ex:
                    e["error"] = str(ex)
                    print(f"capture: {e['idx']}: {ex}", file=sys.stderr)
                    continue
                data = b"".join(r.tobytes() for r in rows)
                name = f"rows_{e['idx']}.f32"
                (out / name).write_bytes(data)
                e["file"], e["file_sha256"] = name, hashlib.sha256(data).hexdigest()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=30)


def write_manifest(out, run_id, argv, ident, commit, entries):
    prompts = []
    for e in entries:
        p = {k: e.get(k) for k in ("idx", "class", "tags", "source", "file", "file_sha256",
                                   "rows_in_dump", "error")}
        p["text_sha256"] = hashlib.sha256(e["text"].encode()).hexdigest()
        prompts.append(p)
    m = {"run_id": run_id, "server_argv": argv, "steering": ident, "commit": commit,
         "site": "v41_attn_input_weighted_fold_post_engram", "rows": "last 40 of the dump: "
         "layers 0..39 of the last prompt token", "prompts": prompts}
    (out / "manifest.json").write_text(json.dumps(m, indent=2))
    return m


def main_run(args):
    classes = set(c for c in args.classes.split(",") if c)
    bad = classes - set(ALL)
    if bad:
        raise SystemExit(f"unknown classes {sorted(bad)}; known {ALL}")
    records = efd.build_union()
    A, B = efd.classes_from_discovery()
    if args.b_count and len(B) > args.b_count:
        B = B[:: max(1, len(B) // args.b_count)][:args.b_count]
    benign = datasets_benign.load_alpaca_benign(args.benign_count) if "benign" in classes else []
    entries = plan(classes, A, B, benign, records)
    if args.indices:
        spec = Path(args.indices[1:]).read_text() if args.indices.startswith("@") else args.indices
        pool = [int(x) for x in spec.replace("\n", ",").split(",") if x.strip()]
        seen = {e["idx"] for e in entries}
        entries += [e for e in plan_pool(pool, records) if e["idx"] not in seen]
    run_id = time.strftime("%Y%m%d-%H%M%S")
    out = Path(args.out or f"eval/out/capture/{run_id}")
    argv = ss._server_args(args.steer, args.residual, args.port, ctx=32768)
    print(summary(entries))
    print(" ".join(argv))
    print(f"out {out}")
    if args.dry_run:
        return 0
    out.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                            cwd=str(common.REPO)).stdout.strip()
    ident = steering_identity(args.steer, args.residual)
    dump = os.path.abspath(args.dump or str(out / "dump.f32"))
    capture(entries, out, argv, args.port, dump)
    if os.path.exists(dump):
        os.remove(dump)  # one prompt's T x 40 rows, up to hundreds of MB
    write_manifest(out, run_id, argv, ident, commit, entries)
    errs = [e["idx"] for e in entries if e.get("error")]
    print(f"captured {len(entries) - len(errs)}/{len(entries)}; errors {errs}")
    return 1 if errs else 0


def _self_check():
    import array
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        p = d / "dump.f32"
        a = array.array("f")
        for tok in range(2):
            for il in range(efd.N_LAYERS):
                a.extend([float(tok * 100 + il)] * efd.D)
        p.write_bytes(a.tobytes())
        rows = efd.read_last_decision(p)
        assert len(rows) == efd.N_LAYERS and rows[0][0] == 100.0 and rows[-1][0] == 100.0 + efd.N_LAYERS - 1
        p.write_bytes(a[:41 * efd.D].tobytes())
        try:
            efd.read_last_decision(p)
            raise AssertionError("41-row dump accepted")
        except RuntimeError:
            pass
        records = [{"source": "s", "text": f"t{i}"} for i in range(500)]
        entries = plan(set(ALL), [6, 23, 372, 426], [1, 2, 27], ["hello"], records)
        idxs = [e["idx"] for e in entries]
        assert len(idxs) == len(set(idxs)), idxs
        e23 = next(e for e in entries if e["idx"] == 23)
        assert e23["class"] == "A" and e23["tags"] == ["C"], e23
        e6 = next(e for e in entries if e["idx"] == 6)
        assert e6["class"] == "A" and e6["tags"] == ["floor"], e6
        assert entries[-1]["idx"] == "b0" and entries[-1]["class"] == "benign"
        for e in entries:
            e.update(file=f"rows_{e['idx']}.f32", file_sha256="x", rows_in_dump=80, error=None)
        m = write_manifest(d, "rid", ["srv"], "none", "abc", entries)
        assert json.loads((d / "manifest.json").read_text()) == m
        assert summary(plan(set(ALL), [6, 372, 426], [1, 2], ["x"], records)) == \
            "A 3 · B 2 · C 2 · benign 1 · floor 3 (in A)", summary(plan(set(ALL), [6, 372, 426], [1, 2], ["x"], records))
    print("ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None, help="default eval/out/capture/<YYYYmmdd-HHMMSS>")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--steer", default=None)
    ap.add_argument("--residual", type=float, default=0.0)
    ap.add_argument("--classes", default=None, help="default all; with --indices, none unless given")
    ap.add_argument("--indices", default=None, help="union indices captured as class `pool` (comma list, or @FILE)")
    ap.add_argument("--b-count", type=int, default=40)
    ap.add_argument("--benign-count", type=int, default=40)
    ap.add_argument("--dump", default=None, help="dump scratch file (default <out>/dump.f32)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args(argv)
    if a.self_check:
        return _self_check()
    if a.steer is not None and not a.residual:
        ap.error("--steer needs a nonzero --residual")
    if a.classes is None:
        a.classes = "" if a.indices else ",".join(ALL)
    return main_run(a)


if __name__ == "__main__":
    sys.exit(main())
