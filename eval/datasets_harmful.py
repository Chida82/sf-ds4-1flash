"""Axis-A harmful-prompt loaders (OpenSpec 402, VALIDATION_FRAMEWORK sec.1).

Each loader fetches to /tmp and returns a list[str] of prompts, or raises an
error naming the missing source. The AdvBench `harmful_behaviors[:100]` slice is
distributedcognition's exact calibration set and is preserved verbatim.

Run `python3 eval/datasets_harmful.py` for the offline self-checks.
"""
import csv
import io
import sys

import common

# Raw sources with stable URLs (no `datasets` dependency). Mirrors are tried in
# order; the first that fetches wins, and a total failure names every id tried.
ADVBENCH_CSV = [
    "https://raw.githubusercontent.com/llm-attacks/llm-attacks/main/data/advbench/harmful_behaviors.csv",
]
HARMBENCH_CSV = [
    "https://raw.githubusercontent.com/centerforaisafety/HarmBench/main/data/behavior_datasets/harmbench_behaviors_text_all.csv",
]
STRONGREJECT_CSV = [
    "https://raw.githubusercontent.com/alexandrasouly/strongreject/main/strongreject_dataset/strongreject_dataset.csv",
]


def _csv_column(text, candidates):
    """Return the first matching column across candidate names, in row order."""
    reader = csv.DictReader(io.StringIO(text))
    field = next((c for c in candidates if c in (reader.fieldnames or [])), None)
    if field is None:
        raise RuntimeError(f"none of {candidates} in columns {reader.fieldnames}")
    return [row[field].strip() for row in reader if row.get(field, "").strip()]


def _fetch_first(urls, name, columns):
    errs = []
    for url in urls:
        try:
            path = common.cache_fetch(url, name)
            return _csv_column(path.read_text(), columns)
        except Exception as e:
            errs.append(str(e))
    raise RuntimeError(f"{name}: all sources failed: {errs}")


def load_advbench():
    return _fetch_first(ADVBENCH_CSV, "advbench_harmful_behaviors.csv", ["goal"])


def harmful_behaviors_100(behaviors=None):
    """distributedcognition's exact calibration slice: AdvBench goal[:100]."""
    behaviors = load_advbench() if behaviors is None else behaviors
    return behaviors[:100]


def load_harmbench():
    return _fetch_first(HARMBENCH_CSV, "harmbench_behaviors.csv",
                        ["Behavior", "behavior"])


def load_strongreject():
    return _fetch_first(STRONGREJECT_CSV, "strongreject_dataset.csv",
                        ["forbidden_prompt", "prompt"])


SOURCES = {
    "advbench": load_advbench,
    "harmbench": load_harmbench,
    "strongreject": load_strongreject,
}


def _selfcheck():
    fixture = ("goal,target\n"
               + "\n".join(f"do bad thing {i},sure {i}" for i in range(150)) + "\n")
    rows = _csv_column(fixture, ["goal"])
    assert len(rows) == 150, len(rows)
    assert rows[0] == "do bad thing 0" and rows[-1] == "do bad thing 149"
    sl = harmful_behaviors_100(rows)
    assert len(sl) == 100 and sl == rows[:100], "the :100 slice must be verbatim"
    # column fallback picks the first present candidate
    hb = _csv_column("Behavior,extra\nmake x,1\n", ["Behavior", "behavior"])
    assert hb == ["make x"], hb
    # missing column names what it looked for
    try:
        _csv_column("other\nz\n", ["goal"])
        assert False
    except RuntimeError as e:
        assert "goal" in str(e)
    print("datasets_harmful.py self-check: OK")


if __name__ == "__main__":
    _selfcheck()
    sys.exit(0)
