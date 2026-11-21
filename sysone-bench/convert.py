#!/usr/bin/env python3
"""Fetch and convert LocalLLaMA/typed-decisions into the bench item format (change 820).

    convert.py --work DIR [--split test] [--config all]
    convert.py --source jevbench --path REPO --out FILE                 (a010)
    convert.py --source jevify --path REPO --suite NAME --out FILE      (a010)

The a010 sources are read from a local clone given by --path; nothing in it is
run. Items whose type is `box`, that need an image, or that have more than 26
options are skipped and counted.

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


JEVBENCH_SPLITS = ("original", "easy", "hard")  # datasets/public/<split>.jsonl, 72 + 48 + 111 = 231


def skip_reason(q, n_options, has_image=False):
    if q.get("type") == "box":
        return "box"
    if has_image:
        return "image"
    if n_options > 26:
        return "more than 26 options"
    return None


def convert_jevbench(path):
    """jevbench datasets/public/*.jsonl. Field mapping:
    id -> id; family -> workflow; group -> state_id (variants of one scenario
    move together in the bootstrap); state -> state; question -> question
    (already Jev's shape: type, instructions, criteria); expected -> label
    ("yes"/"no" -> true/false for noul, the criteria key for choice, the level
    index for score)."""
    items, skipped = [], {}
    for split in JEVBENCH_SPLITS:
        for line in open(os.path.join(path, "datasets", "public", split + ".jsonl")):
            r = json.loads(line)
            q = r["question"]
            why = skip_reason(q, len(q.get("criteria") or ()), bool(r.get("image") or r.get("images")))
            if why:
                skipped[why] = skipped.get(why, 0) + 1
                continue
            lab = r["expected"]
            if q["type"] == "noul":
                lab = lab in (True, "yes", "true")
            items.append({"id": r["id"], "lang": "en", "workflow": f"jevbench-{split}-{r['family']}",
                          "state_id": r["group"], "state": r["state"], "question": q, "label": lab})
    return items, skipped


def convert_jevify(path, suite):
    """jevify suites/<suite>.jsonl. Field mapping: case_id -> id and state_id;
    context -> state; instruction -> question.instructions; options (a list of
    texts) -> a choice whose option names are the texts, with no description;
    label (an index) -> the text of that option."""
    items, skipped = [], {}
    for line in open(os.path.join(path, "suites", suite + ".jsonl")):
        r = json.loads(line)
        q = {"type": "choice", "instructions": r["instruction"], "criteria": {o: "" for o in r["options"]}}
        why = skip_reason(q, len(r["options"]), bool(r.get("image") or r.get("frame")))
        if why or len(q["criteria"]) != len(r["options"]):
            why = why or "duplicate option text"
            skipped[why] = skipped.get(why, 0) + 1
            continue
        items.append({"id": f"{suite}:{r['case_id']}", "lang": "en", "workflow": suite,
                      "state_id": f"{suite}:{r['case_id']}", "state": r["context"], "question": q,
                      "label": r["options"][r["label"]]})
    return items, skipped


def write_items(items, out):
    with open(out, "w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work")
    ap.add_argument("--split", default="test")
    ap.add_argument("--config", default="all")
    ap.add_argument("--source", choices=("typed-decisions", "jevbench", "jevify"), default="typed-decisions")
    ap.add_argument("--path")
    ap.add_argument("--suite")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.source != "typed-decisions":
        if not a.path or not a.out or (a.source == "jevify") != bool(a.suite):
            ap.error("--source jevbench needs --path and --out; jevify also needs --suite")
        items, skipped = convert_jevbench(a.path) if a.source == "jevbench" else convert_jevify(a.path, a.suite)
        write_items(items, a.out)
        print(f"convert: {a.source} {len(items)} items, skipped {sum(skipped.values())} {skipped} -> {a.out}")
        return 0
    if not a.work:
        ap.error("--work is required for typed-decisions")
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
