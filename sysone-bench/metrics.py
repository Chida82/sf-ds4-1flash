"""Pure metric functions for the System One bench (change 820). Standard library only.

A scored item is a dict with:
  probs: {option: p}   (noul: {"true": p, "false": 1-p}; score: {"0": p0, ...})
  label: option key, or None
  state_id: str        (bootstrap resamples states, not items)
  ms: float            (latency of the decision), optional
  legal_mass: float    optional
"""
import hashlib
import math
import random


def top(probs):
    # ties go to the first key in option order, as sf_sysone_finish does
    best = None
    for k, p in probs.items():
        if best is None or p > probs[best]:
            best = k
    return best


def accuracy(items):
    lab = [it for it in items if it.get("label") is not None]
    return sum(top(it["probs"]) == it["label"] for it in lab) / len(lab) if lab else float("nan")


def nll(items):
    lab = [it for it in items if it.get("label") is not None]
    return sum(-math.log(max(it["probs"].get(it["label"], 0.0), 1e-9)) for it in lab) / len(lab) if lab else float("nan")


def brier(items):
    lab = [it for it in items if it.get("label") is not None]
    if not lab:
        return float("nan")
    return sum(sum((p - (k == it["label"])) ** 2 for k, p in it["probs"].items()) for it in lab) / len(lab)


def ece(items, bins=10):
    lab = [it for it in items if it.get("label") is not None]
    if not lab:
        return float("nan")
    acc = [0.0] * bins
    conf = [0.0] * bins
    n = [0] * bins
    for it in lab:
        k = top(it["probs"])
        c = it["probs"][k]
        b = min(int(c * bins), bins - 1)
        n[b] += 1
        conf[b] += c
        acc[b] += k == it["label"]
    return sum(abs(acc[b] - conf[b]) / len(lab) for b in range(bins) if n[b])


def percentile(xs, q):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    i = (len(xs) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def state_id(text):
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def bootstrap_accuracy(items, n=2000, seed=0, samples=False):
    """95% interval on accuracy, resampling states with all their decisions."""
    by_state = {}
    for it in items:
        if it.get("label") is not None:
            by_state.setdefault(it["state_id"], []).append(top(it["probs"]) == it["label"])
    groups = list(by_state.values())
    if not groups:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    accs = []
    for _ in range(n):
        hit = tot = 0
        for _ in range(len(groups)):
            g = groups[rng.randrange(len(groups))]
            hit += sum(g)
            tot += len(g)
        accs.append(hit / tot)
    if samples:
        return accs
    return (percentile(accs, 0.025), percentile(accs, 0.975))


def softmax(logits, t=1.0):
    m = max(x / t for x in logits)
    e = [math.exp(x / t - m) for x in logits]
    s = sum(e)
    return [x / s for x in e]


def auroc(pos_scores, neg_scores):
    """Probability a positive scores above a negative (ties count half)."""
    if not pos_scores or not neg_scores:
        return float("nan")
    wins = 0.0
    for p in pos_scores:
        for q in neg_scores:
            wins += 1.0 if p > q else 0.5 if p == q else 0.0
    return wins / (len(pos_scores) * len(neg_scores))


def summary(items):
    lab = [it for it in items if it.get("label") is not None]
    ms = [it["ms"] for it in items if it.get("ms") is not None]
    mass = [it["legal_mass"] for it in items if it.get("legal_mass") is not None]
    lo, hi = bootstrap_accuracy(items)
    return {
        "n": len(items), "labelled": len(lab), "states": len({it["state_id"] for it in items}),
        "accuracy": accuracy(items), "ci95": (lo, hi), "nll": nll(items), "brier": brier(items), "ece": ece(items),
        "mass_mean": sum(mass) / len(mass) if mass else float("nan"), "mass_min": min(mass) if mass else float("nan"),
        "p50_ms": percentile(ms, 0.5), "p95_ms": percentile(ms, 0.95), "mean_ms": sum(ms) / len(ms) if ms else float("nan"),
        "tokens": (sum(it.get("tokens", 0) for it in items) / len(items)) if items else float("nan"),
    }
