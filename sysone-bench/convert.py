#!/usr/bin/env python3
"""Fetch and convert LocalLLaMA/typed-decisions into the bench item format (change 820).

    convert.py --work DIR [--split test] [--config all]
    convert.py --source jevbench --path REPO --out FILE                 (a010)
    convert.py --source jevify --path REPO --suite NAME --out FILE      (a010)
    convert.py --source s1b --path REPO --work DIR --out FILE [--suite A,B]  (a010; banking77: a040)

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
    move together in the bootstrap; the easy split has no group, so the id); state -> state; question -> question
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
                          "state_id": r.get("group") or r["id"], "state": r["state"], "question": q, "label": lab})
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


# a010: system-one-bench (github.com/alilibx/system-one-bench, Apache-2.0).
# Its build_suites.py samples each source with random.Random(0).shuffle over the
# split's row indices and keeps the first N; the option texts below are copied
# from it verbatim (data, not code). REPO/data.lock.json holds a hash per suite
# over its canonical case JSON; a suite whose rebuilt cases miss that hash is
# refused, so a converted suite holds exactly the items its published results
# were measured on. Rows come from the datasets-server API, which serves the
# dataset's current revision: the hash is what proves it is still the pinned one.
AG = {"world": "world news, politics, international affairs",
      "sports": "sports, athletes, games, competitions",
      "business": "business, economy, companies, markets, finance",
      "sci_tech": "science and technology, computing, internet, research"}
EM = {"sadness": "the writer feels sad, down, hurt, or lonely",
      "joy": "the writer feels happy, pleased, content, or excited",
      "love": "the writer feels love, affection, tenderness, or longing for someone",
      "anger": "the writer feels angry, irritated, resentful, or hostile",
      "fear": "the writer feels afraid, anxious, nervous, or threatened",
      "surprise": "the writer feels surprised, amazed, or astonished"}
S5 = ["very negative review", "negative review", "neutral or mixed review", "positive review", "very positive review"]
NLI = {"entailment": "the hypothesis is definitely true given the premise",
       "neutral": "the hypothesis might be true or false; the premise does not settle it",
       "contradiction": "the hypothesis is definitely false given the premise"}


def _ag(r):
    return {"article": r["text"]}, "topic", {"type": "choice", "instructions": "What is the topic of `article`?",
                                            "criteria": AG}, list(AG)[r["label"]]


def _em(r):
    return {"text": r["text"]}, "emotion", {"type": "choice", "instructions":
                                            "Which emotion does the writer of `text` express most strongly?",
                                            "criteria": EM}, list(EM)[r["label"]]


def _s5(r):
    return {"review": r["text"]}, "sentiment", {"type": "score", "instructions":
                                                "How positive is the sentiment of `review`?", "criteria": S5}, int(r["label"])


def _s2(r):
    return {"review": r["sentence"]}, "positive", {"type": "noul", "instructions":
                                                   "Does `review` express a positive opinion of the movie?"}, int(r["label"])


def _bq(r):
    return ({"passage": r["passage"], "question": r["question"] + "?"}, "answer_yes",
            {"type": "noul", "instructions": "According to `passage`, is the answer to `question` yes?"}, int(r["answer"]))


def _nli(r):
    return ({"premise": r["premise"], "hypothesis": r["hypothesis"]}, "relation",
            {"type": "choice", "instructions": "How does `hypothesis` relate to `premise`?", "criteria": NLI},
            list(NLI)[r["label"]])


BK = {}  # banking77: every label_text of the split, sorted, as build_suites.py builds it (filled by convert_s1b)


def _bk(r):
    return ({"customer_message": r["text"]}, "intent",
            {"type": "choice", "instructions": "Which banking intent best matches `customer_message`?", "criteria": BK},
            r["label_text"])


# suite: (dataset, config, split, n, build). The Arabic suites are not taken.
S1B_SUITES = {"ag_news": ("fancyzhx/ag_news", "default", "test", 200, _ag),
              "emotion": ("dair-ai/emotion", "split", "test", 200, _em),
              "sst5": ("SetFit/sst5", "default", "test", 200, _s5),
              "sst2": ("stanfordnlp/sst2", "default", "validation", 200, _s2),
              "boolq": ("google/boolq", "default", "validation", 200, _bq),
              "xnli_en": ("facebook/xnli", "en", "test", 150, _nli),
              "xnli_fr": ("facebook/xnli", "fr", "test", 150, _nli),
              "banking77": ("mteb/banking77", "default", "test", 200, _bk)}  # a040: 77 options, the id trie


def s1b_sample(total, n):
    import random
    idx = list(range(total))
    random.Random(0).shuffle(idx)
    return idx[:n]


def s1b_case(suite, i, row):
    state, qid, q, label = S1B_SUITES[suite][4](row)
    return {"suite": suite, "id": f"{suite}-{i}", "state": state, "questions": {qid: q},
            "gold": {qid: {"type": q["type"], "label": label}}}


def s1b_hash(cases):
    import hashlib
    h = hashlib.sha256()
    for c in cases:
        h.update(json.dumps(c, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode() + b"\n")
    return h.hexdigest()


def s1b_item(case):
    (qid, q), = case["questions"].items()
    lab = case["gold"][qid]["label"]
    return {"id": case["id"], "lang": "fr" if case["suite"] == "xnli_fr" else "en", "workflow": case["suite"],
            "state": case["state"], "question": q, "label": bool(lab) if q["type"] == "noul" else lab}


def s1b_rows(suite, cache, every=False):
    """The suite's sampled rows, in sample order. Pages of 100 rows hold them; the
    pages read so far are cached in `cache` after each request (the API rate-limits)."""
    d, c, sp, n, _ = S1B_SUITES[suite]
    got = json.load(open(cache)) if os.path.exists(cache) else {"pages": {}}

    def get(o):
        url = API.format(d=d, c=c, s=sp, o=o)
        for attempt in range(8):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    return json.loads(r.read().decode())
            except OSError:
                time.sleep(15 * (attempt + 1))  # 429s clear in about a minute
        raise RuntimeError(f"datasets-server failed: {url}")
    if "total" not in got:
        got["total"] = get(0)["num_rows_total"]
    want = s1b_sample(got["total"], n)
    pages = range((got["total"] + 99) // 100) if every else sorted({o // 100 for o in want})
    for page in pages:
        if str(page) not in got["pages"]:
            got["pages"][str(page)] = [x["row"] for x in get(page * 100)["rows"]]
            with open(cache, "w") as f:
                json.dump(got, f)
            time.sleep(1)
    if every:
        return [r for p in sorted(got["pages"], key=int) for r in got["pages"][p]], \
               [got["pages"][str(o // 100)][o % 100] for o in want]
    return [got["pages"][str(o // 100)][o % 100] for o in want]


def convert_s1b(path, work, suites=None):
    lock = json.load(open(os.path.join(path, "data.lock.json")))["cases.jsonl"]["suites"]
    items, bad = [], []
    for suite in suites or S1B_SUITES:
        cache = os.path.join(work, f"s1b-{suite}.rows.json")
        if suite == "banking77":
            every, rows = s1b_rows(suite, cache, every=True)
            BK.clear()
            BK.update({nm: nm.replace("_", " ") for nm in sorted({r["label_text"] for r in every})})
        else:
            rows = s1b_rows(suite, cache)
        cases = [s1b_case(suite, i, r) for i, r in enumerate(rows)]
        if s1b_hash(cases) != lock[suite]["sha256"] or len(cases) != lock[suite]["n"]:
            bad.append(suite)
            continue
        items += [s1b_item(c) for c in cases]
    return items, bad


def write_items(items, out):
    with open(out, "w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work")
    ap.add_argument("--split", default="test")
    ap.add_argument("--config", default="all")
    ap.add_argument("--source", choices=("typed-decisions", "jevbench", "jevify", "s1b"), default="typed-decisions")
    ap.add_argument("--path")
    ap.add_argument("--suite")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.source == "s1b":
        if not (a.path and a.work and a.out):
            ap.error("--source s1b needs --path, --work and --out")
        os.makedirs(a.work, exist_ok=True)
        items, bad = convert_s1b(a.path, a.work, a.suite.split(",") if a.suite else None)
        write_items(items, a.out)
        print(f"convert: s1b {len(items)} items -> {a.out}" + (f"; REFUSED (hash differs from data.lock.json): {bad}" if bad else ""))
        return 1 if bad else 0
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
