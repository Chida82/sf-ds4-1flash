"""Axis-D capability scorer (OpenSpec 402).

Reuses sf-ds4-1flash-eval and only adds the MMLU ethics-cluster separation. The
parser is tolerant of the eval binary's line format (confirm the exact shape
against one real run); it extracts {name: fraction in [0,1]} from `name: a/b` or
`name: NN%` / `NN.N%` lines.

Run `python3 eval/score_capability.py` for the offline self-checks.
"""
import re
import sys

from datasets_capability import split_ethics, mean  # noqa: reused partition

_FRAC = re.compile(r"^\s*([A-Za-z0-9_./ -]+?)\s*[:=]\s*(\d+)\s*/\s*(\d+)\b")
_PCT = re.compile(r"^\s*([A-Za-z0-9_./ -]+?)\s*[:=]\s*(\d+(?:\.\d+)?)\s*%")


def parse_scores(text):
    """Return {name: fraction}. a/b wins over % when both match a line."""
    scores = {}
    for ln in text.splitlines():
        m = _FRAC.match(ln)
        if m:
            name, a, b = m.group(1).strip(), int(m.group(2)), int(m.group(3))
            if b:
                scores[name] = a / b
            continue
        m = _PCT.match(ln)
        if m:
            scores[m.group(1).strip()] = float(m.group(2)) / 100.0
    return scores


def capability_report(subject_scores):
    """Axis D: overall vs the ethics cluster, reported apart."""
    ethics, rest = split_ethics(subject_scores)
    return {
        "overall": mean(subject_scores),
        "ethics_cluster": mean(ethics),
        "ethics_subjects": ethics,
        "non_ethics": mean(rest),
    }


def _selfcheck():
    text = ("gsm8k: 16/20\n"
            "arc_challenge: 85.0%\n"
            "moral_scenarios = 70%\n"
            "random noise line\n")
    s = parse_scores(text)
    assert abs(s["gsm8k"] - 0.8) < 1e-9, s
    assert abs(s["arc_challenge"] - 0.85) < 1e-9
    assert abs(s["moral_scenarios"] - 0.70) < 1e-9
    rep = capability_report({"moral_scenarios": 0.7, "astronomy": 0.9})
    assert rep["ethics_cluster"] == 0.7 and rep["non_ethics"] == 0.9
    print("score_capability.py self-check: OK")


if __name__ == "__main__":
    _selfcheck()
    sys.exit(0)
