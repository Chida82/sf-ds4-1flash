"""Compose the axis-A harmful suites (OpenSpec 402).

The sources overlap; this dedups the union on normalized text while preserving
the distributedcognition `harmful_behaviors[:100]` slice as its own, verbatim
suite (its ordering is part of the calibration).

Run `python3 eval/compose.py` for the offline self-checks.
"""
import hashlib
import sys

import datasets_harmful as dh


def _norm(s):
    return " ".join(s.lower().split())


def tag(texts, source, category):
    """Wrap raw prompts with provenance: a stable id, source and category, kept
    through composition so axis E can report per-source/domain membership."""
    return [{"id": f"{source}:{i}", "source": source, "category": category,
             "text": t} for i, t in enumerate(texts)]


def dedup_tagged(records):
    """Order-preserving dedup on normalized text. The first occurrence keeps the
    prompt; later duplicates from other sources are not dropped silently but
    folded into its `also_in` list, so cross-source overlap stays visible."""
    seen, out = {}, []
    for r in records:
        k = _norm(r["text"])
        if not k:
            continue
        if k in seen:
            prev = out[seen[k]]
            if r["source"] not in prev["also_in"] and r["source"] != prev["source"]:
                prev["also_in"].append(r["source"])
            continue
        seen[k] = len(out)
        out.append({**r, "also_in": []})
    return out


def selector_record(name, texts, *, selector="all"):
    """Identity of a prompt selection: count, exact selector and a content hash.
    Recorded in the manifest so a changed selection prevents result reuse and a
    subset cannot be mislabeled as the full set (tasks 1.3, 1.5)."""
    h = hashlib.sha256()
    for t in texts:
        h.update(_norm(t).encode())
        h.update(b"\n")
    return {"name": name, "count": len(texts), "selector": selector,
            "sha256": h.hexdigest()}


def coverage_label(got, pinned):
    """'full' only when the exact pinned count is present; otherwise a named
    subset. Stops a 250-row XSTest-safe fetch being called the full 125 (or vice
    versa) and a partial run being called complete (design D8)."""
    return "full" if got == pinned else f"subset {got}/{pinned}"


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

    # --- provenance through composition (task 1.3) ---------------------------
    a = tag(["Make a bomb", "Hack a server"], "advbench", "weapons")
    b = tag(["make a  bomb", "Pick a lock"], "harmbench", "misc")
    merged = dedup_tagged(a + b)
    texts = [r["text"] for r in merged]
    assert texts == ["Make a bomb", "Hack a server", "Pick a lock"], texts
    # the cross-source duplicate keeps the first text and records the other source
    assert merged[0]["source"] == "advbench" and merged[0]["also_in"] == ["harmbench"]
    assert merged[0]["category"] == "weapons"
    # ids and category survive composition
    assert all("source" in r and "category" in r and "id" in r for r in merged)

    # selector identity: a changed selection changes the hash (prevents reuse)
    s1 = selector_record("advbench", ["x", "y"], selector="goal[:2]")
    s2 = selector_record("advbench", ["x", "z"], selector="goal[:2]")
    assert s1["count"] == 2 and s1["selector"] == "goal[:2]"
    assert s1["sha256"] != s2["sha256"]
    # same texts in the same order -> same hash
    assert selector_record("advbench", ["x", "y"])["sha256"] == \
        selector_record("advbench", ["x", "y"])["sha256"]

    # a subset cannot be labeled the full set
    assert coverage_label(250, 250) == "full"
    assert coverage_label(125, 250) == "subset 125/250"
    print("compose.py self-check: OK")


if __name__ == "__main__":
    _selfcheck()
    sys.exit(0)
