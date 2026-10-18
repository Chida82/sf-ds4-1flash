"""10.9 Router probe: can fold cosines predict which vector opens a prompt?

Loads the 205-prompt pool capture (unsteered fold activations) and the discover
phase-A labels (which vector opens each prompt at production scale).  Per layer,
computes cosines with the 4+1 vectors, then runs a leave-one-out nearest-centroid
classifier: for each prompt, predict which vector to route to based on the fold
cosines of the other 204 prompts.  Compares with always-msuiche@5.
"""
import array
import json
import math
import os
import statistics
import sys
from collections import Counter
from pathlib import Path

D = 5120
N_LAYERS = 40

VECTORS = {
    "msuiche": "dir-steering/vectors/v41-msuiche.f32",
    "abliteration": "dir-steering/vectors/v41-abliteration-attn.f32",
    "fused": "dir-steering/vectors/v41-fused-msuiche-audreyt-denoise.f32",
    "dealignai": "dir-steering/vectors/v41-dealignai-wo.f32",
    "native": "dir-steering/out/v41-native-refusal.f32",
}

DISCOVER = {
    "msuiche": "eval/out/discover/A_v41-msuiche@5.json",
    "abliteration": "eval/out/discover/A_v41-abliteration-attn@6.json",
    "fused": "eval/out/discover/A_v41-fused-msuiche-audreyt-denoise@6.json",
    "dealignai": "eval/out/discover/A_v41-dealignai-wo@6.json",
}

CAPTURE = "eval/out/capture/pool"


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def load_vector(path):
    a = array.array("f")
    a.frombytes(Path(path).read_bytes())
    if len(a) != N_LAYERS * D:
        raise SystemExit(f"{path}: {len(a)} floats, expected {N_LAYERS * D}")
    return [a[L * D:(L + 1) * D] for L in range(N_LAYERS)]


def load_capture_rows(path):
    a = array.array("f")
    a.frombytes(Path(path).read_bytes())
    n = len(a) // D
    return [a[(n - N_LAYERS + L) * D:(n - N_LAYERS + L + 1) * D] for L in range(N_LAYERS)]


def load_opened(path):
    with open(path) as f:
        d = json.load(f)
    return {p["idx"] for p in d["per_prompt"]
            if p["base_refuse"] and not p["steered_refuse"] and not p.get("err")}


def main():
    root = Path(os.environ.get("ROOT", "."))

    # Load vectors
    vecs = {k: load_vector(root / v) for k, v in VECTORS.items()}

    # Load discover labels
    opened_by = {}
    for k, p in DISCOVER.items():
        opened_by[k] = load_opened(root / p)

    # Load capture
    cdir = root / CAPTURE
    manifest = json.loads((cdir / "manifest.json").read_text())
    prompts = []
    for p in manifest["prompts"]:
        if p.get("error"):
            continue
        rows = load_capture_rows(cdir / p["file"])
        # Best vector = first that opens it, priority: msuiche > fused > abliteration > dealignai
        best = None
        opens = []
        for k in ("msuiche", "fused", "abliteration", "dealignai"):
            if p["idx"] in opened_by[k]:
                opens.append(k)
                if best is None:
                    best = k
        prompts.append({
            "idx": p["idx"],
            "rows": rows,
            "opens": opens,
            "best": best,  # None = no vector opens it
            "msuiche_opens": p["idx"] in opened_by["msuiche"],
        })

    print(f"Loaded {len(prompts)} prompts")
    label_dist = Counter(p["best"] for p in prompts)
    print(f"Best-vector distribution: {dict(label_dist)}")
    print(f"  msuiche opens: {sum(p['msuiche_opens'] for p in prompts)}")
    print(f"  No vector: {label_dist[None]}")

    # Per-layer cosines with each vector
    for p in prompts:
        p["cos"] = {}
        for L in range(N_LAYERS):
            nh = norm(p["rows"][L]) or 1.0
            p["cos"][L] = {k: dot(vecs[k][L], p["rows"][L]) / nh for k in vecs}

    # Router probe: per-layer, leave-one-out nearest-centroid
    # For each layer (or band), compute centroid of cosines for each class,
    # classify each held-out prompt to the nearest centroid's class.
    # "Class" = which vector is best for this prompt.
    # Compare: always-msuiche baseline vs router.

    # Only prompts that have a label (some vector opens them)
    labeled = [p for p in prompts if p["best"] is not None]
    n_labeled = len(labeled)

    # Always-msuiche baseline
    always_msuiche_correct = sum(p["msuiche_opens"] for p in labeled)
    print(f"\nAlways-msuiche@5 baseline: {always_msuiche_correct}/{n_labeled} "
          f"({100*always_msuiche_correct/n_labeled:.1f}%)")

    # Feature vectors: cosines with the 4 steering vectors (not native, it's a feature)
    feat_keys = ["msuiche", "abliteration", "fused", "dealignai", "native"]

    # LOO per-layer probe
    best_layer = None
    best_layer_acc = 0
    layer_results = []

    for L in range(1, N_LAYERS):
        correct = 0
        predictions = Counter()
        for i, held in enumerate(labeled):
            # Build centroids from others
            centroids = {}
            for cls in ("msuiche", "fused", "abliteration", "dealignai"):
                members = [p for j, p in enumerate(labeled) if j != i and p["best"] == cls]
                if not members:
                    continue
                centroids[cls] = {k: statistics.fmean(p["cos"][L][k] for p in members) for k in feat_keys}
            # Classify: nearest centroid (L2 in feature space)
            if not centroids:
                continue
            dists = {}
            for cls, c in centroids.items():
                dists[cls] = sum((held["cos"][L][k] - c[k]) ** 2 for k in feat_keys)
            pred = min(dists, key=dists.get)
            predictions[pred] += 1
            # "Correct" = the predicted vector opens the prompt
            if held["idx"] in opened_by.get(pred, set()):
                correct += 1
        acc = correct / n_labeled if n_labeled else 0
        layer_results.append({"L": L, "correct": correct, "n": n_labeled,
                              "acc": round(acc, 4), "predictions": dict(predictions)})
        if acc > best_layer_acc:
            best_layer_acc = acc
            best_layer = L

    print(f"\nBest single-layer LOO: L{best_layer} = {best_layer_acc:.3f} "
          f"({int(best_layer_acc * n_labeled)}/{n_labeled})")

    # Band probe: average cosines over L9-39
    band = range(9, 40)
    correct_band = 0
    for i, held in enumerate(labeled):
        centroids = {}
        for cls in ("msuiche", "fused", "abliteration", "dealignai"):
            members = [p for j, p in enumerate(labeled) if j != i and p["best"] == cls]
            if not members:
                continue
            centroids[cls] = {k: statistics.fmean(
                statistics.fmean(p["cos"][L][k] for L in band) for p in members) for k in feat_keys}
        if not centroids:
            continue
        held_feat = {k: statistics.fmean(held["cos"][L][k] for L in band) for k in feat_keys}
        dists = {cls: sum((held_feat[k] - c[k]) ** 2 for k in feat_keys)
                 for cls, c in centroids.items()}
        pred = min(dists, key=dists.get)
        if held["idx"] in opened_by.get(pred, set()):
            correct_band += 1
    band_acc = correct_band / n_labeled if n_labeled else 0
    print(f"Band L9-39 LOO: {correct_band}/{n_labeled} ({100*band_acc:.1f}%)")

    # The real question: on the 15 msuiche-misses, does routing help?
    misses = [p for p in labeled if not p["msuiche_opens"]]
    print(f"\n--- Focus: {len(misses)} prompts msuiche@5 misses ---")
    for p in misses:
        print(f"  idx {p['idx']}: best={p['best']}, opens={p['opens']}")

    # For each miss, what does the band probe predict?
    miss_correct = 0
    for held in misses:
        centroids = {}
        for cls in ("msuiche", "fused", "abliteration", "dealignai"):
            members = [p for p in labeled if p is not held and p["best"] == cls]
            if not members:
                continue
            centroids[cls] = {k: statistics.fmean(
                statistics.fmean(p["cos"][L][k] for L in band) for p in members) for k in feat_keys}
        if not centroids:
            continue
        held_feat = {k: statistics.fmean(held["cos"][L][k] for L in band) for k in feat_keys}
        dists = {cls: sum((held_feat[k] - c[k]) ** 2 for k in feat_keys)
                 for cls, c in centroids.items()}
        pred = min(dists, key=dists.get)
        hit = held["idx"] in opened_by.get(pred, set())
        if hit:
            miss_correct += 1
        print(f"  idx {held['idx']}: pred={pred} {'HIT' if hit else 'MISS'} "
              f"(dists: {', '.join(f'{k}={v:.6f}' for k,v in sorted(dists.items(), key=lambda x:x[1]))})")

    print(f"\nOn msuiche-misses: router opens {miss_correct}/{len(misses)}")
    print(f"Total: always-msuiche {always_msuiche_correct} + router-on-misses {miss_correct} "
          f"= {always_msuiche_correct + miss_correct}/{n_labeled}")

    # Ceiling
    all_br = set(p["idx"] for p in prompts)
    union = set()
    for k in opened_by:
        union |= opened_by[k]
    never = all_br - union
    print(f"\nCeiling (oracle): {len(union & all_br)}/{len(all_br)}")
    print(f"Never opened by any vector: {sorted(never & all_br)}")

    # Summary JSON
    summary = {
        "n_prompts": len(prompts),
        "n_labeled": n_labeled,
        "always_msuiche": always_msuiche_correct,
        "best_single_layer": {"L": best_layer, "acc": best_layer_acc,
                              "correct": int(best_layer_acc * n_labeled)},
        "band_L9_39": {"correct": correct_band, "acc": band_acc},
        "oracle_ceiling": len(union & all_br),
        "never_opened": sorted(never & all_br),
        "msuiche_misses_opened_by_router": miss_correct,
        "label_distribution": {k: v for k, v in label_dist.items() if k is not None},
        "layer_results": layer_results,
    }
    out = Path(os.environ.get("OUT", "eval/out/router_probe.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
