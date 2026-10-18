"""Phase-B (full-length keyword-refuse) screen of extra vectors on discover.py's hard set.

Reuses discover.run_config and the exact hard-set indices of an existing B_*.json, so a
new candidate (e.g. a hybrid α vector) is compared apples-to-apples with msuiche@5's
3/32. Resume-safe: a config whose B_ file exists is skipped. Keyword-refuse is a screen,
not COMPLY (the user-run judge settles that).

A config is `PATH@SCALE` or, rank-2, `PATH@SCALE+PATH2@SCALE2` (the second file goes to
`--dir-steering-file-2/--dir-steering-residual-2`). `--extra "..."` appends verbatim
server flags (gate, write site); `--indices` replaces the hard set (the
eight-prompt screens of 409). The B_ tag carries the second file and a short hash of
`--extra`, so it never collides with a rank-1 config.

  python3 eval/hybrid_phaseb.py --configs dir-steering/out/v41-hybrid-a01.f32@5,dir-steering/out/v41-hybrid-a03.f32@5
  python3 eval/hybrid_phaseb.py --dry-run --configs A.f32@7+B.f32@2 --indices 1,6,13,16,23,27,372,426
"""
import argparse
import json
import shlex
import sys
from pathlib import Path

import discover
import scale_sweep as ss
import score_keyword

REF = "v41-msuiche@5"


def load_b(tag):
    return json.loads((discover.OUT / f"B_{tag}.json").read_text())


def refusing(per):
    return sorted(p["idx"] for p in per if p["keyword_refuse"])


def parse_config(spec, extra):
    """'P@S[+P2@S2]' + extra flags -> (path, scale, server extra argv, tag, files)."""
    first, _, second = spec.partition("+")
    path, _, scale = first.rpartition("@")
    path, scale = Path(path), float(scale)
    tag, argv, files = f"{path.stem}@{scale:g}", [], [path]
    if second:
        p2, _, s2 = second.rpartition("@")
        p2, s2 = Path(p2), float(s2)
        tag += f"+{p2.stem}@{s2:g}"
        files.append(p2)
        argv += ["--dir-steering-file-2", str(p2), "--dir-steering-residual-2", f"{s2:g}"]
    return path, scale, argv + list(extra), tag + discover.extra_tag(extra), files


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--configs", required=True, help="comma list of PATH@SCALE[+PATH2@SCALE2]")
    ap.add_argument("--ref", default=REF, help="B_ tag whose hard set and refusals are the reference")
    ap.add_argument("--indices", default=None, help="comma list of union indices replacing the hard set")
    ap.add_argument("--extra", default="", help="verbatim server flags appended to every config")
    ap.add_argument("--tokens", type=int, default=2048)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    ref = load_b(args.ref)
    hard = ([int(x) for x in args.indices.split(",")] if args.indices
            else [p["idx"] for p in ref])
    ref_refuse = set(refusing(ref)) & set(hard)
    extra = shlex.split(args.extra)
    configs = [parse_config(c, extra) for c in args.configs.split(",")]
    print(f"{len(hard)} prompts {hard if args.indices else 'from B_' + args.ref}; "
          f"ref {args.ref} refuses {sorted(ref_refuse)}")
    for path, scale, cfg_extra, tag, files in configs:
        missing = [str(p) for p in files if not p.exists()]
        print(f"  {tag}" + (f"  (MISSING {missing})" if missing else ""))
        if args.dry_run:
            print("    " + " ".join(ss._server_args(path, scale, discover.PORT, 32768, cfg_extra)))
    if args.dry_run:
        return 0

    records = discover.build_union()
    discover._self_caffeinate()
    for path, scale, cfg_extra, tag, _ in configs:
        out = discover.OUT / f"B_{tag}{'' if not args.indices else '_idx' + str(len(hard))}.json"
        if out.exists():
            per = json.loads(out.read_text())
            print(f"[B] {tag}: exists, keyword-refuse {len(refusing(per))}/{len(hard)}")
        else:
            comp = discover.run_config(hard, records, str(path), scale, args.tokens, extra=cfg_extra)
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
