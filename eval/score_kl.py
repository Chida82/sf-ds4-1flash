"""Axis-B KL scorer (OpenSpec 402, design D2).

KL of the steered next-token distribution from base, on the same forced tokens,
read from `--dump-logprobs --logprobs-top-k` (top-k support, an approximation
noted as such). Reported next to an identity-requant noise floor: a KL below the
floor is model equivalence, not a real shift. The embedding-cosine proxy is the
flagged fallback when logprobs are unavailable.

Run `python3 eval/score_kl.py` for the offline self-checks.
"""
import math
import sys

EPS = 1e-9


def _to_probs(logprob_dict):
    p = {t: math.exp(lp) for t, lp in logprob_dict.items()}
    z = sum(p.values()) or 1.0
    return {t: v / z for t, v in p.items()}


def kl_position(base_lp, steered_lp):
    """KL(base || steered) over the union of top-k support, steered floored by
    EPS where it has no mass (top-k truncation)."""
    p = _to_probs(base_lp)
    q = _to_probs(steered_lp)
    out = 0.0
    for t, pt in p.items():
        if pt <= 0:
            continue
        qt = q.get(t, EPS)
        out += pt * math.log(pt / max(qt, EPS))
    return out


def kl_sequence(base_seq, steered_seq):
    """Mean per-position KL over a forced-token sequence."""
    n = min(len(base_seq), len(steered_seq))
    if n == 0:
        return 0.0
    return sum(kl_position(base_seq[i], steered_seq[i]) for i in range(n)) / n


def report_kl(base_seq, steered_seq, noise_floor):
    kl = kl_sequence(base_seq, steered_seq)
    return {"kl": kl, "noise_floor": noise_floor,
            "above_floor": kl > noise_floor,
            "note": "top-k support approximation of forced-token KL"}


def embedding_cosine_fallback(vec_a, vec_b):
    """Flagged, less-rigorous fallback when logprobs are unavailable."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    na = math.sqrt(sum(a * a for a in vec_a)) or 1.0
    nb = math.sqrt(sum(b * b for b in vec_b)) or 1.0
    return {"cosine": dot / (na * nb), "note": "FALLBACK proxy, not KL"}


def _selfcheck():
    d = {"a": math.log(0.5), "b": math.log(0.3), "c": math.log(0.2)}
    assert abs(kl_position(d, d)) < 1e-9, "KL(p||p) must be ~0"
    assert abs(kl_sequence([d, d], [d, d])) < 1e-9
    shifted = {"a": math.log(0.2), "b": math.log(0.3), "c": math.log(0.5)}
    assert kl_position(d, shifted) > 0
    rep = report_kl([d], [shifted], noise_floor=0.131)
    assert "kl" in rep and rep["noise_floor"] == 0.131
    assert abs(embedding_cosine_fallback([1, 0], [1, 0])["cosine"] - 1.0) < 1e-9
    print("score_kl.py self-check: OK")


if __name__ == "__main__":
    _selfcheck()
    sys.exit(0)
