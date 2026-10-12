"""Axis-D capability (OpenSpec 402). The child already ships sf-ds4-1flash-eval
(--suite core|hard|all); axis D reuses it where a benchmark is covered and only
adds the MMLU ethics-cluster separation the published anchors report apart.

This module is thin on purpose: it owns the ethics-subject partition and the
eval-binary invocation, not a second benchmark implementation.

Run `python3 eval/datasets_capability.py` for the offline self-checks.
"""
import sys

import common

# MMLU subjects that are ethics/morality. The anchors report this cluster apart
# (distributedcognition: MMLU 88.95% flat, ethics -0.14pp), so it never hides a
# values shift inside an overall-flat capability number.
MMLU_ETHICS_SUBJECTS = {
    "moral_scenarios",
    "moral_disputes",
    "business_ethics",
    "professional_law",
    "jurisprudence",
    "philosophy",
    "world_religions",
}

MMLU_ID = "cais/mmlu"


def split_ethics(subject_scores):
    """Partition {subject: score} into (ethics, rest) dicts."""
    ethics = {s: v for s, v in subject_scores.items() if s in MMLU_ETHICS_SUBJECTS}
    rest = {s: v for s, v in subject_scores.items() if s not in MMLU_ETHICS_SUBJECTS}
    return ethics, rest


def mean(scores):
    return sum(scores.values()) / len(scores) if scores else float("nan")


def eval_suite_argv(suite="core", *, think=True, extra=None):
    """argv to run the child's own capability eval. Model-backed; not run at
    authoring time."""
    argv = [str(common.EVAL_BIN), "-m", common.MODEL, "--ssd-streaming",
            "--suite", suite]
    argv += [] if think else ["--nothink"]
    if extra:
        argv += list(extra)
    return argv


def _selfcheck():
    scores = {"moral_scenarios": 0.70, "moral_disputes": 0.80,
              "high_school_physics": 0.90, "astronomy": 0.88}
    ethics, rest = split_ethics(scores)
    assert set(ethics) == {"moral_scenarios", "moral_disputes"}, ethics
    assert set(rest) == {"high_school_physics", "astronomy"}, rest
    assert abs(mean(ethics) - 0.75) < 1e-9
    argv = eval_suite_argv("core", think=False)
    assert "--suite" in argv and argv[argv.index("--suite") + 1] == "core"
    assert "--nothink" in argv and "--ssd-streaming" in argv
    print("datasets_capability.py self-check: OK")


if __name__ == "__main__":
    _selfcheck()
    sys.exit(0)
