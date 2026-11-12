#!/usr/bin/env python3
"""Fetch and convert LocalLLaMA/typed-decisions into the bench item format (change 820).

    convert.py --work DIR [--split test] [--config all]

The set ships as parquet and no parquet reader is installed (and none may be),
so the rows are read as JSON from the Hugging Face datasets-server API into
DIR/typed-decisions-<config>-<split>.rows.json, then written as
DIR/typed-decisions-<config>-<split>.jsonl, one decision per line. Nothing is
written into the repository.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

DATASET = "LocalLLaMA/typed-decisions"
API = "https://datasets-server.huggingface.co/rows?dataset={d}&config={c}&split={s}&offset={o}&length=100"


def fetch(config, split, cache):
    if os.path.exists(cache):
        return json.load(open(cache))
    rows, off, total = [], 0, None
    while total is None or off < total:
        url = API.format(d=DATASET, c=config, s=split, o=off)
        with urllib.request.urlopen(url, timeout=60) as r:
            d = json.loads(r.read().decode())
        total = d["num_rows_total"]
        rows += [x["row"] for x in d["rows"]]
        off += 100
        time.sleep(0.2)
    with open(cache, "w") as f:
        json.dump(rows, f)
    return rows


def convert(rows):
    items = []
    for row in rows:
        questions = json.loads(row["questions"])
        gold = json.loads(row["gold"])
        for name, q in questions.items():
            label = gold[name]["label"]
            items.append({"id": f"{row['id']}:{name}", "lang": "en", "workflow": row["workflow"],
                          "state_id": row["id"], "state": row["state"], "question": q, "label": label})
    return items


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--config", default="all")
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    stem = os.path.join(a.work, f"typed-decisions-{a.config}-{a.split}")
    rows = fetch(a.config, a.split, stem + ".rows.json")
    items = convert(rows)
    with open(stem + ".jsonl", "w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    types = {}
    for it in items:
        types[it["question"]["type"]] = types.get(it["question"]["type"], 0) + 1
    print(f"convert: {len(rows)} states, {len(items)} decisions {types} -> {stem}.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
