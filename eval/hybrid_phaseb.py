"""Phase-B (full-length keyword-refuse) screen of extra vectors on discover.py's hard set.

Reuses discover.run_config and the exact hard-set indices of an existing B_*.json, so a
new candidate (e.g. a hybrid α vector) is compared apples-to-apples with msuiche@5's
3/32. Resume-safe: a config whose B_ file exists is skipped. Keyword-refuse is a screen,
not COMPLY (the user-run judge settles that).

  python3 eval/hybrid_phaseb.py --configs dir-steering/out/v41-hybrid-a01.f32@5,dir-steering/out/v41-hybrid-a03.f32@5
  python3 eval/hybrid_phaseb.py --dry-run --configs ...
"""
import argparse
import json
import sys
from pathlib import Path

import discover
import score_keyword

REF = "v41-msuiche@5"


def load_b(tag):
    return json.loads((discover.OUT / f"B_{tag}.json").read_text())


def refusing(per):
    return sorted(p["idx"] for p in per if p["keyword_refuse"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--configs", required=True, help="comma list of PATH@SCALE")
    ap.add_argument("--ref", default=REF, help="B_ tag whose hard set and refusals are the reference")
    ap.add_argument("--tokens", type=int, default=2048)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    ref = load_b(args.ref)
    hard = [p["idx"] for p in ref]
    ref_refuse = set(refusing(ref))
    configs = []
    for c in args.configs.split(","):
        path, _, scale = c.rpartition("@")
        configs.append((Path(path), float(scale)))
    print(f"hard set {len(hard)} prompts from B_{args.ref}; ref refuses {sorted(ref_refuse)}")
    for path, scale in configs:
        print(f"  {path.stem}@{scale:g}" + ("" if path.exists() else "  (MISSING)"))
    if args.dry_run:
        return 0

    records = discover.build_union()
    discover._self_caffeinate()
    for path, scale in configs:
        tag = f"{path.stem}@{scale:g}"
        out = discover.OUT / f"B_{tag}.json"
        if out.exists():
            per = json.loads(out.read_text())
            print(f"[B] {tag}: exists, keyword-refuse {len(refusing(per))}/{len(hard)}")
        else:
            comp = discover.run_config(hard, records, str(path), scale, args.tokens)
            per = [{"idx": i, "source": records[i]["source"], "prompt": records[i]["text"],
                    "completion": comp[i], "keyword_refuse": score_keyword.is_refusal(comp[i])}
                   for i in hard]
            out.write_text(json.dumps(per, indent=2))
        r = set(refusing(per))
        empty = [p["idx"] for p in per if not p["completion"].strip()]
        print(f"[B] {tag}: keyword-refuse {len(r)}/{len(hard)}  "
              f"opened-vs-ref {sorted(ref_refuse - r)}  lost-vs-ref {sorted(r - ref_refuse)}  "
              f"empty {empty}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
