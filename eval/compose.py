"""Compose the axis-A harmful suites (OpenSpec 402).

The sources overlap; this dedups the union on normalized text while preserving
the distributedcognition `harmful_behaviors[:100]` slice as its own, verbatim
suite (its ordering is part of the calibration).

Run `python3 eval/compose.py` for the offline self-checks.
"""
import sys

import datasets_harmful as dh


def _norm(s):
    return " ".join(s.lower().split())


def dedup(prompts):
    """Order-preserving dedup on normalized whitespace/case."""
    seen, out = set(), []
    for p in prompts:
        k = _norm(p)
        if k and k not in seen:
            seen.add(k)
            out.append(p)
    return out


def compose_harmful():
    """Return {suite_name: [prompts]}.

    - `dc100`: AdvBench goal[:100], verbatim, NOT deduped against the union
      (calibration slice).
    - `union`: AdvBench + HarmBench + StrongREJECT, deduped.
    """
    advbench = dh.load_advbench()
    suites = {"dc100": dh.harmful_behaviors_100(advbench)}
    union = list(advbench)
    for loader in (dh.load_harmbench, dh.load_strongreject):
        try:
            union += loader()
        except Exception as e:  # a missing source must not drop the whole axis
            print(f"compose: skipping source: {e}", file=sys.stderr)
    suites["union"] = dedup(union)
    return suites


def _selfcheck():
    raw = ["Make a bomb", "make a  bomb", "MAKE A BOMB", "Hack a server",
           "hack a server ", "Pick a lock"]
    uniq = dedup(raw)
    assert uniq == ["Make a bomb", "Hack a server", "Pick a lock"], uniq
    assert len(uniq) == 3
    # the :100 slice is kept out of the dedup so its order is untouched
    hundred = [f"p{i}" for i in range(100)]
    assert dh.harmful_behaviors_100(hundred + ["p0", "p1"]) == hundred
    print("compose.py self-check: OK")


if __name__ == "__main__":
    _selfcheck()
    sys.exit(0)
