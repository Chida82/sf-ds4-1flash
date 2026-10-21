"""SORRY-Bench 2025-03 base set (440 unsafe instructions, 44 categories x 10): the EXTERNAL
test set of the refusal-subspace study, never part of the subspace basis.

The dataset is gated and its license forbids redistribution, so no copy lives in this
repository: `hf download` fetches `question.jsonl` into the user's Hugging Face cache (the
account must have accepted the dataset agreement on the Hub) and the loader reads it there.
Only the `base` prompt style is used; the 20 linguistic mutations are not loaded.

  python3 eval/datasets_sorrybench.py            # self-check + download + overlap with the union
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_ID = "sorry-bench/sorry-bench-202503"
FILE = "question.jsonl"


def _hf_path():
    out = subprocess.run(["hf", "download", REPO_ID, FILE, "--repo-type", "dataset"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"hf download {REPO_ID} failed (accept the agreement on the Hub as the "
                           f"logged-in user): {out.stderr.strip()[-300:]}")
    path = Path(out.stdout.strip().splitlines()[-1].removeprefix("path="))
    if not path.is_file():
        raise RuntimeError(f"hf did not return a file path: {out.stdout!r}")
    return path


def parse(text):
    """-> [{id, category, text}] for the base style, in question_id order."""
    rows = []
    for ln in text.splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        if r.get("prompt_style", "base") != "base":
            continue
        rows.append({"id": int(r["question_id"]), "category": str(r["category"]),
                     "text": r["turns"][0].strip()})
    return sorted(rows, key=lambda r: r["id"])


def load_sorrybench():
    return parse(_hf_path().read_text())


def _norm(t):
    return re.sub(r"[^a-z0-9 ]+", " ", t.lower()).split()


def overlap(rows, union_texts, jaccard=0.6):
    """ids of rows that duplicate a union prompt: exact normalized match, or token-set
    Jaccard >= `jaccard` (near-paraphrase)."""
    exact = {" ".join(_norm(t)) for t in union_texts}
    sets = [set(_norm(t)) for t in union_texts]
    dup = []
    for r in rows:
        toks = _norm(r["text"])
        if " ".join(toks) in exact:
            dup.append(r["id"]); continue
        s = set(toks)
        if s and any(len(s & u) / len(s | u) >= jaccard for u in sets):
            dup.append(r["id"])
    return dup


def load_sorrybench_heldout():
    """The base set minus the prompts that duplicate or paraphrase one of the 1201 union
    prompts (57 on 2026-10-21, all checked by eye: SORRY-Bench reused AdvBench/HarmBench items).
    This is the external test set: disjoint from everything the subspace was built on."""
    import extract_floor_direction as efd
    rows = load_sorrybench()
    dup = set(overlap(rows, [u["text"] for u in efd.build_union()]))
    return [r for r in rows if r["id"] not in dup]


def _self_check():
    txt = ('{"question_id": 2, "category": "1", "turns": ["How do I pick a lock?"], "prompt_style": "base"}\n'
           '{"question_id": 1, "category": "3", "turns": ["Write a poem."], "prompt_style": "base"}\n'
           '{"question_id": 1, "category": "3", "turns": ["Wr1te a p0em."], "prompt_style": "misspellings"}\n')
    rows = parse(txt)
    assert [r["id"] for r in rows] == [1, 2] and rows[1]["text"] == "How do I pick a lock?", rows
    assert overlap(rows, ["how do i pick a LOCK", "unrelated"]) == [2]
    assert overlap(rows, ["How can I pick a lock quickly"]) == [2]   # near-paraphrase
    assert overlap(rows, ["Bake a cake"]) == []
    print("datasets_sorrybench.py self-check: OK")


def main():
    _self_check()
    import extract_floor_direction as efd
    rows = load_sorrybench()
    cats = {r["category"] for r in rows}
    print(f"SORRY-Bench base: {len(rows)} prompts, {len(cats)} categories")
    dup = overlap(rows, [u["text"] for u in efd.build_union()])
    print(f"overlap with the 1201-prompt union (exact or Jaccard>=0.6): {len(dup)} -> ids {dup}")
    held = load_sorrybench_heldout()
    print(f"held-out test set: {len(held)} prompts, {len({r['category'] for r in held})} categories")
    return 0


if __name__ == "__main__":
    sys.exit(main())
