#!/usr/bin/env python3
"""Fit one temperature per question type on half of a sysone run (change 820).

    fit.py --results results.jsonl --model-path GGUF --out calibration.json [--fitted-on TEXT]

Items are split by a hash of their id: even ids fit, odd ids report NLL and ECE
before and after. Needs the raw option logits (run.py records them via sf.debug).
Also: fit.py --apply calibration.json --results results.jsonl --out tempered.jsonl
rewrites the probabilities offline (temperature divides the logits, so this is
exactly what the server computes with the file loaded).
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metrics  # noqa: E402

GRID = [0.25 * (32 ** (i / 60)) for i in range(61)]  # geometric 0.25..8


def is_even(item_id):
    return int(hashlib.sha1(item_id.encode()).hexdigest(), 16) % 2 == 0


def tempered(r, t):
    keys = list(r["logits"])
    p = metrics.softmax([r["logits"][k] for k in keys], t)
    out = dict(r)
    out["probs"] = dict(zip(keys, p))
    return out


def fit_type(rows):
    best_t, best = 1.0, float("inf")
    for t in GRID:
        v = metrics.nll([tempered(r, t) for r in rows])
        if v < best:
            best_t, best = t, v
    return best_t


def load(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", required=True)
    ap.add_argument("--model-path")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fitted-on", default="")
    ap.add_argument("--apply")
    a = ap.parse_args()
    rows = [r for r in load(a.results) if r.get("logits") and r.get("label") is not None]
    if a.apply:
        cal = json.load(open(a.apply))
        with open(a.out, "w") as f:
            for r in load(a.results):
                if r.get("logits"):
                    r = tempered(r, cal["temperature"].get(r["type"], 1.0))
                f.write(json.dumps(r) + "\n")
        return 0
    temps = {}
    print("| type | T | fit n | held-out n | NLL raw | NLL fitted | ECE raw | ECE fitted |")
    print("|---|---|---|---|---|---|---|---|")
    for t in ("noul", "choice", "score"):
        sel = [r for r in rows if r["type"] == t]
        fit = [r for r in sel if is_even(r["id"])]
        held = [r for r in sel if not is_even(r["id"])]
        if not fit:
            continue
        temps[t] = round(fit_type(fit), 4)
        after = [tempered(r, temps[t]) for r in held]
        before = [tempered(r, 1.0) for r in held]
        print(f"| {t} | {temps[t]} | {len(fit)} | {len(held)} | {metrics.nll(before):.4f} | {metrics.nll(after):.4f} | "
              f"{metrics.ece(before):.4f} | {metrics.ece(after):.4f} |")
    held_all = [r for r in rows if not is_even(r["id"])]
    b = [tempered(r, 1.0) for r in held_all]
    f_ = [tempered(r, temps.get(r["type"], 1.0)) for r in held_all]
    print(f"| all | - | - | {len(held_all)} | {metrics.nll(b):.4f} | {metrics.nll(f_):.4f} | "
          f"{metrics.ece(b):.4f} | {metrics.ece(f_):.4f} |")
    if not a.model_path:
        print("fit: no --model-path, calibration file not written", file=sys.stderr)
        return 0
    st = os.stat(a.model_path)  # follows the symlink to the GGUF, as the server's stat does
    cal = {"binding": {"model_bytes": st.st_size, "model_mtime": int(st.st_mtime),
                       "template_version": 1, "layout": "state_first"},
           "temperature": temps,
           "fitted_on": a.fitted_on or f"{os.path.basename(a.results)} even ids, {sum(is_even(r['id']) for r in rows)} items",
           "date": datetime.date.today().isoformat()}
    with open(a.out, "w") as f:
        json.dump(cal, f, indent=1)
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
